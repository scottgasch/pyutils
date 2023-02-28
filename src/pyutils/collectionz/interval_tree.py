#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This is an augmented interval tree for storing ranges and identifying overlaps as
described by: https://en.wikipedia.org/wiki/Interval_tree.
"""

from __future__ import annotations

from functools import total_ordering
from typing import Any, Generator, Optional

from overrides import overrides

from pyutils.collectionz import bst
from pyutils.types.simple import Numeric


@total_ordering
class NumericRange(object):
    """Essentially a tuple of numbers denoting a range with some added
    helper methods on it."""

    def __init__(self, low: Numeric, high: Numeric):
        """Creates a NumericRange.

        Args:
            low: the lowest point in the range (inclusive).
            high: the highest point in the range (inclusive).

        .. warning::

            If low > high this code swaps the parameters and keeps the range
            rather than raising.

        """
        if low > high:
            temp: Numeric = low
            low = high
            high = temp
        self.low: Numeric = low
        self.high: Numeric = high
        self.highest_in_subtree: Numeric = high

    def __lt__(self, other: NumericRange) -> bool:
        """
        Returns:
            True is this range is less than (lower low) other, else False.
        """
        if self.low != other.low:
            return self.low < other.low
        else:
            return self.high < other.high

    @overrides
    def __eq__(self, other: object) -> bool:
        """
        Returns:
            True if this is the same range as other, else False.
        """
        if not isinstance(other, NumericRange):
            return False
        return self.low == other.low and self.high == other.high

    def overlaps_with(self, other: NumericRange) -> bool:
        """
        Returns:
            True if this NumericRange overlaps with other, else False.
        """
        return self.low <= other.high and self.high >= other.low

    def __repr__(self) -> str:
        return f"{self.low}..{self.high}"


class AugmentedIntervalTree(bst.BinarySearchTree):
    @staticmethod
    def _assert_value_must_be_range(value: Any) -> None:
        if not isinstance(value, NumericRange):
            raise Exception(
                "AugmentedIntervalTree expects to use NumericRanges, see bst for a "
                + "general purpose tree usable for other types."
            )

    @overrides
    def _on_insert(self, parent: Optional[bst.Node], new: bst.Node) -> None:
        AugmentedIntervalTree._assert_value_must_be_range(new.value)
        for ancestor in self.parent_path(new):
            assert ancestor
            if new.value.high > ancestor.value.highest_in_subtree:
                ancestor.value.highest_in_subtree = new.value.high

    @overrides
    def _on_delete(self, parent: Optional[bst.Node], deleted: bst.Node) -> None:
        if parent:
            new_highest_candidates = [parent.value.high]
            if parent.left:
                new_highest_candidates.append(parent.left.value.highest_in_subtree)
            if parent.right:
                new_highest_candidates.append(parent.right.value.highest_in_subtree)
            parent.value.highest_in_subtree = max(new_highest_candidates)

    def find_one_overlap(self, to_find: NumericRange) -> Optional[NumericRange]:
        """Identify and return one overlapping node from the tree.

        Args:
            to_find: the interval with which to find an overlap.

        Returns:
            An overlapping range from the tree or None if no such
            ranges exist in the tree at present.

        >>> tree = AugmentedIntervalTree()
        >>> tree.insert(NumericRange(20, 24))
        >>> tree.insert(NumericRange(18, 22))
        >>> tree.insert(NumericRange(14, 16))
        >>> tree.insert(NumericRange(1, 30))
        >>> tree.insert(NumericRange(25, 30))
        >>> tree.insert(NumericRange(29, 33))
        >>> tree.insert(NumericRange(5, 12))
        >>> tree.insert(NumericRange(1, 6))
        >>> tree.insert(NumericRange(13, 18))
        >>> tree.insert(NumericRange(16, 28))
        >>> tree.insert(NumericRange(21, 27))
        >>> tree.find_one_overlap(NumericRange(6, 7))
        1..30

        """
        return self._find_one_overlap(self.root, to_find)

    def _find_one_overlap(
        self, root: bst.Node, x: NumericRange
    ) -> Optional[NumericRange]:
        if root is None:
            return None

        if root.value.overlaps_with(x):
            return root.value

        if root.left:
            if root.left.value.highest_in_subtree >= x.low:
                return self._find_one_overlap(root.left, x)

        if root.right:
            return self._find_one_overlap(root.right, x)
        return None

    def find_all_overlaps(
        self, to_find: NumericRange
    ) -> Generator[NumericRange, None, None]:
        """Yields ranges previously added to the tree that overlaps with
        to_find argument.

        Args:
            to_find: the interval with which to find all overlaps.

        Returns:
            A (potentially empty) sequence of all ranges in the tree
            that overlap with the argument.

        >>> tree = AugmentedIntervalTree()
        >>> tree.insert(NumericRange(20, 24))
        >>> tree.insert(NumericRange(18, 22))
        >>> tree.insert(NumericRange(14, 16))
        >>> tree.insert(NumericRange(1, 30))
        >>> tree.insert(NumericRange(25, 30))
        >>> tree.insert(NumericRange(29, 33))
        >>> tree.insert(NumericRange(5, 12))
        >>> tree.insert(NumericRange(1, 6))
        >>> tree.insert(NumericRange(13, 18))
        >>> tree.insert(NumericRange(16, 28))
        >>> tree.insert(NumericRange(21, 27))
        >>> for x in tree.find_all_overlaps(NumericRange(19, 21)):
        ...     print(x)
        20..24
        18..22
        1..30
        16..28
        21..27

        >>> del tree[NumericRange(1, 30)]
        >>> for x in tree.find_all_overlaps(NumericRange(19, 21)):
        ...     print(x)
        20..24
        18..22
        16..28
        21..27

        """
        if self.root is None:
            return
        yield from self._find_all_overlaps(self.root, to_find)

    def _find_all_overlaps(
        self, root: bst.Node, x: NumericRange
    ) -> Generator[NumericRange, None, None]:
        if root is None:
            return None

        if root.value.overlaps_with(x):
            yield root.value

        if root.left:
            if root.left.value.highest_in_subtree >= x.low:
                yield from self._find_all_overlaps(root.left, x)

        if root.right:
            if root.right.value.highest_in_subtree >= x.low:
                yield from self._find_all_overlaps(root.right, x)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
