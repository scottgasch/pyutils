#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A binary search tree implementation."""

from typing import Any, Generator, List, Optional


class Node(object):
    def __init__(self, value: Any) -> None:
        """
        A BST node.  Note that value can be anything as long as it
        is comparable.  Check out :meth:`functools.total_ordering`
        (https://docs.python.org/3/library/functools.html#functools.total_ordering)

        Args:
            value: a reference to the value of the node.
        """
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None
        self.value = value


class BinarySearchTree(object):
    def __init__(self):
        self.root = None
        self.count = 0
        self.traverse = None

    def get_root(self) -> Optional[Node]:
        """
        Returns:
            The root of the BST
        """

        return self.root

    def _on_insert(self, parent: Optional[Node], new: Node) -> None:
        """This is called immediately _after_ a new node is inserted."""
        pass

    def insert(self, value: Any) -> None:
        """
        Insert something into the tree.

        Args:
            value: the value to be inserted.

        >>> t = BinarySearchTree()
        >>> t.insert(10)
        >>> t.insert(20)
        >>> t.insert(5)
        >>> len(t)
        3

        >>> t.get_root().value
        10

        """
        if self.root is None:
            self.root = Node(value)
            self.count = 1
            self._on_insert(None, self.root)
        else:
            self._insert(value, self.root)

    def _insert(self, value: Any, node: Node):
        """Insertion helper"""
        if value < node.value:
            if node.left is not None:
                self._insert(value, node.left)
            else:
                node.left = Node(value)
                self.count += 1
                self._on_insert(node, node.left)
        else:
            if node.right is not None:
                self._insert(value, node.right)
            else:
                node.right = Node(value)
                self.count += 1
                self._on_insert(node, node.right)

    def __getitem__(self, value: Any) -> Optional[Node]:
        """
        Find an item in the tree and return its Node.  Returns
        None if the item is not in the tree.

        >>> t = BinarySearchTree()
        >>> t[99]

        >>> t.insert(10)
        >>> t.insert(20)
        >>> t.insert(5)
        >>> t[10].value
        10

        >>> t[99]

        """
        if self.root is not None:
            return self._find(value, self.root)
        return None

    def _find(self, value: Any, node: Node) -> Optional[Node]:
        """Find helper"""
        if value == node.value:
            return node
        elif value < node.value and node.left is not None:
            return self._find(value, node.left)
        elif value > node.value and node.right is not None:
            return self._find(value, node.right)
        return None

    def _parent_path(
        self, current: Optional[Node], target: Node
    ) -> List[Optional[Node]]:
        """Internal helper"""
        if current is None:
            return [None]
        ret: List[Optional[Node]] = [current]
        if target.value == current.value:
            return ret
        elif target.value < current.value:
            ret.extend(self._parent_path(current.left, target))
            return ret
        else:
            assert target.value > current.value
            ret.extend(self._parent_path(current.right, target))
            return ret

    def parent_path(self, node: Node) -> List[Optional[Node]]:
        """Get a node's parent path.

        Args:
            node: the node to check

        Returns:
            a list of nodes representing the path from
            the tree's root to the node.

        .. note::

            If the node does not exist in the tree, the last element
            on the path will be None but the path will indicate the
            ancestor path of that node were it to be inserted.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(12)
        >>> t.insert(33)
        >>> t.insert(4)
        >>> t.insert(88)
        >>> t
        50
        ├──25
        │  ├──12
        │  │  └──4
        │  └──33
        └──75
           └──88

        >>> n = t[4]
        >>> for x in t.parent_path(n):
        ...     print(x.value)
        50
        25
        12
        4

        >>> del t[4]
        >>> for x in t.parent_path(n):
        ...     if x is not None:
        ...         print(x.value)
        ...     else:
        ...         print(x)
        50
        25
        12
        None

        """
        return self._parent_path(self.root, node)

    def __delitem__(self, value: Any) -> bool:
        """
        Delete an item from the tree and preserve the BST property.

        Args:
            value: the value of the node to be deleted.

        Returns:
            True if the value was found and its associated node was
            successfully deleted and False otherwise.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)
        >>> t.insert(85)
        >>> t
        50
        ├──25
        │  └──22
        │     └──13
        └──75
           ├──66
           └──85

        >>> for value in t.iterate_inorder():
        ...     print(value)
        13
        22
        25
        50
        66
        75
        85

        >>> del t[22]  # Note: bool result is discarded

        >>> for value in t.iterate_inorder():
        ...     print(value)
        13
        25
        50
        66
        75
        85

        >>> t.__delitem__(13)
        True
        >>> for value in t.iterate_inorder():
        ...     print(value)
        25
        50
        66
        75
        85

        >>> t.__delitem__(75)
        True
        >>> for value in t.iterate_inorder():
        ...     print(value)
        25
        50
        66
        85
        >>> t
        50
        ├──25
        └──85
           └──66

        >>> t.__delitem__(99)
        False

        """
        if self.root is not None:
            ret = self._delete(value, None, self.root)
            if ret:
                self.count -= 1
                if self.count == 0:
                    self.root = None
            return ret
        return False

    def _on_delete(self, parent: Optional[Node], deleted: Node) -> None:
        """This is called just after deleted was deleted from the tree"""
        pass

    def _delete(self, value: Any, parent: Optional[Node], node: Node) -> bool:
        """Delete helper"""
        if node.value == value:

            # Deleting a leaf node
            if node.left is None and node.right is None:
                if parent is not None:
                    if parent.left == node:
                        parent.left = None
                    else:
                        assert parent.right == node
                        parent.right = None
                self._on_delete(parent, node)
                return True

            # Node only has a right.
            elif node.left is None:
                assert node.right is not None
                if parent is not None:
                    if parent.left == node:
                        parent.left = node.right
                    else:
                        assert parent.right == node
                        parent.right = node.right
                self._on_delete(parent, node)
                return True

            # Node only has a left.
            elif node.right is None:
                assert node.left is not None
                if parent is not None:
                    if parent.left == node:
                        parent.left = node.left
                    else:
                        assert parent.right == node
                        parent.right = node.left
                self._on_delete(parent, node)
                return True

            # Node has both a left and right.
            else:
                assert node.left is not None and node.right is not None
                descendent = node.right
                while descendent.left is not None:
                    descendent = descendent.left
                node.value = descendent.value
                return self._delete(node.value, node, node.right)
        elif value < node.value and node.left is not None:
            return self._delete(value, node, node.left)
        elif value > node.value and node.right is not None:
            return self._delete(value, node, node.right)
        return False

    def __len__(self):
        """
        Returns:
            The count of items in the tree.

        >>> t = BinarySearchTree()
        >>> len(t)
        0
        >>> t.insert(50)
        >>> len(t)
        1
        >>> t.__delitem__(50)
        True
        >>> len(t)
        0
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)
        >>> t.insert(85)
        >>> len(t)
        6

        """
        return self.count

    def __contains__(self, value: Any) -> bool:
        """
        Returns:
            True if the item is in the tree; False otherwise.
        """
        return self.__getitem__(value) is not None

    def _iterate_preorder(self, node: Node):
        yield node.value
        if node.left is not None:
            yield from self._iterate_preorder(node.left)
        if node.right is not None:
            yield from self._iterate_preorder(node.right)

    def _iterate_inorder(self, node: Node):
        if node.left is not None:
            yield from self._iterate_inorder(node.left)
        yield node.value
        if node.right is not None:
            yield from self._iterate_inorder(node.right)

    def _iterate_postorder(self, node: Node):
        if node.left is not None:
            yield from self._iterate_postorder(node.left)
        if node.right is not None:
            yield from self._iterate_postorder(node.right)
        yield node.value

    def iterate_preorder(self):
        """
        Returns:
            A Generator that yields the tree's items in a
            preorder traversal sequence.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)

        >>> for value in t.iterate_preorder():
        ...     print(value)
        50
        25
        22
        13
        75
        66

        """
        if self.root is not None:
            yield from self._iterate_preorder(self.root)

    def iterate_inorder(self):
        """
        Returns:
            A Generator that yield the tree's items in a preorder
            traversal sequence.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)
        >>> t.insert(24)
        >>> t
        50
        ├──25
        │  └──22
        │     ├──13
        │     └──24
        └──75
           └──66

        >>> for value in t.iterate_inorder():
        ...     print(value)
        13
        22
        24
        25
        50
        66
        75

        """
        if self.root is not None:
            yield from self._iterate_inorder(self.root)

    def iterate_postorder(self):
        """
        Returns:
            A Generator that yield the tree's items in a preorder
            traversal sequence.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)

        >>> for value in t.iterate_postorder():
        ...     print(value)
        13
        22
        25
        66
        75
        50

        """
        if self.root is not None:
            yield from self._iterate_postorder(self.root)

    def _iterate_leaves(self, node: Node):
        if node.left is not None:
            yield from self._iterate_leaves(node.left)
        if node.right is not None:
            yield from self._iterate_leaves(node.right)
        if node.left is None and node.right is None:
            yield node.value

    def iterate_leaves(self):
        """
        Returns:
            A Gemerator that yielde only the leaf nodes in the
            tree.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)

        >>> for value in t.iterate_leaves():
        ...     print(value)
        13
        66

        """
        if self.root is not None:
            yield from self._iterate_leaves(self.root)

    def _iterate_by_depth(self, node: Node, depth: int):
        if depth == 0:
            yield node.value
        else:
            assert depth > 0
            if node.left is not None:
                yield from self._iterate_by_depth(node.left, depth - 1)
            if node.right is not None:
                yield from self._iterate_by_depth(node.right, depth - 1)

    def iterate_nodes_by_depth(self, depth: int) -> Generator[Node, None, None]:
        """
        Args:
            depth: the desired depth

        Returns:
            A Generator that yields nodes at the prescribed depth in
            the tree.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)

        >>> for value in t.iterate_nodes_by_depth(2):
        ...     print(value)
        22
        66

        >>> for value in t.iterate_nodes_by_depth(3):
        ...     print(value)
        13

        """
        if self.root is not None:
            yield from self._iterate_by_depth(self.root, depth)

    def get_next_node(self, node: Node) -> Node:
        """
        Args:
            node: the node whose next greater successor is desired

        Returns:
            Given a tree node, returns the next greater node in the tree.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(75)
        >>> t.insert(25)
        >>> t.insert(66)
        >>> t.insert(22)
        >>> t.insert(13)
        >>> t.insert(23)
        >>> t
        50
        ├──25
        │  └──22
        │     ├──13
        │     └──23
        └──75
           └──66

        >>> n = t[23]
        >>> t.get_next_node(n).value
        25

        >>> n = t[50]
        >>> t.get_next_node(n).value
        66

        """
        if node.right is not None:
            x = node.right
            while x.left is not None:
                x = x.left
            return x

        path = self.parent_path(node)
        assert path[-1] is not None
        assert path[-1] == node
        path = path[:-1]
        path.reverse()
        for ancestor in path:
            assert ancestor is not None
            if node != ancestor.right:
                return ancestor
            node = ancestor
        raise Exception()

    def _depth(self, node: Node, sofar: int) -> int:
        depth_left = sofar + 1
        depth_right = sofar + 1
        if node.left is not None:
            depth_left = self._depth(node.left, sofar + 1)
        if node.right is not None:
            depth_right = self._depth(node.right, sofar + 1)
        return max(depth_left, depth_right)

    def depth(self) -> int:
        """
        Returns:
            The max height (depth) of the tree in plies (edge distance
            from root).

        >>> t = BinarySearchTree()
        >>> t.depth()
        0

        >>> t.insert(50)
        >>> t.depth()
        1

        >>> t.insert(65)
        >>> t.depth()
        2

        >>> t.insert(33)
        >>> t.depth()
        2

        >>> t.insert(2)
        >>> t.insert(1)
        >>> t.depth()
        4

        """
        if self.root is None:
            return 0
        return self._depth(self.root, 0)

    def height(self) -> int:
        """Returns the height (i.e. max depth) of the tree"""
        return self.depth()

    def repr_traverse(
        self,
        padding: str,
        pointer: str,
        node: Optional[Node],
        has_right_sibling: bool,
    ) -> str:
        if node is not None:
            viz = f"\n{padding}{pointer}{node.value}"
            if has_right_sibling:
                padding += "│  "
            else:
                padding += "   "

            pointer_right = "└──"
            if node.right is not None:
                pointer_left = "├──"
            else:
                pointer_left = "└──"

            viz += self.repr_traverse(
                padding, pointer_left, node.left, node.right is not None
            )
            viz += self.repr_traverse(padding, pointer_right, node.right, False)
            return viz
        return ""

    def __repr__(self):
        """
        Returns:
            An ASCII string representation of the tree.

        >>> t = BinarySearchTree()
        >>> t.insert(50)
        >>> t.insert(25)
        >>> t.insert(75)
        >>> t.insert(12)
        >>> t.insert(33)
        >>> t.insert(88)
        >>> t.insert(55)
        >>> t
        50
        ├──25
        │  ├──12
        │  └──33
        └──75
           ├──55
           └──88
        """
        if self.root is None:
            return ""

        ret = f"{self.root.value}"
        pointer_right = "└──"
        if self.root.right is None:
            pointer_left = "└──"
        else:
            pointer_left = "├──"

        ret += self.repr_traverse(
            "", pointer_left, self.root.left, self.root.left is not None
        )
        ret += self.repr_traverse("", pointer_right, self.root.right, False)
        return ret


if __name__ == "__main__":
    import doctest

    doctest.testmod()
