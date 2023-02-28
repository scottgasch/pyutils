#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Right now this package only contains an implementation that allows you to
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
define your own ACLs easily.  Its :meth:`__call__` simply needs to
decide whether an item is allowed or denied.

Once a :class:`SimpleACL` is defined, it can be used within a
:class:`CompoundACL`::

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

A :class:`CompoundACL` can also be used inside another :class:`CompoundACL`
so this should be a flexible framework when defining complex access control
requirements:

There are two flavors of :class:`CompoundACL`:
:class:`AllCompoundACL` and :class:`AnyCompoundAcl`.  The former only
admits an item if all of its sub-acls admit it and the latter will
admit an item if any of its sub-acls admit it.:
"""

import enum
import fnmatch
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Sequence, Set

from overrides import overrides

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

logger = logging.getLogger(__name__)


class Order(enum.Enum):
    """A helper to express the order of evaluation for allows/denies
    in an Access Control List.
    """

    UNDEFINED = 0
    ALLOW_DENY = 1
    DENY_ALLOW = 2


class SimpleACL(ABC):
    """A simple Access Control List interface."""

    def __init__(self, *, order_to_check_allow_deny: Order, default_answer: bool):
        """
        Args:
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        if order_to_check_allow_deny not in (
            Order.ALLOW_DENY,
            Order.DENY_ALLOW,
        ):
            raise Exception(
                'order_to_check_allow_deny must be Order.ALLOW_DENY or '
                + 'Order.DENY_ALLOW'
            )
        self.order_to_check_allow_deny = order_to_check_allow_deny
        self.default_answer = default_answer

    def __call__(self, x: Any) -> bool:
        """
        Returns:
            True if x is allowed, False otherwise.
        """
        logger.debug('SimpleACL checking %s', x)
        if self.order_to_check_allow_deny == Order.ALLOW_DENY:
            logger.debug('Checking allowed first...')
            if self.check_allowed(x):
                logger.debug('%s was allowed explicitly.', x)
                return True
            logger.debug('Checking denied next...')
            if self.check_denied(x):
                logger.debug('%s was denied explicitly.', x)
                return False
        elif self.order_to_check_allow_deny == Order.DENY_ALLOW:
            logger.debug('Checking denied first...')
            if self.check_denied(x):
                logger.debug('%s was denied explicitly.', x)
                return False
            if self.check_allowed(x):
                logger.debug('%s was allowed explicitly.', x)
                return True

        logger.debug(
            f'{x} was not explicitly allowed or denied; '
            + f'using default answer ({self.default_answer})'
        )
        return self.default_answer

    @abstractmethod
    def check_allowed(self, x: Any) -> bool:
        """
        Args:
            x: the object being tested.

        Returns:
            True if x is explicitly allowed, False otherwise.
        """
        pass

    @abstractmethod
    def check_denied(self, x: Any) -> bool:
        """
        Args:
            x: the object being tested.

        Returns:
            True if x is explicitly denied, False otherwise."""
        pass


class SetBasedACL(SimpleACL):
    """An ACL that allows or denies based on membership in a set."""

    def __init__(
        self,
        *,
        allow_set: Optional[Set[Any]] = None,
        deny_set: Optional[Set[Any]] = None,
        order_to_check_allow_deny: Order,
        default_answer: bool,
    ) -> None:
        """
        Args:
            allow_set: the set of items that are allowed.
            deny_set: the set of items that are denied.
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        super().__init__(
            order_to_check_allow_deny=order_to_check_allow_deny,
            default_answer=default_answer,
        )
        self.allow_set = allow_set
        self.deny_set = deny_set

    @overrides
    def check_allowed(self, x: Any) -> bool:
        if self.allow_set is None:
            return False
        return x in self.allow_set

    @overrides
    def check_denied(self, x: Any) -> bool:
        if self.deny_set is None:
            return False
        return x in self.deny_set


class AllowListACL(SetBasedACL):
    """Convenience subclass for a list that only allows known items.
    i.e. an 'allowlist'
    """

    def __init__(self, *, allow_set: Optional[Set[Any]]) -> None:
        """
        Args:
            allow_set: a set containing the items that are allowed.
        """
        super().__init__(
            allow_set=allow_set,
            order_to_check_allow_deny=Order.ALLOW_DENY,
            default_answer=False,
        )


class DenyListACL(SetBasedACL):
    """Convenience subclass for a list that only disallows known items.
    i.e. a 'blocklist'
    """

    def __init__(self, *, deny_set: Optional[Set[Any]]) -> None:
        """
        Args:
            deny_set: a set containing the items that are denied.
        """
        super().__init__(
            deny_set=deny_set,
            order_to_check_allow_deny=Order.DENY_ALLOW,
            default_answer=True,
        )


class BlockListACL(SetBasedACL):
    """Convenience subclass for a list that only disallows known items.
    i.e. a 'blocklist'
    """

    def __init__(self, *, deny_set: Optional[Set[Any]]) -> None:
        """
        Args:
            deny_set: a set containing the items that are denied.
        """
        super().__init__(
            deny_set=deny_set,
            order_to_check_allow_deny=Order.DENY_ALLOW,
            default_answer=True,
        )


class PredicateListBasedACL(SimpleACL):
    """An ACL that allows or denies by applying predicates."""

    def __init__(
        self,
        *,
        allow_predicate_list: Sequence[Callable[[Any], bool]] = None,
        deny_predicate_list: Sequence[Callable[[Any], bool]] = None,
        order_to_check_allow_deny: Order,
        default_answer: bool,
    ) -> None:
        """
        Args:
            allow_predicate_list: a list of callables that indicate that
                an item should be allowed if they return True.
            deny_predicate_list: a list of callables that indicate that an
                item should be denied if they return True.
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        super().__init__(
            order_to_check_allow_deny=order_to_check_allow_deny,
            default_answer=default_answer,
        )
        self.allow_predicate_list = allow_predicate_list
        self.deny_predicate_list = deny_predicate_list

    @overrides
    def check_allowed(self, x: Any) -> bool:
        if self.allow_predicate_list is None:
            return False
        return any(predicate(x) for predicate in self.allow_predicate_list)

    @overrides
    def check_denied(self, x: Any) -> bool:
        if self.deny_predicate_list is None:
            return False
        return any(predicate(x) for predicate in self.deny_predicate_list)


class StringWildcardBasedACL(PredicateListBasedACL):
    """An ACL that allows or denies based on string glob :code:`(*, ?)`
    patterns.
    """

    def __init__(
        self,
        *,
        allowed_patterns: Optional[List[str]] = None,
        denied_patterns: Optional[List[str]] = None,
        order_to_check_allow_deny: Order,
        default_answer: bool,
    ) -> None:
        """
        Args:
            allowed_patterns: a list of string, optionally containing glob-style
                wildcards, that, if they match an item, indicate it should be
                allowed.
            denied_patterns: a list of string, optionally containing glob-style
                wildcards, that, if they match an item, indicate it should be
                denied.
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        allow_predicates = []
        if allowed_patterns is not None:
            for pattern in allowed_patterns:
                allow_predicates.append(
                    lambda x, pattern=pattern: fnmatch.fnmatch(x, pattern)
                )
        deny_predicates = None
        if denied_patterns is not None:
            deny_predicates = []
            for pattern in denied_patterns:
                deny_predicates.append(
                    lambda x, pattern=pattern: fnmatch.fnmatch(x, pattern)
                )

        super().__init__(
            allow_predicate_list=allow_predicates,
            deny_predicate_list=deny_predicates,
            order_to_check_allow_deny=order_to_check_allow_deny,
            default_answer=default_answer,
        )


class StringREBasedACL(PredicateListBasedACL):
    """An ACL that allows or denies by applying regexps."""

    def __init__(
        self,
        *,
        allowed_regexs: Optional[List[re.Pattern]] = None,
        denied_regexs: Optional[List[re.Pattern]] = None,
        order_to_check_allow_deny: Order,
        default_answer: bool,
    ) -> None:
        """
        Args:
            allowed_regexs: a list of regular expressions that, if they match an
                item, indicate that the item should be allowed.
            denied_regexs: a list of regular expressions that, if they match an
                item, indicate that the item should be denied.
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        allow_predicates = None
        if allowed_regexs is not None:
            allow_predicates = []
            for pattern in allowed_regexs:
                allow_predicates.append(
                    lambda x, pattern=pattern: pattern.match(x) is not None
                )
        deny_predicates = None
        if denied_regexs is not None:
            deny_predicates = []
            for pattern in denied_regexs:
                deny_predicates.append(
                    lambda x, pattern=pattern: pattern.match(x) is not None
                )
        super().__init__(
            allow_predicate_list=allow_predicates,
            deny_predicate_list=deny_predicates,
            order_to_check_allow_deny=order_to_check_allow_deny,
            default_answer=default_answer,
        )


class AnyCompoundACL(SimpleACL):
    """An ACL that allows if any of its subacls allow."""

    def __init__(
        self,
        *,
        subacls: Optional[List[SimpleACL]] = None,
        order_to_check_allow_deny: Order,
        default_answer: bool,
    ) -> None:
        """
        Args:
            subacls: a list of sub-ACLs we will consult for each item.  If
                *any* of these sub-ACLs allow the item we will also allow it.
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        super().__init__(
            order_to_check_allow_deny=order_to_check_allow_deny,
            default_answer=default_answer,
        )
        self.subacls = subacls

    @overrides
    def check_allowed(self, x: Any) -> bool:
        if self.subacls is None:
            return False
        return any(acl(x) for acl in self.subacls)

    @overrides
    def check_denied(self, x: Any) -> bool:
        if self.subacls is None:
            return False
        return any(not acl(x) for acl in self.subacls)


class AllCompoundACL(SimpleACL):
    """An ACL that allows if all of its subacls allow."""

    def __init__(
        self,
        *,
        subacls: Optional[List[SimpleACL]] = None,
        order_to_check_allow_deny: Order,
        default_answer: bool,
    ) -> None:
        """
        Args:
            subacls: a list of sub-ACLs that we will consult for each item.  *All*
                sub-ACLs must allow an item for us to also allow that item.
            order_to_check_allow_deny: set this argument to indicate what
                order to check items for allow and deny.  Pass either
                `Order.ALLOW_DENY` to check allow first or `Order.DENY_ALLOW`
                to check deny first.
            default_answer: pass this argument to provide the ACL with a
                default answer.

        .. note::

            By using `order_to_check_allow_deny` and `default_answer` you
            can create both *allow lists* and *deny lists*.  The former
            uses `Order.ALLOW_DENY` with a default anwser of False whereas
            the latter uses `Order.DENY_ALLOW` with a default answer of
            True.
        """
        super().__init__(
            order_to_check_allow_deny=order_to_check_allow_deny,
            default_answer=default_answer,
        )
        self.subacls = subacls

    @overrides
    def check_allowed(self, x: Any) -> bool:
        if self.subacls is None:
            return False
        return all(acl(x) for acl in self.subacls)

    @overrides
    def check_denied(self, x: Any) -> bool:
        if self.subacls is None:
            return False
        return any(not acl(x) for acl in self.subacls)
