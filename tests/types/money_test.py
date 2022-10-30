#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""money unittest."""

import unittest
from decimal import Decimal

from pyutils import unittest_utils
from pyutils.types.money import Money


class TestMoney(unittest.TestCase):
    def test_basic_utility(self):
        amount = Money(1.45)
        another = Money.parse("USD 1.45")
        self.assertAlmostEqual(amount.amount, another.amount)

    def test_negation(self):
        amount = Money(1.45)
        amount = -amount
        self.assertAlmostEqual(Money(-1.45).amount, amount.amount)

    def test_addition_and_subtraction(self):
        amount = Money(1.00)
        another = Money(2.00)
        total = amount + another
        self.assertEqual(Money(3.00), total)
        delta = another - amount
        self.assertEqual(Money(1.00), delta)
        neg = amount - another
        self.assertEqual(Money(-1.00), neg)
        neg += another
        self.assertEqual(Money(1.00), neg)
        neg += 1.00
        self.assertEqual(Money(2.00), neg)
        neg -= 1
        self.assertEqual(Money(1.00), neg)
        x = 10 - amount
        self.assertEqual(Money(9.0), x)

    def test_multiplication(self):
        amount = Money(3.00)
        amount *= 3
        self.assertEqual(Money(9.00), amount)
        with self.assertRaises(TypeError):
            another = Money(0.33)
            amount *= another

    def test_division(self):
        amount = Money(10.00)
        x = amount / 5.0
        self.assertEqual(Money(2.00), x)
        with self.assertRaises(TypeError):
            another = Money(1.33)
            amount /= another

    def test_equality(self):
        usa = Money(1.0, "USD")
        can = Money(1.0, "CAD")
        self.assertNotEqual(usa, can)
        eh = Money(1.0, "CAD")
        self.assertEqual(can, eh)

    def test_comparison(self):
        one = Money(1.0)
        two = Money(2.0)
        three = Money(3.0)
        neg_one = Money(-1)
        self.assertLess(one, two)
        self.assertLess(neg_one, one)
        self.assertGreater(one, neg_one)
        self.assertGreater(three, one)
        looney = Money(1.0, "CAD")
        with self.assertRaises(TypeError):
            print(looney < one)

    def test_strict_mode(self):
        one = Money(1.0, strict_mode=True)
        two = Money(2.0, strict_mode=True)
        with self.assertRaises(TypeError):
            x = one + 2.4
        self.assertEqual(Money(3.0), one + two)
        with self.assertRaises(TypeError):
            x = two - 1.9
        self.assertEqual(Money(1.0), two - one)
        with self.assertRaises(TypeError):
            print(one == 1.0)
        self.assertTrue(Money(1.0) == one)
        with self.assertRaises(TypeError):
            print(one < 2.0)
        self.assertTrue(one < two)
        with self.assertRaises(TypeError):
            print(two > 1.0)
        self.assertTrue(two > one)

    def test_truncate_and_round(self):
        ten = Money(10.0)
        x = ten * 2 / 3
        expected = Decimal(6.66)
        expected = expected.quantize(Decimal(".01"))
        self.assertEqual(expected, x.truncate_fractional_cents())
        x = ten * 2 / 3
        expected = Decimal(6.67)
        expected = expected.quantize(Decimal(".01"))
        self.assertEqual(expected, x.round_fractional_cents())


if __name__ == "__main__":
    unittest.main()
