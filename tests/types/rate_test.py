#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""rate unittest."""

import unittest

from pyutils import unittest_utils
from pyutils.types.money import Money
from pyutils.types.rate import Rate


class TestRate(unittest.TestCase):
    def test_basic_utility(self):
        my_stock_returns = Rate(percent_change=-20.0)
        my_portfolio = 1000.0
        self.assertAlmostEqual(800.0, my_stock_returns.apply_to(my_portfolio))

        my_bond_returns = Rate(percentage=104.5)
        my_money = Money(500.0)
        self.assertAlmostEqual(Money(522.5), my_bond_returns.apply_to(my_money))

        my_multiplier = Rate(multiplier=1.72)
        my_nose_length = 3.2
        self.assertAlmostEqual(5.504, my_multiplier.apply_to(my_nose_length))

    def test_conversions(self):
        x = Rate(104.55)
        s = x.__repr__()
        y = Rate(s)
        self.assertAlmostEqual(x, y)
        f = float(x)
        z = Rate(f)
        self.assertAlmostEqual(x, z)

    def test_divide(self):
        x = Rate(20.0)
        x /= 2
        self.assertAlmostEqual(10.0, x)
        x = Rate(-20.0)
        x /= 2
        self.assertAlmostEqual(-10.0, x)

    def test_add(self):
        x = Rate(5.0)
        y = Rate(10.0)
        z = x + y
        self.assertAlmostEqual(15.0, z)
        x = Rate(-5.0)
        x += y
        self.assertAlmostEqual(5.0, x)

    def test_sub(self):
        x = Rate(5.0)
        y = Rate(10.0)
        z = x - y
        self.assertAlmostEqual(-5.0, z)
        z = y - x
        self.assertAlmostEqual(5.0, z)

    def test_repr(self):
        x = Rate(percent_change=-50.0)
        s = x.__repr__(relative=True)
        self.assertEqual("-50.000%", s)
        s = x.__repr__()
        self.assertEqual("+50.000%", s)


if __name__ == "__main__":
    unittest.main()
