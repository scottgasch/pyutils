#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Helper functions for dealing with dictionaries."""

from itertools import islice
from typing import Any, Callable, Dict, Iterator, List, Tuple


def init_or_inc(
    d: Dict[Any, Any],
    key: Any,
    *,
    init_value: Any = 1,
    inc_function: Callable[..., Any] = lambda x: x + 1,
) -> bool:
    """
    Initialize a dict value (if it doesn't exist) or increments it (using the
    inc_function, which is customizable) if it already does exist.  Returns
    True if the key already existed or False otherwise.

    >>> d = {}
    >>> init_or_inc(d, "test")
    False
    >>> init_or_inc(d, "test")
    True
    >>> init_or_inc(d, 'ing')
    False
    >>> d
    {'test': 2, 'ing': 1}

    """
    if key in d.keys():
        d[key] = inc_function(d[key])
        return True
    d[key] = init_value
    return False


def shard(d: Dict[Any, Any], size: int) -> Iterator[Dict[Any, Any]]:
    """
    Shards a dict into N subdicts which, together, contain all keys/values
    from the original unsharded dict.
    """
    items = d.items()
    for x in range(0, len(d), size):
        yield dict(islice(items, x, x + size))


def coalesce_by_creating_list(_, new_value, old_value):
    """Helper for use with :meth:`coalesce` that creates a list on
    collision."""
    from pyutils.list_utils import flatten

    return flatten([new_value, old_value])


def coalesce_by_creating_set(key, new_value, old_value):
    """Helper for use with :meth:`coalesce` that creates a set on
    collision."""
    return set(coalesce_by_creating_list(key, new_value, old_value))


def coalesce_last_write_wins(_, new_value, discarded_old_value):
    """Helper for use with :meth:`coalsce` that klobbers the old
    with the new one on collision."""
    return new_value


def coalesce_first_write_wins(_, discarded_new_value, old_value):
    """Helper for use with :meth:`coalsce` that preserves the old
    value and discards the new one on collision."""
    return old_value


def raise_on_duplicated_keys(key, new_value, old_value):
    """Helper for use with :meth:`coalesce` that raises an exception
    when a collision is detected.
    """
    raise Exception(f'Key {key} is duplicated in more than one input dict.')


def coalesce(
    inputs: Iterator[Dict[Any, Any]],
    *,
    aggregation_function: Callable[[Any, Any, Any], Any] = coalesce_by_creating_list,
) -> Dict[Any, Any]:
    """Merge N dicts into one dict containing the union of all keys /
    values in the input dicts.  When keys collide, apply the
    aggregation_function which, by default, creates a list of values.
    See also several other alternative functions for coalescing values:

        * :meth:`coalesce_by_creating_set`
        * :meth:`coalesce_first_write_wins`
        * :meth:`coalesce_last_write_wins`
        * :meth:`raise_on_duplicated_keys`
        * or provive your own collision resolution code.

    >>> a = {'a': 1, 'b': 2}
    >>> b = {'b': 1, 'c': 2, 'd': 3}
    >>> c = {'c': 1, 'd': 2}
    >>> coalesce([a, b, c])
    {'a': 1, 'b': [1, 2], 'c': [1, 2], 'd': [2, 3]}

    >>> coalesce([a, b, c], aggregation_function=coalesce_last_write_wins)
    {'a': 1, 'b': 1, 'c': 1, 'd': 2}

    >>> coalesce([a, b, c], aggregation_function=raise_on_duplicated_keys)
    Traceback (most recent call last):
    ...
    Exception: Key b is duplicated in more than one input dict.

    """
    out: Dict[Any, Any] = {}
    for d in inputs:
        for key in d:
            if key in out:
                value = aggregation_function(key, d[key], out[key])
            else:
                value = d[key]
            out[key] = value
    return out


def item_with_max_value(d: Dict[Any, Any]) -> Tuple[Any, Any]:
    """Returns the key and value of the item with the max value in a dict.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> item_with_max_value(d)
    ('c', 3)
    >>> item_with_max_value({})
    Traceback (most recent call last):
    ...
    ValueError: max() arg is an empty sequence

    """
    return max(d.items(), key=lambda _: _[1])


def item_with_min_value(d: Dict[Any, Any]) -> Tuple[Any, Any]:
    """Returns the key and value of the item with the min value in a dict.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> item_with_min_value(d)
    ('a', 1)

    """
    return min(d.items(), key=lambda _: _[1])


def key_with_max_value(d: Dict[Any, Any]) -> Any:
    """Returns the key with the max value in the dict.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> key_with_max_value(d)
    'c'

    """
    return item_with_max_value(d)[0]


def key_with_min_value(d: Dict[Any, Any]) -> Any:
    """Returns the key with the min value in the dict.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> key_with_min_value(d)
    'a'

    """
    return item_with_min_value(d)[0]


def max_value(d: Dict[Any, Any]) -> Any:
    """Returns the maximum value in the dict.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> max_value(d)
    3

    """
    return item_with_max_value(d)[1]


def min_value(d: Dict[Any, Any]) -> Any:
    """Returns the minimum value in the dict.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> min_value(d)
    1

    """
    return item_with_min_value(d)[1]


def max_key(d: Dict[Any, Any]) -> Any:
    """Returns the maximum key in dict (ignoring values totally)

    >>> d = {'a': 3, 'b': 2, 'c': 1}
    >>> max_key(d)
    'c'

    """
    return max(d.keys())


def min_key(d: Dict[Any, Any]) -> Any:
    """Returns the minimum key in dict (ignoring values totally)

    >>> d = {'a': 3, 'b': 2, 'c': 1}
    >>> min_key(d)
    'a'

    """
    return min(d.keys())


def parallel_lists_to_dict(keys: List[Any], values: List[Any]) -> Dict[Any, Any]:
    """Given two parallel lists (keys and values), create and return
    a dict.

    >>> k = ['name', 'phone', 'address', 'zip']
    >>> v = ['scott', '555-1212', '123 main st.', '12345']
    >>> parallel_lists_to_dict(k, v)
    {'name': 'scott', 'phone': '555-1212', 'address': '123 main st.', 'zip': '12345'}

    """
    if len(keys) != len(values):
        raise Exception("Parallel keys and values lists must have the same length")
    return dict(zip(keys, values))


def dict_to_key_value_lists(d: Dict[Any, Any]) -> Tuple[List[Any], List[Any]]:
    """
    >>> d = {'name': 'scott', 'phone': '555-1212', 'address': '123 main st.', 'zip': '12345'}
    >>> (k, v) = dict_to_key_value_lists(d)
    >>> k
    ['name', 'phone', 'address', 'zip']
    >>> v
    ['scott', '555-1212', '123 main st.', '12345']

    """
    r: Tuple[List[Any], List[Any]] = ([], [])
    for (k, v) in d.items():
        r[0].append(k)
        r[1].append(v)
    return r


if __name__ == '__main__':
    import doctest

    doctest.testmod()
