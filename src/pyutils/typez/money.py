#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""A class to represent money.  See also centcount.py"""

import re
from decimal import Decimal
from typing import Optional, Tuple

from pyutils import math_utils


class Money(object):
    """A class for representing monetary amounts potentially with
    different currencies.
    """

    def __init__(
        self,
        amount: Decimal = Decimal("0"),
        currency: str = 'USD',
        *,
        strict_mode=False,
    ):
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
        a = float(self.amount)
        a = round(a, 2)
        s = f'{a:,.2f}'
        if self.currency is not None:
            return f'{s} {self.currency}'
        else:
            return f'${s}'

    def __pos__(self):
        return Money(amount=self.amount, currency=self.currency)

    def __neg__(self):
        return Money(amount=-self.amount, currency=self.currency)

    def __add__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return Money(amount=self.amount + other.amount, currency=self.currency)
            else:
                raise TypeError('Incompatible currencies in add expression')
        else:
            if self.strict_mode:
                raise TypeError('In strict_mode only two moneys can be added')
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
                raise TypeError('Incompatible currencies in add expression')
        else:
            if self.strict_mode:
                raise TypeError('In strict_mode only two moneys can be added')
            else:
                return Money(
                    amount=self.amount - Decimal(float(other)),
                    currency=self.currency,
                )

    def __mul__(self, other):
        if isinstance(other, Money):
            raise TypeError('can not multiply monetary quantities')
        else:
            return Money(
                amount=self.amount * Decimal(float(other)),
                currency=self.currency,
            )

    def __truediv__(self, other):
        if isinstance(other, Money):
            raise TypeError('can not divide monetary quantities')
        else:
            return Money(
                amount=self.amount / Decimal(float(other)),
                currency=self.currency,
            )

    def __float__(self):
        return self.amount.__float__()

    def truncate_fractional_cents(self):
        x = float(self)
        self.amount = Decimal(math_utils.truncate_float(x))
        return self.amount

    def round_fractional_cents(self):
        x = float(self)
        self.amount = Decimal(round(x, 2))
        return self.amount

    __radd__ = __add__

    def __rsub__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return Money(amount=other.amount - self.amount, currency=self.currency)
            else:
                raise TypeError('Incompatible currencies in sub expression')
        else:
            if self.strict_mode:
                raise TypeError('In strict_mode only two moneys can be added')
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
                raise TypeError('can not directly compare different currencies')
        else:
            if self.strict_mode:
                raise TypeError('In strict mode, only two Moneys can be compated')
            else:
                return self.amount < Decimal(float(other))

    def __gt__(self, other):
        if isinstance(other, Money):
            if self.currency == other.currency:
                return self.amount > other.amount
            else:
                raise TypeError('can not directly compare different currencies')
        else:
            if self.strict_mode:
                raise TypeError('In strict mode, only two Moneys can be compated')
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
        chunks = s.split(' ')
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
            return (amount, 'USD')
        return None

    @classmethod
    def parse(cls, s: str) -> 'Money':
        chunks = Money._parse(s)
        if chunks is not None:
            return Money(chunks[0], chunks[1])
        raise Exception(f'Unable to parse money string "{s}"')
