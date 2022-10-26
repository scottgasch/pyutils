#!/usr/bin/env python3

"""Utilities for dealing with Dataclasses.  A non-official type hint and some
friendly wrappers around conversion to/from Dicts."""

import dataclasses
from typing import Any, Dict, Protocol, Type


class Dataclass(Protocol):
    """Dataclass isn't really a first class type and therefore there is no offical
    type hint for Dataclasses in Python (yet).  If you need one, here's a suitable
    stand in.  Example usage::

        def f(d: Dataclass) -> Any:
            pass

        def g(d: Dict[str, Any]) -> Dataclass:
            pass
    """

    __dataclass_fields__: Dict


def dataclass_from_dict(dataclass: Type[Dataclass], d: Dict[str, Any]) -> Dataclass:
    """Given a Dataclass type and a dict, return a populated instance.

    Args:
        dataclass: the Class type to return an instance of
        d: the dict to be used to populate the new instance

    Returns:
        A constructed and populated dataclass instance.

    >>> from dataclasses import dataclass
    >>> from datetime import date

    >>> @dataclass
    ... class Record:
    ...     name: str
    ...     phone: str
    ...     address: str
    ...     age: int
    ...     member_since: date
    ...

    >>> d = {
    ...         'name': 'John Smith',
    ...         'phone': '555-1234',
    ...         'address': '994 Main St.',
    ...         'age': 26,
    ...         'member_since': date(2006, 5, 14),
    ...     }

    >>> dataclass_from_dict(Record, d)
    Record(name='John Smith', phone='555-1234', address='994 Main St.', age=26, member_since=datetime.date(2006, 5, 14))
    """
    fields = {f.name for f in dataclasses.fields(dataclass) if f.init}
    filtered_args = {k: v for k, v in d.items() if k in fields}
    return dataclass(**filtered_args)


def dataclass_to_dict(dataclass: Dataclass) -> Dict[str, Any]:
    """
    Returns:
        A dict-representation of a valid dataclass.

    >>> from dataclasses import dataclass
    >>> from datetime import date

    >>> @dataclass
    ... class Record:
    ...     name: str
    ...     phone: str
    ...     address: str
    ...     age: int
    ...     member_since: date
    ...
    >>> r = Record(name='Jane Doe', phone='555-1232', address='998 Main St.', age=23, member_since=date(2008, 3, 1))
    >>> dataclass_to_dict(r)
    {'name': 'Jane Doe', 'phone': '555-1232', 'address': '998 Main St.', 'age': 23, 'member_since': datetime.date(2008, 3, 1)}
    """
    assert dataclasses.is_dataclass(dataclass)
    return dataclasses.asdict(dataclass)


if __name__ == '__main__':
    import doctest

    doctest.testmod()
