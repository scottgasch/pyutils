#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Make sure id_generator is thread safe."""

import unittest

from pyutils import id_generator
from pyutils import unittest_utils as uu
from pyutils.parallelize import parallelize as par
from pyutils.parallelize import smart_future, thread_utils


class TestIdGenerator(unittest.TestCase):
    @par.parallelize(method=par.Method.THREAD)
    def get_some_ids(self):
        name = thread_utils.current_thread_id()
        print(f"Hello from {name}")
        results = []
        for _ in range(10000):
            results.append(id_generator.get("TestSequence"))
        return results

    def test_is_safe(self):
        results = []
        for i in range(10):
            results.append(self.get_some_ids())

        smart_future.wait_all(results)
        already_seen = set()
        for result in results:
            for identifier in result:
                if identifier in already_seen:
                    self.fail(f"Saw the id {identifier} more than once?!")
                else:
                    already_seen.add(identifier)


if __name__ == "__main__":
    unittest.main()
