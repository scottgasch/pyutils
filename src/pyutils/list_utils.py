#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Some useful(?) utilities for dealing with Lists."""

import random
from collections import Counter
from itertools import chain, combinations, islice
from typing import Any, Iterator, List, MutableSequence, Sequence, Tuple


def shard(lst: List[Any], size: int) -> Iterator[Any]:
    """
    Yield successive size-sized shards from lst.

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
    Flatten out a list:

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
    Prepend an item to a list.

    >>> prepend('foo', ['bar', 'baz'])
    ['foo', 'bar', 'baz']

    """
    lst.insert(0, item)
    return lst


def remove_list_if_one_element(lst: List[Any]) -> Any:
    """
    Remove the list and return the 0th element iff its length is one.

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
    list item in the original list.

    >>> population_counts([1, 1, 1, 2, 2, 3, 3, 3, 4])
    Counter({1: 3, 3: 3, 2: 2, 4: 1})

    """
    return Counter(lst)


def most_common(lst: List[Any], *, count=1) -> Any:

    """
    Return the most common item in the list.  In the case of ties,
    which most common item is returned will be random.

    >>> most_common([1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4])
    3

    >>> most_common([1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4], count=2)
    [3, 1]

    """
    p = population_counts(lst)
    return remove_list_if_one_element([_[0] for _ in p.most_common()[0:count]])


def least_common(lst: List[Any], *, count=1) -> Any:
    """
    Return the least common item in the list.  In the case of
    ties, which least common item is returned will be random.

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
    Remove duplicates from the list performantly.

    >>> dedup_list([1, 2, 1, 3, 3, 4, 2, 3, 4, 5, 1])
    [1, 2, 3, 4, 5]

    """
    return list(set(lst))


def uniq(lst: List[Any]) -> List[Any]:
    """
    Alias for dedup_list.
    """
    return dedup_list(lst)


def contains_duplicates(lst: List[Any]) -> bool:
    """
    Does the list contian duplicate elements or not?

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
    Inverted alias for contains_duplicates.
    """
    return not contains_duplicates(lst)


def transpose(lst: List[Any]) -> List[Any]:
    """
    Transpose a list of lists.

    >>> lst = [[1, 2], [3, 4], [5, 6]]
    >>> transpose(lst)
    [[1, 3, 5], [2, 4, 6]]

    """
    transposed = zip(*lst)
    return [list(_) for _ in transposed]


def ngrams(lst: Sequence[Any], n):
    """
    Return the ngrams in the sequence.

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
    Returns all permutations of a sequence; takes O(N!) time.

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
    return shuffle(seq)


def binary_search(lst: Sequence[Any], target: Any) -> Tuple[bool, int]:
    """Performs a binary search on lst (which must already be sorted).
    Returns a Tuple composed of a bool which indicates whether the
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


def powerset(lst: Sequence[Any]) -> Iterator[Sequence[Any]]:
    """Returns the powerset of the items in the input sequence.

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
    return chain.from_iterable(combinations(lst, r) for r in range(len(lst) + 1))


if __name__ == '__main__':
    import doctest

    doctest.testmod()
