#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""dict_utils unittest."""

import unittest

from pyutils import dict_utils as du
from pyutils import unittest_utils  # Needed for --unittests_ignore_perf flag


class TestDictUtils(unittest.TestCase):
    def test_init_or_inc(self):
        d = {}
        du.init_or_inc(d, 'a')
        du.init_or_inc(d, 'b')
        du.init_or_inc(d, 'a')
        du.init_or_inc(d, 'b')
        du.init_or_inc(d, 'c')
        du.init_or_inc(d, 'c')
        du.init_or_inc(d, 'd')
        du.init_or_inc(d, 'e')
        du.init_or_inc(d, 'a')
        du.init_or_inc(d, 'b')
        e = {'a': 3, 'b': 3, 'c': 2, 'd': 1, 'e': 1}
        self.assertEqual(d, e)

    def test_shard_coalesce(self):
        d = {'a': 3, 'b': 3, 'c': 2, 'd': 1, 'e': 1}
        shards = du.shard(d, 2)
        merged = du.coalesce(shards)
        self.assertEqual(d, merged)

    def test_item_with_max_value(self):
        d = {'a': 4, 'b': 3, 'c': 2, 'd': 1, 'e': 1}
        self.assertEqual('a', du.item_with_max_value(d)[0])
        self.assertEqual(4, du.item_with_max_value(d)[1])
        self.assertEqual('a', du.key_with_max_value(d))
        self.assertEqual(4, du.max_value(d))

    def test_item_with_min_value(self):
        d = {'a': 4, 'b': 3, 'c': 2, 'd': 1, 'e': 0}
        self.assertEqual('e', du.item_with_min_value(d)[0])
        self.assertEqual(0, du.item_with_min_value(d)[1])
        self.assertEqual('e', du.key_with_min_value(d))
        self.assertEqual(0, du.min_value(d))

    def test_min_max_key(self):
        d = {'a': 4, 'b': 3, 'c': 2, 'd': 1, 'e': 0}
        self.assertEqual('a', du.min_key(d))
        self.assertEqual('e', du.max_key(d))


if __name__ == '__main__':
    unittest.main()
