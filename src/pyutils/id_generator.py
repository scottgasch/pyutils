#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""A helper class for generating thread safe monotonically increasing
id numbers.

"""

import itertools
import logging

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

logger = logging.getLogger(__name__)
generators = {}


def get(name: str, *, start=0) -> int:
    """
    Returns a thread-safe, monotonically increasing id suitable for use
    as a globally unique identifier.

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
    logger.debug("Generated next id %d", x)
    return x


if __name__ == '__main__':
    import doctest

    doctest.testmod()
