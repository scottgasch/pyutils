#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""File-based locking helper."""

from __future__ import annotations

import contextlib
import datetime
import json
import logging
import os
import signal
import sys
import warnings
from dataclasses import dataclass
from typing import Literal, Optional

from pyutils import config, decorator_utils
from pyutils.datetimez import datetime_utils

cfg = config.add_commandline_args(f'Lockfile ({__file__})', 'Args related to lockfiles')
cfg.add_argument(
    '--lockfile_held_duration_warning_threshold_sec',
    type=float,
    default=60.0,
    metavar='SECONDS',
    help='If a lock is held for longer than this threshold we log a warning',
)
logger = logging.getLogger(__name__)


class LockFileException(Exception):
    """An exception related to lock files."""

    pass


@dataclass
class LockFileContents:
    """The contents we'll write to each lock file."""

    pid: int
    """The pid of the process that holds the lock"""

    commandline: str
    """The commandline of the process that holds the lock"""

    expiration_timestamp: Optional[float]
    """When this lock will expire as seconds since Epoch"""


class LockFile(contextlib.AbstractContextManager):
    """A file locking mechanism that has context-manager support so you
    can use it in a with statement.  e.g.::

        with LockFile('./foo.lock'):
            # do a bunch of stuff... if the process dies we have a signal
            # handler to do cleanup.  Other code (in this process or another)
            # that tries to take the same lockfile will block.  There is also
            # some logic for detecting stale locks.
    """

    def __init__(
        self,
        lockfile_path: str,
        *,
        do_signal_cleanup: bool = True,
        expiration_timestamp: Optional[float] = None,
        override_command: Optional[str] = None,
    ) -> None:
        """C'tor.

        Args:
            lockfile_path: path of the lockfile to acquire
            do_signal_cleanup: handle SIGINT and SIGTERM events by
                releasing the lock before exiting
            expiration_timestamp: when our lease on the lock should
                expire (as seconds since the Epoch).  None means the
                lock will not expire until we explicltly release it.
            override_command: don't use argv to determine our commandline
                rather use this instead if provided.
        """
        self.is_locked: bool = False
        self.lockfile: str = lockfile_path
        self.locktime: Optional[int] = None
        self.override_command: Optional[str] = override_command
        if do_signal_cleanup:
            signal.signal(signal.SIGINT, self._signal)
            signal.signal(signal.SIGTERM, self._signal)
        self.expiration_timestamp = expiration_timestamp

    def locked(self):
        """Is it locked currently?"""
        return self.is_locked

    def available(self):
        """Is it available currently?"""
        return not os.path.exists(self.lockfile)

    def try_acquire_lock_once(self) -> bool:
        """Attempt to acquire the lock with no blocking.

        Returns:
            True if the lock was acquired and False otherwise.
        """
        logger.debug("Trying to acquire %s.", self.lockfile)
        try:
            # Attempt to create the lockfile.  These flags cause
            # os.open to raise an OSError if the file already
            # exists.
            fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            with os.fdopen(fd, "a") as f:
                contents = self._get_lockfile_contents()
                logger.debug(contents)
                f.write(contents)
            logger.debug('Success; I own %s.', self.lockfile)
            self.is_locked = True
            return True
        except OSError:
            pass
        logger.warning('Couldn\'t acquire %s.', self.lockfile)
        return False

    def acquire_with_retries(
        self,
        *,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_attempts=5,
    ) -> bool:
        """Attempt to acquire the lock repeatedly with retries and backoffs.

        Args:
            initial_delay: how long to wait before retrying the first time
            backoff_factor: a float >= 1.0 the multiples the current retry
                delay each subsequent time we attempt to acquire and fail
                to do so.
            max_attempts: maximum number of times to try before giving up
                and failing.

        Returns:
            True if the lock was acquired and False otherwise.
        """

        @decorator_utils.retry_if_false(
            tries=max_attempts, delay_sec=initial_delay, backoff=backoff_factor
        )
        def _try_acquire_lock_with_retries() -> bool:
            success = self.try_acquire_lock_once()
            if not success and os.path.exists(self.lockfile):
                self._detect_stale_lockfile()
            return success

        if os.path.exists(self.lockfile):
            self._detect_stale_lockfile()
        return _try_acquire_lock_with_retries()

    def release(self):
        """Release the lock"""
        try:
            os.unlink(self.lockfile)
        except Exception as e:
            logger.exception(e)
        self.is_locked = False

    def __enter__(self):
        if self.acquire_with_retries():
            self.locktime = datetime.datetime.now().timestamp()
            return self
        msg = f"Couldn't acquire {self.lockfile}; giving up."
        logger.warning(msg)
        raise LockFileException(msg)

    def __exit__(self, _, value, traceback) -> Literal[False]:
        if self.locktime:
            ts = datetime.datetime.now().timestamp()
            duration = ts - self.locktime
            if (
                duration
                >= config.config['lockfile_held_duration_warning_threshold_sec']
            ):
                # Note: describe duration briefly only does 1s granularity...
                str_duration = datetime_utils.describe_duration_briefly(int(duration))
                msg = f'Held {self.lockfile} for {str_duration}'
                logger.warning(msg)
                warnings.warn(msg, stacklevel=2)
        self.release()
        return False

    def __del__(self):
        if self.is_locked:
            self.release()

    def _signal(self, *args):
        if self.is_locked:
            self.release()

    def _get_lockfile_contents(self) -> str:
        if self.override_command:
            cmd = self.override_command
        else:
            cmd = ' '.join(sys.argv)
        contents = LockFileContents(
            pid=os.getpid(),
            commandline=cmd,
            expiration_timestamp=self.expiration_timestamp,
        )
        return json.dumps(contents.__dict__)

    def _detect_stale_lockfile(self) -> None:
        try:
            with open(self.lockfile, 'r') as rf:
                lines = rf.readlines()
                if len(lines) == 1:
                    line = lines[0]
                    line_dict = json.loads(line)
                    contents = LockFileContents(**line_dict)
                    logger.debug('Blocking lock contents="%s"', contents)

                    # Does the PID exist still?
                    try:
                        os.kill(contents.pid, 0)
                    except OSError:
                        logger.warning(
                            'Lockfile %s\'s pid (%d) is stale; force acquiring...',
                            self.lockfile,
                            contents.pid,
                        )
                        self.release()

                    # Has the lock expiration expired?
                    if contents.expiration_timestamp is not None:
                        now = datetime.datetime.now().timestamp()
                        if now > contents.expiration_timestamp:
                            logger.warning(
                                'Lockfile %s\'s expiration time has passed; force acquiring',
                                self.lockfile,
                            )
                            self.release()
        except Exception:
            pass  # If the lockfile doesn't exist or disappears, good.
