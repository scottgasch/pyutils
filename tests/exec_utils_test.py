#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""exec_utils unittest."""

import subprocess
import unittest

from pyutils import exec_utils, unittest_utils


class TestExecUtils(unittest.TestCase):
    def test_cmd_showing_output(self):
        with unittest_utils.RecordStdout() as record:
            ret = exec_utils.cmd_showing_output('/usr/bin/printf hello')
        self.assertEqual('hello', record().readline())
        self.assertEqual(0, ret)
        record().close()

    def test_cmd_showing_output_with_timeout(self):
        try:
            exec_utils.cmd_showing_output('sleep 10', timeout_seconds=0.1)
        except subprocess.TimeoutExpired:
            pass
        else:
            self.fail('Expected a TimeoutException, didn\'t see one.')

    def test_cmd_showing_output_fails(self):
        with unittest_utils.RecordStdout() as record:
            ret = exec_utils.cmd_showing_output('/usr/bin/printf hello && false')
        self.assertEqual('hello', record().readline())
        self.assertEqual(1, ret)
        record().close()

    def test_cmd_in_background(self):
        p = exec_utils.cmd_in_background('sleep 100')
        self.assertEqual(None, p.poll())


if __name__ == '__main__':
    unittest.main()
