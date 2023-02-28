#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
A helper class for generating thread safe monotonically increasing
id numbers.

.. note::

    This code is thread safe but not process safe; for use only
    within one python process.
"""

import itertools
import logging

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

logger = logging.getLogger(__name__)
generators = {}


def get(name: str, *, start: int = 0) -> int:
    """
    Returns a thread-safe, monotonically increasing id suitable for use
    as a globally unique identifier.

    Args:
        name: the sequence identifier name.
        start: the starting id (i.e. the first id that should be returned)

    Returns:
        An integer id such that within one sequence identifier name the
        id returned is unique and is the maximum id ever returned.

    >>> import id_generator
    >>> id_generator.get('student_id')
    0
    >>> id_generator.get('student_id')
    1
    >>> id_generator.get('employee_id', start=10000)
    10000
    >>> id_generator.get('employee_id', start=10000)
    10001
    """
    if name not in generators:
        generators[name] = itertools.count(start, 1)
    x = next(generators[name])
    logger.debug("Generated next id %d in sequence %s", x, name)
    return x


if __name__ == "__main__":
    import doctest

    doctest.testmod()
