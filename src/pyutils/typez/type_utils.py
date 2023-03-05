#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Utility functions for dealing with typing."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def unwrap_optional(x: Optional[Any]) -> Any:
    """Unwrap an Optional[Type] argument returning a Type value back.
    Use this to satisfy most type checkers that a value that could be
    None isn't so as to drop the Optional typing hint.

    Args:
        x: an Optional[Type] argument

    Returns:
        If the Optional[Type] argument is non-None, return it.
        If the Optional[Type] argument is None, however, raise an
        exception.

    >>> x: Optional[bool] = True
    >>> unwrap_optional(x)
    True

    >>> y: Optional[str] = None
    >>> unwrap_optional(y)
    Traceback (most recent call last):
    ...
    AssertionError: Argument to unwrap_optional was unexpectedly None
    """
    if x is None:
        msg = 'Argument to unwrap_optional was unexpectedly None'
        logger.critical(msg)
        raise AssertionError(msg)
    return x


if __name__ == '__main__':
    import doctest

    doctest.testmod()
