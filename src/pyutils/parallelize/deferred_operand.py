#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This is the base class of
:class:`pyutils.parallelize.smart_future.SmartFuture`, which is a
piece of the simple parallelization framework.

This base class is essentially tries to have every Python `__dunder__`
method defined with a reasonabe default implementation so that, when
it is used in a manner that requires the value to be known, it calls
:meth:`DeferredOperand.resolve` and either gets the requisite value or
blocks until the data necessary to resolve the value is ready.  This
is meant to enable more transparent :class:`Future` objects that can
be just used directly.

See :class:`pyutils.parallelize.smart_future.SmartFuture` for more
information.

"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Set, TypeVar

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

T = TypeVar('T')


class DeferredOperand(ABC, Generic[T]):
    """A wrapper around an operand whose value is deferred until it is
    needed (i.e. accessed).  See the subclass
    :class:`pyutils.parallelize.smart_future.SmartFuture` for an
    example usage and/or a more useful patten.
    """

    def __init__(self, local_attributes: Set[str] = None):
        """
        Args:
            local_attributes: because this class attempts to act as a
                transparent wrapper around a normal Future, it needs
                to be able to differentiate between attempts to set a
                property of it/its subclasses or the wrapped object.
                The local_attributes argument is a set of names that,
                if we intercept a set operation for, refer to an
                attribute in the wrapper and not the wrapped class.
        """
        self.__dict__['local_attributes'] = local_attributes

    @abstractmethod
    def _resolve(self, timeout=None) -> T:
        pass

    @staticmethod
    def resolve(x: Any) -> Any:
        """
        When this object is used in a manner that requires it to know
        its value, this method is called to either return the value or
        block until it can do so.

        Args:
            x: the object whose value is required

        Returns:
            The value of x... immediately if possible, eventually if
            not possible.
        """
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

    def __getattr__(self, name):
        return getattr(DeferredOperand.resolve(self), name)

    def __setattr__(self, name, value):
        # subclass setting its own properties
        if name in self.local_attributes:
            object.__setattr__(self, name, value)
            return

        # otherwise operate on the wrapped result
        DeferredOperand.resolve(self).__setattr__(name, value)

    def __delattr__(self, name):
        return delattr(DeferredOperand.resolve(self), name)

    def __dir__(self):
        return dir(DeferredOperand.resolve(self))
