#!/usr/bin/env python3

# © Copyright 2024, Scott Gasch

"""Terminal input utilities."""

import contextlib
import select
import sys
import termios
import tty
from typing import Callable, Literal, Optional


class KeystrokeReader(contextlib.AbstractContextManager):
    """Save the terminal settings, put the terminal in raw mode and
    return a helper that can be used to wait for and return a single
    keystroke event (with a timeout).  Restores the previous terminal
    mode on exit.

    Example usage::

        with input_utils.KeystrokeReader() as get_keystroke:
            while True:
                # Check / parse any keys.
                key = get_keystroke(timeout_seconds=0.01)
                if key:
                    if key == ' ':
                        if not stopwatch.running:
                            stopwatch.start()
                        else:
                            stopwatch.pause()
                    elif key == 'r':
                        stopwatch.reset()
                    elif key == 'l':
                        print(f"Lap: {stopwatch.get_elapsed_time():.5f}")
                    elif key == 'q' or key == chr(3):
                        break
                ...

    """

    def __init__(self) -> None:
        super().__init__()
        self.fd = sys.stdin.fileno()

    def __enter__(self) -> Callable[[], Optional[str]]:
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        return self._get_single_keystroke

    def _get_single_keystroke(
        self, timeout_seconds: Optional[float] = None
    ) -> Optional[str]:
        """Helper to read a single raw keystroke from stdin with a timeout."""

        rlist, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
        if rlist:
            keystroke = sys.stdin.read(1)
            return keystroke
        return None

    def __exit__(self, *args) -> Literal[False]:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        return False


if __name__ == "__main__":
    import doctest

    doctest.testmod()
