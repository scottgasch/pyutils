#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A class to represent a rate of change."""

from typing import Optional


class Rate(object):
    """A class to represent a rate of change."""

    def __init__(
        self,
        multiplier: Optional[float] = None,
        *,
        percentage: Optional[float] = None,
        percent_change: Optional[float] = None,
    ):
        """Constructs a new :class:`Rate` from a multiplier, percentage, or
        percent change.  One and only one of these may be passed.  These are
        a little confusing so here's an example...

        .. note::

            A multiplier of 1.5x is the same as a percentage of 150% and
            is also the same as a 50% change.  Let's examine an original
            amount of 100.  Multiplying it by a 1.5x multiplier yields 150.
            Multiplying it by 150% yields 150.  Increasing it by 50% also
            yields 150.

        Args:
            multiplier: provides the number that you would multiply a base
                amount by to modify it
            percentage: provides the multiplier as a percentage
            percent_change: provides the multiplier as a percent change to
                the base amount
        """
        count = 0
        if multiplier is not None:
            if isinstance(multiplier, str):
                multiplier = multiplier.replace("%", "")
                m = float(multiplier)
                m /= 100
                self.multiplier: float = m
            else:
                self.multiplier = multiplier
            count += 1
        if percentage is not None:
            self.multiplier = percentage / 100
            count += 1
        if percent_change is not None:
            self.multiplier = 1.0 + percent_change / 100
            count += 1
        if count != 1:
            raise Exception(
                "Exactly one of percentage, percent_change or multiplier is required."
            )

    def apply_to(self, other):
        """Applies the rate to a base number.

        Args:
            other: the base to apply the change rate to.

        Returns:
            The result after the change.
        """
        return self.__mul__(other)

    def of(self, other):
        """Applies the rate to a base number.

        Args:
            other: the base to apply the change rate to.

        Returns:
            The result after the change.
        """
        return self.__mul__(other)

    def __float__(self):
        return self.multiplier

    def __mul__(self, other):
        return self.multiplier * float(other)

    __rmul__ = __mul__

    def __truediv__(self, other):
        return self.multiplier / float(other)

    def __add__(self, other):
        return self.multiplier + float(other)

    __radd__ = __add__

    def __sub__(self, other):
        return self.multiplier - float(other)

    def __eq__(self, other):
        return self.multiplier == float(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.multiplier < float(other)

    def __gt__(self, other):
        return self.multiplier > float(other)

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __hash__(self):
        return self.multiplier

    def __repr__(self, *, relative=False, places=3):
        if relative:
            percentage = (self.multiplier - 1.0) * 100.0
        else:
            percentage = self.multiplier * 100.0
        return f"{percentage:+.{places}f}%"
