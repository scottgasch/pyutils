#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A simple stopwatch decorator / context for timing things.  This was factored out
of decorator utils so that bootstrap.py can keep its imports lighter."""

import contextlib
import time
from typing import Callable, Literal


class Timer(contextlib.AbstractContextManager):
    """
    A stopwatch to time how long something takes (walltime).

    Example usage::

        with stopwatch.Timer() as t:
            do_the_thing()

        walltime = t()
        print(f'That took {walltime} seconds.')
    """

    def __init__(self) -> None:
        self.start = 0.0
        self.end = 0.0

    def __enter__(self) -> Callable[[], float]:
        """Returns a functor that, when called, returns the walltime of the
        operation in seconds.
        """
        self.start = time.perf_counter()
        self.end = 0.0
        return lambda: self.end - self.start

    def __exit__(self, *args) -> Literal[False]:
        self.end = time.perf_counter()
        return False
