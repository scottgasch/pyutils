#!/usr/bin/env python3
# pylint: disable=too-many-nested-blocks

# © Copyright 2021-2023, Scott Gasch

"""This is a module concerned with the creation of and searching of a
corpus of documents.  The corpus and index are held in memory.
The query language contains AND, OR, NOT, and parenthesis to support
flexible search semantics.
"""

from __future__ import annotations

import enum
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union


class ParseError(Exception):
    """An error encountered while parsing a logical search expression."""

    def __init__(self, message: str):
        super().__init__()
        self.message = message


@dataclass
class Document:
    """A class representing a searchable document."""

    docid: str = ""
    """A unique identifier for each document -- must be provided
    by the caller.  See :meth:`python_modules.id_generator.get` or
    :meth:`python_modules.string_utils.generate_uuid` for potential
    sources."""

    tags: Set[str] = field(default_factory=set)
    """A set of tag strings for this document.  May be empty.  Tags
    are simply text labels that are associated with a document and
    may be used to search for it later.
    """

    properties: List[Tuple[str, str]] = field(default_factory=list)
    """A list of key->value strings for this document.  May be empty.
    Properties are more flexible tags that have both a label and a
    value.  e.g. "category:mystery" or "author:smith"."""

    reference: Optional[Any] = None
    """An optional reference to something else for convenience;
    interpreted only by caller code, ignored here.
    """


class Operation(enum.Enum):
    """A logical search query operation."""

    QUERY = 1
    CONJUNCTION = 2
    DISJUNCTION = 3
    INVERSION = 4

    @staticmethod
    def from_token(token: str):
        table = {
            "not": Operation.INVERSION,
            "and": Operation.CONJUNCTION,
            "or": Operation.DISJUNCTION,
        }
        return table.get(token, None)

    def num_operands(self) -> Optional[int]:
        table = {
            Operation.INVERSION: 1,
            Operation.CONJUNCTION: 2,
            Operation.DISJUNCTION: 2,
        }
        return table.get(self, None)


class Corpus(object):
    """A collection of searchable documents.  The caller can
    add documents to it (or edit existing docs) via :meth:`add_doc`,
    retrieve a document given its docid via :meth:`get_doc`, and
    perform various lookups of documents.  The most interesting
    lookup is implemented in :meth:`query`.

    >>> c = Corpus()
    >>> c.add_doc(Document(
    ...                    docid=1,
    ...                    tags=set(['urgent', 'important']),
    ...                    properties=[
    ...                                ('author', 'Scott'),
    ...                                ('subject', 'your anniversary')
    ...                    ],
    ...                    reference=None,
    ...                   )
    ...          )
    >>> c.add_doc(Document(
    ...                    docid=2,
    ...                    tags=set(['important']),
    ...                    properties=[
    ...                                ('author', 'Joe'),
    ...                                ('subject', 'your performance at work')
    ...                    ],
    ...                    reference=None,
    ...                   )
    ...          )
    >>> c.add_doc(Document(
    ...                    docid=3,
    ...                    tags=set(['urgent']),
    ...                    properties=[
    ...                                ('author', 'Scott'),
    ...                                ('subject', 'car turning in front of you')
    ...                    ],
    ...                    reference=None,
    ...                   )
    ...          )
    >>> c.query('author:Scott and important')
    {1}
    >>> c.query('*')
    {1, 2, 3}
    >>> c.query('*:*')
    {1, 2, 3}
    >>> c.query('*:Scott')
    {1, 3}
    """

    def __init__(self) -> None:
        self.docids_by_tag: Dict[str, Set[str]] = defaultdict(set)
        self.docids_by_property: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.docids_with_property: Dict[str, Set[str]] = defaultdict(set)
        self.documents_by_docid: Dict[str, Document] = {}

    def add_doc(self, doc: Document) -> None:
        """Add a new Document to the Corpus.  Each Document must have a
        distinct docid that will serve as its primary identifier.  If
        the same Document is added multiple times, only the most
        recent addition is indexed.  If two distinct documents with
        the same docid are added, the latter klobbers the former in
        the indexes.  See :meth:`python_modules.id_generator.get` or
        :meth:`python_modules.string_utils.generate_uuid` for potential
        sources of docids.

        Each Document may have an optional set of tags which can be
        used later in expressions to the query method.  These are simple
        text labels.

        Each Document may have an optional list of key->value tuples
        which can be used later in expressions to the query method.

        Document includes a user-defined "reference" field which is
        never interpreted by this module.  This is meant to allow easy
        mapping between Documents in this corpus and external objects
        they may represent.

        Args:
            doc: the document to add or edit
        """

        if doc.docid in self.documents_by_docid:
            # Handle collisions; assume that we are re-indexing the
            # same document so remove it from the indexes before
            # adding it back again.
            colliding_doc = self.documents_by_docid[doc.docid]
            assert colliding_doc.docid == doc.docid
            del self.documents_by_docid[doc.docid]
            for tag in colliding_doc.tags:
                self.docids_by_tag[tag].remove(doc.docid)
            for key, value in colliding_doc.properties:
                self.docids_by_property[(key, value)].remove(doc.docid)
                self.docids_with_property[key].remove(doc.docid)

        # Index the new Document
        assert doc.docid not in self.documents_by_docid
        self.documents_by_docid[doc.docid] = doc
        for tag in doc.tags:
            self.docids_by_tag[tag].add(doc.docid)
        for key, value in doc.properties:
            self.docids_by_property[(key, value)].add(doc.docid)
            self.docids_with_property[key].add(doc.docid)

    def get_docids_by_exact_tag(self, tag: str) -> Set[str]:
        """Return the set of docids that have a particular tag.

        Args:
            tag: the tag for which to search

        Returns:
            A set containing docids with the provided tag which
            may be empty."""
        return self.docids_by_tag[tag]

    def get_docids_by_searching_tags(self, tag: str) -> Set[str]:
        """Return the set of docids with a tag that contains a str.

        Args:
            tag: the tag pattern for which to search

        Returns:
            A set containing docids with tags that match the pattern
            provided.  e.g., if the arg was "foo" tags "football", "foobar",
            and "food" all match.
        """
        ret = set()
        for search_tag in self.docids_by_tag:
            if tag in search_tag:
                for docid in self.docids_by_tag[search_tag]:
                    ret.add(docid)
        return ret

    def get_docids_with_property(self, key: str) -> Set[str]:
        """Return the set of docids that have a particular property no matter
        what that property's value.

        Args:
            key: the key value to search for.

        Returns:
            A set of docids that contain the key (no matter what value)
            which may be empty.
        """
        return self.docids_with_property[key]

    def get_docids_by_property(self, key: str, value: str) -> Set[str]:
        """Return the set of docids that have a particular property with a
        particular value.

        Args:
            key: the key to search for
            value: the value that key must have in order to match a doc.

        Returns:
            A set of docids that contain key with value which may be empty.
        """
        return self.docids_by_property[(key, value)]

    def invert_docid_set(self, original: Set[str]) -> Set[str]:
        """Invert a set of docids."""
        return {docid for docid in self.documents_by_docid if docid not in original}

    def get_doc(self, docid: str) -> Optional[Document]:
        """Given a docid, retrieve the previously added Document.

        Args:
            docid: the docid to retrieve

        Returns:
            The Document with docid or None to indicate no match.
        """
        return self.documents_by_docid.get(docid, None)

    def query(self, query: str) -> Optional[Set[str]]:
        """Query the corpus for documents that match a logical expression.

        Args:
            query: the logical query expressed using a simple language
                that understands conjunction (and operator), disjunction
                (or operator) and inversion (not operator) as well as
                parenthesis.  Here are some legal sample queries::

                    tag1 and tag2 and not tag3

                    (tag1 or tag2) and (tag3 or tag4)

                    (tag1 and key2:value2) or (tag2 and key1:value1)

                    key:*

                    tag1 and key:*

        Returns:
            A (potentially empty) set of docids for the matching
            (previously added) documents or None on error.
        """

        try:
            root = self._parse_query(query)
        except ParseError as e:
            print(e.message, file=sys.stderr)
            return None
        return root.eval()

    def _parse_query(self, query: str):
        """Internal parse helper; prefer to use query instead."""

        parens = set(["(", ")"])
        and_or = set(["and", "or"])

        def operator_precedence(token: str) -> Optional[int]:
            table = {
                "(": 4,  # higher
                ")": 4,
                "not": 3,
                "and": 2,
                "or": 1,  # lower
            }
            return table.get(token, None)

        def is_operator(token: str) -> bool:
            return operator_precedence(token) is not None

        def lex(query: str):
            tokens = query.split()
            for token in tokens:
                # Handle ( and ) operators stuck to the ends of tokens
                # that split() doesn't understand.
                if len(token) > 1:
                    first = token[0]
                    if first in parens:
                        tail = token[1:]
                        yield first
                        token = tail
                    last = token[-1]
                    if last in parens:
                        head = token[0:-1]
                        yield head
                        token = last
                yield token

        def evaluate(corpus: Corpus, stack: List[str]):
            node_stack: List[Node] = []
            for token in stack:
                node = None
                if not is_operator(token):
                    node = Node(corpus, Operation.QUERY, [token])
                else:
                    args = []
                    operation = Operation.from_token(token)
                    operand_count = operation.num_operands()
                    if len(node_stack) < operand_count:
                        raise ParseError(
                            f"Incorrect number of operations for {operation}"
                        )
                    for _ in range(operation.num_operands()):
                        args.append(node_stack.pop())
                    node = Node(corpus, operation, args)
                node_stack.append(node)
            return node_stack[0]

        output_stack = []
        operator_stack = []
        for token in lex(query):
            if not is_operator(token):
                output_stack.append(token)
                continue

            # token is an operator...
            if token == "(":
                operator_stack.append(token)
            elif token == ")":
                ok = False
                while len(operator_stack) > 0:
                    pop_operator = operator_stack.pop()
                    if pop_operator != "(":
                        output_stack.append(pop_operator)
                    else:
                        ok = True
                        break
                if not ok:
                    raise ParseError("Unbalanced parenthesis in query expression")

            # and, or, not
            else:
                my_precedence = operator_precedence(token)
                if my_precedence is None:
                    raise ParseError(f"Unknown operator: {token}")
                while len(operator_stack) > 0:
                    peek_operator = operator_stack[-1]
                    if not is_operator(peek_operator) or peek_operator == "(":
                        break
                    peek_precedence = operator_precedence(peek_operator)
                    if peek_precedence is None:
                        raise ParseError("Internal error")
                    if (
                        (peek_precedence < my_precedence)
                        or (peek_precedence == my_precedence)
                        and (peek_operator not in and_or)
                    ):
                        break
                    output_stack.append(operator_stack.pop())
                operator_stack.append(token)
        while len(operator_stack) > 0:
            token = operator_stack.pop()
            if token in parens:
                raise ParseError("Unbalanced parenthesis in query expression")
            output_stack.append(token)
        return evaluate(self, output_stack)


class Node(object):
    """A query AST node."""

    def __init__(
        self,
        corpus: Corpus,
        op: Operation,
        operands: Sequence[Union[Node, str]],
    ):
        self.corpus = corpus
        self.op = op
        self.operands = operands

    def eval(self) -> Set[str]:
        """Evaluate this node."""

        evaled_operands: List[Union[Set[str], str]] = []
        for operand in self.operands:
            if isinstance(operand, Node):
                evaled_operands.append(operand.eval())
            elif isinstance(operand, str):
                evaled_operands.append(operand)
            else:
                raise ParseError(f"Unexpected operand: {operand}")

        retval = set()
        if self.op is Operation.QUERY:
            for tag in evaled_operands:
                if isinstance(tag, str):
                    if ":" in tag:
                        try:
                            key, value = tag.split(":")
                        except ValueError as v:
                            raise ParseError(
                                f'Invalid key:value syntax at "{tag}"'
                            ) from v

                        if key == "*":
                            r = set()
                            for kv, s in self.corpus.docids_by_property.items():
                                if value in ("*", kv[1]):
                                    r.update(s)
                        else:
                            if value == "*":
                                r = self.corpus.get_docids_with_property(key)
                            else:
                                r = self.corpus.get_docids_by_property(key, value)
                    else:
                        if tag == "*":
                            r = set()
                            for s in self.corpus.docids_by_tag.values():
                                r.update(s)
                        else:
                            r = self.corpus.get_docids_by_exact_tag(tag)
                    retval.update(r)
                else:
                    raise ParseError(f"Unexpected query {tag}")
        elif self.op is Operation.DISJUNCTION:
            if len(evaled_operands) != 2:
                raise ParseError("Operation.DISJUNCTION (or) expects two operands.")
            retval.update(evaled_operands[0])
            retval.update(evaled_operands[1])
        elif self.op is Operation.CONJUNCTION:
            if len(evaled_operands) != 2:
                raise ParseError("Operation.CONJUNCTION (and) expects two operands.")
            retval.update(evaled_operands[0])
            retval = retval.intersection(evaled_operands[1])
        elif self.op is Operation.INVERSION:
            if len(evaled_operands) != 1:
                raise ParseError("Operation.INVERSION (not) expects one operand.")
            _ = evaled_operands[0]
            if isinstance(_, set):
                retval.update(self.corpus.invert_docid_set(_))
            else:
                raise ParseError(f"Unexpected negation operand {_} ({type(_)})")
        return retval


if __name__ == "__main__":
    import doctest

    doctest.testmod()
