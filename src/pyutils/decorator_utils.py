#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch
# Portions (marked) below retain the original author's copyright.

"""Useful(?) decorators."""

import enum
import functools
import inspect
import logging
import math
import multiprocessing
import random
import signal
import sys
import threading
import time
import traceback
import warnings
from typing import Any, Callable, List, Optional

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

logger = logging.getLogger(__name__)


def timed(func: Callable) -> Callable:
    """Print the runtime of the decorated function.

    >>> @timed
    ... def foo():
    ...     import time
    ...     time.sleep(0.01)

    >>> foo()  # doctest: +ELLIPSIS
    Finished foo in ...

    """

    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        msg = f"Finished {func.__qualname__} in {run_time:.4f}s"
        print(msg)
        logger.info(msg)
        return value

    return wrapper_timer


def invocation_logged(func: Callable) -> Callable:
    """Log the call of a function on stdout and the info log.

    >>> @invocation_logged
    ... def foo():
    ...     print('Hello, world.')

    >>> foo()
    Entered foo
    Hello, world.
    Exited foo

    """

    @functools.wraps(func)
    def wrapper_invocation_logged(*args, **kwargs):
        msg = f"Entered {func.__qualname__}"
        print(msg)
        logger.info(msg)
        ret = func(*args, **kwargs)
        msg = f"Exited {func.__qualname__}"
        print(msg)
        logger.info(msg)
        return ret

    return wrapper_invocation_logged


def rate_limited(n_calls: int, *, per_period_in_seconds: float = 1.0) -> Callable:
    """Limit invocation of a wrapped function to n calls per time period.
    Thread safe.  In testing this was relatively fair with multiple
    threads using it though that hasn't been measured in detail.

    >>> import time
    >>> from pyutils import decorator_utils
    >>> from pyutils.parallelize import thread_utils

    >>> calls = 0

    >>> @decorator_utils.rate_limited(10, per_period_in_seconds=1.0)
    ... def limited(x: int):
    ...     global calls
    ...     calls += 1

    >>> @thread_utils.background_thread
    ... def a(stop):
    ...     for _ in range(3):
    ...         limited(_)

    >>> @thread_utils.background_thread
    ... def b(stop):
    ...     for _ in range(3):
    ...         limited(_)

    >>> start = time.time()
    >>> (t1, e1) = a()
    >>> (t2, e2) = b()
    >>> t1.join()
    >>> t2.join()
    >>> end = time.time()
    >>> dur = end - start
    >>> dur > 0.5
    True

    >>> calls
    6

    """
    min_interval_seconds = per_period_in_seconds / float(n_calls)

    def wrapper_rate_limited(func: Callable) -> Callable:
        cv = threading.Condition()
        last_invocation_timestamp = [0.0]

        def may_proceed() -> float:
            now = time.time()
            last_invocation = last_invocation_timestamp[0]
            if last_invocation != 0.0:
                elapsed_since_last = now - last_invocation
                wait_time = min_interval_seconds - elapsed_since_last
            else:
                wait_time = 0.0
            logger.debug('@%.4f> wait_time = %.4f', time.time(), wait_time)
            return wait_time

        def wrapper_wrapper_rate_limited(*args, **kargs) -> Any:
            with cv:
                while True:
                    if cv.wait_for(
                        lambda: may_proceed() <= 0.0,
                        timeout=may_proceed(),
                    ):
                        break
            with cv:
                logger.debug('@%.4f> calling it...', time.time())
                ret = func(*args, **kargs)
                last_invocation_timestamp[0] = time.time()
                logger.debug(
                    '@%.4f> Last invocation <- %.4f',
                    time.time(),
                    last_invocation_timestamp[0],
                )
                cv.notify()
            return ret

        return wrapper_wrapper_rate_limited

    return wrapper_rate_limited


def debug_args(func: Callable) -> Callable:
    """Print the function signature and return value at each call.

    >>> @debug_args
    ... def foo(a, b, c):
    ...     print(a)
    ...     print(b)
    ...     print(c)
    ...     return (a + b, c)

    >>> foo(1, 2.0, "test")
    Calling foo(1:<class 'int'>, 2.0:<class 'float'>, 'test':<class 'str'>)
    1
    2.0
    test
    foo returned (3.0, 'test'):<class 'tuple'>
    (3.0, 'test')
    """

    @functools.wraps(func)
    def wrapper_debug_args(*args, **kwargs):
        args_repr = [f"{repr(a)}:{type(a)}" for a in args]
        kwargs_repr = [f"{k}={v!r}:{type(v)}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        msg = f"Calling {func.__qualname__}({signature})"
        print(msg)
        logger.info(msg)
        value = func(*args, **kwargs)
        msg = f"{func.__qualname__} returned {value!r}:{type(value)}"
        print(msg)
        logger.info(msg)
        return value

    return wrapper_debug_args


def debug_count_calls(func: Callable) -> Callable:
    """Count function invocations and print a message befor every call.

    >>> @debug_count_calls
    ... def factoral(x):
    ...     if x == 1:
    ...         return 1
    ...     return x * factoral(x - 1)

    >>> factoral(5)
    Call #1 of 'factoral'
    Call #2 of 'factoral'
    Call #3 of 'factoral'
    Call #4 of 'factoral'
    Call #5 of 'factoral'
    120

    """

    @functools.wraps(func)
    def wrapper_debug_count_calls(*args, **kwargs):
        wrapper_debug_count_calls.num_calls += 1
        msg = f"Call #{wrapper_debug_count_calls.num_calls} of {func.__name__!r}"
        print(msg)
        logger.info(msg)
        return func(*args, **kwargs)

    wrapper_debug_count_calls.num_calls = 0  # type: ignore
    return wrapper_debug_count_calls


class DelayWhen(enum.IntEnum):
    """When should we delay: before or after calling the function (or
    both)?

    """

    BEFORE_CALL = 1
    AFTER_CALL = 2
    BEFORE_AND_AFTER = 3


def delay(
    _func: Callable = None,
    *,
    seconds: float = 1.0,
    when: DelayWhen = DelayWhen.BEFORE_CALL,
) -> Callable:
    """Slow down a function by inserting a delay before and/or after its
    invocation.

    >>> import time

    >>> @delay(seconds=1.0)
    ... def foo():
    ...     pass

    >>> start = time.time()
    >>> foo()
    >>> dur = time.time() - start
    >>> dur >= 1.0
    True

    """

    def decorator_delay(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper_delay(*args, **kwargs):
            if when & DelayWhen.BEFORE_CALL:
                logger.debug("@delay for %fs BEFORE_CALL to %s", seconds, func.__name__)
                time.sleep(seconds)
            retval = func(*args, **kwargs)
            if when & DelayWhen.AFTER_CALL:
                logger.debug("@delay for %fs AFTER_CALL to %s", seconds, func.__name__)
                time.sleep(seconds)
            return retval

        return wrapper_delay

    if _func is None:
        return decorator_delay
    else:
        return decorator_delay(_func)


class _SingletonWrapper:
    """
    A singleton wrapper class. Its instances would be created
    for each decorated class.

    """

    def __init__(self, cls):
        self.__wrapped__ = cls
        self._instance = None

    def __call__(self, *args, **kwargs):
        """Returns a single instance of decorated class"""
        logger.debug(
            '@singleton returning global instance of %s', self.__wrapped__.__name__
        )
        if self._instance is None:
            self._instance = self.__wrapped__(*args, **kwargs)
        return self._instance


def singleton(cls):
    """
    A singleton decorator. Returns a wrapper objects. A call on that object
    returns a single instance object of decorated class. Use the __wrapped__
    attribute to access decorated class directly in unit tests

    >>> @singleton
    ... class foo(object):
    ...     pass

    >>> a = foo()
    >>> b = foo()
    >>> a is b
    True

    >>> id(a) == id(b)
    True

    """
    return _SingletonWrapper(cls)


def memoized(func: Callable) -> Callable:
    """Keep a cache of previous function call results.

    The cache here is a dict with a key based on the arguments to the
    call.  Consider also: functools.cache for a more advanced
    implementation.  See:
    https://docs.python.org/3/library/functools.html#functools.cache

    >>> import time

    >>> @memoized
    ... def expensive(arg) -> int:
    ...     # Simulate something slow to compute or lookup
    ...     time.sleep(1.0)
    ...     return arg * arg

    >>> start = time.time()
    >>> expensive(5)           # Takes about 1 sec
    25

    >>> expensive(3)           # Also takes about 1 sec
    9

    >>> expensive(5)           # Pulls from cache, fast
    25

    >>> expensive(3)           # Pulls from cache again, fast
    9

    >>> dur = time.time() - start
    >>> dur < 3.0
    True

    """

    @functools.wraps(func)
    def wrapper_memoized(*args, **kwargs):
        cache_key = args + tuple(kwargs.items())
        if cache_key not in wrapper_memoized.cache:
            value = func(*args, **kwargs)
            logger.debug('Memoizing %s => %s for %s', cache_key, value, func.__name__)
            wrapper_memoized.cache[cache_key] = value
        else:
            logger.debug('Returning memoized value for %s', {func.__name__})
        return wrapper_memoized.cache[cache_key]

    wrapper_memoized.cache = {}  # type: ignore
    return wrapper_memoized


def retry_predicate(
    tries: int,
    *,
    predicate: Callable[..., bool],
    delay_sec: float = 3.0,
    backoff: float = 2.0,
):
    """Retries a function or method up to a certain number of times with a
    prescribed initial delay period and backoff rate (multiplier).

    Args:
        tries: the maximum number of attempts to run the function
        delay_sec: sets the initial delay period in seconds
        backoff: a multiplier (must be >=1.0) used to modify the
            delay at each subsequent invocation
        predicate: a Callable that will be passed the retval of
            the decorated function and must return True to indicate
            that we should stop calling or False to indicate a retry
            is necessary
    """

    if backoff < 1.0:
        msg = f"backoff must be greater than or equal to 1, got {backoff}"
        logger.critical(msg)
        raise ValueError(msg)

    tries = math.floor(tries)
    if tries < 0:
        msg = f"tries must be 0 or greater, got {tries}"
        logger.critical(msg)
        raise ValueError(msg)

    if delay_sec <= 0:
        msg = f"delay_sec must be greater than 0, got {delay_sec}"
        logger.critical(msg)
        raise ValueError(msg)

    def deco_retry(f):
        @functools.wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay_sec  # make mutable
            logger.debug('deco_retry: will make up to %d attempts...', mtries)
            retval = f(*args, **kwargs)
            while mtries > 0:
                if predicate(retval) is True:
                    logger.debug('Predicate succeeded, deco_retry is done.')
                    return retval
                logger.debug("Predicate failed, sleeping and retrying.")
                mtries -= 1
                time.sleep(mdelay)
                mdelay *= backoff
                retval = f(*args, **kwargs)
            return retval

        return f_retry

    return deco_retry


def retry_if_false(tries: int, *, delay_sec=3.0, backoff=2.0):
    """A helper for @retry_predicate that retries a decorated
    function as long as it keeps returning False.

    >>> import time

    >>> counter = 0
    >>> @retry_if_false(5, delay_sec=1.0, backoff=1.1)
    ... def foo():
    ...     global counter
    ...     counter += 1
    ...     return counter >= 3

    >>> start = time.time()
    >>> foo()  # fail, delay 1.0, fail, delay 1.1, succeed
    True

    >>> dur = time.time() - start
    >>> counter
    3
    >>> dur > 2.0
    True
    >>> dur < 2.3
    True

    """
    return retry_predicate(
        tries,
        predicate=lambda x: x is True,
        delay_sec=delay_sec,
        backoff=backoff,
    )


def retry_if_none(tries: int, *, delay_sec=3.0, backoff=2.0):
    """Another helper for @retry_predicate above.  Retries up to N
    times so long as the wrapped function returns None with a delay
    between each retry and a backoff that can increase the delay.
    """

    return retry_predicate(
        tries,
        predicate=lambda x: x is not None,
        delay_sec=delay_sec,
        backoff=backoff,
    )


def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.

    >>> @deprecated
    ... def foo() -> None:
    ...     pass
    >>> foo()   # prints + logs "Call to deprecated function foo"
    """

    @functools.wraps(func)
    def wrapper_deprecated(*args, **kwargs):
        msg = f"Call to deprecated function {func.__qualname__}"
        logger.warning(msg)
        warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
        print(msg, file=sys.stderr)
        return func(*args, **kwargs)

    return wrapper_deprecated


def thunkify(func):
    """
    Make a function immediately return a function of no args which,
    when called, waits for the result, which will start being
    processed in another thread.
    """

    @functools.wraps(func)
    def lazy_thunked(*args, **kwargs):
        wait_event = threading.Event()

        result = [None]
        exc: List[Any] = [False, None]

        def worker_func():
            try:
                func_result = func(*args, **kwargs)
                result[0] = func_result
            except Exception:
                exc[0] = True
                exc[1] = sys.exc_info()  # (type, value, traceback)
                msg = f"Thunkify has thrown an exception (will be raised on thunk()):\n{traceback.format_exc()}"
                logger.warning(msg)
            finally:
                wait_event.set()

        def thunk():
            wait_event.wait()
            if exc[0]:
                assert exc[1]
                raise exc[1][0](exc[1][1])
            return result[0]

        threading.Thread(target=worker_func).start()
        return thunk

    return lazy_thunked


############################################################
# Timeout
############################################################

# http://www.saltycrane.com/blog/2010/04/using-python-timeout-decorator-uploading-s3/
# Used work of Stephen "Zero" Chappell <Noctis.Skytower@gmail.com>
# in https://code.google.com/p/verse-quiz/source/browse/trunk/timeout.py

# Original work is covered by PSF-2.0:

# 1. This LICENSE AGREEMENT is between the Python Software Foundation
# ("PSF"), and the Individual or Organization ("Licensee") accessing
# and otherwise using this software ("Python") in source or binary
# form and its associated documentation.
#
# 2. Subject to the terms and conditions of this License Agreement,
# PSF hereby grants Licensee a nonexclusive, royalty-free, world-wide
# license to reproduce, analyze, test, perform and/or display
# publicly, prepare derivative works, distribute, and otherwise use
# Python alone or in any derivative version, provided, however, that
# PSF's License Agreement and PSF's notice of copyright, i.e.,
# "Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006 Python Software
# Foundation; All Rights Reserved" are retained in Python alone or in
# any derivative version prepared by Licensee.

# 3. In the event Licensee prepares a derivative work that is based on
# or incorporates Python or any part thereof, and wants to make the
# derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary
# of the changes made to Python.

# (N.B. See NOTICE file in the root of this module for a list of
# changes)

# 4. PSF is making Python available to Licensee on an "AS IS"
# basis. PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED. BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR
# FITNESS FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL
# NOT INFRINGE ANY THIRD PARTY RIGHTS.

# 5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
# FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS A
# RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON, OR ANY
# DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

# 6. This License Agreement will automatically terminate upon a
# material breach of its terms and conditions.

# 7. Nothing in this License Agreement shall be deemed to create any
# relationship of agency, partnership, or joint venture between PSF
# and Licensee. This License Agreement does not grant permission to
# use PSF trademarks or trade name in a trademark sense to endorse or
# promote products or services of Licensee, or any third party.

# 8. By copying, installing or otherwise using Python, Licensee agrees
# to be bound by the terms and conditions of this License Agreement.


def _raise_exception(exception, error_message: Optional[str]):
    if error_message is None:
        raise Exception(exception)
    else:
        raise Exception(error_message)


def _target(queue, function, *args, **kwargs):
    """Run a function with arguments and return output via a queue.

    This is a helper function for the Process created in _Timeout. It runs
    the function with positional arguments and keyword arguments and then
    returns the function's output by way of a queue. If an exception gets
    raised, it is returned to _Timeout to be raised by the value property.
    """
    try:
        queue.put((True, function(*args, **kwargs)))
    except Exception:
        queue.put((False, sys.exc_info()[1]))


class _Timeout(object):
    """Wrap a function and add a timeout to it.

    Instances of this class are automatically generated by the add_timeout
    function defined below.  Do not use directly.
    """

    def __init__(
        self,
        function: Callable,
        timeout_exception: Exception,
        error_message: str,
        seconds: float,
    ):
        self.__limit = seconds
        self.__function = function
        self.__timeout_exception = timeout_exception
        self.__error_message = error_message
        self.__name__ = function.__name__
        self.__doc__ = function.__doc__
        self.__timeout = time.time()
        self.__process = multiprocessing.Process()
        self.__queue: multiprocessing.queues.Queue = multiprocessing.Queue()

    def __call__(self, *args, **kwargs):
        """Execute the embedded function object asynchronously.

        The function given to the constructor is transparently called and
        requires that "ready" be intermittently polled. If and when it is
        True, the "value" property may then be checked for returned data.
        """
        self.__limit = kwargs.pop("timeout", self.__limit)
        self.__queue = multiprocessing.Queue(1)
        args = (self.__queue, self.__function) + args
        self.__process = multiprocessing.Process(
            target=_target, args=args, kwargs=kwargs
        )
        self.__process.daemon = True
        self.__process.start()
        if self.__limit is not None:
            self.__timeout = self.__limit + time.time()
        while not self.ready:
            time.sleep(0.1)
        return self.value

    def cancel(self):
        """Terminate any possible execution of the embedded function."""
        if self.__process.is_alive():
            self.__process.terminate()
        _raise_exception(self.__timeout_exception, self.__error_message)

    @property
    def ready(self):
        """Read-only property indicating status of "value" property."""
        if self.__limit and self.__timeout < time.time():
            self.cancel()
        return self.__queue.full() and not self.__queue.empty()

    @property
    def value(self):
        """Read-only property containing data returned from function."""
        if self.ready is True:
            flag, load = self.__queue.get()
            if flag:
                return load
            raise load
        return None


def timeout(
    seconds: float = 1.0,
    use_signals: Optional[bool] = None,
    timeout_exception=TimeoutError,
    error_message="Function call timed out",
):
    """Add a timeout parameter to a function and return the function.

    Note: the use_signals parameter is included in order to support
    multiprocessing scenarios (signal can only be used from the process'
    main thread).  When not using signals, timeout granularity will be
    rounded to the nearest 0.1s.

    Beware that an @timeout on a function inside a module will be
    evaluated at module load time and not when the wrapped function is
    invoked.  This can lead to problems when relying on the automatic
    main thread detection code (use_signals=None, the default) since
    the import probably happens on the main thread and the invocation
    can happen on a different thread (which can't use signals).

    Raises an exception when/if the timeout is reached.

    It is illegal to pass anything other than a function as the first
    parameter.  The function is wrapped and returned to the caller.

    >>> @timeout(0.2)
    ... def foo(delay: float):
    ...     time.sleep(delay)
    ...     return "ok"

    >>> foo(0)
    'ok'

    >>> foo(1.0)
    Traceback (most recent call last):
    ...
    Exception: Function call timed out

    """
    if use_signals is None:
        import pyutils.parallelize.thread_utils as tu

        use_signals = tu.is_current_thread_main_thread()

    def decorate(function):
        if use_signals:

            def handler(unused_signum, unused_frame):
                _raise_exception(timeout_exception, error_message)

            @functools.wraps(function)
            def new_function(*args, **kwargs):
                new_seconds = kwargs.pop("timeout", seconds)
                if new_seconds:
                    old = signal.signal(signal.SIGALRM, handler)
                    signal.setitimer(signal.ITIMER_REAL, new_seconds)

                if not seconds:
                    return function(*args, **kwargs)

                try:
                    return function(*args, **kwargs)
                finally:
                    if new_seconds:
                        signal.setitimer(signal.ITIMER_REAL, 0)
                        signal.signal(signal.SIGALRM, old)

            return new_function
        else:

            @functools.wraps(function)
            def new_function(*args, **kwargs):
                timeout_wrapper = _Timeout(
                    function, timeout_exception, error_message, seconds
                )
                return timeout_wrapper(*args, **kwargs)

            return new_function

    return decorate


def synchronized(lock):
    """Emulates java's synchronized keyword: given a lock, require that
    threads take that lock (or wait) before invoking the wrapped
    function and automatically releases the lock afterwards.
    """

    def wrap(f):
        @functools.wraps(f)
        def _gatekeeper(*args, **kw):
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                lock.release()

        return _gatekeeper

    return wrap


def call_with_sample_rate(sample_rate: float) -> Callable:
    """Calls the wrapped function probabilistically given a rate between
    0.0 and 1.0 inclusive (0% probability and 100% probability).
    """

    if not 0.0 <= sample_rate <= 1.0:
        msg = f"sample_rate must be between [0, 1]. Got {sample_rate}."
        logger.critical(msg)
        raise ValueError(msg)

    def decorator(f):
        @functools.wraps(f)
        def _call_with_sample_rate(*args, **kwargs):
            if random.uniform(0, 1) < sample_rate:
                return f(*args, **kwargs)
            else:
                logger.debug("@call_with_sample_rate skipping a call to %s", f.__name__)
                return None

        return _call_with_sample_rate

    return decorator


def decorate_matching_methods_with(decorator, acl=None):
    """Apply the given decorator to all methods in a class whose names
    begin with prefix.  If prefix is None (default), decorate all
    methods in the class.
    """

    def decorate_the_class(cls):
        for name, m in inspect.getmembers(cls, inspect.isfunction):
            if acl is None:
                setattr(cls, name, decorator(m))
            else:
                if acl(name):
                    setattr(cls, name, decorator(m))
        return cls

    return decorate_the_class


if __name__ == '__main__':
    import doctest

    doctest.testmod()
