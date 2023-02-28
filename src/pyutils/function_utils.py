#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Helper methods dealing with functions."""

from typing import Callable


def function_identifier(f: Callable) -> str:
    """
    Given a named `Callable`, return a string that identifies it.
    Usually that string is just "__module__:__name__" but there's a
    corner case: when __module__ is __main__ (i.e. the callable is
    defined in the same module as __main__).  In this case,
    f.__module__ returns "__main__" instead of the file that it is
    defined in.  Work around this using `pathlib.Path`.

    Args:
        f: a Callable

    Returns:
        A unique identifier for that callable in the format
        module:function that avoids the pseudo-module '__main__'

    >>> function_identifier(function_identifier)
    'function_utils:function_identifier'

    """

    if f.__module__ == '__main__':
        from pathlib import Path

        import __main__

        module = __main__.__file__
        module = Path(module).stem
        return f'{module}:{f.__name__}'
    else:
        return f'{f.__module__}:{f.__name__}'


if __name__ == '__main__':
    import doctest

    doctest.testmod()
