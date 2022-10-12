#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""An amount of money (USD) represented as an integral count of
cents."""

import re
from typing import Optional, Tuple

from pyutils import math_utils


class CentCount(object):
    """A class for representing monetary amounts potentially with
    different currencies meant to avoid floating point rounding
    issues by treating amount as a simple integral count of cents.
    """

    def __init__(self, centcount, currency: str = 'USD', *, strict_mode=False):
        self.strict_mode = strict_mode
        if isinstance(centcount, str):
            ret = CentCount._parse(centcount)
            if ret is None:
                raise Exception(f'Unable to parse money string "{centcount}"')
            centcount = ret[0]
            currency = ret[1]
        if isinstance(centcount, float):
            centcount = int(centcount * 100.0)
        if not isinstance(centcount, int):
            centcount = int(centcount)
        self.centcount = centcount
        if not currency:
            self.currency: Optional[str] = None
        else:
            self.currency = currency

    def __repr__(self):
        a = float(self.centcount)
        a /= 100
        a = round(a, 2)
        s = f'{a:,.2f}'
        if self.currency is not None:
            return f'{s} {self.currency}'
        else:
            return f'${s}'

    def __pos__(self):
        return CentCount(centcount=self.centcount, currency=self.currency)

    def __neg__(self):
        return CentCount(centcount=-self.centcount, currency=self.currency)

    def __add__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return CentCount(
                    centcount=self.centcount + other.centcount,
                    currency=self.currency,
                )
            else:
                raise TypeError('Incompatible currencies in add expression')
        else:
            if self.strict_mode:
                raise TypeError('In strict_mode only two moneys can be added')
            else:
                return self.__add__(CentCount(other, self.currency))

    def __sub__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return CentCount(
                    centcount=self.centcount - other.centcount,
                    currency=self.currency,
                )
            else:
                raise TypeError('Incompatible currencies in add expression')
        else:
            if self.strict_mode:
                raise TypeError('In strict_mode only two moneys can be added')
            else:
                return self.__sub__(CentCount(other, self.currency))

    def __mul__(self, other):
        if isinstance(other, CentCount):
            raise TypeError('can not multiply monetary quantities')
        else:
            return CentCount(
                centcount=int(self.centcount * float(other)),
                currency=self.currency,
            )

    def __truediv__(self, other):
        if isinstance(other, CentCount):
            raise TypeError('can not divide monetary quantities')
        else:
            return CentCount(
                centcount=int(float(self.centcount) / float(other)),
                currency=self.currency,
            )

    def __int__(self):
        return self.centcount.__int__()

    def __float__(self):
        return self.centcount.__float__() / 100.0

    def truncate_fractional_cents(self):
        x = int(self)
        self.centcount = int(math_utils.truncate_float(x))
        return self.centcount

    def round_fractional_cents(self):
        x = int(self)
        self.centcount = int(round(x, 2))
        return self.centcount

    __radd__ = __add__

    def __rsub__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return CentCount(
                    centcount=other.centcount - self.centcount,
                    currency=self.currency,
                )
            else:
                raise TypeError('Incompatible currencies in sub expression')
        else:
            if self.strict_mode:
                raise TypeError('In strict_mode only two moneys can be added')
            else:
                return CentCount(
                    centcount=int(other) - self.centcount,
                    currency=self.currency,
                )

    __rmul__ = __mul__

    #
    # Override comparison operators to also compare currency.
    #
    def __eq__(self, other):
        if other is None:
            return False
        if isinstance(other, CentCount):
            return self.centcount == other.centcount and self.currency == other.currency
        if self.strict_mode:
            raise TypeError("In strict mode only two CentCounts can be compared")
        else:
            return self.centcount == int(other)

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return self.centcount < other.centcount
            else:
                raise TypeError('can not directly compare different currencies')
        else:
            if self.strict_mode:
                raise TypeError('In strict mode, only two CentCounts can be compated')
            else:
                return self.centcount < int(other)

    def __gt__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return self.centcount > other.centcount
            else:
                raise TypeError('can not directly compare different currencies')
        else:
            if self.strict_mode:
                raise TypeError('In strict mode, only two CentCounts can be compated')
            else:
                return self.centcount > int(other)

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __hash__(self) -> int:
        return hash(self.__repr__)

    CENTCOUNT_RE = re.compile(r"^([+|-]?)(\d+)(\.\d+)$")
    CURRENCY_RE = re.compile(r"^[A-Z][A-Z][A-Z]$")

    @classmethod
    def _parse(cls, s: str) -> Optional[Tuple[int, str]]:
        centcount = None
        currency = None
        s = s.strip()
        chunks = s.split(' ')
        try:
            for chunk in chunks:
                if CentCount.CENTCOUNT_RE.match(chunk) is not None:
                    centcount = int(float(chunk) * 100.0)
                elif CentCount.CURRENCY_RE.match(chunk) is not None:
                    currency = chunk
        except Exception:
            pass
        if centcount is not None and currency is not None:
            return (centcount, currency)
        elif centcount is not None:
            return (centcount, 'USD')
        return None

    @classmethod
    def parse(cls, s: str) -> 'CentCount':
        chunks = CentCount._parse(s)
        if chunks is not None:
            return CentCount(chunks[0], chunks[1])
        raise Exception(f'Unable to parse money string "{s}"')
