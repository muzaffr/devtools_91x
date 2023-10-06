#!/usr/bin/python3

"""
Developer Tools for rs911x.

Celebi came from the future by crossing over time.
It is thought that so long as Celebi appears, a bright and shining future awaits us.
"""

from os import getuid
from typing import Dict, List

from chore_manager import ChoreManager

class Data:

    class BuildData:

        def __init__(self: int) -> None:
            self.id
            self.tests
            self.firmwares
            self.time
            self.pc
            self.path
            self.commit_hash
            self.tree_hash
            self.name


    def __init__(self) -> None:
        self.commit_to_tree: Dict[int, List[int]] = {}
        self.tree_to_commit: Dict[int, int] = {}
        self.build_data_list: List[self.BuildData] = []
        self.current_build_data: self.BuildData
    

def check_sudo() -> None:
    '''Check if current user has superuser privileges.'''
    if not getuid():
        raise PermissionError('Run the script with unelevated privileges.')


def main() -> None:

    ChoreManager().parse_args()


if __name__ == '__main__':
    check_sudo()
    try:
        main()
        # from pickle import dumps
        # print(dumps(set([Result.PASS])))
        pass
    except KeyboardInterrupt:
        # TODO: improve handler?
        print('\nProgram terminated.')
    except EOFError:
        # FIXME: does not work?
        print('Input terminated.')


# TODO: PEP8
# TODO: replace all prints with logging, or at least file redirect
# TODO: fix all cwd/invocs
# TODO: keep fingerprint detached? handle staged files in fingerprinting
# TODO: name of the fw/commit
# TODO: store info about past builds to avoid recompilation
# TODO: config editor, config in editor
# TODO: info in comments: skipped, copied, path?, ROM changed
# TODO: git info exclude logdt, should be in git root since it will be independent for every repo
# TODO: intelligent make clean
# TODO: capture line numbers in warnings
# TODO: copy flash option
# TODO: use tree hash (git cat-file -p HEAD)
# TODO: fix --bb with wa
# TODO: refactor argument parsing
# TODO: dynamic linker: remove garbage files?
# TODO: git checkout not reflected during warnings
# TODO: detect terminal width, change progress bar
# TODO: multiline comments support
# TODO: abstract [STATUS] messages


'''
config options
config_editor:
copy OneBox: (bool)
    ip address
    username
    password?
store_logs:
force_make_clean:
smart_make_clean:
force_rebuild:
pipe_make_output_level:
break_on_failure:
multithreading:
base_branch:
windows_output_path:
log_file_path: (multiple paths?)
garbage collection params (age, count, ?)

file structure
src/
    config
    progress_bar
    warning_tracker
    pretty
    types
    database
    chore_manager
    main
config/
'''
