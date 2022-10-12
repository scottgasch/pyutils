#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

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
        count = 0
        if multiplier is not None:
            if isinstance(multiplier, str):
                multiplier = multiplier.replace('%', '')
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
                'Exactly one of percentage, percent_change or multiplier is required.'
            )

    def apply_to(self, other):
        return self.__mul__(other)

    def of(self, other):
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
        return f'{percentage:+.{places}f}%'
