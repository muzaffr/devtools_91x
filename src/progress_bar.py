from time import perf_counter

from pretty import Color, paint

class ProgressBar:

    def __init__(self, name: str, max_value: float) -> None:
        self._name = name
        self._max_value = max_value
        self._LENGTH = 48
        self._START_TIME = perf_counter()
        self._LEAST_COUNT = 8
        self.current_value = 0

    def update(self, current_value: float) -> None:
        if current_value < 1 or current_value > self._max_value:
            return
        self.current_value = current_value
        chars = (' ',) + tuple(map(chr, range(9615, 9615 - self._LEAST_COUNT, -1)))
        v = chr(9474)
        ratio = current_value / self._max_value
        frac = ratio * self._LENGTH
        whole = int(frac)
        part = int((frac % 1) * self._LEAST_COUNT)
        elapsed_time = perf_counter() - self._START_TIME
        eta = (1 - ratio) * elapsed_time / ratio
        print(
            paint(
                f'\r  {self._name} {v}'
                + chars[-1] * whole
                + chars[part] * int(whole < self._LENGTH)
                + (self._LENGTH - whole - 1) * ' '
                + f'{v} {int(100 * ratio)}% '
                + f'{v} {elapsed_time:.1f}s ',
                # + f'{v} ETA: {eta:.1f}s ',
                Color.GRAY,
            ),
            end='',
        )

    def update_relative(self, delta: float) -> None:
        self.update(self.current_value + delta)

    def finalize(self) -> None:
        self.update(self._max_value)
        print()
