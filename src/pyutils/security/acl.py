#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""This module defines various flavors of Access Control Lists."""

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
        """Returns True if x is allowed, False otherwise."""
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
        """Return True if x is explicitly allowed, False otherwise."""
        pass

    @abstractmethod
    def check_denied(self, x: Any) -> bool:
        """Return True if x is explicitly denied, False otherwise."""
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
        super().__init__(
            deny_set=deny_set,
            order_to_check_allow_deny=Order.ALLOW_DENY,
            default_answer=True,
        )


class BlockListACL(SetBasedACL):
    """Convenience subclass for a list that only disallows known items.
    i.e. a 'blocklist'
    """

    def __init__(self, *, deny_set: Optional[Set[Any]]) -> None:
        super().__init__(
            deny_set=deny_set,
            order_to_check_allow_deny=Order.ALLOW_DENY,
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
