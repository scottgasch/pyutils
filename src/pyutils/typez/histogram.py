#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# © Copyright 2021-2023, Scott Gasch

"""
This is a text-based histogram class.  It creates output like this:

A Histogram helper class.  Creates outputs like this::

      [5..6): ▏                                                     ( 0.10% n=1)
      [6..7): █▋                                                    ( 0.49% n=5)
      [7..8): █████▏                                                ( 1.46% n=15)
      [8..9): ███████████▉                                          ( 3.42% n=35)
     [9..10): ██████████████████████▏                               ( 6.35% n=65)
    [10..11): ██████████████████████████████████▌                   ( 9.86% n=101)
    [11..12): ██████████████████████████████████████████████▏       (13.18% n=135)
    [12..13): ████████████████████████████████████████████████████▉ (15.14% n=155)
    [13..14): ████████████████████████████████████████████████████▉ (15.14% n=155)
    [14..15): ██████████████████████████████████████████████▏       (13.18% n=135)
    [15..16): ██████████████████████████████████▌                   ( 9.86% n=101)
    [16..17): ██████████████████████▏                               ( 6.35% n=65)
    [17..18): ███████████▉                                          ( 3.42% n=35)
    [18..19): █████▏                                                ( 1.46% n=15)
    [19..20): █▋                                                    ( 0.49% n=5)
    [20..21): ▏                                                     ( 0.10% n=1)
    --------------------------------------------------------------------------------
     [5..21):                                                         pop(Σn)=1024
                                                                      mean(μ)=12.500
                                                                  median(p50)=12.000
                                                                     mode(Mo)=12.000
                                                                     stdev(σ)=2.500
"""

import math
from dataclasses import dataclass
from typing import Dict, Generic, Iterable, List, Optional, Tuple, TypeVar

T = TypeVar("T", int, float)
Bound = int
Count = int


@dataclass
class BucketDetails:
    """A collection of details about the internal histogram buckets."""

    num_populated_buckets: int = 0
    """Count of populated buckets"""

    max_population: Optional[int] = None
    """The max population in a bucket currently"""

    last_bucket_start: Optional[int] = None
    """The last bucket starting point"""

    lowest_start: Optional[int] = None
    """The lowest populated bucket's starting point"""

    highest_end: Optional[int] = None
    """The highest populated bucket's ending point"""

    max_label_width: Optional[int] = None
    """The maximum label width (for display purposes)"""


class SimpleHistogram(Generic[T]):
    """A simple histogram."""

    # Useful in defining wide open bottom/top bucket bounds:
    POSITIVE_INFINITY = math.inf
    NEGATIVE_INFINITY = -math.inf

    def __init__(self, buckets: List[Tuple[Bound, Bound]]):
        """C'tor.

        Args:
            buckets: a list of [start..end] tuples that define the
                buckets we are counting population in.  See also
                :meth:`n_evenly_spaced_buckets` to generate these
                buckets more easily.
        """
        from pyutils.math_utils import NumericPopulation

        self.buckets: Dict[Tuple[Bound, Bound], Count] = {}
        for start_end in buckets:
            if self._get_bucket(start_end[0]) is not None:
                raise Exception("Buckets overlap?!")
            self.buckets[start_end] = 0
        self.sigma: float = 0.0
        self.stats: NumericPopulation = NumericPopulation()
        self.maximum: Optional[T] = None
        self.minimum: Optional[T] = None
        self.count: Count = 0

    @staticmethod
    def n_evenly_spaced_buckets(
        min_bound: T,
        max_bound: T,
        n: int,
    ) -> List[Tuple[int, int]]:
        """A helper method for generating the buckets argument to
        our c'tor provided that you want N evenly spaced buckets.

        Args:
            min_bound: the minimum possible value
            max_bound: the maximum possible value
            n: how many buckets to create

        Returns:
            A list of bounds that define N evenly spaced buckets
        """
        ret: List[Tuple[int, int]] = []
        stride = int((max_bound - min_bound) / n)
        if stride <= 0:
            raise Exception("Min must be < Max")
        imax = math.ceil(max_bound)
        imin = math.floor(min_bound)
        for bucket_start in range(imin, imax, stride):
            ret.append((bucket_start, bucket_start + stride))
        return ret

    def _get_bucket(self, item: T) -> Optional[Tuple[int, int]]:
        """Given an item, what bucket is it in?"""
        for start_end in self.buckets:
            if start_end[0] <= item < start_end[1]:
                return start_end
        return None

    def add_item(self, item: T) -> bool:
        """Adds a single item to the histogram (reculting in us incrementing
        the population in the correct bucket.

        Args:
            item: the item to be added

        Returns:
            True if the item was successfully added or False if the item
            is not within the bounds established during class construction.
        """
        bucket = self._get_bucket(item)
        if bucket is None:
            return False
        self.count += 1
        self.buckets[bucket] += 1
        self.sigma += item
        self.stats.add_number(item)
        if self.maximum is None or item > self.maximum:
            self.maximum = item
        if self.minimum is None or item < self.minimum:
            self.minimum = item
        return True

    def add_items(self, lst: Iterable[T]) -> bool:
        """Adds a collection of items to the histogram and increments
        the correct bucket's population for each item.

        Args:
            lst: An iterable of items to be added

        Returns:
            True if all items were added successfully or False if any
            item was not able to be added because it was not within the
            bounds established at object construction.
        """
        all_true = True
        for item in lst:
            all_true = all_true and self.add_item(item)
        return all_true

    def _get_bucket_details(self, label_formatter: str) -> BucketDetails:
        """Get the details about one bucket."""
        details = BucketDetails()
        for (start, end), pop in sorted(self.buckets.items(), key=lambda x: x[0]):
            if pop > 0:
                details.num_populated_buckets += 1
                details.last_bucket_start = start
                if details.max_population is None or pop > details.max_population:
                    details.max_population = pop
                if details.lowest_start is None or start < details.lowest_start:
                    details.lowest_start = start
                if details.highest_end is None or end > details.highest_end:
                    details.highest_end = end
                label = f"[{label_formatter}..{label_formatter}): " % (start, end)
                label_width = len(label)
                if (
                    details.max_label_width is None
                    or label_width > details.max_label_width
                ):
                    details.max_label_width = label_width
        return details

    def __repr__(self, *, width: int = 80, label_formatter: str = "%d") -> str:
        """Returns a pretty (text) representation of the histogram and
        some vital stats about the population in it (min, max, mean,
        median, mode, stdev, etc...)
        """
        from pyutils.text_utils import BarGraphText, bar_graph_string

        details = self._get_bucket_details(label_formatter)
        txt = ""
        if details.num_populated_buckets == 0:
            return txt
        assert details.max_label_width is not None
        assert details.lowest_start is not None
        assert details.highest_end is not None
        assert details.max_population is not None
        sigma_label = f"[{label_formatter}..{label_formatter}): " % (
            details.lowest_start,
            details.highest_end,
        )
        if len(sigma_label) > details.max_label_width:
            details.max_label_width = len(sigma_label)
        bar_width = width - (details.max_label_width + 17)

        for (start, end), pop in sorted(self.buckets.items(), key=lambda x: x[0]):
            if start < details.lowest_start:
                continue
            label = f"[{label_formatter}..{label_formatter}): " % (start, end)
            bar = bar_graph_string(
                pop,
                details.max_population,
                text=BarGraphText.NONE,
                width=bar_width,
                left_end="",
                right_end="",
            )
            txt += label.rjust(details.max_label_width)
            txt += bar
            txt += f"({pop/self.count*100.0:5.2f}% n={pop})\n"
            if start == details.last_bucket_start:
                break
        txt += "-" * width + "\n"
        txt += sigma_label.rjust(details.max_label_width)
        txt += " " * (bar_width - 2)
        txt += f"     pop(Σn)={self.count}\n"
        txt += " " * (bar_width + details.max_label_width - 2)
        txt += f"     mean(μ)={self.stats.get_mean():.3f}\n"
        txt += " " * (bar_width + details.max_label_width - 2)
        txt += f" median(p50)={self.stats.get_median():.3f}\n"
        txt += " " * (bar_width + details.max_label_width - 2)
        txt += f"    mode(Mo)={self.stats.get_mode()[0]:.3f}\n"
        txt += " " * (bar_width + details.max_label_width - 2)
        txt += f"    stdev(σ)={self.stats.get_stdev():.3f}\n"
        txt += "\n"
        return txt
