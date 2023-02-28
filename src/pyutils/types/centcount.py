#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""An amount of money represented as an integral count of cents so as
to avoid floating point artifacts.  Multiplication and division are
performed using floating point arithmetic but the quotient is cast
back to an integer number thus truncating the result and
avoiding floating point arithmetic artifacts.  See details below.

The type guards against inadvertent aggregation of instances with
non-matching currencies, the division of one CentCount by another, and
has a strict mode which disallows comparison or aggregation with
non-CentCount operands (i.e. no comparison or aggregation with literal
numbers).

.. note::

    Multiplication and division are performed by converting the
    `CentCount` into a float and operating on two floating point
    numbers.  The result is then cast back to an int which loses
    precision beyond the 1-cent granularity in order to avoid floating
    point representation artifacts.

    This can cause "problems" such as the one illustrated
    below::

        >>> c = CentCount(100.00)
        >>> c
        100.00 USD
        >>> c = c * 2
        >>> c
        200.00 USD
        >>> c = c / 3
        >>> c
        66.66 USD

    Two-thirds of $100.00 is $66.66666... which might be
    expected to round upwards to $66.67 but it does not
    because the `int` cast truncates the result.  Be aware
    of this and decide whether it's suitable for your
    application.

See also the :class:`pyutils.types.Money` class which uses Python
Decimals (see: https://docs.python.org/3/library/decimal.html) to
represent monetary amounts.
"""

import re
from typing import Optional, Tuple, Union


class CentCount(object):
    """A class for representing monetary amounts potentially with
    different currencies meant to avoid floating point rounding
    issues by treating amount as a simple integral count of cents.
    """

    def __init__(
        self,
        centcount: Union[int, float, str, "CentCount"] = 0,
        currency: str = "USD",
        *,
        strict_mode=False,
    ):
        """
        Args:
            centcount: the amount of money being represented; this can be
                a float, int, CentCount or str.
            currency: optionally declare the currency being represented by
                this instance.  If provided it will guard against operations
                such as attempting to add it to non-matching currencies.
            strict_mode: if True, the instance created will object if you
                compare or aggregate it with non-CentCount objects; that is,
                strict_mode disallows comparison with literal numbers or
                aggregation with literal numbers.
        """
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
        w = self.centcount // 100
        p = self.centcount % 100
        s = f"{w}.{p:02d}"
        if self.currency is not None:
            return f"{s} {self.currency}"
        else:
            return f"${s}"

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
                raise TypeError("Incompatible currencies in add expression")
        else:
            if self.strict_mode:
                raise TypeError("In strict_mode only two moneys can be added")
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
                raise TypeError("Incompatible currencies in add expression")
        else:
            if self.strict_mode:
                raise TypeError("In strict_mode only two moneys can be added")
            else:
                return self.__sub__(CentCount(other, self.currency))

    def __mul__(self, other):
        """
        .. note::

            Multiplication and division are performed by converting the
            CentCount into a float and operating on two floating point
            numbers.  But the result is then cast back to an int which
            loses precision beyond the 1-cent granularity in order to
            avoid floating point representation artifacts.

            This can cause "problems" such as the one illustrated
            below::

                >>> c = CentCount(100.00)
                >>> c = c * 2
                >>> c = c / 3
                >>> c
                66.66 USD

            Two-thirds of $100.00 is $66.66666... which might be
            expected to round upwards to $66.67 but it does not
            because the int cast truncates the result.  Be aware
            of this and decide whether it's suitable for your
            application.
        """
        if isinstance(other, CentCount):
            raise TypeError("can not multiply monetary quantities")
        else:
            return CentCount(
                centcount=int(self.centcount * float(other)),
                currency=self.currency,
            )

    def __truediv__(self, other):
        """
        .. note::

            Multiplication and division are performed by converting the
            CentCount into a float and operating on two floating point
            numbers.  But the result is then cast back to an int which
            loses precision beyond the 1-cent granularity in order to
            avoid floating point representation artifacts.

            This can cause "problems" such as the one illustrated
            below::

                >>> c = CentCount(100.00)
                >>> c = c * 2
                >>> c = c / 3
                >>> c
                66.66 USD

            Two-thirds of $100.00 is $66.66666... which might be
            expected to round upwards to $66.67 but it does not
            because the int cast truncates the result.  Be aware
            of this and decide whether it's suitable for your
            application.
        """
        if isinstance(other, CentCount):
            raise TypeError("can not divide monetary quantities")
        else:
            return CentCount(
                centcount=int(float(self.centcount) / float(other)),
                currency=self.currency,
            )

    def __int__(self):
        return self.centcount.__int__()

    def __float__(self):
        return self.centcount.__float__() / 100.0

    __radd__ = __add__

    def __rsub__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return CentCount(
                    centcount=other.centcount - self.centcount,
                    currency=self.currency,
                )
            else:
                raise TypeError("Incompatible currencies in sub expression")
        else:
            if self.strict_mode:
                raise TypeError("In strict_mode only two moneys can be added")
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
                raise TypeError("can not directly compare different currencies")
        else:
            if self.strict_mode:
                raise TypeError("In strict mode, only two CentCounts can be compated")
            else:
                return self.centcount < int(other)

    def __gt__(self, other):
        if isinstance(other, CentCount):
            if self.currency == other.currency:
                return self.centcount > other.centcount
            else:
                raise TypeError("can not directly compare different currencies")
        else:
            if self.strict_mode:
                raise TypeError("In strict mode, only two CentCounts can be compated")
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
        chunks = s.split(" ")
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
            return (centcount, "USD")
        return None

    @classmethod
    def parse(cls, s: str) -> "CentCount":
        """Parses a string format monetary amount and returns a CentCount
        if possible.

        Args:
            s: the string to be parsed
        """
        chunks = CentCount._parse(s)
        if chunks is not None:
            return CentCount(chunks[0], chunks[1])
        raise Exception(f'Unable to parse money string "{s}"')


if __name__ == "__main__":
    import doctest

    doctest.testmod()
