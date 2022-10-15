#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Miscellaneous utilities."""

import os
import sys


def is_running_as_root() -> bool:
    """
    Returns:
        True if running as root, False otherwise.

    >>> is_running_as_root()
    False
    """
    return os.geteuid() == 0


def debugger_is_attached() -> bool:
    """
    Returns:
        True if a debugger is attached, False otherwise.
    """
    gettrace = getattr(sys, 'gettrace', lambda: None)
    return gettrace() is not None


if __name__ == '__main__':
    import doctest

    doctest.testmod()
