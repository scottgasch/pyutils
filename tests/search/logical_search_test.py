#!/usr/bin/env python3

import unittest

from pyutils import unittest_utils as uu
from pyutils.search.logical_search import Corpus, Document


class TestLogicalSearch(unittest.TestCase):
    def setUp(self) -> None:
        """Initialize a corpus with a variety of test documents."""
        self.corpus = Corpus()

        # Doc 1: Basic tags and numeric properties
        d1 = Document(
            docid="doc1",
            tags={"kiosk", "nature"},
            properties=[("rating", "5"), ("year", "2020"), ("author", "Scott")],
        )

        # Doc 2: Temporal data and lists
        d2 = Document(
            docid="doc2",
            tags={"nature", "waterfall"},
            properties=[
                ("date", "2023-11-23T14:30:00Z"),
                ("rating", "3"),
                ("author", "Lynn"),
            ],
        )

        # Doc 3: Edge cases for dates and regex
        d3 = Document(
            docid="doc3",
            tags={"kiosk"},
            properties=[
                ("date", "1999-01-01"),
                ("temp", "-10.5"),
                ("filename", "IMG_001.JPG"),
            ],
        )

        for d in [d1, d2, d3]:
            self.corpus.add_doc(d)

    def test_basic_tag_search(self) -> None:
        """Test exact string match for tags."""
        self.assertEqual(self.corpus.query("kiosk"), {"doc1", "doc3"})
        self.assertEqual(self.corpus.query("waterfall"), {"doc2"})
        self.assertEqual(self.corpus.query("nonexistent"), set())

    def test_boolean_logic(self) -> None:
        """Test and, or, not, and parentheses."""
        # Intersection
        self.assertEqual(self.corpus.query("kiosk and nature"), {"doc1"})
        # Union
        self.assertEqual(self.corpus.query("waterfall or nature"), {"doc1", "doc2"})
        # Negation
        self.assertEqual(self.corpus.query("nature and not waterfall"), {"doc1"})
        # Complex nesting
        self.assertEqual(
            self.corpus.query("(kiosk or nature) and not doc3"), {"doc1", "doc2"}
        )

    def test_property_comparisons(self) -> None:
        """Test numeric and string property lookups."""
        self.assertEqual(self.corpus.query("rating:5"), {"doc1"})
        self.assertEqual(self.corpus.query("rating>3"), {"doc1"})
        self.assertEqual(self.corpus.query("temp<0"), {"doc3"})
        self.assertEqual(self.corpus.query("author:Scott"), {"doc1"})

    def test_temporal_logic(self) -> None:
        """Test ISO 8601 date parsing and comparisons."""
        # Exact match
        self.assertEqual(self.corpus.query("date:1999-01-01"), {"doc3"})
        # Greater than (ISO comparison)
        self.assertEqual(self.corpus.query("date>2000-01-01"), {"doc2"})
        # Window
        self.assertEqual(
            self.corpus.query("date>=1990-01-01 and date<=2000-01-01"), {"doc3"}
        )

    def test_regex_matching(self) -> None:
        """Test the ~ operator for regex support."""
        self.assertEqual(self.corpus.query("filename~^IMG_.*"), {"doc3"})
        self.assertEqual(self.corpus.query("author~^Sc.*t$"), {"doc1"})

    def test_syntactic_sugar(self) -> None:
        """Test BETWEEN (..) and IN ([]) desugaring."""
        # BETWEEN Numeric
        self.assertEqual(self.corpus.query("rating:3..5"), {"doc1", "doc2"})
        # BETWEEN Temporal
        self.assertEqual(self.corpus.query("date:1998-01-01..2000-01-01"), {"doc3"})
        # IN List
        self.assertEqual(self.corpus.query("author:[Scott,Lynn]"), {"doc1", "doc2"})
        # IN List with tags (desugared to or)
        self.assertEqual(self.corpus.query("rating:[1,3,5]"), {"doc1", "doc2"})

    def test_wildcard(self) -> None:
        """Test the * wildcard for 'any'."""
        self.assertEqual(self.corpus.query("*"), {"doc1", "doc2", "doc3"})
        self.assertEqual(
            self.corpus.query("author:*"), {"doc1", "doc2"}
        )  # Docs with 'author' key

    def test_parse_errors(self) -> None:
        """Ensure the engine handles malformed queries gracefully."""
        # This shouldn't crash, but return None/Empty based on your implementation
        self.assertEqual(set(), self.corpus.query("(unclosed parenthesis"))
        self.assertEqual(set(), self.corpus.query("and and and"))

    def test_direct_property_lookup(self) -> None:
        """
        Directly exercises the get_docids_by_property method.
        This will fail if self.docids_by_property is not initialized.
        """
        # doc1 has property ('rating', '5')
        results = self.corpus.get_docids_by_property("rating", "5")
        self.assertIn("doc1", results)
        self.assertEqual(len(results), 1)

        # doc2 has property ('author', 'Lynn')
        results = self.corpus.get_docids_by_property("author", "Lynn")
        self.assertIn("doc2", results)


if __name__ == "__main__":
    unittest.main()
