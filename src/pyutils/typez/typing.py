#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""My type hints."""

from abc import abstractmethod
from typing import Any, Protocol


class Comparable(Protocol):
    """Anything that implements basic comparison methods such that it
    can be compared to other instances of the same type.

    Check out :meth:`functools.total_ordering`
    (https://docs.python.org/3/library/functools.html#functools.total_ordering)
    for an easy way to make your type comparable.
    """

    @abstractmethod
    def __lt__(self, other: Any) -> bool:
        ...

    @abstractmethod
    def __le__(self, other: Any) -> bool:
        ...

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        ...
