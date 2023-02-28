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
from typing import List, Optional

logger = logging.getLogger(__file__)


def cmd_showing_output(
    command: str,
    *,
    timeout_seconds: Optional[float] = None,
) -> int:
    """Kick off a child process.  Capture and emit all output that it
    produces on stdout and stderr in a raw, character by character,
    manner so that we don't have to wait on newlines.  This was done
    to capture, for example, the output of a subprocess that creates
    dots to show incremental progress on a task and render it
    correctly.

    Args:
        command: the command to execute
        timeout_seconds: terminate the subprocess if it takes longer
            than N seconds; None means to wait as long as it takes.

    Returns:
        the exit status of the subprocess once the subprocess has
        exited.  Raises `TimeoutExpired` after killing the subprocess
        if the timeout expires.

    Side effects:
        prints all output of the child process (stdout or stderr)
    """

    def timer_expired(p):
        p.kill()
        raise subprocess.TimeoutExpired(command, timeout_seconds)

    line_enders = set([b"\n", b"\r"])
    sel = selectors.DefaultSelector()
    with subprocess.Popen(
        command,
        shell=True,
        bufsize=0,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    ) as p:
        timer = None
        if timeout_seconds:
            import threading

            timer = threading.Timer(timeout_seconds, timer_expired(p))
            timer.start()
        try:
            sel.register(p.stdout, selectors.EVENT_READ)  # type: ignore
            sel.register(p.stderr, selectors.EVENT_READ)  # type: ignore
            done = False
            while not done:
                for key, _ in sel.select():
                    char = key.fileobj.read(1)  # type: ignore
                    if not char:
                        sel.unregister(key.fileobj)
                        if len(sel.get_map()) == 0:
                            sys.stdout.flush()
                            sys.stderr.flush()
                            sel.close()
                            done = True
                    if key.fileobj is p.stdout:
                        os.write(sys.stdout.fileno(), char)
                        if char in line_enders:
                            sys.stdout.flush()
                    else:
                        os.write(sys.stderr.fileno(), char)
                        if char in line_enders:
                            sys.stderr.flush()
            p.wait()
        finally:
            if timer:
                timer.cancel()
        return p.returncode


def cmd_exitcode(command: str, timeout_seconds: Optional[float] = None) -> int:
    """Run a command silently in the background and return its exit
    code once it has finished.  If timeout_seconds is provided and the
    command runs longer than timeout_seconds, raise a `TimeoutExpired`
    exception.

    Args:
        command: the command to run
        timeout_seconds: optional the max number of seconds to allow
            the subprocess to execute or None to indicate no timeout

    Returns:
        the exit status of the subprocess once the subprocess has
        exited

    >>> cmd_exitcode('/bin/echo foo', 10.0)
    0

    >>> cmd_exitcode('/bin/sleep 2', 0.01)
    Traceback (most recent call last):
    ...
    subprocess.TimeoutExpired: Command '['/bin/bash', '-c', '/bin/sleep 2']' timed out after 0.01 seconds

    """
    return subprocess.check_call(["/bin/bash", "-c", command], timeout=timeout_seconds)


def cmd(command: str, timeout_seconds: Optional[float] = None) -> str:
    """Run a command and capture its output to stdout and stderr into a
    string buffer.  Return that string as this function's output.
    Raises subprocess.CalledProcessError or TimeoutExpired on error.

    Args:
        command: the command to run
        timeout_seconds: the max number of seconds to allow the subprocess
            to execute or None to indicate no timeout

    Returns:
        The captured output of the subprocess' stdout as a string buffer

    >>> cmd('/bin/echo foo')[:-1]
    'foo'

    >>> cmd('/bin/sleep 2', 0.01)
    Traceback (most recent call last):
    ...
    subprocess.TimeoutExpired: Command '/bin/sleep 2' timed out after 0.01 seconds

    """
    ret = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=timeout_seconds,
    ).stdout
    return ret.decode("utf-8")


def run_silently(command: str, timeout_seconds: Optional[float] = None) -> None:
    """Run a command silently but raise
    `subprocess.CalledProcessError` if it fails (i.e. returns a
    non-zero return value) and raise a `TimeoutExpired` if it runs too
    long.

    Args:
        command: the command to run.
        timeout_seconds: the optional max number of seconds to allow
            the subprocess to execute or None (default) to indicate no
            time limit.

    Returns:
        No return value; error conditions (including non-zero child process
        exits) produce exceptions.

    >>> run_silently("/usr/bin/true")

    >>> run_silently("/usr/bin/false")
    Traceback (most recent call last):
    ...
    subprocess.CalledProcessError: Command '/usr/bin/false' returned non-zero exit status 1.

    """
    subprocess.run(
        command,
        shell=True,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        capture_output=False,
        check=True,
        timeout=timeout_seconds,
    )


def cmd_in_background(command: str, *, silent: bool = False) -> subprocess.Popen:
    """Spawns a child process in the background and registers an exit
    handler to make sure we kill it if the parent process (us) is
    terminated.

    Args:
        command: the command to run
        silent: do not allow any output from the child process to be displayed
            in the parent process' window

    Returns:
        the :class:`Popen` object that can be used to communicate
            with the background process.
    """
    args = shlex.split(command)
    if silent:
        subproc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subproc = subprocess.Popen(args, stdin=subprocess.DEVNULL)

    def kill_subproc() -> None:
        try:
            if subproc.poll() is None:
                logger.info("At exit handler: killing %s (%s)", subproc, command)
                subproc.terminate()
                subproc.wait(timeout=10.0)
        except BaseException:
            logger.exception(
                "Failed to terminate background process %s; giving up.", subproc
            )

    atexit.register(kill_subproc)
    return subproc


def cmd_list(command: List[str]) -> str:
    """Run a command with args encapsulated in a list and return the
    output text as a string.  Raises subprocess.CalledProcessError.
    """
    ret = subprocess.run(command, capture_output=True, check=True).stdout
    return ret.decode("utf-8")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
