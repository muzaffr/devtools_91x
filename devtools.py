#!/usr/bin/python3

"""
Developer Tools for rs911x.
"""

from argparse import ArgumentParser, SUPPRESS
from datetime import datetime
from enum import Enum
from filecmp import cmp as fcmp
from os import chdir, remove as osremove
from pathlib import Path, PureWindowsPath
from re import findall, sub
from shutil import copy as shcopy
from subprocess import run, Popen, PIPE
from textwrap import wrap
from time import perf_counter, sleep
from threading import Thread, Event
from typing import Any, Dict, List, Tuple, Union
from selectors import DefaultSelector, EVENT_READ


get_output = lambda x: run(x.split(), capture_output=True).stdout.decode('utf8').rstrip()


class Test(Enum):

    STYLE_CHECK = 'Style Check'
    REMOTE_SYNC = 'Remote Sync'


class BuildType(Enum):

    RS9116_A10_ROM  = '9116 1.4 ROM'
    RS9116_A10      = '9116 1.4'
    RS9116_A11_ROM  = '9116 1.5 ROM'
    RS9116_A11      = '9116 1.5'
    RS9117_A0_ROM   = '9117 A0 ROM'
    RS9117_A0       = '9117 A0'
    RS9117_B0_ROM   = '9117 B0 ROM'
    RS9117_B0       = '9117 B0'
    RS9116_A11_ANT  = '9116 1.5 Garmin'
    RS9117_A1       = '9117 A1'


class Color(Enum):

    RED         = 'ff0000'
    GREEN       = '00ff00'
    BLUE        = '0000ff'
    WHITE       = 'ffffff'
    BLACK       = '000000'
    CYAN        = '00ffff'
    MAGENTA     = 'ff00ff'
    YELLOW      = 'ffff00'
    GRAY        = '6f6f6f'
    SILVER      = '9f9f9f'
    ORANGE      = 'ff7f00'
    CAPRI       = '00bfff'
    TEAL        = '7fffff'


class LegacyColor(Enum):

    RED          = (1, 31, 40,)
    GREEN        = (1, 32, 40,)
    YELLOW       = (1, 33, 40,)
    CYAN         = (1, 36, 40,)
    PURPLE       = (1, 35, 40,)
    SOLID_RED    = (1, 37, 41,)
    SOLID_GREEN  = (2, 30, 42,)
    SOLID_YELLOW = (2, 30, 43,)


def paint(text: str, fgcolor: Color, bgcolor: Color = None) -> str:
    '''
    Formats/highlights text to be printed on the console as per the ANSI coloring scheme.
    '''
    colored_text = '\033[38;2;'
    hex_to_seq = lambda y: ';'.join(map(lambda x: str(int(x, 16)), wrap(y.value, 2))) + 'm'
    colored_text += hex_to_seq(fgcolor)
    if bgcolor:
        colored_text += '\033[48;2;'
        colored_text += hex_to_seq(bgcolor)
    colored_text += text
    colored_text += '\033[0m'
    return colored_text
    # return '\033[{}m{}\033[0m'.format(';'.join(map(str, color.value)), text)


class PrettyTable:

    def __init__(self) -> None:

        self._BASE_HEADERS = (
            '#',
            'Name',
            'Result',
            'Comment',
        )
        self._results: Dict[Union[Test, BuildType], Tuple[str, str]] = {}
        self._width = list(map(lambda x: len(x) + 1, self._BASE_HEADERS))


    class Char(Enum):

        TOP_LEFT    = chr(9554)
        TOP_MID     = chr(9572)
        TOP_RIGHT   = chr(9557)
        MID_LEFT    = chr(9566)
        MID_MID     = chr(9578)
        MID_RIGHT   = chr(9569)
        BOT_LEFT    = chr(9560)
        BOT_MID     = chr(9575)
        BOT_RIGHT   = chr(9563)
        VER_SEP     = chr(9474)
        HOR_SEP     = chr(9552)


    def add_result(self, test: Union[BuildType, Test], result: str, comment: str) -> None:

        self._results[test] = (result, comment)
        self._width[1] = max(self._width[1], len(test.value) + 1)
        self._width[2] = max(self._width[2], len(result) + 1)
        self._width[3] = max(self._width[3], len(comment) + 1)


    def _print_row(self, *args: Union[Tuple, str]) -> None:

        if len(args) != len(self._BASE_HEADERS):
            raise Exception() # FIXME
        widths = tuple(self._width[i] + len(paint('', *arg[1:])) if type(arg) is tuple else self._width[i] for i, arg in enumerate(args))
        # apply paint to arguments if they carry any
        args = tuple(paint(*arg) if type(arg) is tuple else arg for arg in args)

        print(self.Char.VER_SEP.value.join([''] + [f' {arg:<{widths[i]}}' for i, arg in enumerate(args)] + ['']))
        

    def print_all(self) -> None:

        if not self._results:
            return

        print(paint('\n[SUMMARY]', Color.SILVER))    # FIXME: probably not the right place
        self._width[0] = len(str(len(self._results))) + 1
        print(
            self.Char.TOP_LEFT.value +
            self.Char.TOP_MID.value.join((w+1) * self.Char.HOR_SEP.value for w in self._width) + 
            self.Char.TOP_RIGHT.value
        )
        self._print_row(*self._BASE_HEADERS)
        print(
            self.Char.MID_LEFT.value +
            self.Char.MID_MID.value.join((w+1) * self.Char.HOR_SEP.value for w in self._width) + 
            self.Char.MID_RIGHT.value
        )
        for idx, (build_type, (result, comment)) in enumerate(self._results.items()):
            result_color = {
                'FAIL': (Color.WHITE, Color.RED),
                'PASS': (Color.BLACK, Color.GREEN),
                'N/A' : (Color.BLACK, Color.YELLOW),
            }.get(result.upper(), (Color.BLACK, Color.YELLOW))
            self._print_row(str(idx+1), (build_type.value, Color.CAPRI), (result, *result_color), comment)
        print(
            self.Char.BOT_LEFT.value +
            self.Char.BOT_MID.value.join((w+1) * self.Char.HOR_SEP.value for w in self._width) + 
            self.Char.BOT_RIGHT.value
        )


class ElapsedTimeThread(Thread):
    """Stoppable thread that prints the time elapsed"""
    def __init__(self) -> None:
        super(ElapsedTimeThread, self).__init__()
        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def run(self) -> None:
        thread_start = perf_counter()
        while not self.stopped():
            print(f'\rElapsed time: {perf_counter() - thread_start:.2f}s', end='')
            # include a delay here so the thread doesn't uselessly hog the CPU
            sleep(0.07)


class WarningTracker:

    def __init__(self) -> None:
        
        self._old_db = {}
        self._new_db = {}
        self._active_db: Dict = None


    def set_db(self, dest: str) -> None:

        if dest == 'old':
            self._active_db = self._old_db
        elif dest == 'new':
            self._active_db = self._new_db
        else:
            raise NameError('Invalid name') # HACK

    
    def add(self, warning: str) -> None:

        db = self._active_db
        warning = sub(r':[0-9]+:', ':#:', warning)
        warning = sub(r':[0-9]+:', ':#:', warning)
        if warning in db:
            db[warning] += 1
        else:
            db[warning] = 1


    def get_diff(self) -> None:

        print(paint('\n[WARNINGS]', Color.SILVER))
        removed_db, added_db = {}, {}
        for warning, count in self._old_db.items():
            if warning in self._new_db:
                count_diff = self._new_db[warning] - count
            else:
                count_diff = -count
            if count_diff < 0:
                removed_db[warning] = -count_diff
            elif count_diff > 0:
                added_db[warning] = count_diff
        for warning, count in self._new_db.items():
            if warning not in self._old_db:
                added_db[warning] = count
        print('Removed:')
        for warning in removed_db:
            print(warning)
        print('Added:')
        for warning in added_db:
            print(warning)
            if added_db[warning] > 1:
                print(added_db[warning])
        print(f'{sum(removed_db.values())} warnings removed.')
        print(f'{sum(added_db.values())} warnings added.')


class DeveloperToolbox:

    def __init__(self, path: str) -> None:

        self._BASE_PATH = Path(path).expanduser()
        self._LMAC_PATH = self._BASE_PATH / 'LMAC'
        self._COEX_PATH = self._LMAC_PATH  / 'ebuild/coex'
        self._RELEASE_PATH = self._LMAC_PATH / 'erelease'

        chdir(self._BASE_PATH)

        self._name = ''
        self._force_rebuild = False     # unused

        # TODO: make use of pipe make output level
        self._pipe_make_output_level = 0
        self._break_on_failure = True
        self._multithreading = True

        self._builds: List[BuildType] = []

        self._git_was_dirty = False
        self._actual_head = ''
        self._short_commit_hash = ''
        self._base_branch = ''
        self._merge_base = ''

        self._warning_tracker: WarningTracker = None
        self._pretty_table = PrettyTable()

        # TODO: make a class for this?
        self._METADATA: Dict[BuildType, Any] = {
            BuildType.RS9116_A10_ROM: {
                'args': ('--14R', '--9116R',),
                'hidden_args': ('--14r', '--a10r', '--911614R', '--911614ROM', '--1614R', '--A10R', '--18R', '--A10ROM',),
                'options': ('chip=9118', 'rom'),
                'rom_path': self._LMAC_PATH / 'ROM_Binaries/rom_content_TA.mem',
            },
            BuildType.RS9116_A10: {
                'args': ('-4', '-6', '--14', '--9116',),
                'hidden_args': ('-8', '--4', '--6', '--911614', '--1614', '--A10', '--16', '--18',),
                'options': ('chip=9118',),
                'invoc': self._COEX_PATH,
                'linker': self._COEX_PATH / 'linker_script_icache_qspi_all_coex_9118_wc.x',
                'convobj': self._COEX_PATH / 'convobj_coex_qspi_threadx_9118.sh',
                'bootdesc': self._LMAC_PATH / 'ebuild/wlan/boot_desc.c'
            },
            BuildType.RS9116_A11_ROM: {
                'args': ('--15R', '--91162R',),
                'hidden_args': ('--15r', '--a11r', '--911615R', '--911615ROM', '--1615R', '--A11R', '--182R', '--A11ROM',),
                'options': ('chip=9118', 'rev=2', 'rom'),
                'rom_path': self._LMAC_PATH / 'ROM2_Binaries/rom_content_TA.mem',
            },
            BuildType.RS9116_A11: {
                'args': ('-5', '--15', '--91162',),
                'hidden_args': ('-2', '--5', '--911615', '--1615', '--82', '--A11', '--162', '--182',),
                'options': ('chip=9118', 'rev=2',),
                'invoc': self._COEX_PATH,
                'linker': self._COEX_PATH / 'linker_script_icache_qspi_all_coex_9118_wc_rom2.x',
                'convobj': self._COEX_PATH / 'convobj_coex_qspi_threadx_9118_rom2.sh',
                'bootdesc': self._LMAC_PATH / 'ebuild/wlan/boot_desc_rom2.c'
            },
            BuildType.RS9116_A11_ANT: {
                'options': ('chip=9118', 'rev=2', 'ant=1',),
                'invoc': self._COEX_PATH,
                'linker': self._COEX_PATH / 'linker_script_icache_qspi_all_coex_9118_wc_rom2_ant.x',
                'convobj': self._COEX_PATH / 'convobj_coex_qspi_threadx_9118_ant_rom2.sh',
                'bootdesc': self._LMAC_PATH / 'ebuild/wlan/boot_desc_rom2.c',
                'garbage': self._BASE_PATH / 'ant_stack/ant_vnd_bin',
            },
            BuildType.RS9117_A0_ROM: {
                'args': ('--A0R', '--9117A0R',),
                'hidden_args': ('--a0r', '--9117A0ROM', '--17A0R', '--A0ROM', '--a0rom'),
                'options': ('chip=9117', 'rom',),
                'rom_path': self._LMAC_PATH / 'Si9117A0_ROM_Binaries/rom_content_TA.mem',
            },
            BuildType.RS9117_A0: {
                'args': ('-7', '-A', '--17', '--9117',),
                'hidden_args': ('-a', '--9117A0', '--17A0', '--A0', '--a0'),
                'options': ('chip=9117',),
                'invoc': self._COEX_PATH,
                'linker': self._LMAC_PATH / 'common/chip_dep/RS9117/cpu/linker_script_icache_qspi_all_coex_9117_wc_rom2.x',
                'convobj': self._LMAC_PATH / 'common/chip_dep/RS9117/cpu/convobj_coex_qspi_threadx_9117_rom2.sh',
                'bootdesc': self._LMAC_PATH / 'common/chip_dep/RS9117/cpu/boot_desc_9117_rom2.c',
            },
            BuildType.RS9117_B0_ROM: {
                'args': ('--B0R', '--9117B0R',),
                'hidden_args': ('--b0r', '--9117B0ROM', '--17B0R', '--B0ROM', '--b0rom',),
                'options': ('chip=9117', 'rom_version=B0', 'rom',),
                'rom_path': self._LMAC_PATH / 'Si9117B0_ROM_Binaries/rom_content_TA.mem',
            },
            BuildType.RS9117_B0: {
                'args': ('-B', '--B0', '--17B0',),
                'hidden_args': ('-9', '-b', '--9117B0', '--b0'),
                'options': ('chip=9117', 'rom_version=B0',),
                'invoc': self._COEX_PATH,
                'linker': self._LMAC_PATH / 'common/chip_dep/9117B0/cpu/linker_script_icache_qspi_all_coex_9117_wc_rom2.x',
                'convobj': self._LMAC_PATH / 'common/chip_dep/9117B0/cpu/convobj_coex_qspi_threadx_9117_rom2.sh',
                'bootdesc': self._LMAC_PATH / 'common/chip_dep/9117B0/cpu/boot_desc_9117_rom2.c',
            },
            # TODO: increase coverage
        }


    def _initialize(self) -> None:

        username = PureWindowsPath(get_output('wslvar USERPROFILE')).stem
        self._DEST_PATH = Path(f'/mnt/c/Users/{username}/Downloads/builds')
        self._DEST_PATH.mkdir(parents=True, exist_ok=True)
        self._LOG_FILE = self._DEST_PATH / f'{datetime.now().strftime("%y%m%d-%H%M%S")}.txt'
        self._LOG_FILE.touch()


    def parse_args(self) -> None:

        parser = ArgumentParser(
            description='rs911x developer tools',
            # TODO: epilog='confluence link',
        )

        parser.add_argument(
            '--bb', '--base-branch',
            dest='base_branch',
            help='Specify the base branch. This is only used to check formatting and if your branch is in sync with remote.',
            metavar='<branch-name>'
        )
        parser.add_argument(
            '-r', '--remote',
            dest='remote',
            action='store_true',
            help='Check if the base branch is in sync with remote (origin).',
        )
        parser.add_argument(
            '--cs', '--check-styling',
            dest='clang_check',
            action='store_true',
            help='Check for styling errors. This does NOT apply the fixes.',
        )
        parser.add_argument(
            '-s', '--apply-styling',
            dest='clang_format',
            action='store_true',
            help='Check for styling errors and apply the fixes.',
        )
        parser.add_argument(
            '-n', '--name',
            dest='name',
            help='Set a name for the build.',
            metavar='<build-name>'
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A10]['args'],
            dest='a10',
            action='store_true',
            help='Compile 9116 1.4 NCP firmware and copy it to Windows.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A10]['hidden_args'],
            dest='a10',
            action='store_true',
            help=SUPPRESS,
        )
        # TODO: move args to metadata
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A11]['args'],
            dest='a11',
            action='store_true',
            help='Compile 9116 1.5 NCP firmware and copy it to Windows.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A11]['hidden_args'],
            dest='a11',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_A0]['args'],
            dest='a0',
            action='store_true',
            help='Compile 9117 A0 NCP firmware and copy it to Windows.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_A0]['hidden_args'],
            dest='a0',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_B0]['args'],
            dest='b0',
            action='store_true',
            help='Compile 9117 B0 NCP firmware and copy it to Windows.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_B0]['hidden_args'],
            dest='b0',
            action='store_true',
            help=SUPPRESS
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A10_ROM]['args'],
            dest='a10r',
            action='store_true',
            help='Check whether 9116 1.4 ROM content has changed.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A10_ROM]['hidden_args'],
            dest='a10r',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A11_ROM]['args'],
            dest='a11r',
            action='store_true',
            help='Check whether 9116 1.5 ROM content has changed.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9116_A11_ROM]['hidden_args'],
            dest='a11r',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_A0_ROM]['args'],
            dest='a0r',
            action='store_true',
            help='Check whether 9117 A0 ROM content has changed.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_A0_ROM]['hidden_args'],
            dest='a0r',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_B0_ROM]['args'],
            dest='b0r',
            action='store_true',
            help='Check whether 9117 B0 ROM content has changed.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_B0_ROM]['hidden_args'],
            dest='b0r',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            '--G0', '--g0',
            dest='g0',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            '--G2', '--g2',
            dest='g2',
            action='store_true',
            help=SUPPRESS,
        )
        parser.add_argument(
            '-e', '--all', '--full',
            dest='all',
            action='store_true',
            help='Run all tools.'
        )

        subparsers = parser.add_subparsers()
        warnings_parser = subparsers.add_parser('warnings', aliases=['wa'])
        warnings_parser.add_argument('wc', metavar='chip')
        warnings_parser.add_argument('--thorough', action='store_true')
        
        args = parser.parse_args()

        clargs = vars(args).copy()
        clargs.pop('base_branch')
        if not any(x for x in clargs.values()):
            parser.print_help()
            return

        self._initialize()
        self._git_imprint()

        try:
            if args.base_branch:
                self.set_base_branch(args.base_branch)
            if args.name:
                self.set_name(args.name)
            if 'wc' in clargs:
                self._warning_tracker = WarningTracker()
                if args.wc in ('9117', '7', 'A0'):
                    self.check_warnings(BuildType.RS9117_A0)
                elif args.wc in ('B', 'B0'):
                    self.check_warnings(BuildType.RS9117_B0)
                raise GeneratorExit()   # HACK: used to wipe imprint
            if args.all or args.clang_check or args.clang_format or args.remote:
                if not self._base_branch:
                    self._infer_base_branch()
            if args.all or args.remote:
                self.check_remote_sync()
            if args.clang_format:
                self.check_styling(apply=True)
            elif args.all or args.clang_check:
                self.check_styling(apply=False)
            if args.all or args.g0 or args.a10r:
                self.add_build(BuildType.RS9116_A10_ROM)
            if args.all or args.g0 or args.g2 or args.a10:
                self.add_build(BuildType.RS9116_A10)
            if args.all or args.g0 or args.a11r:
                self.add_build(BuildType.RS9116_A11_ROM)
            if args.all or args.g0 or args.g2 or args.a11:
                self.add_build(BuildType.RS9116_A11)
            if args.all or args.g0 or args.a0r:
                self.add_build(BuildType.RS9117_A0_ROM)
            if args.all or args.g0 or args.g2 or args.a0:
                self.add_build(BuildType.RS9117_A0)
            if args.all or args.g0 or args.b0r:
                self.add_build(BuildType.RS9117_B0_ROM)
            if args.all or args.g0 or args.g2 or args.b0:
                self.add_build(BuildType.RS9117_B0)
            if args.all or args.g0:
                self.add_build(BuildType.RS9116_A11_ANT)
            if self._builds:
                self.execute_builds()

        except GeneratorExit:
            pass
        finally:
            self._git_imprint_wipe()
            self._pretty_table.print_all()
            get_output(f'cp {self._LOG_FILE} {self._COEX_PATH / "logdt.txt"}')


    def _git_imprint(self) -> None:

        print(paint('\n[GIT]', Color.SILVER))
        self._actual_head = get_output('git rev-parse HEAD')
        if run('git diff --quiet'.split(), cwd=self._BASE_PATH).returncode:
            print(f'{paint("Uncommitted changes found.", Color.ORANGE)}\nLeaving fingerprint...')
            get_output('git commit -am fingerprint')
            self._git_was_dirty = True
        short_commit_hash = get_output('git rev-parse --short HEAD')
        print(f'On commit {paint(short_commit_hash, Color.CAPRI)}')
        commit_hash = get_output('git rev-parse HEAD')
        self._short_commit_hash = short_commit_hash
        with open(self._LOG_FILE, 'a') as logfile:
            logfile.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]\n')
            logfile.write(f'invocation path: {self._BASE_PATH}\n')
            logfile.write(f'commit hash: {commit_hash}\n')
            # logfile.write(f'lca hash: {parent_hash}\n')


    def _git_imprint_wipe(self) -> None:

        if self._git_was_dirty:
            print(paint('\n[GIT]', Color.SILVER))
            get_output('git reset HEAD^')
            print('Wiped fingerprint.')


    def _infer_base_branch(self) -> None:

        print(paint('\n[BRANCH]', Color.SILVER))
        # TODO: this logic can perhaps be improved by ignoring origin/currentbranch
        current_branch = get_output('git branch --show-current')
        log = get_output(f'git log --pretty=format:%D {self._actual_head}^')
        refs_to_head = sorted(log[log.find('origin/'):].split('\n')[0].split(', '), key=lambda s: len(s))
        refs_to_head = [x for x in refs_to_head if x.startswith('origin/') and not x.endswith('HEAD')]
        # look for potential base branches further if the only
        # remote ref to the first remote head has the same name as current branch
        if current_branch and 'origin/' + current_branch in refs_to_head:
            if len(refs_to_head) == 1:
                log = get_output(f'git log --pretty=format:%D {refs_to_head[0]}^')
                refs_to_head = log[log.find('origin/'):].split('\n')[0].split(', ')
            else:
                refs_to_head.remove('origin/' + current_branch)
        base_branch = refs_to_head[0]   # HACK
        self._base_branch = base_branch
        self._merge_base = base_branch
        print(f'Assuming base branch is {paint(self._base_branch, Color.CAPRI)}. '
                'If incorrect, specify the correct base branch using --bb.')


    def check_remote_sync(self) -> None:

        print(paint('\n[REMOTE]', Color.SILVER))
        fetch_process = run('git fetch --dry-run'.split(), capture_output=True)
        git_fetch_output = (fetch_process.stdout + fetch_process.stderr).decode('utf-8').rstrip()
        if fetch_process.returncode:
            # raise ConnectionRefusedError()
            print(paint('Could not establish a connection to remote.', Color.RED))
            self._pretty_table.add_result(Test.REMOTE_SYNC, 'N/A', 'No connection.')
        elif self._base_branch in git_fetch_output:
            print(f'{paint("Remote is ahead", Color.RED)} of {self._base_branch}. '
                    'Consider doing an update and rebase/merge before pushing.')
            self._pretty_table.add_result(Test.REMOTE_SYNC, 'FAIL', 'Remote ahead.')
        else:
            print(f'{self._base_branch} is {paint("in sync with remote", Color.GREEN)}. Update not required.')
            self._pretty_table.add_result(Test.REMOTE_SYNC, 'PASS', 'In sync.')


    def check_styling(self, apply: bool=False) -> None:

        print(paint('\n[STYLING]', Color.SILVER))
        diff_files = get_output(f'git diff --name-only {self._merge_base}').split('\n')
        styling_needed = False
        for file in diff_files:
            if not(file.endswith('.c') or file.endswith('.h')):
                continue
            flag = True
            for parent in tuple(Path(file).parents)[:-1]:
                if (self._BASE_PATH / parent / '.clang-format').is_file():
                    flag = False
                    break
            if flag:
                if run(f'clang-format --Werror --dry-run {file}'.split(), cwd=self._BASE_PATH, capture_output=True).returncode:
                    styling_needed = True
                    if apply:
                        run(f'clang-format -i {file}'.split(), cwd=self._BASE_PATH, capture_output=True)
                        print(f'Style-formatted {file}.')
                    else:
                        print(f'{file} {paint("requires styling fixes.", Color.RED)}')
        if styling_needed:
            if apply:
                self._pretty_table.add_result(Test.STYLE_CHECK, 'DONE', 'Styling applied.')
            else:
                self._pretty_table.add_result(Test.STYLE_CHECK, 'FAIL', 'Needs styling.')
        else:
            print(f'{paint("No styling changes required.", Color.GREEN)}')
            self._pretty_table.add_result(Test.STYLE_CHECK, 'PASS', 'Styling proper.')


    def set_base_branch(self, branch_name: str) -> None:

        if run(f'git rev-parse --verify {branch_name}'.split(), capture_output=True).returncode:
            raise NameError('Branch name or commit ID invalid.')
        if run(f'git merge-base --is-ancestor {self._actual_head} {branch_name}'.split(), capture_output=True).returncode \
            and run(f'git merge-base --is-ancestor {branch_name} {self._actual_head}'.split(), capture_output=True).returncode: # HACK
            print(paint('Warning: base branch has diverged from the current branch. Consider doing a rebase/merge.', Color.YELLOW))
        self._base_branch = branch_name
        self._merge_base = get_output(f'git merge-base {branch_name} {self._actual_head}')


    def set_name(self, name: str) -> None:

        self._name = name


    def check_warnings(self, build: BuildType) -> None:

        if not self._merge_base:
            self._infer_base_branch()
        self._warning_tracker.set_db('new')
        results = self._make(self._METADATA[build]['options'], invoc=self._COEX_PATH)
        for file in ('linker', 'convobj', 'bootdesc', 'garbage'):
            if file in self._METADATA[build]:
                get_output(f'git restore {self._METADATA[build][file]}')
        print(results)
        # if not (results['status'] == 'PASS' or results['rerun']):
        #     print('Compilation failed.')
        #     print(results['logs']['error'])
        #     return
        get_output(f'git checkout {self._merge_base}')
        self._warning_tracker.set_db('old')
        self._make(self._METADATA[build]['options'], invoc=self._COEX_PATH)
        for file in ('linker', 'convobj', 'bootdesc', 'garbage'):
            if file in self._METADATA[build]:
                get_output(f'git restore {self._METADATA[build][file]}')
        get_output(f'git checkout -')
        self._warning_tracker.get_diff()


    def add_build(self, build: BuildType) -> None:

        if type(build) is not BuildType:
            raise TypeError
        self._builds.append(build)


    def _make(self, options: Tuple[str], invoc: Path = None, skip_clean: bool = False) -> Dict[str, Any]:
        
        if not invoc:
            invoc = self._COEX_PATH
        results = {
            'options': options,
            'status': 'FAIL',
            'rerun': False,
            'size': 0,
            'path': None,
            'logs': {},
        }
        if skip_clean is False:
            run('make clean'.split(), cwd=invoc)
        cmd = ['make'] + list(options)
        print(paint(f'[[ {" ".join(cmd)} ]]', Color.GRAY))
        if self._multithreading:
            cmd.append('-j')
            cmd.append('-Orecurse')
        p = Popen(cmd, cwd=invoc, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        sel = DefaultSelector()
        sel.register(p.stdout, EVENT_READ)
        sel.register(p.stderr, EVENT_READ)
        elapsed_time_thread = ElapsedTimeThread()
        elapsed_time_thread.daemon = True
        elapsed_time_thread.start()
        compiler_log = ''
        categorized_logs = {
            'linker': '',
            'error': '',
            'warning': '',
        }
        context = ''
        ok = True
        while ok:
            for key, _ in sel.select():
                line = key.fileobj.readline()
                if not line:
                    ok = False
                    break
                if key.fileobj is p.stdout:
                    if 'Size of flash image' in line:
                        results['status'] = 'PASS'
                        results['size'] = int(findall(r'\d+', line)[0])
                    elif 'Please run make again!' in line:
                        results['rerun'] = True
                else:
                    compiler_log += line
                    # TODO: improve this if clause
                    if '/tmp/cc' in line:
                        pass
                    elif '/bin/ld' in line and 'warning:' not in line:
                        categorized_logs['linker'] += context
                        context = ''
                        categorized_logs['linker'] += line
                    elif ': error:' in line or ': undefined reference' in line:
                        categorized_logs['error'] += context
                        context = ''
                        categorized_logs['error'] += line
                    elif ': warning:' in line:
                        # TODO: to be enabled on the day when we no more have an insane number of warnings
                        # categorized_logs['warning'] += context
                        if self._warning_tracker:
                            self._warning_tracker.add(context + line)
                        context = ''
                        # categorized_logs['warning'] += line
                    else:
                        context += line

        elapsed_time_thread.stop()
        elapsed_time_thread.join()
        print()

        with open(self._LOG_FILE, 'a') as logfile:
            logfile.write(f'\n[[{" ".join(cmd)}]]\n')
            logfile.write(compiler_log)
        
        # TODO: write stdout as well

        results['logs'] = categorized_logs
        return results


    def _make_flash(self, options: Tuple[str]) -> Dict[str, Any]:

        results = self._make(options, invoc=self._COEX_PATH)
        while results['rerun']:
            results = self._make(options, invoc=self._COEX_PATH, skip_clean=True)
        # TODO: use exceptions instead of dict to indicate failure?
        # if results['status'] is False:
        #     raise SourceCompilationError()
        outlist = tuple(self._RELEASE_PATH.glob('*.rps'))
        # if len(outlist) < 1:
        #     raise FileNotFoundError('rps not generated')
        if len(outlist):
            results['path'] = outlist[0]
        return results


    def _check_rom(self, chip: BuildType) -> bool:

        # TODO: return comments?
        gen_rom_path = self._COEX_PATH / 'rom_content_TA.mem'
        if gen_rom_path.is_file():
            osremove(gen_rom_path)
        self._make(self._METADATA[chip]['options'], invoc=self._COEX_PATH)
        return gen_rom_path.is_file() and fcmp(self._METADATA[chip]['rom_path'], gen_rom_path)


    def execute_builds(self) -> None:

        if not self._builds:
            return
        print(paint('\n[BUILDS]', Color.SILVER))
        # HACK: use invoc? research chdir
        chdir(self._COEX_PATH)
        # remove any duplicates
        self._builds = dict.fromkeys(self._builds).keys()
        try:
            for build in self._builds:
                print(f'Building {paint(build.name, Color.TEAL)}...')
                if build.name.endswith('ROM'):
                    result = self._check_rom(build)
                    if result is False:
                        print(paint('ROM changed.', Color.RED))
                        self._pretty_table.add_result(build, 'FAIL', 'ROM changed.')
                        if self._break_on_failure:
                            break
                    else:
                        print(paint('ROM unchanged.', Color.GREEN))
                        self._pretty_table.add_result(build, 'PASS', 'ROM unchanged.')
                else:
                    flash_target = self._DEST_PATH / f'{build.name}_{self._short_commit_hash}.rps'
                    if flash_target.is_file() and not self._force_rebuild:
                        print('Already built. Rebuilding...') # TODO: skip build
                    results = self._make_flash(self._METADATA[build]['options'])
                    for file in ('linker', 'convobj', 'bootdesc', 'garbage'):
                        if file in self._METADATA[build]:
                            get_output(f'git restore {self._METADATA[build][file]}')
                    self._pretty_table.add_result(build, results['status'], f'Size: {results["size"]}')
                    if results['status'] == 'PASS':
                        flash_src = results['path']
                        shcopy(flash_src, flash_target)
                        print(paint('Compilation successful.', Color.GREEN))
                    else:
                        print(paint('Compilation failed.', Color.RED))
                        if results['logs']['error']:
                            print(f'\nError log:\n{results["logs"]["error"]}')
                        if results['logs']['linker']:
                            # TODO: attempt to fix linker
                            print(f'\nLinker log:\n{results["logs"]["linker"]}')
                            print(f'Path: {self._METADATA[build]["linker"]}')
                        if self._break_on_failure:
                            break
        finally:
            # TODO: to clean or not to clean?
            # run('make clean'.split())
            pass


def main() -> None:

    dt = DeveloperToolbox('~/rs911x')
    dt.parse_args()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # TODO: improve handler?
        print('\nProgram terminated.')
    except EOFError:
        # FIXME: does not work?
        print('Input terminated.')

# TODO: PEP8
# TODO: replace all prints with logging, or at least file redirect
# TODO: fix all cwd/invocs
# TODO: keep fingerprint detached?
# TODO: name of the fw/commit
# TODO: store info about past builds to avoid recompilation
# TODO: advise against su
# TODO: config editor, config in editor
# TODO: info in comments: skipped, copied, path?, ROM changed
# TODO: git info exclude logdt, should be in git root since it will be independent for every repo
# TODO: intelligent make clean
