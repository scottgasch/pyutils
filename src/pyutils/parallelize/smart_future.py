#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
A :class:`Future` that can be treated as a substutute for the result
that it contains and will not block until it is used.  At that point,
if the underlying value is not yet available yet, it will block until
the internal result actually becomes available.

Results from :class:`parallelize.parallelize` are returned wrapped
in :class:`SmartFuture` instances.

Also contains some utilility code for waiting for one/many futures.
"""

from __future__ import annotations

import concurrent
import concurrent.futures as fut
import logging
from typing import Callable, List, Set, TypeVar

from overrides import overrides

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.
from pyutils import id_generator
from pyutils.parallelize.deferred_operand import DeferredOperand

logger = logging.getLogger(__name__)

T = TypeVar("T")


def wait_any(
    futures: List[SmartFuture],
    *,
    callback: Callable = None,
    log_exceptions: bool = True,
    timeout: float = None,
):
    """Await the completion of any of a collection of SmartFutures and
    invoke callback each time one completes, repeatedly, until they are
    all finished.

    Args:
        futures: A collection of SmartFutures to wait on
        callback: An optional callback to invoke whenever one of the
            futures completes
        log_exceptions: Should we log (warning + exception) any
            underlying exceptions raised during future processing or
            silently ignore them?
        timeout: invoke callback with a periodicity of timeout while
            awaiting futures

    Returns:
        A :class:`SmartFuture` from the futures list with a result
        available without blocking.
    """

    real_futures = []
    smart_future_by_real_future = {}
    completed_futures: Set[fut.Future] = set()
    for x in futures:
        assert isinstance(x, SmartFuture)
        real_futures.append(x.wrapped_future)
        smart_future_by_real_future[x.wrapped_future] = x

    while len(completed_futures) != len(real_futures):
        try:
            newly_completed_futures = concurrent.futures.as_completed(
                real_futures, timeout=timeout
            )
            for f in newly_completed_futures:
                if callback is not None:
                    callback()
                completed_futures.add(f)
                if log_exceptions and not f.cancelled():
                    exception = f.exception()
                    if exception is not None:
                        logger.exception(
                            "Future 0x%x raised an unhandled exception and exited.",
                            id(f),
                            exc_info=exception,
                        )
                        raise exception
                yield smart_future_by_real_future[f]
        except concurrent.futures.TimeoutError:
            if callback is not None:
                callback()
    if callback is not None:
        callback()


def wait_all(
    futures: List[SmartFuture],
    *,
    log_exceptions: bool = True,
) -> None:
    """Wait for all of the SmartFutures in the collection to finish before
    returning.

    Args:
        futures: A collection of futures that we're waiting for
        log_exceptions: Should we log (warning + exception) any
            underlying exceptions raised during future processing or
            silently ignore them?

    Returns:
        Only when all futures in the input list are ready.  Blocks
        until such time.
    """

    real_futures = []
    for x in futures:
        assert isinstance(x, SmartFuture)
        real_futures.append(x.wrapped_future)

    (done, not_done) = concurrent.futures.wait(
        real_futures, timeout=None, return_when=concurrent.futures.ALL_COMPLETED
    )
    if log_exceptions:
        for f in real_futures:
            if not f.cancelled():
                exception = f.exception()
                if exception is not None:
                    logger.exception(
                        "Future 0x%x raised an unhandled exception and exited.",
                        id(f),
                        exc_info=exception,
                    )
                    raise exception
    assert len(done) == len(real_futures)
    assert len(not_done) == 0


class SmartFuture(DeferredOperand):
    """This is a SmartFuture, a class that wraps a normal :class:`Future`
    and can then be used, mostly, like a normal (non-Future)
    identifier of the type of that SmartFuture's result.

    Using a FutureWrapper in expressions will block and wait until
    the result of the deferred operation is known.
    """

    def __init__(self, wrapped_future: fut.Future) -> None:
        """
        Args:
            wrapped_future: a normal Python :class:`concurrent.Future`
                object that we are wrapping.
        """
        super().__init__(set(["id", "wrapped_future", "get_id", "is_ready"]))
        assert isinstance(wrapped_future, fut.Future)
        self.wrapped_future = wrapped_future
        self.id = id_generator.get("smart_future_id")

        # Note: if you are adding any settable properties to this
        # class, go add them to the set in DeferredOperand.__setattr__()

    def get_id(self) -> int:
        """
        Returns:
            A unique identifier for this instance.
        """
        return self.id

    def is_ready(self) -> bool:
        """
        Returns:
            True if the wrapped future is ready without blocking, False
            otherwise.
        """
        return self.wrapped_future.done()

    # You shouldn't have to call this; instead, have a look at defining a
    # method on DeferredOperand base class.
    @overrides
    def _resolve(self, timeout=None) -> T:
        return self.wrapped_future.result(timeout)
