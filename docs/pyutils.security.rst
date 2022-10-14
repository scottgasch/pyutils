pyutils.security package
========================

Right now this package only contains an implementation that allows you to
define and evaluate Access Control Lists (ACLs) easily.  For example::

        even = acl.SetBasedACL(
            allow_set=set([2, 4, 6, 8, 10]),
            deny_set=set([1, 3, 5, 7, 9]),
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        self.assertTrue(even(2))
        self.assertFalse(even(3))
        self.assertFalse(even(-4))

ACLs can also be defined based on other criteria, for example::

        a_or_b = acl.StringWildcardBasedACL(
            allowed_patterns=['a*', 'b*'],
            order_to_check_allow_deny=acl.Order.ALLOW_DENY,
            default_answer=False,
        )
        self.assertTrue(a_or_b('aardvark'))
        self.assertTrue(a_or_b('baboon'))
        self.assertFalse(a_or_b('cheetah'))

Or::

        weird = acl.StringREBasedACL(
            denied_regexs=[re.compile('^a.*a$'), re.compile('^b.*b$')],
            order_to_check_allow_deny=acl.Order.DENY_ALLOW,
            default_answer=True,
        )
        self.assertTrue(weird('aardvark'))
        self.assertFalse(weird('anaconda'))
        self.assertFalse(weird('blackneb'))
        self.assertTrue(weird('crow'))

There are implementations for wildcards, sets, regular expressions,
allow lists, deny lists, sequences of user defined predicates, etc...
You can also just subclass the base :class:`SimpleACL` interface to
define your own ACLs easily.  Its __call__ method simply needs to
decide whether an item is allowed or denied.

Once a :class:`SimpleACL` is defined, it can be used in :class:`CompoundACLs`::

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

a :class:`CompoundACL` can also be used inside another :class:`CompoundACL`
so this should be a flexible framework when defining complex access control
requirements:

There are two flavors of :class:`CompoundACLs`:
:class:`AllCompoundACL` and :class:`AnyCompoundAcl`.  The former only
admits an item if all of its sub-acls admit it and the latter will
admit an item if any of its sub-acls admit it.:


Submodules
----------

pyutils.security.acl module
---------------------------

.. automodule:: pyutils.security.acl
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

.. automodule:: pyutils.security
   :members:
   :undoc-members:
   :show-inheritance:
