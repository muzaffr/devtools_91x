from enum import Enum
from textwrap import wrap
from typing import Dict, Tuple, Union

from base_types import Test, BuildType

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
