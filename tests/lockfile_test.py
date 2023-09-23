#!/usr/bin/env python3

# © Copyright 2022-2023, Scott Gasch

"""Tests for lockfile.py"""

import logging
import os
import time
import unittest

from pyutils import bootstrap, unittest_utils
from pyutils.files import lockfile

logger = logging.getLogger(__name__)


class TestLockfile(unittest.TestCase):
    def test_lockfile_basic_operations(self) -> None:
        pid = os.getpid()
        filename = f'/tmp/test_lockfile.{pid}'
        with lockfile.LockFile(filename) as lf:
            assert lf.locked()
            assert lf._read_lockfile().startswith(f'{{"pid": {pid}')
            assert not lf.acquire_with_retries(max_attempts=1)
            assert not lf.try_acquire_lock_once()

    def test_acquire_stale_lockfile(self) -> None:
        pid = os.getpid()
        filename = f'/tmp/test_lockfile.{pid}'
        now = time.time()
        with lockfile.LockFile(filename, expiration_timestamp=(now + 1.0)) as lf:
            assert lf.locked()
            assert not lf.try_acquire_lock_once()
            time.sleep(2.0)
            assert lf.locked()
            assert lf.try_acquire_lock_once()


if __name__ == '__main__':
    bootstrap.initialize(unittest.main)()
