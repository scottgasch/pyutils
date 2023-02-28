#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This module contains helper functions for dealing with Python dictionaries."""

from itertools import islice
from typing import Any, Callable, Dict, Iterator, List, Tuple

from pyutils import dataclass_utils


def init_or_inc(
    d: Dict[Any, Any],
    key: Any,
    *,
    init_value: Any = 1,
    inc_function: Callable[..., Any] = lambda x: x + 1,
) -> bool:
    """
    Initialize a dict value (if it doesn't exist) or increments it (using the
    inc_function, which is customizable) if it already does exist.

    Args:
        d: the dict to increment or initialize a value in
        key: the key to increment or initialize
        init_value: default initial value
        inc_function: Callable use to increment a value

    Returns:
        True if the key already existed or False otherwise

    See also: :py:class:`collections.defaultdict` and
    :py:class:`collections.Counter`.

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
    Shards (i.e. splits) a dict into N subdicts which, together,
    contain all keys/values from the original unsharded dict.

    Args:
        d: the input dict to be sharded (split)
        size: the ideal shard size (number of elements per shard)

    Returns:
        A generator that yields subsequent shards.

    .. note::

        If `len(d)` is not an even multiple of `size` then the last
        shard will not have `size` items in it.  It will have
        `len(d) % size` items instead.

    >>> d = {
    ...     'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6,
    ...     'g': 7, 'h': 8, 'i': 9, 'j': 10, 'k': 11, 'l': 12,
    ... }
    >>> for r in shard(d, 5):
    ...     r
    {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
    {'f': 6, 'g': 7, 'h': 8, 'i': 9, 'j': 10}
    {'k': 11, 'l': 12}
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
    """Coalesce (i.e. combine) N input dicts into one output dict
    ontaining the union of all keys / values in every input dict.
    When keys collide, apply the aggregation_function which, by
    default, creates a list of values with the same key in the output
    dict.

    Args:
        inputs: an iterable set of dicts to coalesce
        aggregation_function: a Callable to deal with key collisions; one of
            the below functions already defined or your own strategy:

            * :meth:`coalesce_by_creating_list` creates a list of values
              with the same key in the output dict.
            * :meth:`coalesce_by_creating_set` creates a set of values with
              the same key in the output dict.
            * :meth:`coalesce_first_write_wins` only preserves the first
              value with a duplicated key.  Others are dropped silently.
            * :meth:`coalesce_last_write_wins` only preserves the last
              value with a duplicated key.  Others are dropped silently.
            * :meth:`raise_on_duplicated_keys` raises an Exception on
              duplicated keys; use when keys should never collide.
            * Your own strategy; Callables will be passed the key and
              two values and can return whatever they want which will
              be stored in the output dict.

    Returns:
        The coalesced output dict.

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
    """
    Args:
        d: a dict with comparable values

    Returns:
        The key and value of the item with the highest value in a
        dict as a `Tuple[key, value]`.

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
    """
    Args:
        d: a dict with comparable values

    Returns:
        The key and value of the item with the lowest value in a
        dict as a `Tuple[key, value]`.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> item_with_min_value(d)
    ('a', 1)

    """
    return min(d.items(), key=lambda _: _[1])


def key_with_max_value(d: Dict[Any, Any]) -> Any:
    """
    Args:
        d: a dict with comparable keys

    Returns:
        The maximum key in the dict when comparing the keys with
        each other.

    .. note:: This code totally ignores values; it is comparing key
        against key to find the maximum key in the keyspace.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> key_with_max_value(d)
    'c'

    """
    return item_with_max_value(d)[0]


def key_with_min_value(d: Dict[Any, Any]) -> Any:
    """
    Args:
        d: a dict with comparable keys

    Returns:
        The minimum key in the dict when comparing the keys with
        each other.

    .. note:: This code totally ignores values; it is comparing key
        against key to find the minimum key in the keyspace.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> key_with_min_value(d)
    'a'

    """
    return item_with_min_value(d)[0]


def max_value(d: Dict[Any, Any]) -> Any:
    """
    Args:
        d: a dict with compatable values

    Returns:
        The maximum value in the dict *without its key*.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> max_value(d)
    3
    """
    return item_with_max_value(d)[1]


def min_value(d: Dict[Any, Any]) -> Any:
    """
    Args:
        d: a dict with comparable values

    Returns:
        The minimum value in the dict *without its key*.

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> min_value(d)
    1
    """
    return item_with_min_value(d)[1]


def max_key(d: Dict[Any, Any]) -> Any:
    """
    Args:
        d: a dict with comparable keys

    Returns:
        The maximum key in dict (ignoring values totally)

    .. note:: This code totally ignores values; it is comparing key
        against key to find the maximum key in the keyspace.

    >>> d = {'a': 3, 'b': 2, 'c': 1}
    >>> max_key(d)
    'c'
    """
    return max(d.keys())


def min_key(d: Dict[Any, Any]) -> Any:
    """
    Args:
        d: a dict with comparable keys

    Returns:
        The minimum key in dict (ignoring values totally)

    .. note:: This code totally ignores values; it is comparing key
        against key to find the minimum key in the keyspace.

    >>> d = {'a': 3, 'b': 2, 'c': 1}
    >>> min_key(d)
    'a'
    """
    return min(d.keys())


def parallel_lists_to_dict(keys: List[Any], values: List[Any]) -> Dict[Any, Any]:
    """Given two parallel lists (keys and values), create and return
    a dict.

    Args:
        keys: list containing keys and no duplicated keys
        values: a parallel list (to keys) containing values

    Returns:
        A dict composed of zipping the keys list and values list together.

    >>> k = ['name', 'phone', 'address', 'zip']
    >>> v = ['scott', '555-1212', '123 main st.', '12345']
    >>> parallel_lists_to_dict(k, v)
    {'name': 'scott', 'phone': '555-1212', 'address': '123 main st.', 'zip': '12345'}
    """
    if len(keys) != len(values):
        raise Exception("Parallel keys and values lists must have the same length")
    return dict(zip(keys, values))


def dict_to_key_value_lists(d: Dict[Any, Any]) -> Tuple[List[Any], List[Any]]:
    """Given a dict, decompose it into a list of keys and values.

    Args:
        d: a dict

    Returns:
        A tuple of two elements: the first is the keys list and the second
        is the values list.

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


dict_to_dataclass = dataclass_utils.dataclass_from_dict

dict_from_dataclass = dataclass_utils.dataclass_to_dict


if __name__ == '__main__':
    import doctest

    doctest.testmod()
