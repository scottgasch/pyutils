#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A simple graph class that can be optionally directed and weighted and
some operations on it."""


import math
from typing import Dict, Generator, List, Optional, Set, Tuple

from pyutils import list_utils
from pyutils.types.simple import Numeric


class Graph(object):
    def __init__(self, directed: bool = False):
        """Constructs a new Graph object.

        Args:
            directed: are we modeling a directed graph?  See :meth:`add_edge`.

        """
        self.directed = directed
        self.graph: Dict[str, Dict[str, Numeric]] = {}
        self.dijkstra: Optional[Tuple[str, Dict[str, str], Dict[str, Numeric]]] = None

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
            self.dijkstra = None
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
        self.dijkstra = None

    def remove_edge(self, source: str, dest: str):
        """Remove a previously added edge in the graph.  If the graph is
        not directed (see :meth:`__init__`), also removes the reciprocal
        edge from dest back to source.

        .. note::

            This method does not remove vertexes (unlinked or otherwise).

        Args:
            source: the source vertex of the edge to remove
            dest: the destination vertex of the edge to remove

        >>> g = Graph()
        >>> g.add_edge('A', 'B')
        >>> g.add_edge('B', 'C')
        >>> g.get_edges()
        {'A': {'B': 1}, 'B': {'A': 1, 'C': 1}, 'C': {'B': 1}}
        >>> g.remove_edge('A', 'B')
        >>> g.get_edges()
        {'B': {'C': 1}, 'C': {'B': 1}}
        """
        del self.graph[source][dest]
        if len(self.graph[source]) == 0:
            del self.graph[source]
        if not self.directed:
            del self.graph[dest][source]
            if len(self.graph[dest]) == 0:
                del self.graph[dest]
        self.dijkstra = None

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

    def _generate_dijkstra(self, source: str) -> None:
        """Internal helper that runs Dijkstra's from source"""
        unvisited_nodes = self.get_vertices()

        shortest_path: Dict[str, Numeric] = {}
        for node in unvisited_nodes:
            shortest_path[node] = math.inf
        shortest_path[source] = 0

        previous_nodes: Dict[str, str] = {}
        while unvisited_nodes:
            current_min_node = None
            for node in unvisited_nodes:
                if current_min_node is None:
                    current_min_node = node
                elif shortest_path[node] < shortest_path[current_min_node]:
                    current_min_node = node

            assert current_min_node
            neighbors = self.graph[current_min_node]
            for neighbor in neighbors:
                tentative_value = (
                    shortest_path[current_min_node]
                    + self.graph[current_min_node][neighbor]
                )
                if tentative_value < shortest_path[neighbor]:
                    shortest_path[neighbor] = tentative_value
                    previous_nodes[neighbor] = current_min_node
            unvisited_nodes.remove(current_min_node)
        self.dijkstra = (source, previous_nodes, shortest_path)

    def minimum_path_between(
        self, source: str, dest: str
    ) -> Tuple[Optional[Numeric], List[str]]:
        """Compute the minimum path (lowest cost path) between source
        and dest.

        .. note::

            This method runs Dijkstra's algorithm
            (https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
            internally and caches the results.  Subsequent calls made with
            the same source node before modifying the graph are less
            expensive due to these cached intermediate results.

        Returns:
            A tuple containing the minimum distance of the path and the path itself.
            If there is no path between the requested nodes, returns (None, []).

        .. graphviz::

            graph g {
                node [shape=record];
                A -- B [weight=3];
                B -- D;
                A -- C [weight=2];
                C -- D -- E -- F;
                F -- F;
                E -- G;
                H;
            }

        >>> g = Graph()
        >>> g.add_edge('A', 'B', 3)
        >>> g.add_edge('A', 'C', 2)
        >>> g.add_edge('B', 'D')
        >>> g.add_edge('C', 'D')
        >>> g.add_edge('D', 'E')
        >>> g.add_edge('E', 'F')
        >>> g.add_edge('E', 'G')
        >>> g.add_edge('F', 'F')
        >>> g.add_vertex('H')
        True
        >>> g.minimum_path_between('A', 'D')
        (3, ['A', 'C', 'D'])
        >>> g.minimum_path_between('A', 'H')
        (None, [])

        """
        if self.dijkstra is None or self.dijkstra[0] != source:
            self._generate_dijkstra(source)

        assert self.dijkstra
        path = []
        node: Optional[str] = dest
        while node != source:
            assert node
            path.append(node)
            node = self.dijkstra[1].get(node, None)
            if node is None:
                return (None, [])
        path.append(source)
        path = path[::-1]

        cost: Numeric = 0
        for (a, b) in list_utils.ngrams(path, 2):
            cost += self.graph[a][b]
        return (cost, path)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
