#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""decorator_utils unittest such as it is."""

import unittest

from pyutils import decorator_utils as du
from pyutils import unittest_utils as uu


class TestDecorators(unittest.TestCase):
    def test_singleton(self):
        @du.singleton
        class FooBar:
            pass

        x = FooBar()
        y = FooBar()
        self.assertTrue(x is y)


if __name__ == '__main__':
    unittest.main()
