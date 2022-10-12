#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""logging_utils unittest."""

import os
import sys
import tempfile
import unittest

from pyutils import logging_utils as lutils
from pyutils import string_utils as sutils
from pyutils import unittest_utils as uu


class TestLoggingUtils(unittest.TestCase):
    def test_output_context(self):
        unique_suffix = sutils.generate_uuid(True)
        filename = f'/tmp/logging_utils_test.{unique_suffix}'
        secret_message = f'This is a test, {unique_suffix}.'

        with tempfile.SpooledTemporaryFile(mode='r+') as tmpfile1:
            with uu.RecordStdout() as record:
                with lutils.OutputMultiplexerContext(
                    lutils.OutputMultiplexer.Destination.FILENAMES
                    | lutils.OutputMultiplexer.Destination.FILEHANDLES
                    | lutils.OutputMultiplexer.Destination.LOG_INFO,
                    filenames=[filename, '/dev/null'],
                    handles=[tmpfile1, sys.stdout],
                ) as mplex:
                    mplex.print(secret_message, end='')

                # Make sure it was written to the filename.
                with open(filename, 'r') as rf:
                    self.assertEqual(rf.readline(), secret_message)
                os.unlink(filename)

            # Make sure it was written to stdout.
            tmp = record().readline()
            self.assertEqual(tmp, secret_message)

            # Make sure it was written to the filehandle.
            tmpfile1.seek(0)
            tmp = tmpfile1.readline()
            self.assertEqual(tmp, secret_message)

    def test_record_streams(self):
        with uu.RecordMultipleStreams(sys.stderr, sys.stdout) as record:
            print("This is a test!")
            print("This is one too.", file=sys.stderr)
        self.assertEqual(
            record().readlines(), ["This is a test!\n", "This is one too.\n"]
        )


if __name__ == '__main__':
    unittest.main()
