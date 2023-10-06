from argparse   import ArgumentParser, SUPPRESS
from filecmp    import cmp as fcmp
from os         import remove as osremove
from pathlib    import Path, PureWindowsPath
from re         import findall
from selectors  import DefaultSelector, EVENT_READ
from shutil     import copy as shcopy
from subprocess import run, Popen, PIPE
from typing     import Any, Dict, List, Tuple, Union

from base_types import Test, BuildType, Result
from pretty import Color, PrettyTable, paint
from progress_bar import ProgressBar
from warning_tracker import WarningTracker


class ChoreManager:

    def __init__(self) -> None:

        p = run('git rev-parse --show-toplevel'.split(), capture_output=True)
        if p.returncode != 0:
            raise FileNotFoundError('Not a git repository')
        self._BASE_PATH = Path(p.stdout.decode('utf8').rstrip())
        self._LMAC_PATH = self._BASE_PATH / 'LMAC'
        self._COEX_PATH = self._LMAC_PATH  / 'ebuild/coex'
        self._RELEASE_PATH = self._LMAC_PATH / 'erelease'

        self._cwd = self._BASE_PATH

        self._name = ''
        self._force_rebuild = False     # unused

        # TODO: make use of pipe make output level
        self._pipe_make_output_level = 0
        self._break_on_failure = False
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
                'invoc': self._COEX_PATH,
                'rom_path': self._LMAC_PATH / 'rom_binaries/ROM_Binaries/rom_content_TA.mem',
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
                'invoc': self._COEX_PATH,
                'rom_path': self._LMAC_PATH / 'rom_binaries/ROM2_Binaries/rom_content_TA.mem',
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
                'linker': self._BASE_PATH / 'ant_stack/linker_script_icache_qspi_all_coex_9118_wc_rom2.x',
                'convobj': self._COEX_PATH / 'convobj_coex_qspi_threadx_9118_ant_rom2.sh',
                'bootdesc': self._LMAC_PATH / 'ebuild/wlan/boot_desc_rom2.c',
                'garbage': self._BASE_PATH / 'ant_stack/ant_vnd_bin',
            },
            BuildType.RS9117_A0_ROM: {
                'args': ('--A0R', '--9117A0R',),
                'invoc': self._COEX_PATH,
                'hidden_args': ('--a0r', '--9117A0ROM', '--17A0R', '--A0ROM', '--a0rom'),
                'options': ('chip=9117', 'rom',),
                'rom_path': self._LMAC_PATH / 'rom_binaries/Si9117A0_ROM_Binaries/rom_content_TA.mem',
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
                'invoc': self._COEX_PATH,
                'hidden_args': ('--b0r', '--9117B0ROM', '--17B0R', '--B0ROM', '--b0rom',),
                'options': ('chip=9117', 'rom_version=B0', 'rom',),
                'rom_path': self._LMAC_PATH / 'rom_binaries/Si9117B0_ROM_Binaries/rom_content_TA.mem',
            },
            BuildType.RS9117_B0: {
                'args': ('-B', '--B0', '--17B0',),
                'hidden_args': ('-9', '-b', '--9117B0', '--b0',),
                'options': ('chip=9117', 'rom_version=B0',),
                'invoc': self._COEX_PATH,
                'linker': self._LMAC_PATH / 'common/chip_dep/9117B0/cpu/linker_script_icache_qspi_all_coex_9117_wc_rom2.x',
                'convobj': self._LMAC_PATH / 'common/chip_dep/9117B0/cpu/convobj_coex_qspi_threadx_9117_rom2.sh',
                'bootdesc': self._LMAC_PATH / 'common/chip_dep/9117B0/cpu/boot_desc_9117_rom2.c',
            },
            BuildType.RS9117_A0_TINY: {
                'args': ('--A0T', '--A0SA',),
                'hidden_args': ('--a0t', '--a0sa',),
                'options': ('chip=9117', 'sta_alone=1',),
                'invoc': self._COEX_PATH,
                'linker': self._LMAC_PATH / 'common/chip_dep/RS9117/cpu/linker_script_icache_qspi_all_coex_9117_wc_rom2_sta_alone.x',
                'convobj': self._LMAC_PATH / 'common/chip_dep/RS9117/cpu/convobj_coex_qspi_threadx_9117_rom2_sta_alone.sh',
                'bootdesc': self._LMAC_PATH / 'common/chip_dep/RS9117/cpu/boot_desc_9117_rom2_sta_alone.c',
            },
            # TODO: increase coverage
        }


    def get_cmd_stdout(self, cmd: str, cwd=None) -> str:

        if cwd is None:
            cwd = self._cwd
        return run(cmd.split(), capture_output=True, cwd=cwd).stdout.decode('utf8').rstrip()


    def get_cmd_rc(self, cmd: str, cwd=None) -> int:

        if cwd is None:
            cwd = self._cwd
        return run(cmd.split(), capture_output=True, cwd=cwd).returncode


    def _initialize(self) -> None:

        username = PureWindowsPath(self.get_cmd_stdout('wslvar USERPROFILE')).stem
        self._WIN_PATH = Path(f'/mnt/c/Users/{username}/Documents/celebi')
        self._DEST_PATH = self._WIN_PATH
        self._DEST_PATH.mkdir(parents=True, exist_ok=True)
        (self._DEST_PATH / 'logs').mkdir(exist_ok=True)
        self._DB_FILE = self._DEST_PATH / 'data'
        if not self._DB_FILE.exists():
            self._DB_FILE.touch()


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
            *self._METADATA[BuildType.RS9117_A0_TINY]['args'],
            dest='a0t',
            action='store_true',
            help='Compile 9117 A0 Tiny NCP firmware and copy it to Windows.',
        )
        parser.add_argument(
            *self._METADATA[BuildType.RS9117_A0_TINY]['hidden_args'],
            dest='a0t',
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
            '--rom', '--ROM',
            dest='rom',
            action='store_true',
            help='Check for ROM changes (all ROMs).',
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

        # If no meaningful argument is given, print help and exit.
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
                if args.wc in ('9117', '7', 'A0', 'A'):
                    self.check_warnings(BuildType.RS9117_A0)
                elif args.wc in ('B', 'B0'):
                    self.check_warnings(BuildType.RS9117_B0)
                elif args.wc in ('6', '4'):
                    self.check_warnings(BuildType.RS9116_A10)
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
            if args.all or args.g0 or args.a10r or args.rom:
                self.add_build(BuildType.RS9116_A10_ROM)
            if args.all or args.g0 or args.g2 or args.a10:
                self.add_build(BuildType.RS9116_A10)
            if args.all or args.g0 or args.a11r or args.rom:
                self.add_build(BuildType.RS9116_A11_ROM)
            if args.all or args.g0 or args.g2 or args.a11:
                self.add_build(BuildType.RS9116_A11)
            if args.all or args.g0 or args.a0r or args.rom:
                self.add_build(BuildType.RS9117_A0_ROM)
            if args.all or args.g0 or args.g2 or args.a0:
                self.add_build(BuildType.RS9117_A0)
            if args.all or args.g0 or args.b0r or args.rom:
                self.add_build(BuildType.RS9117_B0_ROM)
            if args.all or args.g0 or args.g2 or args.b0:
                self.add_build(BuildType.RS9117_B0)
            if args.all or args.g0 or args.g2 or args.a0t:
                self.add_build(BuildType.RS9117_A0_TINY)
            if args.all or args.g0:
                self.add_build(BuildType.RS9116_A11_ANT)
            if self._builds:
                self.execute_builds()

        except GeneratorExit:
            pass
        finally:
            self._git_imprint_wipe()
            self._pretty_table.print_all()
            # shcopy(self._LOG_FILE, self._BASE_PATH / 'logdt.txt')
            print(paint('\n[SAFE EXIT]', Color.SILVER))
            (self._COEX_PATH / 'logdt.txt').unlink(missing_ok=True)
            (self._COEX_PATH / 'logdt.txt').symlink_to(self._BASE_PATH / 'logdt.txt')


    def _git_imprint(self) -> None:

        print(paint('\n[GIT]', Color.SILVER))
        self._actual_head = self.get_cmd_stdout('git rev-parse HEAD')
        if self.get_cmd_rc('git diff --quiet'):
            print(f'{paint("Uncommitted changes found.", Color.ORANGE)}\nLeaving fingerprint...')
            self.get_cmd_rc('git commit -am fingerprint')
            self._git_was_dirty = True
        short_commit_hash = self.get_cmd_stdout('git rev-parse --short HEAD')
        print(f'On commit {paint(short_commit_hash, Color.CAPRI)}')
        commit_hash = self.get_cmd_stdout('git rev-parse HEAD')
        self._short_commit_hash = short_commit_hash
        # with open(self._LOG_FILE, 'a') as logfile:
        #     logfile.write(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]\n')
        #     logfile.write(f'invocation path: {self._BASE_PATH}\n')
        #     logfile.write(f'commit hash: {commit_hash}\n')
        #     logfile.write(f'lca hash: {parent_hash}\n')


    def _git_imprint_wipe(self) -> None:

        if self._git_was_dirty:
            print(paint('\n[GIT]', Color.SILVER))
            self.get_cmd_rc('git reset HEAD^')
            print('Wiped fingerprint.')


    def _infer_base_branch(self) -> None:

        print(paint('\n[BRANCH]', Color.SILVER))
        # TODO: this logic can perhaps be improved by ignoring origin/currentbranch
        current_branch = self.get_cmd_stdout('git branch --show-current')
        log = self.get_cmd_stdout(f'git log --pretty=format:%D {self._actual_head}^')
        refs_to_head = sorted(log[log.find('origin/'):].split('\n')[0].split(', '), key=lambda s: len(s))
        refs_to_head = [x for x in refs_to_head if x.startswith('origin/') and not x.endswith('HEAD')]
        # look for potential base branches further if the only
        # remote ref to the first remote head has the same name as current branch
        if current_branch and 'origin/' + current_branch in refs_to_head:
            if len(refs_to_head) == 1:
                log = self.get_cmd_stdout(f'git log --pretty=format:%D {refs_to_head[0]}^')
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
        fetch_process = run('git fetch --dry-run'.split(), capture_output=True, cwd=self._BASE_PATH)
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
        diff_files = self.get_cmd_stdout(f'git diff --name-only {self._merge_base}').split('\n')
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
                if self.get_cmd_rc(f'clang-format --Werror --dry-run {file}'):
                    styling_needed = True
                    if apply:
                        self.get_cmd_rc(f'clang-format -i {file}')
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

        if self.get_cmd_rc(f'git rev-parse --verify {branch_name}'):
            raise NameError('Branch name or commit ID invalid.')
        if self.get_cmd_rc(f'git merge-base --is-ancestor {self._actual_head} {branch_name}') \
            and self.get_cmd_rc(f'git merge-base --is-ancestor {branch_name} {self._actual_head}'): # HACK
            print(paint('Warning: base branch has diverged from the current branch. Consider doing a rebase/merge.', Color.YELLOW))
        self._base_branch = branch_name
        self._merge_base = self.get_cmd_stdout(f'git merge-base {branch_name} {self._actual_head}')


    def set_name(self, name: str) -> None:

        self._name = name


    def check_warnings(self, build: BuildType) -> None:

        if not self._merge_base:
            self._infer_base_branch()
        self._warning_tracker.set_db('new')
        results = self._make(self._METADATA[build]['options'], invoc=self._COEX_PATH)
        self._clean_auto_files(self._METADATA[build])
        if not (results['status'] == 'PASS' or results['rerun']):
            print('Compilation failed.')
            print(results['logs']['error'])
            return
        self.get_cmd_rc(f'git checkout {self._merge_base}')
        self._warning_tracker.set_db('old')
        self._make(self._METADATA[build]['options'], invoc=self._COEX_PATH)
        self._clean_auto_files(self._METADATA[build])
        self.get_cmd_rc(f'git checkout -')
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
            self.get_cmd_rc('make clean', cwd=invoc)
        cmd = ['make'] + list(options)
        if self._multithreading:
            cmd.append('-j')
            cmd.append('-Otarget')
        cmd.append('--trace')
        targets = run(cmd + ['--dry-run'], capture_output=True, cwd=invoc).stdout.count(b'<builtin>: update target')
        pb = ProgressBar(f'{" ".join(options)}', targets)
        p = Popen(cmd, cwd=invoc, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        sel = DefaultSelector()
        sel.register(p.stdout, EVENT_READ)
        sel.register(p.stderr, EVENT_READ)

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
                    elif '<builtin>: update target' in line:
                        pb.update_relative(1)
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

        if p.returncode == 0:
            pb.finalize()
        print()

        # with open(self._LOG_FILE, 'a') as logfile:
        #     logfile.write(f'\n[[{" ".join(cmd)}]]\n')
        #     logfile.write(compiler_log)

        # TODO: write stdout as well

        results['logs'] = categorized_logs
        return results


    def _clean_auto_files(self, build):
        for file in ('linker', 'convobj', 'bootdesc', 'garbage'):
            if file in build:
                self.get_cmd_rc(f'git restore {build[file]}')


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
                    self._clean_auto_files(self._METADATA[build])
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
