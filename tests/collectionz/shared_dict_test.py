#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""shared_dict unittest."""

import random
import unittest

from pyutils import unittest_utils
from pyutils.collectionz.shared_dict import SharedDict
from pyutils.parallelize import parallelize as p
from pyutils.parallelize import smart_future


class SharedDictTest(unittest.TestCase):
    @p.parallelize(method=p.Method.PROCESS)
    def doit(self, n: int, dict_name: str, parent_lock_id: int):
        assert id(SharedDict.LOCK) == parent_lock_id
        d = SharedDict(dict_name, None)
        try:
            msg = f'Hello from shard {n}'
            for x in range(0, 1000):
                d[n] = msg
                self.assertTrue(n in d)
                self.assertEqual(msg, d[n])
                y = d.get(random.randrange(0, 99), None)
            return n
        finally:
            d.close()

    def test_basic_operations(self):
        dict_name = 'test_shared_dict'
        d = SharedDict(dict_name, 4096)
        try:
            self.assertEqual(dict_name, d.get_name())
            results = []
            for n in range(100):
                f = self.doit(n, d.get_name(), id(SharedDict.LOCK))
                results.append(f)
            smart_future.wait_all(results)
            for f in results:
                self.assertTrue(f.wrapped_future.done())
            for k in d:
                self.assertEqual(d[k], f'Hello from shard {k}')
            assert len(d) == 100
        finally:
            d.close()
            d.cleanup()

    @p.parallelize(method=p.Method.PROCESS)
    def add_one(self, name: str, expected_lock_id: int):
        d = SharedDict(name)
        self.assertEqual(id(SharedDict.LOCK), expected_lock_id)
        try:
            for x in range(1000):
                with SharedDict.LOCK:
                    d["sum"] += 1
        finally:
            d.close()

    def test_locking_works(self):
        dict_name = 'test_shared_dict_lock'
        d = SharedDict(dict_name, 4096)
        try:
            d["sum"] = 0
            results = []
            for n in range(10):
                f = self.add_one(d.get_name(), id(SharedDict.LOCK))
                results.append(f)
            smart_future.wait_all(results)
            self.assertEqual(10000, d["sum"])
        finally:
            d.close()
            d.cleanup()


if __name__ == '__main__':
    unittest.main()
