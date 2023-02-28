#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Helper utilities with a mathematical / statictical focus."""

import collections
import functools
import math
from heapq import heappop, heappush
from typing import Dict, List, Optional, Tuple

from pyutils import dict_utils
from pyutils.types.simple import Numeric


class NumericPopulation(object):
    """This object *store* a numeric population in a way that enables relatively
    fast addition of new numbers (:math:`O(2log_2 n)`) and instant access to the
    median value in the population (:math:`O(1)`).  It also provides other population
    summary statistics such as the :meth:`get_mode`, :meth:`get_percentile` and
    :meth:`get_stdev`.

    .. note::

        Because this class stores a copy of all numbers added to it, it shouldn't
        be used for very large populations.  Consider sampling.

    >>> pop = NumericPopulation()
    >>> pop.add_number(1)
    >>> pop.add_number(10)
    >>> pop.add_number(3)
    >>> len(pop)
    3
    >>> pop.get_median()
    3
    >>> pop.add_number(7)
    >>> pop.add_number(5)
    >>> pop.get_median()
    5
    >>> pop.get_mean()
    5.2
    >>> round(pop.get_stdev(), 1)
    3.1
    >>> pop.get_percentile(20)
    3
    >>> pop.get_percentile(60)
    7
    """

    def __init__(self):
        self.lowers, self.highers = [], []
        self.aggregate = 0.0
        self.sorted_copy: Optional[List[Numeric]] = None
        self.maximum = None
        self.minimum = None

    def add_number(self, number: Numeric):
        """Adds a number to the population.  Runtime complexity of this
        operation is :math:`O(2 log_2 n)`

        Args:
            number: the number to add_number to the population
        """

        if not self.highers or number > self.highers[0]:
            heappush(self.highers, number)
        else:
            heappush(self.lowers, -number)  # for lowers we need a max heap
        self.aggregate += number
        self._rebalance()
        if not self.maximum or number > self.maximum:
            self.maximum = number
        if not self.minimum or number < self.minimum:
            self.minimum = number

    def __len__(self):
        """
        Returns:
            the population's current size.
        """
        n = 0
        if self.highers:
            n += len(self.highers)
        if self.lowers:
            n += len(self.lowers)
        return n

    def _rebalance(self):
        """Internal helper for rebalancing the `lowers` and `highers` heaps"""
        if len(self.lowers) - len(self.highers) > 1:
            heappush(self.highers, -heappop(self.lowers))
        elif len(self.highers) - len(self.lowers) > 1:
            heappush(self.lowers, -heappop(self.highers))

    def get_median(self) -> Numeric:
        """
        Returns:
            The median (p50) of the current population in :math:`O(1)` time.
        """
        if len(self.lowers) == len(self.highers):
            return -self.lowers[0]
        elif len(self.lowers) > len(self.highers):
            return -self.lowers[0]
        else:
            return self.highers[0]

    def get_mean(self) -> float:
        """
        Returns:
            The mean (arithmetic mean) so far in :math:`O(1)` time.
        """
        count = len(self)
        return self.aggregate / count

    def get_mode(self) -> Tuple[Numeric, int]:
        """
        Returns:
            The population mode (most common member in the population)
            in :math:`O(n)` time.
        """
        count: Dict[Numeric, int] = collections.defaultdict(int)
        for n in self.lowers:
            count[-n] += 1
        for n in self.highers:
            count[n] += 1
        return dict_utils.item_with_max_value(count)

    def get_stdev(self) -> float:
        """
        Returns:
            The stdev of the current population in :math:`O(n)` time.
        """
        mean = self.get_mean()
        variance = 0.0
        for n in self.lowers:
            n = -n
            variance += (n - mean) ** 2
        for n in self.highers:
            variance += (n - mean) ** 2
        count = len(self.lowers) + len(self.highers)
        return math.sqrt(variance / count)

    def _create_sorted_copy_if_needed(self, count: int):
        """Internal helper."""
        if not self.sorted_copy or count != len(self.sorted_copy):
            self.sorted_copy = []
            for x in self.lowers:
                self.sorted_copy.append(-x)
            for x in self.highers:
                self.sorted_copy.append(x)
            self.sorted_copy = sorted(self.sorted_copy)

    def get_percentile(self, n: float) -> Numeric:
        """
        Returns: the number at approximately pn% in the population
        (i.e. the nth percentile) in :math:`O(n log_2 n)` time (it
        performs a full sort).  This is not the most efficient
        algorithm.

        Not thread-safe; does caching across multiple calls without
        an invocation to :meth:`add_number` for perf reasons.

        Args:
            n: the percentile to compute
        """
        if n == 50:
            return self.get_median()
        count = len(self)
        self._create_sorted_copy_if_needed(count)
        assert self.sorted_copy
        index = round(count * (n / 100.0))
        index = max(0, index)
        index = min(count - 1, index)
        return self.sorted_copy[index]


def gcd_floats(a: float, b: float) -> float:
    """
    Returns:
        The greatest common divisor of a and b.

    Args:
        a: first operand
        b: second operatnd
    """
    if a < b:
        return gcd_floats(b, a)

    # base case
    if abs(b) < 0.001:
        return a
    return gcd_floats(b, a - math.floor(a / b) * b)


def gcd_float_sequence(lst: List[float]) -> float:
    """
    Returns:
        The greatest common divisor of a list of floats.

    Args:
        lst: a list of operands
    """
    if len(lst) <= 0:
        raise ValueError("Need at least one number")
    if len(lst) == 1:
        return lst[0]
    assert len(lst) >= 2
    gcd = gcd_floats(lst[0], lst[1])
    for i in range(2, len(lst)):
        gcd = gcd_floats(gcd, lst[i])
    return gcd


def truncate_float(n: float, decimals: int = 2):
    """
    Returns:
        A truncated float to a particular number of decimals.

    Args:
        n: the float to truncate
        decimals: how many decimal places are desired?

    >>> truncate_float(3.1415927, 3)
    3.141
    """
    assert 0 < decimals < 10
    multiplier = 10**decimals
    return int(n * multiplier) / multiplier


def percentage_to_multiplier(percent: float) -> float:
    """Given a percentage that represents a return or percent change
    (e.g. 155%), determine the factor (i.e.  multiplier) needed to
    scale a number by that percentage (e.g. 2.55x)

    Args:
        percent: the return percent to scale by

    >>> percentage_to_multiplier(155)
    2.55
    >>> percentage_to_multiplier(45)
    1.45
    >>> percentage_to_multiplier(-25)
    0.75

    """
    multiplier = percent / 100
    multiplier += 1.0
    return multiplier


def multiplier_to_percent(multiplier: float) -> float:
    """Convert a multiplicative factor into a percent change or return
    percentage.

    Args:
        multiplier: the multiplier for which to compute the percent change

    >>> multiplier_to_percent(0.75)
    -25.0
    >>> multiplier_to_percent(1.0)
    0.0
    >>> multiplier_to_percent(1.99)
    99.0
    """
    percent = multiplier
    if percent > 0.0:
        percent -= 1.0
    else:
        percent = 1.0 - percent
    percent *= 100.0
    return percent


@functools.lru_cache(maxsize=1024, typed=True)
def is_prime(n: int) -> bool:
    """
    Args:
        n: the number for which primeness is to be determined.

    Returns:
        True if n is prime and False otherwise.

    .. note::

         Obviously(?) very slow for very large input numbers until
         we get quantum computers.

    >>> is_prime(13)
    True
    >>> is_prime(22)
    False
    >>> is_prime(51602981)
    True
    """
    if not isinstance(n, int):
        raise TypeError("argument passed to is_prime is not of 'int' type")

    # Corner cases
    if n <= 1:
        return False
    if n <= 3:
        return True

    # This is checked so that we can skip middle five numbers in below
    # loop
    if n % 2 == 0 or n % 3 == 0:
        return False

    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i = i + 6
    return True


if __name__ == "__main__":
    import doctest

    doctest.testmod()
