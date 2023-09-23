#!/usr/bin/env python3

# © Copyright 2022-2023, Scott Gasch

"""Tests for state_tracker.py"""

import logging
import threading
import time
import unittest
from unittest.mock import ANY, Mock, call

from pyutils import bootstrap, state_tracker, unittest_utils

logger = logging.getLogger(__name__)


class MockStateTracker(state_tracker.StateTracker):
    update = Mock()


class MockAutomaticStateTracker(state_tracker.AutomaticStateTracker):
    update = Mock()


class MockWaitableAutomaticStateTracker(state_tracker.WaitableAutomaticStateTracker):
    update = Mock()


class TestStateTracker(unittest.TestCase):
    def test_state_tracker_basic_operations(self) -> None:
        st = MockStateTracker(
            {
                'A': 0,
                'B': 10.0,
            }
        )
        st.heartbeat()
        st.update.assert_has_calls(
            [
                call('A', ANY, None),
                call('B', ANY, None),
            ],
            any_order=False,
        )
        time.sleep(0.1)
        st.heartbeat()
        calls = st.update.call_args_list
        assert len(calls) == 3

    def test_automatic_state_tracker(self) -> None:
        ast = MockAutomaticStateTracker(
            {
                'A': 1.0,
                'B': 10.0,
                'C': 20.0,
            }
        )
        try:
            assert ast.sleep_delay == 1.0
            time.sleep(0.1)
            ast.update.assert_has_calls(
                [
                    call('A', ANY, None),
                    call('B', ANY, None),
                    call('C', ANY, None),
                ],
                any_order=False,
            )
            time.sleep(1.1)
            assert ast.update.call_count == 4
        finally:
            ast.shutdown()

    def test_waitable_automatic_state_tracker(self) -> None:
        def make_something_change(wast) -> None:
            time.sleep(0.2)
            wast.something_changed()

        wast = MockWaitableAutomaticStateTracker({'A': 1.0})
        try:
            assert wast.sleep_delay == 1.0
            time.sleep(0.1)
            wast.update.assert_has_calls(
                [
                    call('A', ANY, None),
                ]
            )
            wast.wait(timeout=0.5)
            assert wast.did_something_change() is False
            thread = threading.Thread(target=make_something_change, args=[wast])
            thread.start()
            try:
                assert wast.wait() is True
                assert wast.did_something_change() is True
                wast.reset()
                assert wast.did_something_change() is False
                assert wast.wait(timeout=0.1) is False
                assert wast.did_something_change() is False
            finally:
                thread.join()
        finally:
            wast.shutdown()


if __name__ == '__main__':
    bootstrap.initialize(unittest.main)()
