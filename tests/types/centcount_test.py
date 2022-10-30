#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""centcount unittest."""

import unittest

from pyutils import unittest_utils
from pyutils.types.centcount import CentCount


class TestCentCount(unittest.TestCase):
    def test_basic_utility(self):
        amount = CentCount(1.45)
        another = CentCount.parse("USD 1.45")
        self.assertEqual(amount, another)

    def test_negation(self):
        amount = CentCount(1.45)
        amount = -amount
        self.assertEqual(CentCount(-1.45), amount)

    def test_addition_and_subtraction(self):
        amount = CentCount(1.00)
        another = CentCount(2.00)
        total = amount + another
        self.assertEqual(CentCount(3.00), total)
        delta = another - amount
        self.assertEqual(CentCount(1.00), delta)
        neg = amount - another
        self.assertEqual(CentCount(-1.00), neg)
        neg += another
        self.assertEqual(CentCount(1.00), neg)
        neg += 1.00
        self.assertEqual(CentCount(2.00), neg)
        neg -= 1.00
        self.assertEqual(CentCount(1.00), neg)
        x = 1000 - amount
        self.assertEqual(CentCount(9.0), x)

    def test_multiplication(self):
        amount = CentCount(3.00)
        amount *= 3
        self.assertEqual(CentCount(9.00), amount)
        with self.assertRaises(TypeError):
            another = CentCount(0.33)
            amount *= another

    def test_division(self):
        amount = CentCount(10.00)
        x = amount / 5.0
        self.assertEqual(CentCount(2.00), x)
        y = amount / 1.9999999999
        self.assertEqual(CentCount(5.00), y)
        with self.assertRaises(TypeError):
            another = CentCount(1.33)
            amount /= another

    def test_equality(self):
        usa = CentCount(1.0, "USD")
        can = CentCount(1.0, "CAD")
        self.assertNotEqual(usa, can)
        eh = CentCount(1.0, "CAD")
        self.assertEqual(can, eh)

    def test_comparison(self):
        one = CentCount(1.0)
        two = CentCount(2.0)
        three = CentCount(3.0)
        neg_one = CentCount(-1)
        self.assertLess(one, two)
        self.assertLess(neg_one, one)
        self.assertGreater(one, neg_one)
        self.assertGreater(three, one)
        looney = CentCount(1.0, "CAD")
        with self.assertRaises(TypeError):
            print(looney < one)

    def test_strict_mode(self):
        one = CentCount(1.0, strict_mode=True)
        two = CentCount(2.0, strict_mode=True)
        with self.assertRaises(TypeError):
            x = one + 2.4
        self.assertEqual(CentCount(3.0), one + two)
        with self.assertRaises(TypeError):
            x = two - 1.9
        self.assertEqual(CentCount(1.0), two - one)
        with self.assertRaises(TypeError):
            print(one == 1.0)
        self.assertTrue(CentCount(1.0) == one)
        with self.assertRaises(TypeError):
            print(one < 2.0)
        self.assertTrue(one < two)
        with self.assertRaises(TypeError):
            print(two > 1.0)
        self.assertTrue(two > one)


if __name__ == "__main__":
    unittest.main()
