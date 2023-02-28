#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Utilities for dealing with threads + threading."""

import functools
import logging
import os
import threading
from typing import Any, Callable, Optional, Tuple

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

logger = logging.getLogger(__name__)


def current_thread_id() -> str:
    """
    Returns:
        A string composed of the parent process' id, the
        current process' id and the current thread name that can be used
        as a unique identifier for the current thread.  The former two are
        numbers (pids) whereas the latter is a thread id passed during
        thread creation time.

    >>> from pyutils.parallelize import thread_utils
    >>> ret = thread_utils.current_thread_id()
    >>> ret  # doctest: +SKIP
    '76891/84444/MainThread:'
    >>> (ppid, pid, tid) = ret.split('/')
    >>> ppid.isnumeric()
    True
    >>> pid.isnumeric()
    True
    """
    ppid = os.getppid()
    pid = os.getpid()
    tid = threading.current_thread().name
    return f"{ppid}/{pid}/{tid}:"


def is_current_thread_main_thread() -> bool:
    """
    Returns:
        True is the current (calling) thread is the process' main
        thread and False otherwise.

    >>> from pyutils.parallelize import thread_utils
    >>> thread_utils.is_current_thread_main_thread()
    True

    >>> result = None
    >>> def am_i_the_main_thread():
    ...     global result
    ...     result = thread_utils.is_current_thread_main_thread()

    >>> am_i_the_main_thread()
    >>> result
    True

    >>> import threading
    >>> thread = threading.Thread(target=am_i_the_main_thread)
    >>> thread.start()
    >>> thread.join()
    >>> result
    False
    """
    return threading.current_thread() is threading.main_thread()


def background_thread(
    _funct: Optional[Callable[..., Any]],
) -> Callable[..., Tuple[threading.Thread, threading.Event]]:
    """A function decorator to create a background thread.

    Args:
        _funct: The function being wrapped such that it is invoked
            on a background thread.

    Example usage::

        import threading
        import time

        from pyutils.parallelize import thread_utils

        @thread_utils.background_thread
        def random(a: int, b: str, stop_event: threading.Event) -> None:
            while True:
                print(f"Hi there {b}: {a}!")
                time.sleep(10.0)
                if stop_event.is_set():
                    return

        def main() -> None:
            (thread, event) = random(22, "dude")
            print("back!")
            time.sleep(30.0)
            event.set()
            thread.join()

    .. warning::

        In addition to any other arguments the function has, it must
        take a stop_event as the last unnamed argument which it should
        periodically check.  If the event is set, it means the thread has
        been requested to terminate ASAP.
    """

    def wrapper(funct: Callable):
        @functools.wraps(funct)
        def inner_wrapper(*a, **kwa) -> Tuple[threading.Thread, threading.Event]:
            should_terminate = threading.Event()
            should_terminate.clear()
            newargs = (*a, should_terminate)
            thread = threading.Thread(
                target=funct,
                args=newargs,
                kwargs=kwa,
            )
            thread.start()
            logger.debug('Started thread "%s" tid=%d', thread.name, thread.ident)
            return (thread, should_terminate)

        return inner_wrapper

    if _funct is None:
        return wrapper  # type: ignore
    else:
        return wrapper(_funct)


class ThreadWithReturnValue(threading.Thread):
    """A thread whose return value is plumbed back out as the return
    value of :meth:`join`.  Use like a normal thread::

        import threading

        from pyutils.parallelize import thread_utils

        def thread_entry_point(args):
            # do something interesting...
            return result

        if __name__ == "__main__":
            thread = thread_utils.ThreadWithReturnValue(
                target=thread_entry_point,
                args=(whatever)
            )
            thread.start()
            result = thread.join()
            print(f"thread finished and returned {result}")

    """

    def __init__(
        self, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None
    ):
        threading.Thread.__init__(
            self,
            group=None,
            target=target,
            name=None,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
        )
        self._target = target
        self._return = None
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        """Create a little wrapper around invoking the real thread entry
        point so we can pay attention to its return value."""
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self, *args) -> Any:
        """Wait until the thread terminates and return the value it terminated with
        as the result of join.

        Like normal :meth:`join`, this blocks the calling thread until
        the thread whose :meth:`join` is called terminates – either
        normally or through an unhandled exception or until the
        optional timeout occurs.

        When the timeout argument is present and not None, it should
        be a floating point number specifying a timeout for the
        operation in seconds (or fractions thereof).

        When the timeout argument is not present or None, the
        operation will block until the thread terminates.

        A thread can be joined many times.

        :meth:`join` raises a RuntimeError if an attempt is made to join the
        current thread as that would cause a deadlock. It is also an
        error to join a thread before it has been started and
        attempts to do so raises the same exception.
        """
        threading.Thread.join(self, *args)
        return self._return


def periodically_invoke(
    period_sec: float,
    stop_after: Optional[int],
):
    """
    Periodically invoke the decorated function on a background thread.

    Args:
        period_sec: the delay period in seconds between invocations
        stop_after: total number of invocations to make or, if None,
            call forever

    Returns:
        a :class:`Thread` object and an :class:`Event` that, when
        signaled, will stop the invocations.

    .. note::
        It is possible to be invoked one time after the :class:`Event`
        is set.  This event can be used to stop infinite
        invocation style or finite invocation style decorations.

    Usage::

        from pyutils.parallelize import thread_utils

        @thread_utils.periodically_invoke(period_sec=1.0, stop_after=3)
        def hello(name: str) -> None:
            print(f"Hello, {name}")

        @thread_utils.periodically_invoke(period_sec=0.5, stop_after=None)
        def there(name: str, age: int) -> None:
            print(f"   ...there {name}, {age}")

    Usage as a decorator doesn't give you access to the returned stop event or
    thread object.  To get those, wrap your periodic function manually::

        from pyutils.parallelize import thread_utils

        def periodic(m: str) -> None:
            print(m)

        f = thread_utils.periodically_invoke(period_sec=5.0, stop_after=None)(periodic)
        thread, event = f("testing")
        ...
        event.set()
        thread.join()

    See also :mod:`pyutils.state_tracker`.
    """

    def decorator_repeat(func):
        def helper_thread(should_terminate, *args, **kwargs) -> None:
            if stop_after is None:
                while True:
                    func(*args, **kwargs)
                    res = should_terminate.wait(period_sec)
                    if res:
                        return
            else:
                for _ in range(stop_after):
                    func(*args, **kwargs)
                    res = should_terminate.wait(period_sec)
                    if res:
                        return
                return

        @functools.wraps(func)
        def wrapper_repeat(*args, **kwargs):
            should_terminate = threading.Event()
            should_terminate.clear()
            newargs = (should_terminate, *args)
            thread = threading.Thread(target=helper_thread, args=newargs, kwargs=kwargs)
            thread.start()
            logger.debug('Started thread "%s" tid=%d', thread.name, thread.ident)
            return (thread, should_terminate)

        return wrapper_repeat

    return decorator_repeat


if __name__ == "__main__":
    import doctest

    doctest.testmod()
