#!/usr/bin/env python3
# © Copyright 2021-2023, Scott Gasch
"""Helper methods concerned with executing subprocesses."""

import atexit
import logging
import os
import selectors
import shlex
import subprocess
import sys
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)


def cmd_showing_output(
    command: str,
    *,
    timeout_seconds: Optional[float] = None,
) -> int:
    """Kick off a child process, streaming its stdout/stderr character-by-character
    to our own stdout/stderr in real time.  Useful for subprocesses that emit
    incremental progress (dots, spinners, etc.) where waiting on newlines would
    produce a bad user experience.

    Args:
        command: the shell command to execute
        timeout_seconds: kill the subprocess and raise TimeoutExpired if it
            runs longer than this; None means wait indefinitely.

    Returns:
        The exit status of the subprocess.

    Raises:
        TimeoutExpired: if the timeout expires before the child terminates.

    .. warning::
        Invokes a subshell — sanitize user-provided data with :func:`shlex.quote`
        before passing it in.  See:
        https://docs.python.org/3/library/subprocess.html#security-considerations
    """
    line_enders = {b"\n", b"\r"}
    timed_out = threading.Event()

    with subprocess.Popen(
        command,
        shell=True,
        bufsize=0,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    ) as p:

        def _on_timeout() -> None:
            timed_out.set()
            p.kill()

        timer = None
        if timeout_seconds is not None:
            timer = threading.Timer(timeout_seconds, _on_timeout)
            timer.start()

        try:
            sel = selectors.DefaultSelector()
            sel.register(p.stdout, selectors.EVENT_READ)  # type: ignore[arg-type]
            sel.register(p.stderr, selectors.EVENT_READ)  # type: ignore[arg-type]

            while sel.get_map():
                for key, _ in sel.select():
                    char = key.fileobj.read(1)  # type: ignore[union-attr]
                    if not char:
                        sel.unregister(key.fileobj)
                        continue
                    if key.fileobj is p.stdout:
                        os.write(sys.stdout.fileno(), char)
                        if char in line_enders:
                            sys.stdout.flush()
                    else:
                        os.write(sys.stderr.fileno(), char)
                        if char in line_enders:
                            sys.stderr.flush()

            sys.stdout.flush()
            sys.stderr.flush()
            sel.close()
            p.wait()
        finally:
            if timer is not None:
                timer.cancel()

    if timed_out.is_set():
        assert timeout_seconds
        raise subprocess.TimeoutExpired(command, timeout_seconds)
    return p.returncode


def cmd_exitcode(command: str, timeout_seconds: Optional[float] = None) -> int:
    """Run a command silently and return its exit code.

    Unlike :func:`cmd`, a non-zero exit does NOT raise — the caller is expected
    to inspect the return value.  Use :func:`run_silently` if you want an
    exception on failure.

    Args:
        command: the shell command to run
        timeout_seconds: max seconds to wait; None means no limit.

    Returns:
        The exit status of the subprocess.

    Raises:
        TimeoutExpired: if the child runs longer than timeout_seconds.

    >>> cmd_exitcode('/bin/echo foo', 10.0)
    0
    >>> cmd_exitcode('false')
    1
    >>> cmd_exitcode('/bin/sleep 2', 0.01)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    subprocess.TimeoutExpired: Command '/bin/sleep 2' timed out...
    """
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout_seconds,
    )
    return result.returncode


def cmd(
    command: str,
    timeout_seconds: Optional[float] = None,
    *,
    include_stderr: bool = False,
) -> str:
    """Run a command and return its stdout as a string.

    Args:
        command: the shell command to run
        timeout_seconds: max seconds to wait; None means no limit.
        include_stderr: if True, merge stderr into the returned string;
            if False (default), stderr is logged at WARNING level on failure
            and discarded on success.

    Returns:
        The stdout of the subprocess as a decoded string.

    Raises:
        CalledProcessError: if the subprocess exits non-zero.
        TimeoutExpired: if the child runs longer than timeout_seconds.

    .. warning::
        Invokes a subshell — sanitize user-provided data with :func:`shlex.quote`.

    >>> cmd('/bin/echo foo').strip()
    'foo'
    >>> cmd('/bin/sleep 2', 0.01)
    Traceback (most recent call last):
    ...
    subprocess.TimeoutExpired: Command '/bin/sleep 2' timed out after 0.01 seconds
    """
    stderr_dest = subprocess.STDOUT if include_stderr else subprocess.PIPE
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=stderr_dest,
            check=True,
            timeout=timeout_seconds,
        )
    except subprocess.CalledProcessError as e:
        if not include_stderr and e.stderr:
            logger.warning(
                "cmd %r stderr: %s", command, e.stderr.decode("utf-8", errors="replace")
            )
        raise
    return result.stdout.decode("utf-8")


def run_silently(command: str, timeout_seconds: Optional[float] = None) -> None:
    """Run a command, suppressing all output.  Raise on non-zero exit.

    Args:
        command: the shell command to run
        timeout_seconds: max seconds to wait; None means no limit.

    Raises:
        CalledProcessError: if the subprocess exits non-zero.
        TimeoutExpired: if the child runs longer than timeout_seconds.

    .. warning::
        Invokes a subshell — sanitize user-provided data with :func:`shlex.quote`.

    >>> run_silently("/usr/bin/true")
    >>> run_silently("/usr/bin/false")
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: Command '/usr/bin/false' returned non-zero exit status 1.
    """
    subprocess.run(
        command,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=timeout_seconds,
    )


def cmd_in_background(command: str, *, silent: bool = False) -> subprocess.Popen:
    """Spawn a child process in the background.

    Registers an atexit handler to terminate the child if the parent exits,
    so background processes don't outlive their parent.

    Args:
        command: the command to run
        silent: if True, suppress all child output (stdin/stdout/stderr to DEVNULL)

    Returns:
        The :class:`subprocess.Popen` object for the background process.
    """
    args = shlex.split(command)
    devnull = subprocess.DEVNULL if silent else None
    subproc = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=devnull,
        stderr=devnull,
    )
    logger.info("Spawned background process pid=%d: %s", subproc.pid, command)

    def _kill_on_exit() -> None:
        if subproc.poll() is not None:
            return
        try:
            logger.info(
                "atexit: terminating background pid=%d (%s)", subproc.pid, command
            )
            subproc.terminate()
            subproc.wait(timeout=10.0)
        except BaseException:
            logger.exception(
                "Failed to terminate background pid=%d; giving up.", subproc.pid
            )

    atexit.register(_kill_on_exit)
    return subproc


def cmd_list(command: List[str], timeout_seconds: Optional[float] = None) -> str:
    """Run a command supplied as a pre-tokenized list (no shell interpolation).

    Prefer this over :func:`cmd` when constructing commands programmatically
    from parts, since it avoids subshell injection entirely.

    Args:
        command: the command and arguments as a list, e.g. ['ls', '-la', '/tmp']
        timeout_seconds: max seconds to wait; None means no limit.

    Returns:
        The stdout of the subprocess as a decoded string.

    Raises:
        CalledProcessError: if the subprocess exits non-zero.
        TimeoutExpired: if the child runs longer than timeout_seconds.

    >>> cmd_list(['/bin/echo', 'foo']).strip()
    'foo'
    """
    result = subprocess.run(
        command,
        capture_output=True,
        check=True,
        timeout=timeout_seconds,
    )
    return result.stdout.decode("utf-8")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
