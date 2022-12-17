#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""A simple graph class that can be optionally directed and weighted and
some operations on it."""


from typing import Dict, Generator, List, Optional, Set

from pyutils.types.simple import Numeric


class Graph(object):
    def __init__(self, directed: bool = False):
        """Constructs a new Graph object.

        Args:
            directed: are we modeling a directed graph?  See :meth:`add_edge`.

        """
        self.directed = directed
        self.graph: Dict[str, Dict[str, Numeric]] = {}

    def add_vertex(self, vertex_id: str) -> bool:
        """Adds a new vertex to the graph.

        Args:
            vertex_id: the unique identifier of the new vertex.

        Returns:
            True unless vertex_id is already in the graph.

        >>> g = Graph()
        >>> g.add_vertex('a')
        True
        >>> g.add_vertex('b')
        True
        >>> g.add_vertex('a')
        False
        >>> len(g.get_vertices())
        2

        """
        if vertex_id not in self.graph:
            self.graph[vertex_id] = {}
            return True
        return False

    def add_edge(self, src: str, dest: str, weight: Numeric = 1) -> None:
        """Adds a new (optionally weighted) edge between src and dest
        vertexes.  If the graph is not directed (see c'tor) this also
        adds a reciprocal edge with the same weight back from dest to
        src too.

        .. note::

            If either or both of src and dest are not already added to
            the graph, they are implicitly added by adding this edge.

        Args:
            src: the source vertex id
            dest: the destination vertex id
            weight: optionally, the weight of the edge(s) added

        >>> g = Graph()
        >>> g.add_edge('a', 'b')
        >>> g.add_edge('b', 'c', weight=2)
        >>> len(g.get_vertices())
        3
        >>> g.get_edges()
        {'a': {'b': 1}, 'b': {'a': 1, 'c': 2}, 'c': {'b': 2}}

        """
        self.add_vertex(src)
        self.add_vertex(dest)
        self.graph[src][dest] = weight
        if not self.directed:
            self.graph[dest][src] = weight

    def get_vertices(self) -> List[str]:
        """
        Returns:
            a list of the vertex ids in the graph.

        >>> g = Graph()
        >>> g.add_vertex('a')
        True
        >>> g.add_edge('b', 'c')
        >>> g.get_vertices()
        ['a', 'b', 'c']
        """
        return list(self.graph.keys())

    def get_edges(self) -> Dict[str, Dict[str, Numeric]]:
        """
        Returns:
            A dict whose keys are source vertexes and values
            are dicts of destination vertexes with values describing the
            weight of the edge from source to destination.

        >>> g = Graph(directed=True)
        >>> g.add_edge('a', 'b')
        >>> g.add_edge('b', 'c', weight=2)
        >>> len(g.get_vertices())
        3
        >>> g.get_edges()
        {'a': {'b': 1}, 'b': {'c': 2}, 'c': {}}
        """
        return self.graph

    def _dfs(self, vertex: str, visited: Set[str]):
        yield vertex
        visited.add(vertex)
        for neighbor in self.graph[vertex]:
            if neighbor not in visited:
                yield from self._dfs(neighbor, visited)

    def dfs(
        self, starting_vertex: str, target: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Performs a depth first traversal of the graph.

        Args:
            starting_vertex: The DFS starting point.
            target: The vertex that, if found, indicates to halt.

        Returns:
            An ordered sequence of vertex ids visited by the traversal.

        .. graphviz::

            graph g {
                node [shape=record];
                A -- B -- D;
                A -- C -- D -- E -- F;
                F -- F;
                E -- G;
            }

        >>> g = Graph()
        >>> g.add_edge('A', 'B')
        >>> g.add_edge('A', 'C')
        >>> g.add_edge('B', 'D')
        >>> g.add_edge('C', 'D')
        >>> g.add_edge('D', 'E')
        >>> g.add_edge('E', 'F')
        >>> g.add_edge('E', 'G')
        >>> g.add_edge('F', 'F')
        >>> for node in g.dfs('A'):
        ...     print(node)
        A
        B
        D
        C
        E
        F
        G

        >>> for node in g.dfs('F', 'B'):
        ...     print(node)
        F
        E
        D
        B
        """
        visited: Set[str] = set()
        for node in self._dfs(starting_vertex, visited):
            yield node
            if node == target:
                return

    def bfs(
        self, starting_vertex: str, target: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Performs a breadth first traversal of the graph.

        Args:
            starting_vertex: The BFS starting point.
            target: The vertex that, if found, we should halt the search.

        Returns:
            An ordered sequence of vertex ids visited by the traversal.

        .. graphviz::

            graph g {
                node [shape=record];
                A -- B -- D;
                A -- C -- D -- E -- F;
                F -- F;
                E -- G;
            }

        >>> g = Graph()
        >>> g.add_edge('A', 'B')
        >>> g.add_edge('A', 'C')
        >>> g.add_edge('B', 'D')
        >>> g.add_edge('C', 'D')
        >>> g.add_edge('D', 'E')
        >>> g.add_edge('E', 'F')
        >>> g.add_edge('E', 'G')
        >>> g.add_edge('F', 'F')
        >>> for node in g.bfs('A'):
        ...     print(node)
        A
        B
        C
        D
        E
        F
        G

        >>> for node in g.bfs('F', 'G'):
        ...     print(node)
        F
        E
        D
        G
        """
        todo = []
        visited = set()

        todo.append(starting_vertex)
        visited.add(starting_vertex)

        while todo:
            vertex = todo.pop(0)
            yield vertex
            if vertex == target:
                return

            neighbors = self.graph[vertex]
            for neighbor in neighbors:
                if neighbor not in visited:
                    todo.append(neighbor)
                    visited.add(neighbor)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
