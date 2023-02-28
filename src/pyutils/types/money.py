#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A class to represent money.  This class represents monetary amounts as Python Decimals
(see https://docs.python.org/3/library/decimal.html) internally.

The type guards against inadvertent aggregation of instances with
non-matching currencies, the division of one :class:`Money` by
another, and has a strict mode which disallows comparison or
aggregation with non-:class:`Money` operands (i.e. no comparison or
aggregation with literal numbers).

See also :class:`pyutils.types.centcount.CentCount` which represents
monetary amounts as an integral number of cents.
"""

import re
from decimal import ROUND_FLOOR, ROUND_HALF_DOWN, Decimal
from typing import Optional, Tuple, Union


class Money(object):
    """A class for representing monetary amounts potentially with
    different currencies.
    """

    def __init__(
        self,
        amount: Union[Decimal, str, float, int, "Money"] = Decimal("0"),
        currency: str = "USD",
        *,
        strict_mode=False,
    ):
        """
        Args:
            amount: the initial monetary amount to be represented; can be a
                Money, int, float, Decimal, str, etc...
            currency: if provided, indicates what currency this amount is
                units of and guards against operations such as attempting
                to aggregate Money instances with non-matching currencies
                directly.  If not provided defaults to "USD".
            strict_mode: if True, disallows comparison or arithmetic operations
                between Money instances and any non-Money types (e.g. literal
                numbers).
        """
        self.strict_mode = strict_mode
        if isinstance(amount, str):
            ret = Money._parse(amount)
            if ret is None:
                raise Exception(f'Unable to parse money string "{amount}"')
            amount = ret[0]
            currency = ret[1]
        if not isinstance(amount, Decimal):
            amount = Decimal(float(amount))
        self.amount = amount
        if not currency:
            self.currency: Optional[str] = None
        else:
            self.currency = currency

    def __repr__(self):
        q = Decimal(10) ** -2
        sign, digits, _ = self.amount.quantize(q).as_tuple()
        result = []
        digits = list(map(str, digits))
        build, nxt = result.append, digits.pop
        for i in range(2):
            build(nxt() if digits else "0")
        build(".")
        if not digits:
            build("0")
        i = 0
        while digits:
            build(nxt())
            i += 1
            if i == 3 and digits:
                i = 0
        if sign:
            build("-")
        if self.currency:
            return "".join(reversed(result)) + " " + self.currency
        else:
            return "$" + "".join(reversed(result))

    def __pos__(self):
        return Money(amount=self.amount, currency=self.currency)

    def __neg__(self):
        return Money(amount=-self.amount, currency=self.currency)

    def __add__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return Money(amount=self.amount + other.amount, currency=self.currency)
            else:
                raise TypeError("Incompatible currencies in add expression")
        else:
            if self.strict_mode:
                raise TypeError("In strict_mode only two moneys can be added")
            else:
                return Money(
                    amount=self.amount + Decimal(float(other)),
                    currency=self.currency,
                )

    def __sub__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return Money(amount=self.amount - other.amount, currency=self.currency)
            else:
                raise TypeError("Incompatible currencies in add expression")
        else:
            if self.strict_mode:
                raise TypeError("In strict_mode only two moneys can be added")
            else:
                return Money(
                    amount=self.amount - Decimal(float(other)),
                    currency=self.currency,
                )

    def __mul__(self, other):
        if isinstance(other, Money):
            raise TypeError("can not multiply monetary quantities")
        else:
            return Money(
                amount=self.amount * Decimal(float(other)),
                currency=self.currency,
            )

    def __truediv__(self, other):
        if isinstance(other, Money):
            raise TypeError("can not divide monetary quantities")
        else:
            return Money(
                amount=self.amount / Decimal(float(other)),
                currency=self.currency,
            )

    def __float__(self):
        return self.amount.__float__()

    def truncate_fractional_cents(self):
        """
        Truncates fractional cents being represented.  e.g.

        >>> m = Money(100.00)
        >>> m *= 2
        >>> m /= 3

        At this point the internal representation of `m` is a long
        `Decimal`:

        >>> m.amount
        Decimal('66.66666666666666666666666667')

        It will be rendered by `__repr__` reasonably:

        >>> m
        66.67 USD

        If you want to truncate this long decimal representation, this
        method will do that for you:

        >>> m.truncate_fractional_cents()
        Decimal('66.66')
        >>> m.amount
        Decimal('66.66')
        >>> m
        66.66 USD

        See also :meth:`round_fractional_cents`
        """
        self.amount = self.amount.quantize(Decimal(".01"), rounding=ROUND_FLOOR)
        return self.amount

    def round_fractional_cents(self):
        """
        Rounds fractional cents being represented.  e.g.

        >>> m = Money(100.00)
        >>> m *= 2
        >>> m /= 3

        At this point the internal representation of `m` is a long
        `Decimal`:

        >>> m.amount
        Decimal('66.66666666666666666666666667')

        It will be rendered by `__repr__` reasonably:

        >>> m
        66.67 USD

        If you want to round this long decimal representation, this
        method will do that for you:

        >>> m.round_fractional_cents()
        Decimal('66.67')
        >>> m.amount
        Decimal('66.67')
        >>> m
        66.67 USD

        See also :meth:`truncate_fractional_cents`
        """
        self.amount = self.amount.quantize(Decimal(".01"), rounding=ROUND_HALF_DOWN)
        return self.amount

    __radd__ = __add__

    def __rsub__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return Money(amount=other.amount - self.amount, currency=self.currency)
            else:
                raise TypeError("Incompatible currencies in sub expression")
        else:
            if self.strict_mode:
                raise TypeError("In strict_mode only two moneys can be added")
            else:
                return Money(
                    amount=Decimal(float(other)) - self.amount,
                    currency=self.currency,
                )

    __rmul__ = __mul__

    #
    # Override comparison operators to also compare currency.
    #
    def __eq__(self, other):
        if other is None:
            return False
        if isinstance(other, Money):
            return self.amount == other.amount and self.currency == other.currency
        if self.strict_mode:
            raise TypeError("In strict mode only two Moneys can be compared")
        else:
            return self.amount == Decimal(float(other))

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return self.amount < other.amount
            else:
                raise TypeError("can not directly compare different currencies")
        else:
            if self.strict_mode:
                raise TypeError("In strict mode, only two Moneys can be compated")
            else:
                return self.amount < Decimal(float(other))

    def __gt__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return self.amount > other.amount
            else:
                raise TypeError("can not directly compare different currencies")
        else:
            if self.strict_mode:
                raise TypeError("In strict mode, only two Moneys can be compated")
            else:
                return self.amount > Decimal(float(other))

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __hash__(self) -> int:
        return hash(self.__repr__)

    AMOUNT_RE = re.compile(r"^([+|-]?)(\d+)(\.\d+)$")
    CURRENCY_RE = re.compile(r"^[A-Z][A-Z][A-Z]$")

    @classmethod
    def _parse(cls, s: str) -> Optional[Tuple[Decimal, str]]:
        amount = None
        currency = None
        s = s.strip()
        chunks = s.split(" ")
        try:
            for chunk in chunks:
                if Money.AMOUNT_RE.match(chunk) is not None:
                    amount = Decimal(chunk)
                elif Money.CURRENCY_RE.match(chunk) is not None:
                    currency = chunk
        except Exception:
            pass
        if amount is not None and currency is not None:
            return (amount, currency)
        elif amount is not None:
            return (amount, "USD")
        return None

    @classmethod
    def parse(cls, s: str) -> "Money":
        """Parses a string an attempts to create a :class:`Money`
        instance.

        Args:
            s: the string to parse
        """
        chunks = Money._parse(s)
        if chunks is not None:
            return Money(chunks[0], chunks[1])
        raise Exception(f'Unable to parse money string "{s}"')


if __name__ == "__main__":
    import doctest

    doctest.testmod()
