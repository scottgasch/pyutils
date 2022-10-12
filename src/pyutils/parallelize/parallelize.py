#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""A decorator to help with dead simple parallelization."""


import atexit
import functools
import typing
from enum import Enum


class Method(Enum):
    """How should we parallelize; by threads, processes or remote workers?"""

    THREAD = 1
    PROCESS = 2
    REMOTE = 3


def parallelize(
    _funct: typing.Optional[typing.Callable] = None, *, method: Method = Method.THREAD
) -> typing.Callable:
    """This is a decorator that was created to make multi-threading,
    multi-processing and remote machine parallelism simple in python.

    Sample usage::

        @parallelize    # defaults to thread-mode
        def my_function(a, b, c) -> int:
            ...do some slow / expensive work, e.g., an http request

        @parallelize(method=Method.PROCESS)
        def my_other_function(d, e, f) -> str:
            ...do more really expensive work, e.g., a network read

        @parallelize(method=Method.REMOTE)
        def my_other_other_function(g, h) -> int:
            ...this work will be distributed to a remote machine pool

    This decorator will invoke the wrapped function on::

        Method.THREAD (default): a background thread
        Method.PROCESS: a background process
        Method.REMOTE: a process on a remote host

    The wrapped function returns immediately with a value that is
    wrapped in a :class:`SmartFuture`.  This value will block if it is
    either read directly (via a call to :meth:`_resolve`) or indirectly
    (by using the result in an expression, printing it, hashing it,
    passing it a function argument, etc...).  See comments on
    :class:`SmartFuture` for details.

    .. warning::
        You may stack @parallelized methods and it will "work".
        That said, having multiple layers of :code:`Method.PROCESS` or
        :code:`Method.REMOTE` will prove to be problematic because each process in
        the stack will use its own independent pool which may overload
        your machine with processes or your network with remote processes
        beyond the control mechanisms built into one instance of the pool.
        Be careful.

    .. note::
        There is non-trivial overhead of pickling code and
        copying it over the network when you use :code:`Method.REMOTE`.  There's
        a smaller but still considerable cost of creating a new process
        and passing code to/from it when you use :code:`Method.PROCESS`.
    """

    def wrapper(funct: typing.Callable):
        @functools.wraps(funct)
        def inner_wrapper(*args, **kwargs):
            from pyutils.parallelize import executors, smart_future

            # Look for as of yet unresolved arguments in _funct's
            # argument list and resolve them now.
            newargs = []
            for arg in args:
                newargs.append(smart_future.SmartFuture.resolve(arg))
            newkwargs = {}
            for kw in kwargs:
                newkwargs[kw] = smart_future.SmartFuture.resolve(kwargs[kw])

            executor = None
            if method == Method.PROCESS:
                executor = executors.DefaultExecutors().process_pool()
            elif method == Method.THREAD:
                executor = executors.DefaultExecutors().thread_pool()
            elif method == Method.REMOTE:
                executor = executors.DefaultExecutors().remote_pool()
            assert executor is not None
            atexit.register(executors.DefaultExecutors().shutdown)

            future = executor.submit(funct, *newargs, **newkwargs)

            # Wrap the future that's returned in a SmartFuture object
            # so that callers do not need to call .result(), they can
            # just use is as normal.
            return smart_future.SmartFuture(future)

        return inner_wrapper

    if _funct is None:
        return wrapper
    else:
        return wrapper(_funct)
