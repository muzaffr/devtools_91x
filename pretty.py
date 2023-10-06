from enum import Enum
from textwrap import wrap

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
    CREAM       = 'cfaf8f'


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
