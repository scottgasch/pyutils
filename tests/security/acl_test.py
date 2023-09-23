#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""acl unittest."""

import re
import unittest

from pyutils import unittest_utils  # Needed for --unittests_ignore_perf flag
from pyutils.security import acl


class TestSimpleACL(unittest.TestCase):
    def test_set_based_acl(self):
        even = acl.SetBasedACL(
            allow_set=set([2, 4, 6, 8, 10]),
            deny_set=set([1, 3, 5, 7, 9]),
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        self.assertTrue(even(2))
        self.assertFalse(even(3))
        self.assertFalse(even(-4))

    def test_wildcard_based_acl(self):
        a_or_b = acl.StringWildcardBasedACL(
            allowed_patterns=['a*', 'b*'],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        self.assertTrue(a_or_b('aardvark'))
        self.assertTrue(a_or_b('baboon'))
        self.assertFalse(a_or_b('cheetah'))

    def test_re_based_acl(self):
        weird = acl.StringREBasedACL(
            denied_regexs=[re.compile('^a.*a$'), re.compile('^b.*b$')],
            order_to_check_allow_deny=acl.Order.DENY_ALLOW,
            default_answer=True,
        )
        self.assertTrue(weird('aardvark'))
        self.assertFalse(weird('anaconda'))
        self.assertFalse(weird('blackneb'))
        self.assertTrue(weird('crow'))

    def test_compound_acls_disjunction(self):
        a_b_c = acl.StringWildcardBasedACL(
            allowed_patterns=['a*', 'b*', 'c*'],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        c_d_e = acl.StringWildcardBasedACL(
            allowed_patterns=['c*', 'd*', 'e*'],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        disjunction = acl.AnyCompoundACL(
            subacls=[a_b_c, c_d_e],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        self.assertTrue(disjunction('aardvark'))
        self.assertTrue(disjunction('caribou'))
        self.assertTrue(disjunction('eagle'))
        self.assertFalse(disjunction('newt'))

    def test_compound_acls_conjunction(self):
        a_b_c = acl.StringWildcardBasedACL(
            allowed_patterns=['a*', 'b*', 'c*'],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        c_d_e = acl.StringWildcardBasedACL(
            allowed_patterns=['c*', 'd*', 'e*'],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        conjunction = acl.AllCompoundACL(
            subacls=[a_b_c, c_d_e],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        self.assertFalse(conjunction('aardvark'))
        self.assertTrue(conjunction('caribou'))
        self.assertTrue(conjunction('condor'))
        self.assertFalse(conjunction('eagle'))
        self.assertFalse(conjunction('newt'))


if __name__ == '__main__':
    unittest.main()
