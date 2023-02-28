#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Miscellaneous utilities."""

import os
import random
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
    gettrace = getattr(sys, "gettrace", lambda: None)
    return gettrace() is not None


def execute_probabilistically(probability_to_execute: float) -> bool:
    """
    Args:
        probability_to_execute: the probability of returning True.

    Returns:
        True with a given probability.

    >>> random.seed(22)
    >>> execute_probabilistically(50.0)
    False
    >>> execute_probabilistically(50.0)
    True

    """
    return random.uniform(0.0, 100.0) < probability_to_execute


if __name__ == "__main__":
    import doctest

    doctest.testmod()
