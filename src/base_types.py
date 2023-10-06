from enum import Enum, auto as enumauto


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
    RS9117_A0_TINY  = '9117 A0 Tiny'


class Result(Enum):

    NONE = enumauto()
    PASS = enumauto()
    FAIL = enumauto()
    DIFF = enumauto()
    DONE = enumauto()

