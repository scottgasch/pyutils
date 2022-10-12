#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""This is a helper class that tries to define every __dunder__ method
so as to defer that evaluation of an object as long as possible.  It
is used by smart_future.py as a base class.

"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

T = TypeVar('T')


class DeferredOperand(ABC, Generic[T]):
    """A wrapper around an operand whose value is deferred until it is
    needed (i.e. accessed).  See the subclass :class:`SmartFuture` for
    an example usage and/or a more useful patten.
    """

    @abstractmethod
    def _resolve(self, timeout=None) -> T:
        pass

    @staticmethod
    def resolve(x: Any) -> Any:
        while isinstance(x, DeferredOperand):
            x = x._resolve()
        return x

    def __lt__(self, other: Any) -> bool:
        return DeferredOperand.resolve(self) < DeferredOperand.resolve(other)

    def __le__(self, other: Any) -> bool:
        return DeferredOperand.resolve(self) <= DeferredOperand.resolve(other)

    def __eq__(self, other: Any) -> bool:
        return DeferredOperand.resolve(self) == DeferredOperand.resolve(other)

    def __ne__(self, other: Any) -> bool:
        return DeferredOperand.resolve(self) != DeferredOperand.resolve(other)

    def __gt__(self, other: Any) -> bool:
        return DeferredOperand.resolve(self) > DeferredOperand.resolve(other)

    def __ge__(self, other: Any) -> bool:
        return DeferredOperand.resolve(self) >= DeferredOperand.resolve(other)

    def __not__(self) -> bool:
        return not DeferredOperand.resolve(self)

    def bool(self) -> bool:
        return DeferredOperand.resolve(self)

    def __add__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) + DeferredOperand.resolve(other)

    def __iadd__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) + DeferredOperand.resolve(other)

    def __radd__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) + DeferredOperand.resolve(other)

    def __sub__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) - DeferredOperand.resolve(other)

    def __mul__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) * DeferredOperand.resolve(other)

    def __pow__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) ** DeferredOperand.resolve(other)

    def __truediv__(self, other: Any) -> Any:
        return DeferredOperand.resolve(self) / DeferredOperand.resolve(other)

    def __floordiv__(self, other: Any) -> T:
        return DeferredOperand.resolve(self) // DeferredOperand.resolve(other)

    def __contains__(self, other):
        return DeferredOperand.resolve(other) in DeferredOperand.resolve(self)

    def and_(self, other):
        return DeferredOperand.resolve(self) & DeferredOperand.resolve(other)

    def or_(self, other):
        return DeferredOperand.resolve(self) & DeferredOperand.resolve(other)

    def xor(self, other):
        return DeferredOperand.resolve(self) & DeferredOperand.resolve(other)

    def invert(self):
        return ~(DeferredOperand.resolve(self))

    def is_(self, other):
        return DeferredOperand.resolve(self) is DeferredOperand.resolve(other)

    def is_not(self, other):
        return DeferredOperand.resolve(self) is not DeferredOperand.resolve(other)

    def __abs__(self):
        return abs(DeferredOperand.resolve(self))

    def setitem(self, k, v):
        DeferredOperand.resolve(self)[DeferredOperand.resolve(k)] = v

    def delitem(self, k):
        del DeferredOperand.resolve(self)[DeferredOperand.resolve(k)]

    def getitem(self, k):
        return DeferredOperand.resolve(self)[DeferredOperand.resolve(k)]

    def lshift(self, other):
        return DeferredOperand.resolve(self) << DeferredOperand.resolve(other)

    def rshift(self, other):
        return DeferredOperand.resolve(self) >> DeferredOperand.resolve(other)

    def mod(self, other):
        return DeferredOperand.resolve(self) % DeferredOperand.resolve(other)

    def matmul(self, other):
        return DeferredOperand.resolve(self) @ DeferredOperand.resolve(other)

    def neg(self):
        return -(DeferredOperand.resolve(self))

    def pos(self):
        return +(DeferredOperand.resolve(self))

    def truth(self):
        return DeferredOperand.resolve(self)

    def __hash__(self):
        return DeferredOperand.resolve(self).__hash__()

    def __call__(self):
        return DeferredOperand.resolve(self)()

    def __iter__(self):
        return DeferredOperand.resolve(self).__iter__()

    def __repr__(self) -> str:
        return DeferredOperand.resolve(self).__repr__()

    def __bytes__(self) -> bytes:
        return DeferredOperand.resolve(self).__bytes__()

    def __int__(self) -> int:
        return int(DeferredOperand.resolve(self))

    def __float__(self) -> float:
        return float(DeferredOperand.resolve(self))

    def __getattr__(self, method_name):
        def method(*args, **kwargs):
            return getattr(DeferredOperand.resolve(self), method_name)(*args, **kwargs)

        return method
