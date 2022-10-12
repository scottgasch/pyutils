#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""letter_compress unittest."""

import math
import random
import unittest

from pyutils import bootstrap
from pyutils import unittest_utils as uu
from pyutils.compress import letter_compress


class TestLetterCompress(unittest.TestCase):
    def test_with_random_strings(self):
        alphabet = 'abcdefghijklmnopqrstuvwxyz .,"-'
        for n in range(20):
            message = ""
            for letter in random.choices(alphabet, k=random.randrange(10, 5000)):
                message += letter
            mlen = len(message)
            compressed = letter_compress.compress(message)
            clen = len(compressed)
            self.assertEqual(math.ceil(mlen * 5.0 / 8.0), clen)
            decompressed = letter_compress.decompress(compressed)
            self.assertEqual(
                decompressed, message, f'The bad message string was "{message}"'
            )


if __name__ == '__main__':
    bootstrap.initialize(unittest.main)()
