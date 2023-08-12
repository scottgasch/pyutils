#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""decorator_utils unittest such as it is."""

import threading
import unittest

from pyutils import decorator_utils as du
from pyutils import unittest_utils as uu


class TestCounter:
    def __init__(self):
        self.x = 0

    def increment(self):
        self.x += 1


@du.synchronized()
def increment(x: TestCounter) -> None:
    x.increment()


def increment_loop(x: TestCounter) -> None:
    for n in range(10000):
        increment(x)


class TestDecorators(unittest.TestCase):
    def test_singleton(self) -> None:
        @du.singleton
        class FooBar:
            pass

        x = FooBar()
        y = FooBar()
        self.assertTrue(x is y)

    def test_synchronized(self) -> None:
        x = TestCounter()
        threads = []
        for n in range(4):
            t = threading.Thread(
                target=increment_loop,
                args=(x,),
            )
            t.start()
            threads.append(t)

        while len(threads) > 0:
            t = threads.pop()
            t.join()

        self.assertEqual(x.x, 40000)


if __name__ == '__main__':
    unittest.main()
