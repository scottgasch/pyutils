#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
logical_search.py - In-memory boolean and property query engine.

Supports:
- Boolean: and, or, not, ()
- Tags: exact string match
- Properties: key:val, key==val, key<val, key>val, key<=val, key>=val
- Temporal: ISO 8601 strings (YYYY-MM-DD[THH:MM:SS]) support full comparison
- Regex: key~^pattern
- IN: key:[val1,val2]
- BETWEEN: key:min..max
"""

from __future__ import annotations

import enum
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pyutils.exceptions import PyUtilsParseError

logger = logging.getLogger(__name__)


def _try_parse_date(val: Any) -> Optional[datetime]:
    if not isinstance(val, str) or len(val) < 10:
        return None
    try:
        # Standardize the string for ISO parsing
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))

        # Accessor check: if it lacks tzinfo, it's naive.
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


@dataclass
class Document:
    """A searchable unit. Properties remain a list of tuples for compatibility."""

    docid: str = ""
    tags: Set[str] = field(default_factory=set)
    properties: List[Tuple[str, str]] = field(default_factory=list)
    reference: Optional[Any] = None


class Operation(enum.Enum):
    """Logical operations for the AST."""

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
        return table.get(token.lower(), None)

    def num_operands(self) -> int:
        return {
            Operation.INVERSION: 1,
            Operation.CONJUNCTION: 2,
            Operation.DISJUNCTION: 2,
        }.get(self, 0)


class Corpus(object):
    """The indexing and search engine."""

    def __init__(self) -> None:
        self.docids_by_tag: Dict[str, Set[str]] = defaultdict(set)
        self.docids_with_property: Dict[str, Set[str]] = defaultdict(set)
        self.docids_by_property: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.documents_by_docid: Dict[str, Document] = {}

    def add_doc(self, doc: Document) -> None:
        """Indexes a document. Supports the list-of-tuples properties."""
        if doc.docid in self.documents_by_docid:
            old = self.documents_by_docid[doc.docid]
            for tag in old.tags:
                self.docids_by_tag[tag].discard(doc.docid)
            for key, _ in old.properties:
                self.docids_with_property[key].discard(doc.docid)

        self.documents_by_docid[doc.docid] = doc
        for tag in doc.tags:
            self.docids_by_tag[tag].add(doc.docid)
        for key, value in doc.properties:
            self.docids_with_property[key].add(doc.docid)
            self.docids_by_property[(key, value)].add(doc.docid)

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

    def query(self, query_str: str) -> Optional[Set[str]]:
        """Entry point for searching."""
        try:
            root = self._parse_query(query_str)
            return root.eval()
        except PyUtilsParseError:
            logger.exception("Parse error!")
            return None
        except Exception:
            logger.exception("Internal query evaluation error")
            return None

    def _parse_query(self, query_str: str) -> Node:
        """Parses query string into AST with pre-processing for IN/BETWEEN."""
        token_pattern = (
            r"(\(|\)|\[|\]|,)|(and|or|not)|(\.\.|<=|>=|==|<|>|~|:)|([^\s()<>:~=\[\],]+)"
        )
        tokens = [
            m.group(0) for m in re.finditer(token_pattern, query_str, re.IGNORECASE)
        ]

        merged_tokens = []
        i = 0
        while i < len(tokens):
            # BETWEEN: key:val1..val2
            if i + 4 < len(tokens) and tokens[i + 1] == ":" and tokens[i + 3] == "..":
                k, v1, v2 = tokens[i], tokens[i + 2], tokens[i + 4]
                merged_tokens.append(f"{k}:{v1}..{v2}")
                i += 5
            # IN: key:[v1,v2] -> desugar to (key:v1 or key:v2)
            elif i + 2 < len(tokens) and tokens[i + 1] == ":" and tokens[i + 2] == "[":
                key = tokens[i]
                start_idx = i
                i += 3
                inner_vals = []
                while i < len(tokens) and tokens[i] != "]":
                    if tokens[i] != ",":
                        inner_vals.append(tokens[i])
                    i += 1
                desugared = "(" + " or ".join([f"{key}:{v}" for v in inner_vals]) + ")"
                raw_fragment = "".join(tokens[start_idx : i + 1])
                return self._parse_query(query_str.replace(raw_fragment, desugared, 1))
            elif i + 2 < len(tokens) and tokens[i + 1] in (
                "<",
                ">",
                "<=",
                ">=",
                "==",
                ":",
                "~",
            ):
                merged_tokens.append(f"{tokens[i]}{tokens[i+1]}{tokens[i+2]}")
                i += 3
            else:
                merged_tokens.append(tokens[i])
                i += 1

        output: List[Node] = []
        ops: List[str] = []
        precedence = {"(": 0, "or": 1, "and": 2, "not": 3}

        for token in merged_tokens:
            low_t = token.lower()
            if low_t == "(":
                ops.append(low_t)
            elif low_t == ")":
                while ops and ops[-1] != "(":
                    self._build_op_node(output, ops.pop())
                if ops:
                    ops.pop()
            elif low_t in precedence:
                while ops and precedence.get(ops[-1], 0) >= precedence[low_t]:
                    self._build_op_node(output, ops.pop())
                ops.append(low_t)
            else:
                output.append(Node(self, Operation.QUERY, [token]))

        while ops:
            self._build_op_node(output, ops.pop())
        return output[0] if output else Node(self, Operation.QUERY, [""])

    def _build_op_node(self, stack: List[Node], op_str: str):
        op = Operation.from_token(op_str)
        if not op or len(stack) < op.num_operands():
            return
        operands = [stack.pop() for _ in range(op.num_operands())]
        stack.append(Node(self, op, operands[::-1]))


class Node(object):
    """AST Node. Evaluates properties against stored Documents."""

    def __init__(self, corpus: Corpus, op: Operation, operands: List[Union[Node, str]]):
        self.corpus = corpus
        self.op = op
        self.operands = operands

    def _compare(self, doc_val: Any, op: str, query_val: str) -> bool:
        """Handles temporal, numeric, and string comparison."""
        # 1. Regex
        if op == "~":
            try:
                return re.search(query_val, str(doc_val), re.IGNORECASE) is not None
            except re.error:
                return False

        # 2. Range (BETWEEN)
        if ".." in query_val:
            low_raw, high_raw = query_val.split("..")
            # Try date range first
            d_dt, l_dt, h_dt = [
                _try_parse_date(v) for v in (doc_val, low_raw, high_raw)
            ]
            if d_dt and l_dt and h_dt:
                return l_dt <= d_dt <= h_dt

            # Fallback to numeric/string range
            try:
                return float(low_raw) <= float(doc_val) <= float(high_raw)
            except (ValueError, TypeError):
                return str(low_raw) <= str(doc_val) <= str(high_raw)

        # 3. Equality (Fast Path)
        if op in (":", "=="):
            if query_val == "*":
                return True
            d_dt, q_dt = _try_parse_date(doc_val), _try_parse_date(query_val)
            if d_dt and q_dt:
                return d_dt == q_dt
            return str(doc_val).lower() == query_val.lower()

        # 4. Temporal comparison (Greater/Less)
        d_dt, q_dt = _try_parse_date(doc_val), _try_parse_date(query_val)
        if d_dt and q_dt:
            if op == "<":
                return d_dt < q_dt
            if op == ">":
                return d_dt > q_dt
            if op == "<=":
                return d_dt <= q_dt
            if op == ">=":
                return d_dt >= q_dt

        # 5. Numeric comparison fallback
        try:
            d_num, q_num = float(doc_val), float(query_val)
            if op == "<":
                return d_num < q_num
            if op == ">":
                return d_num > q_num
            if op == "<=":
                return d_num <= q_num
            if op == ">=":
                return d_num >= q_num
        except (ValueError, TypeError):
            # 6. String comparison fallback
            if op == "<":
                return str(doc_val) < query_val
            if op == ">":
                return str(doc_val) > query_val

        return False

    def eval(self) -> Set[str]:
        """Evaluates Node recursively."""
        if self.op == Operation.CONJUNCTION:
            return self.operands[0].eval() & self.operands[1].eval()
        if self.op == Operation.DISJUNCTION:
            return self.operands[0].eval() | self.operands[1].eval()
        if self.op == Operation.INVERSION:
            return set(self.corpus.documents_by_docid.keys()) - self.operands[0].eval()

        # QUERY node
        expr = self.operands[0]
        results = set()
        match = re.search(r"(<=|>=|==|<|>|~|:)", expr)

        if match:
            op = match.group(0)
            key, val = expr.split(op, 1)
            candidates = self.corpus.docids_with_property.get(key, set())
            for docid in candidates:
                doc = self.corpus.documents_by_docid[docid]
                for k, v in doc.properties:
                    if k == key and self._compare(v, op, val):
                        results.add(docid)
                        break

        else:
            if expr == "*":
                results = set(self.corpus.documents_by_docid.keys())
            else:
                # Check tags first
                results = self.corpus.docids_by_tag.get(expr, set())
                # If no tags match, check if it's a direct docid match
                if not results and expr in self.corpus.documents_by_docid:
                    results = {expr}
        return results
