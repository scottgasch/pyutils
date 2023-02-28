#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This is a lockfile implementation I created for use with cronjobs
on my machine to prevent multiple copies of a job from running in
parallel.

For local operations, when one job is running this code keeps a file
on disk to indicate a lock is held.  Other copies will fail to start
if they detect this lock until the lock is released.  There are
provisions in the code for timing out locks, cleaning up a lock when a
signal is received, gracefully retrying lock acquisition on failure,
etc...

Also allows for Zookeeper-based locks when lockfile path is prefixed
with 'zk:' in order to synchronize processes across different
machines.

"""

from __future__ import annotations

import contextlib
import datetime
import json
import logging
import os
import platform
import signal
import sys
import warnings
from dataclasses import dataclass
from typing import Literal, Optional

import kazoo

from pyutils import argparse_utils, config, decorator_utils, zookeeper
from pyutils.datetimes import datetime_utils

cfg = config.add_commandline_args(f"Lockfile ({__file__})", "Args related to lockfiles")
cfg.add_argument(
    "--lockfile_held_duration_warning_threshold",
    type=argparse_utils.valid_duration,
    default=datetime.timedelta(60.0),
    metavar="DURATION",
    help="If a lock is held for longer than this threshold we log a warning",
)
logger = logging.getLogger(__name__)


class LockFileException(Exception):
    """An exception related to lock files."""

    pass


@dataclass
class LocalLockFileContents:
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
            lockfile_path: path of the lockfile to acquire; may begin
                with zk: to indicate a path in zookeeper rather than
                on the local filesystem.  Note that zookeeper-based
                locks require an expiration_timestamp as the stale
                detection semantics are skipped for non-local locks.
            do_signal_cleanup: handle SIGINT and SIGTERM events by
                releasing the lock before exiting
            expiration_timestamp: when our lease on the lock should
                expire (as seconds since the Epoch).  None means the
                lock will not expire until we explicltly release it.
                Note that this is required for zookeeper based locks.
            override_command: don't use argv to determine our commandline
                rather use this instead if provided.
        """
        self.is_locked: bool = False
        self.lockfile: str = ""
        self.zk_client: Optional[kazoo.client.KazooClient] = None
        self.zk_lease: Optional[zookeeper.RenewableReleasableLease] = None

        if lockfile_path.startswith("zk:"):
            logger.debug("Lockfile is on Zookeeper.")
            if expiration_timestamp is None:
                raise Exception("Zookeeper locks require an expiration timestamp")
            self.lockfile = lockfile_path[3:]
            if not self.lockfile.startswith("/leases"):
                self.lockfile = "/leases" + self.lockfile
            self.zk_client = zookeeper.get_started_zk_client()
        else:
            logger.debug("Lockfile is local.")
            self.lockfile = lockfile_path
        self.locktime: Optional[float] = None
        self.override_command: Optional[str] = override_command
        if do_signal_cleanup:
            signal.signal(signal.SIGINT, self._signal)
            signal.signal(signal.SIGTERM, self._signal)
        self.expiration_timestamp = expiration_timestamp

    def locked(self) -> bool:
        """Is it locked currently?"""
        return self.is_locked

    def _try_acquire_local_filesystem_lock(self) -> bool:
        """Attempt to create the lockfile.  These flags cause os.open
        to raise an OSError if the file already exists.
        """
        try:
            logger.debug("Trying to acquire local lock %s.", self.lockfile)
            fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            with os.fdopen(fd, "a") as f:
                contents = self._construct_local_lockfile_contents()
                logger.debug(contents)
                f.write(contents)
            return True
        except OSError:
            logger.warning("Couldn't acquire local lock %s.", self.lockfile)
            return False

    def _try_acquire_zk_lock(self) -> bool:
        assert self.expiration_timestamp
        identifier = f"Lockfile for pid={os.getpid()} on machine {platform.node()}"
        if self.override_command:
            identifier += f" running {self.override_command}"
        self.zk_lease = zookeeper.RenewableReleasableLease(
            self.zk_client,
            self.lockfile,
            datetime.timedelta(seconds=self.expiration_timestamp),
            identifier,
        )
        return self.zk_lease

    def try_acquire_lock_once(self) -> bool:
        """Attempt to acquire the lock with no blocking.

        Returns:
            True if the lock was acquired and False otherwise.
        """
        success = False
        if self.zk_client:
            if self._try_acquire_zk_lock():
                success = True
        else:
            success = self._try_acquire_local_filesystem_lock()

        if success:
            self.locktime = datetime.datetime.now().timestamp()
            logger.debug("Success; I own %s.", self.lockfile)
            self.is_locked = True
        return success

    def acquire_with_retries(
        self,
        *,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_attempts: int = 5,
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

    def release(self) -> None:
        """Release the lock"""

        if not self.zk_client:
            try:
                os.unlink(self.lockfile)
            except Exception:
                logger.exception("Failed to unlink path %s; giving up.", self.lockfile)
        else:
            if self.zk_lease:
                self.zk_lease.release()
            self.zk_client.stop()
        self.is_locked = False

    def __enter__(self):
        if self.acquire_with_retries():
            return self

        msg = "Couldn't acquire lockfile; giving up."
        if not self.zk_client:
            raw_contents = self._read_lockfile()
            if raw_contents:
                contents = LocalLockFileContents(**json.loads(raw_contents))
                msg = f"Couldn't acquire {self.lockfile} after several attempts.  It's held by pid={contents.pid} ({contents.commandline}).  Giving up."
        logger.warning(msg)
        raise LockFileException(msg)

    def __exit__(self, _, value, traceback) -> Literal[False]:
        if self.locktime:
            ts = datetime.datetime.now().timestamp()
            duration = ts - self.locktime
            warning_threshold = config.config[
                "lockfile_held_duration_warning_threshold"
            ]
            assert warning_threshold
            if duration >= warning_threshold.total_seconds():
                # Note: describe duration briefly only does second-level granularity...
                str_duration = datetime_utils.describe_duration_briefly(int(duration))
                msg = f"Held {self.lockfile} for {str_duration}"
                logger.warning(msg)
                warnings.warn(msg, stacklevel=2)
        self.release()
        return False

    def __del__(self):
        if self.is_locked:
            self.release()

    def _signal(self, *unused_args):
        if self.is_locked:
            self.release()

    def _construct_local_lockfile_contents(self) -> str:
        if not self.zk_client:
            if self.override_command:
                cmd = self.override_command
            else:
                cmd = " ".join(sys.argv)
            contents = LocalLockFileContents(
                pid=os.getpid(),
                commandline=cmd,
                expiration_timestamp=self.expiration_timestamp,
            )
            return json.dumps(contents.__dict__)
        raise Exception("Non-local lockfiles should not call this?!")

    def _read_lockfile(self) -> Optional[str]:
        if not self.zk_client:
            try:
                with open(self.lockfile, "r") as rf:
                    lines = rf.readlines()
                    return lines[0]
            except Exception:
                logger.exception(
                    "Failed to read from path %s; giving up.", self.lockfile
                )
        return None

    def _detect_stale_lockfile(self) -> None:
        if not self.zk_client:
            raw_contents = self._read_lockfile()
            if not raw_contents:
                return
            contents = LocalLockFileContents(**json.loads(raw_contents))
            logger.debug('Blocking lock contents="%s"', contents)

            # Does the PID exist still?
            try:
                os.kill(contents.pid, 0)
            except OSError:
                logger.warning(
                    "Lockfile %s's pid (%d) is stale; force acquiring...",
                    self.lockfile,
                    contents.pid,
                )
                self.release()

            # Has the lock expiration expired?
            if contents.expiration_timestamp is not None:
                now = datetime.datetime.now().timestamp()
                if now > contents.expiration_timestamp:
                    logger.warning(
                        "Lockfile %s's expiration time has passed; force acquiring",
                        self.lockfile,
                    )
                    self.release()
