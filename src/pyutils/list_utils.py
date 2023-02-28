#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This module contains helper functions for dealing with Python lists."""

import random
from collections import Counter
from itertools import chain, combinations, islice
from typing import Any, Iterator, List, MutableSequence, Sequence, Tuple


def shard(lst: List[Any], size: int) -> Iterator[Any]:
    """
    Shards (i.e. splits) a list into sublists of size `size` whcih,
    together, contain all items in the original unsharded list.

    Args:
        lst: the original input list to shard
        size: the ideal shard size (number of elements per shard)

    Returns:
        A generator that yields successive shards.

    .. note::

        If `len(lst)` is not an even multiple of `size` then the last
        shard will not have `size` items in it.  It will have
        `len(lst) % size` items instead.

    >>> for sublist in shard([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 3):
    ...     [_ for _ in sublist]
    [1, 2, 3]
    [4, 5, 6]
    [7, 8, 9]
    [10, 11, 12]
    """
    for x in range(0, len(lst), size):
        yield islice(lst, x, x + size)


def flatten(lst: List[Any]) -> List[Any]:
    """
    Flatten out a list.  That is, for each item in list that contains
    a list, remove the nested list and replace it with its items.

    Args:
        lst: the list to flatten

    Returns:
        The flattened list.  See example.

    >>> flatten([ 1, [2, 3, 4, [5], 6], 7, [8, [9]]])
    [1, 2, 3, 4, 5, 6, 7, 8, 9]
    """
    if len(lst) == 0:
        return lst
    if isinstance(lst[0], list):
        return flatten(lst[0]) + flatten(lst[1:])
    return lst[:1] + flatten(lst[1:])


def prepend(item: Any, lst: List[Any]) -> List[Any]:
    """
    Prepend an item to a list.  An alias for `list.insert(0, item)`.
    The opposite of `list.append()`.

    Args:
        item: the item to be prepended
        lst: the list on which to prepend

    Returns:
        The list with item prepended.

    >>> prepend('foo', ['bar', 'baz'])
    ['foo', 'bar', 'baz']
    """
    lst.insert(0, item)
    return lst


def remove_list_if_one_element(lst: List[Any]) -> Any:
    """
    Remove the list and return the 0th element iff its length is one.

    Args:
        lst: the List to check

    Returns:
        Either `lst` (if `len(lst) > 1`) or `lst[0]` (if `len(lst) == 1`).

    >>> remove_list_if_one_element([1234])
    1234

    >>> remove_list_if_one_element([1, 2, 3, 4])
    [1, 2, 3, 4]
    """
    if len(lst) == 1:
        return lst[0]
    else:
        return lst


def population_counts(lst: Sequence[Any]) -> Counter:
    """
    Return a population count mapping for the list (i.e. the keys are
    list items and the values are the number of occurrances of that
    list item in the original list).  Note: this is used internally
    to implement :meth:`most_common` and :meth:`least_common`.

    Args:
        lst: the list whose population should be counted

    Returns:
        a `Counter` containing the population count of `lst` items.

    >>> population_counts([1, 1, 1, 2, 2, 3, 3, 3, 4])
    Counter({1: 3, 3: 3, 2: 2, 4: 1})
    """
    return Counter(lst)


def most_common(lst: List[Any], *, count: int = 1) -> Any:
    """
    Return the N most common item in the list.

    Args:
        lst: the list to find the most common item in
        count: the number of most common items to return

    Returns:
        The most common item in `lst`.

    .. warning::

        In the case of ties for most common item, which most common
        item is returned is undefined.

    >>> most_common([1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4])
    3

    >>> most_common([1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4], count=2)
    [3, 1]

    """
    p = population_counts(lst)
    return remove_list_if_one_element([_[0] for _ in p.most_common()[0:count]])


def least_common(lst: List[Any], *, count: int = 1) -> Any:
    """
    Return the N least common item in the list.

    Args:
        lst: the list to find the least common item in
        count: the number of least common items to return

    Returns:
        The least common item in `lst`

    .. warning::

       In the case of ties, which least common item is returned
       is undefined.

    >>> least_common([1, 1, 1, 2, 2, 3, 3, 3, 4])
    4

    >>> least_common([1, 1, 1, 2, 2, 3, 3, 3, 4], count=2)
    [4, 2]
    """
    p = population_counts(lst)
    mc = p.most_common()[-count:]
    mc.reverse()
    return remove_list_if_one_element([_[0] for _ in mc])


def dedup_list(lst: List[Any]) -> List[Any]:
    """
    Remove duplicates from the list.

    Args:
        lst: the list to de-duplicate

    Returns:
        The de-duplicated input list.  That is, the same list with
        all extra duplicate items removed.  The list composed of
        the set of unique items from the input `lst`

    >>> dedup_list([1, 2, 1, 3, 3, 4, 2, 3, 4, 5, 1])
    [1, 2, 3, 4, 5]
    """
    return list(set(lst))


def uniq(lst: List[Any]) -> List[Any]:
    """
    Alias for :meth:`dedup_list`.
    """
    return dedup_list(lst)


def contains_duplicates(lst: List[Any]) -> bool:
    """
    Does the list contain duplicate elements or not?

    Args:
        lst: the list to check for duplicates

    Returns:
        True if the input `lst` contains duplicated items and
        False otherwise.

    >>> lst = [1, 2, 1, 3, 3, 4, 4, 5, 6, 1, 3, 4]
    >>> contains_duplicates(lst)
    True

    >>> contains_duplicates(dedup_list(lst))
    False
    """
    seen = set()
    for _ in lst:
        if _ in seen:
            return True
        seen.add(_)
    return False


def all_unique(lst: List[Any]) -> bool:
    """
    Inverted alias for :meth:`contains_duplicates`.
    """
    return not contains_duplicates(lst)


def transpose(lst: List[Any]) -> List[Any]:
    """
    Transpose a list of lists.

    Args:
        lst: the list of lists to be transposed.

    Returns:
        The transposed result.  See example.

    >>> lst = [[1, 2], [3, 4], [5, 6]]
    >>> transpose(lst)
    [[1, 3, 5], [2, 4, 6]]

    """
    transposed = zip(*lst)
    return [list(_) for _ in transposed]


def ngrams(lst: Sequence[Any], n: int):
    """
    Return the ngrams in the sequence.

    Args:
        lst: the list in which to find ngrams
        n: the size of each ngram to return

    Returns:
        A generator that yields all ngrams of size `n` in `lst`.

    >>> seq = 'encyclopedia'
    >>> for _ in ngrams(seq, 3):
    ...     _
    'enc'
    'ncy'
    'cyc'
    'ycl'
    'clo'
    'lop'
    'ope'
    'ped'
    'edi'
    'dia'

    >>> seq = ['this', 'is', 'an', 'awesome', 'test']
    >>> for _ in ngrams(seq, 3):
    ...     _
    ['this', 'is', 'an']
    ['is', 'an', 'awesome']
    ['an', 'awesome', 'test']
    """
    for i in range(len(lst) - n + 1):
        yield lst[i : i + n]


def permute(seq: str):
    """
    Returns all permutations of a sequence.

    Args:
        seq: the sequence to permute

    Returns:
        All permutations creatable by shuffling items in `seq`.

    .. warning::

        Takes O(N!) time, beware of large inputs.

    >>> for x in permute('cat'):
    ...     print(x)
    cat
    cta
    act
    atc
    tca
    tac
    """
    yield from _permute(seq, "")


def _permute(seq: str, path: str):
    """Internal helper to permute items recursively."""
    seq_len = len(seq)
    if seq_len == 0:
        yield path

    for i in range(seq_len):
        car = seq[i]
        left = seq[0:i]
        right = seq[i + 1 :]
        cdr = left + right
        yield from _permute(cdr, path + car)


def shuffle(seq: MutableSequence[Any]) -> MutableSequence[Any]:
    """Shuffles a sequence into a random order.

    Args:
        seq: a sequence to shuffle

    Returns:
        The shuffled sequence.

    >>> random.seed(22)
    >>> shuffle([1, 2, 3, 4, 5])
    [3, 4, 1, 5, 2]

    >>> shuffle('example')
    'empaelx'
    """
    if isinstance(seq, str):
        from pyutils import string_utils

        return string_utils.shuffle(seq)
    else:
        random.shuffle(seq)
        return seq


def scramble(seq: MutableSequence[Any]) -> MutableSequence[Any]:
    """An alias for :meth:`shuffle`."""
    return shuffle(seq)


def binary_search(lst: Sequence[Any], target: Any) -> Tuple[bool, int]:
    """Performs a binary search on lst (which must already be sorted).

    Args:
        lst: the (already sorted!) list in which to search
        target: the item value to be found

    Returns:
        A Tuple composed of a bool which indicates whether the
        target was found and an int which indicates the index closest to
        target whether it was found or not.

    >>> a = [1, 4, 5, 6, 7, 9, 10, 11]
    >>> binary_search(a, 4)
    (True, 1)

    >>> binary_search(a, 12)
    (False, 8)

    >>> binary_search(a, 3)
    (False, 1)

    >>> binary_search(a, 2)
    (False, 1)

    >>> a.append(9)
    >>> binary_search(a, 4)
    Traceback (most recent call last):
    ...
    AssertionError

    """
    if __debug__:
        last = None
        for x in lst:
            if last is not None:
                assert x >= last  # This asserts iff the list isn't sorted
            last = x  # in ascending order.
    return _binary_search(lst, target, 0, len(lst) - 1)


def _binary_search(
    lst: Sequence[Any], target: Any, low: int, high: int
) -> Tuple[bool, int]:
    """Internal helper to perform a binary search recursively."""
    if high >= low:
        mid = (high + low) // 2
        if lst[mid] == target:
            return (True, mid)
        elif lst[mid] > target:
            return _binary_search(lst, target, low, mid - 1)
        else:
            return _binary_search(lst, target, mid + 1, high)
    else:
        return (False, low)


def powerset(seq: Sequence[Any]) -> Iterator[Sequence[Any]]:
    """Returns the powerset of the items in the input sequence.  That is,
    return the set containing every set constructable using items from
    seq (including the empty set and the "full" set: `seq` itself).

    Args:
        seq: the sequence whose items will be used to construct the powerset.

    Returns:
        The powerset composed of all sets possible to create with items from `seq`.
        See: https://en.wikipedia.org/wiki/Power_set.

    >>> for x in powerset([1, 2, 3]):
    ...     print(x)
    ()
    (1,)
    (2,)
    (3,)
    (1, 2)
    (1, 3)
    (2, 3)
    (1, 2, 3)
    """
    return chain.from_iterable(combinations(seq, r) for r in range(len(seq) + 1))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
