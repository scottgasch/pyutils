#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A collection of :class:`Iterator` subclasses that can be composed
with another iterator and provide extra functionality:

    + :class:`PeekingIterator`
    + :class:`PushbackIterator`
    + :class:`SamplingIterator`

"""

import random
from collections.abc import Iterator
from typing import Any, List, Optional


class PeekingIterator(Iterator):
    """An iterator that lets you :meth:`peek` at the next item on deck.
    Returns None when there is no next item (i.e. when
    :meth:`__next__` will produce a `StopIteration` exception).

    >>> p = PeekingIterator(iter(range(3)))
    >>> p.__next__()
    0
    >>> p.peek()
    1
    >>> p.peek()
    1
    >>> p.__next__()
    1
    >>> p.__next__()
    2
    >>> p.peek() == None
    True
    >>> p.__next__()
    Traceback (most recent call last):
      ...
    StopIteration
    """

    def __init__(self, source_iter: Iterator):
        """
        Args:
            source_iter: the iterator we want to peek at
        """
        self.source_iter = source_iter
        self.on_deck: List[Any] = []

    def __iter__(self) -> Iterator:
        return self

    def __next__(self) -> Any:
        if len(self.on_deck) > 0:
            return self.on_deck.pop()
        else:
            item = self.source_iter.__next__()
            return item

    def peek(self) -> Optional[Any]:
        """Peek at the upcoming value on the top of our contained
        :py:class:`Iterator` non-destructively (i.e. calling :meth:`__next__` will
        still produce the peeked value).

        Returns:
            The value that will be produced by the contained iterator next
            or None if the contained Iterator is exhausted and will raise
            `StopIteration` when read.

        """
        if len(self.on_deck) > 0:
            return self.on_deck[0]
        try:
            item = next(self.source_iter)
            self.on_deck.append(item)
            return self.peek()
        except StopIteration:
            return None


class PushbackIterator(Iterator):
    """An iterator that allows you to push items back onto the front
    of the sequence so that they are produced before the items at the
    front/top of the contained py:class:`Iterator`. e.g.

    >>> i = PushbackIterator(iter(range(3)))
    >>> i.__next__()
    0
    >>> i.push_back(99)
    >>> i.push_back(98)
    >>> i.__next__()
    98
    >>> i.__next__()
    99
    >>> i.__next__()
    1
    >>> i.__next__()
    2
    >>> i.push_back(100)
    >>> i.__next__()
    100
    >>> i.__next__()
    Traceback (most recent call last):
      ...
    StopIteration

    """

    def __init__(self, source_iter: Iterator):
        self.source_iter = source_iter
        self.pushed_back: List[Any] = []

    def __iter__(self) -> Iterator:
        return self

    def __next__(self) -> Any:
        if len(self.pushed_back) > 0:
            return self.pushed_back.pop()
        return self.source_iter.__next__()

    def push_back(self, item: Any) -> None:
        """Push an item onto the top of the contained iterator such that
        the next time :meth:`__next__` is invoked we produce that item.

        Args:
            item: the item to produce from :meth:`__next__` next.
        """
        self.pushed_back.append(item)


class SamplingIterator(Iterator):
    """An :py:class:`Iterator` that simply echoes what its
    `source_iter` produces but also collects a random sample (of size
    `sample_size`) from the stream that can be queried at any time.

    .. note::
        Until `sample_size` elements have been produced by the
        `source_iter`, the sample return will be less than `sample_size`
        elements in length.

    .. note::
        If `sample_size` is >= `len(source_iter)` then this will produce
        a copy of `source_iter`.

    >>> import collections
    >>> import random

    >>> random.seed(22)
    >>> s = SamplingIterator(iter(range(100)), 10)
    >>> s.__next__()
    0

    >>> s.__next__()
    1

    >>> s.get_sample()
    [0, 1]

    >>> collections.deque(s)
    deque([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99])

    >>> s.get_sample()
    [78, 18, 47, 83, 93, 26, 25, 73, 94, 38]

    """

    def __init__(self, source_iter: Iterator, sample_size: int):
        self.source_iter = source_iter
        self.sample_size = sample_size
        self.resovoir: List[Any] = []
        self.stream_length_so_far = 0

    def __iter__(self) -> Iterator:
        return self

    def __next__(self) -> Any:
        item = self.source_iter.__next__()
        self.stream_length_so_far += 1

        # Filling the resovoir
        pop = len(self.resovoir)
        if pop < self.sample_size:
            self.resovoir.append(item)
            if self.sample_size == (pop + 1):  # just finished filling...
                random.shuffle(self.resovoir)

        # Swap this item for one in the resovoir with probabilty
        # sample_size / stream_length_so_far.  See:
        #
        # https://en.wikipedia.org/wiki/Reservoir_sampling
        else:
            r = random.randint(0, self.stream_length_so_far)
            if r < self.sample_size:
                self.resovoir[r] = item
        return item

    def get_sample(self) -> List[Any]:
        """
        Returns:
            The current sample set populated randomly from the items
            returned by the contained :class:`Iterator` so far.

        .. note::
            Until `sample_size` elements have been produced by the
            `source_iter`, the sample return will be less than `sample_size`
            elements in length.

        .. note::
            If `sample_size` is >= `len(source_iter)` then this will produce
            a copy of `source_iter`.
        """
        return self.resovoir


if __name__ == "__main__":
    import doctest

    doctest.testmod()
