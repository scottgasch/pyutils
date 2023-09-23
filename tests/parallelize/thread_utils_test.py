#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""thread_utils unittest."""

import threading
import time
import unittest

from pyutils import unittest_utils
from pyutils.parallelize import thread_utils


class TestThreadUtils(unittest.TestCase):
    invocation_count = 0

    @thread_utils.background_thread
    def background_thread(self, a: int, b: str, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.assertEqual(123, a)
            self.assertEqual('abc', b)
            time.sleep(0.1)

    def test_background_thread(self):
        (thread, event) = self.background_thread(123, 'abc')
        self.assertTrue(thread.is_alive())
        time.sleep(1.0)
        event.set()
        thread.join()
        self.assertFalse(thread.is_alive())

    @thread_utils.periodically_invoke(period_sec=0.3, stop_after=3)
    def periodic_invocation_target(self, a: int, b: str):
        self.assertEqual(123, a)
        self.assertEqual('abc', b)
        TestThreadUtils.invocation_count += 1

    def test_periodically_invoke_with_limit(self):
        TestThreadUtils.invocation_count = 0
        (thread, event) = self.periodic_invocation_target(123, 'abc')
        self.assertTrue(thread.is_alive())
        time.sleep(1.0)
        self.assertEqual(3, TestThreadUtils.invocation_count)
        self.assertFalse(thread.is_alive())

    @thread_utils.periodically_invoke(period_sec=0.1, stop_after=None)
    def forever_periodic_invocation_target(self, a: int, b: str):
        self.assertEqual(123, a)
        self.assertEqual('abc', b)
        TestThreadUtils.invocation_count += 1

    def test_periodically_invoke_runs_forever(self):
        TestThreadUtils.invocation_count = 0
        (thread, event) = self.forever_periodic_invocation_target(123, 'abc')
        self.assertTrue(thread.is_alive())
        time.sleep(1.0)
        self.assertTrue(thread.is_alive())
        time.sleep(1.0)
        event.set()
        thread.join()
        self.assertFalse(thread.is_alive())
        self.assertTrue(TestThreadUtils.invocation_count >= 19)


if __name__ == '__main__':
    unittest.main()
