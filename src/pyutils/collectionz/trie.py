#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This module contains the implementation of a Trie tree (or prefix
tree).  See: https://en.wikipedia.org/wiki/Trie.

It can be used with arbitrary sequences as keys and stores its values
in a tree with paths determined by the sequence determined by each
keys' sequences.  Thus, it can determine whether a given value is
contained in the tree via a simple traversal in :math:`O(n)` where n
is the number of steps in the item's sequence and can also check
whether a key-prefix is present in the tree in :math:`O(n)` time.

Given a node in the BST, it is easy to determine all items that are
stored beneath that node.  See examples below.

"""

import logging
from typing import Any, Dict, Generator, Sequence

logger = logging.getLogger(__name__)


class Trie(object):
    """
    This is a Trie class, see: https://en.wikipedia.org/wiki/Trie.

    It attempts to follow Pythonic container patterns.  See doctests
    for examples.
    """

    def __init__(self):
        """Create an empty trie."""
        self.root = {}
        self.end = "~END~"
        self.length = 0
        self.viz = ""
        self.content_generator: Generator[str] = None

    def insert(self, item: Sequence[Any]) -> None:
        """
        Insert an item into the trie.  Items are represented by a :class:`Sequence`
        where each item in the sequence describes a set in the path to the item.

        Args:
            item: the item to be inserted.

        >>> t = Trie()
        >>> t.insert('test')
        >>> t.__contains__('test')
        True
        """
        current = self.root
        for child in item:
            current = current.setdefault(child, {})
        current[self.end] = self.end
        self.length += 1

    def __contains__(self, item: Sequence[Any]) -> bool:
        """
        Checks whether an item is in the Trie.

        Args:
            item: the item whose presence is to be determined.

        Returns:
            True if `item` is present, False otherwise.

        >>> t = Trie()
        >>> t.insert('test')
        >>> t.__contains__('test')
        True
        >>> t.__contains__('testing')
        False
        >>> 'test' in t
        True
        """
        current = self.__traverse__(item)
        if current is None:
            return False
        else:
            return self.end in current

    def contains_prefix(self, item: Sequence[Any]):
        """
        Check whether a prefix is in the Trie.  The prefix may or may not
        be a full item.

        Args:
            item: the item describing the prefix to be checked.

        Returns:
            True if the prefix described by `item` is present, False otherwise.

        >>> t = Trie()
        >>> t.insert('tricycle')
        >>> t.contains_prefix('tri')
        True
        >>> t.contains_prefix('tricycle')
        True
        >>> t.contains_prefix('triad')
        False

        """
        current = self.__traverse__(item)
        return current is not None

    def __traverse__(self, item: Sequence[Any]):
        current = self.root
        for child in item:
            if child in current:
                current = current[child]
            else:
                return None
        return current

    def __getitem__(self, item: Sequence[Any]) -> Dict[Any, Any]:
        """Given an item, return its trie node which contains all
        of the successor (child) node pointers.  If the item is not
        a node in the Trie, raise a KeyError.

        Args:
            item: the item whose node is to be retrieved

        Returns:
            A mapping that represents item in the trie.  If the
            keyspace of the mapping includes '~END~' a valid item
            ends at the node.  If the mapping contains other keys,
            each key indicates the presence of one or more children
            on the edge below the node.

        Raises:
            KeyError if item is not present in the trie.

        >>> t = Trie()
        >>> t.insert('test')
        >>> t.insert('testicle')
        >>> t.insert('tessera')
        >>> t.insert('tesack')
        >>> t['tes']
        {'t': {'~END~': '~END~', 'i': {'c': {'l': {'e': {'~END~': '~END~'}}}}}, 's': {'e': {'r': {'a': {'~END~': '~END~'}}}}, 'a': {'c': {'k': {'~END~': '~END~'}}}}

        """
        ret = self.__traverse__(item)
        if ret is None:
            raise KeyError(f"Node '{item}' is not in the trie")
        return ret

    def delete_recursively(self, node: Dict[Any, Any], item: Sequence[Any]) -> bool:
        """
        Deletes an item from the trie by walking the path from root to where it
        ends.

        Args:
            node: root under which to search for item
            item: item whose node is the root of the recursive deletion operation

        Returns:
            True if the item was not the prefix of another item such that there
            is nothing below item remaining anymore post delete and False if the
            deleted item was a proper prefix of another item in the tree such that
            there is still data below item remaining in the tree.
        """
        if len(item) == 1:
            del node[item]
            if len(node) == 0 and node is not self.root:
                del node
                return True
            return False
        else:
            car = item[0]
            cdr = item[1:]
            lower = node[car]
            ret = self.delete_recursively(lower, cdr)
            ret = ret and self.delete_recursively(node, car)
            return ret

    def __delitem__(self, item: Sequence[Any]):
        """
        Delete an item from the Trie.

        Args:
            item: the item to be deleted.

        >>> t = Trie()
        >>> t.insert('test')
        >>> t.insert('tess')
        >>> t.insert('tessel')
        >>> len(t)
        3
        >>> t.root
        {'t': {'e': {'s': {'t': {'~END~': '~END~'}, 's': {'~END~': '~END~', 'e': {'l': {'~END~': '~END~'}}}}}}}
        >>> t.__delitem__('test')
        >>> len(t)
        2
        >>> t.root
        {'t': {'e': {'s': {'s': {'~END~': '~END~', 'e': {'l': {'~END~': '~END~'}}}}}}}
        >>> for x in t:
        ...     print(x)
        tess
        tessel
        >>> t.__delitem__('tessel')
        >>> len(t)
        1
        >>> t.root
        {'t': {'e': {'s': {'s': {'~END~': '~END~'}}}}}
        >>> for x in t:
        ...     print(x)
        tess
        >>> t.__delitem__('tess')
        >>> len(t)
        0
        >>> t.length
        0
        >>> t.root
        {}
        >>> t.insert('testy')
        >>> t.length
        1
        >>> len(t)
        1
        """
        if item not in self:
            raise KeyError(f"Node '{item}' is not in the trie")
        self.delete_recursively(self.root, item)
        self.length -= 1

    def __len__(self):
        """
        Returns:
            A count of the trie's item population.

        >>> t = Trie()
        >>> len(t)
        0
        >>> t.insert('test')
        >>> len(t)
        1
        >>> t.insert('tree')
        >>> len(t)
        2
        """
        return self.length

    def __iter__(self):
        self.content_generator = self.generate_recursively(self.root, "")
        return self

    def generate_recursively(self, node, path: Sequence[Any]):
        """
        Returns:
            A generator that yields the trie's items one at a time.

        >>> t = Trie()
        >>> t.insert('test')
        >>> t.insert('tickle')
        >>> for item in t.generate_recursively(t.root, ''):
        ...     print(item)
        test
        tickle

        """
        for child in node:
            if child == self.end:
                yield path
            else:
                yield from self.generate_recursively(node[child], path + child)

    def __next__(self):
        """
        Iterate through the contents of the trie.

        >>> t = Trie()
        >>> t.insert('test')
        >>> t.insert('tickle')
        >>> for item in t:
        ...     print(item)
        test
        tickle

        """
        ret = next(self.content_generator)
        if ret is not None:
            return ret
        raise StopIteration

    def successors(self, item: Sequence[Any]):
        """
        Returns:
            A list of the successors of an item.

        >>> t = Trie()
        >>> t.insert('what')
        >>> t.insert('who')
        >>> t.insert('when')
        >>> t.successors('wh')
        ['a', 'o', 'e']

        >>> u = Trie()
        >>> u.insert(['this', 'is', 'a', 'test'])
        >>> u.insert(['this', 'is', 'a', 'robbery'])
        >>> u.insert(['this', 'is', 'a', 'walrus'])
        >>> u.successors(['this', 'is', 'a'])
        ['test', 'robbery', 'walrus']
        """
        node = self.__traverse__(item)
        if node is None:
            return None
        return [x for x in node if x != self.end]

    def _repr_fancy(
        self,
        padding: str,
        pointer: str,
        node: Any,
        has_sibling: bool,
    ) -> str:
        """
        Helper that return a fancy representation of the Trie, used by
        :meth:`__repr__`.
        """
        if node is None:
            return ""
        if node is not self.root:
            ret = f"\n{padding}{pointer}"
            if has_sibling:
                padding += "│  "
            else:
                padding += "   "
        else:
            ret = f"{pointer}"

        child_count = 0
        for child in node:
            if child != self.end:
                child_count += 1

        for child in node:
            if child != self.end:
                if child_count > 1:
                    pointer = "├──"
                    has_sibling = True
                else:
                    pointer = "└──"
                    has_sibling = False
                pointer += f"{child}"
                child_count -= 1
                ret += self._repr_fancy(padding, pointer, node[child], has_sibling)
        return ret

    def repr_brief(self, node: Dict[Any, Any], delimiter: str):
        """
        A friendly string representation of the contents of the Trie.

        Args:
            node: the root of the trie to represent.
            delimiter: character or string to stuff between edges.

        Returns:
            A brief string representation of the trie.  See example.

        >>> t = Trie()
        >>> t.insert([10, 0, 0, 1])
        >>> t.insert([10, 0, 0, 2])
        >>> t.insert([10, 10, 10, 1])
        >>> t.insert([10, 10, 10, 2])
        >>> t.repr_brief(t.root, '.')
        '10.[0.0.[1,2],10.10.[1,2]]'

        """
        child_count = 0
        my_rep = ""
        for child in node:
            if child != self.end:
                child_count += 1
                child_rep = self.repr_brief(node[child], delimiter)
                if len(child_rep) > 0:
                    my_rep += str(child) + delimiter + child_rep + ","
                else:
                    my_rep += str(child) + ","
        if len(my_rep) > 1:
            my_rep = my_rep[:-1]
        if child_count > 1:
            my_rep = f"[{my_rep}]"
        return my_rep

    def __repr__(self):
        """
        A friendly string representation of the contents of the Trie.  Under
        the covers uses _repr_fancy.

        >>> t = Trie()
        >>> t.insert([10, 0, 0, 1])
        >>> t.insert([10, 0, 0, 2])
        >>> t.insert([10, 10, 10, 1])
        >>> t.insert([10, 10, 10, 2])
        >>> print(t)
        *
        └──10
           ├──0
           │  └──0
           │     ├──1
           │     └──2
           └──10
              └──10
                 ├──1
                 └──2

        """
        return self._repr_fancy("", "*", self.root, False)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
