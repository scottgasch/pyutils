#!/usr/bin/env python3

"""This is an augmented interval tree for storing ranges and identifying overlaps as
described by: https://en.wikipedia.org/wiki/Interval_tree.
"""

from __future__ import annotations

from functools import total_ordering
from typing import Any, Optional, Union

from overrides import overrides

from pyutils.collectionz import bst

Numeric = Union[int, float]


@total_ordering
class NumericRange(object):
    def __init__(self, low: Numeric, high: Numeric):
        if low > high:
            temp: Numeric = low
            low = high
            high = temp
        self.low: Numeric = low
        self.high: Numeric = high
        self.highest_in_subtree: Numeric = high

    def __lt__(self, other: NumericRange) -> bool:
        return self.low < other.low

    @overrides
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NumericRange):
            return False
        return self.low == other.low and self.high == other.high

    def overlaps_with(self, other: NumericRange) -> bool:
        return self.low <= other.high and self.high >= other.low

    def __repr__(self) -> str:
        return f"{self.low}..{self.high}"


class AugmentedIntervalTree(bst.BinarySearchTree):
    def __init__(self):
        super().__init__()

    @staticmethod
    def assert_value_must_be_range(value: Any) -> None:
        if not isinstance(value, NumericRange):
            raise Exception(
                "AugmentedIntervalTree expects to use NumericRanges, see bst for a "
                + "general purpose tree usable for other types."
            )

    @overrides
    def _on_insert(self, parent: Optional[bst.Node], new: bst.Node) -> None:
        AugmentedIntervalTree.assert_value_must_be_range(new.value)
        for ancestor in self.parent_path(new):
            assert ancestor
            if new.value.high > ancestor.value.highest_in_subtree:
                ancestor.value.highest_in_subtree = new.value.high

    @overrides
    def _on_delete(self, parent: Optional[bst.Node], deleted: bst.Node) -> None:
        if parent:
            new_highest_candidates = []
            if deleted.left:
                new_highest_candidates.append(deleted.left.value.highest_in_subtree)
            if deleted.right:
                new_highest_candidates.append(deleted.right.value.highest_in_subtree)
            if len(new_highest_candidates):
                parent.value.highest_in_subtree = max(
                    parent.value.high, max(new_highest_candidates)
                )
            else:
                parent.value.highest_in_subtree = parent.value.high

    def find_overlaps(self, x: NumericRange):
        """Yields ranges previously added to the tree that x overlaps with.

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
        >>> for x in tree.find_overlaps(NumericRange(19, 21)):
        ...     print(x)
        20..24
        18..22
        1..30
        16..28
        21..27
        """
        if self.root is None:
            return
        yield from self._find_overlaps(self.root, x)

    def _find_overlaps(self, root: bst.Node, x: NumericRange):
        """It's known that two intervals A and B overlap only
        when both A.low <= B.high and A.high >= B.low.  When
        searching the trees for nodes overlapping with a given
        interval, we can immediately skip:

            * all nodes to the right of nodes whose low value is past
              the end of the given interval and
            * all nodes that have their maximum high value below the
              start of the given interval.
        """
        if root is None:
            return

        if root.value.overlaps_with(x):
            yield root.value

        if root.left:
            if root.left.value.highest_in_subtree >= x.low:
                yield from self._find_overlaps(root.left, x)

        if root.value.low <= x.high:
            if root.right:
                yield from self._find_overlaps(root.right, x)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
