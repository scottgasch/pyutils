#!/usr/bin/python3

# © Copyright 2021-2022, Scott Gasch

"""Helpers for commandline argument parsing."""

import argparse
import datetime
import logging
import os
from typing import Any

from overrides import overrides

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

logger = logging.getLogger(__name__)


class ActionNoYes(argparse.Action):
    """An argparse Action that allows for commandline arguments like this::

        cfg.add_argument(
            '--enable_the_thing',
            action=ActionNoYes,
            default=False,
            help='Should we enable the thing?'
        )

    This creates the following cmdline arguments::

        --enable_the_thing
        --no_enable_the_thing

    These arguments can be used to indicate the inclusion or exclusion of
    binary exclusive behaviors.
    """

    def __init__(self, option_strings, dest, default=None, required=False, help=None):
        if default is None:
            msg = 'You must provide a default with Yes/No action'
            logger.critical(msg)
            raise ValueError(msg)
        if len(option_strings) != 1:
            msg = 'Only single argument is allowed with NoYes action'
            logger.critical(msg)
            raise ValueError(msg)
        opt = option_strings[0]
        if not opt.startswith('--'):
            msg = 'Yes/No arguments must be prefixed with --'
            logger.critical(msg)
            raise ValueError(msg)

        opt = opt[2:]
        opts = ['--' + opt, '--no_' + opt]
        super().__init__(
            opts,
            dest,
            nargs=0,
            const=None,
            default=default,
            required=required,
            help=help,
        )

    @overrides
    def __call__(self, parser, namespace, values, option_strings=None):
        if option_strings.startswith('--no-') or option_strings.startswith('--no_'):
            setattr(namespace, self.dest, False)
        else:
            setattr(namespace, self.dest, True)


def valid_bool(v: Any) -> bool:
    """
    If the string is a valid bool, return its value.

    >>> valid_bool(True)
    True

    >>> valid_bool("true")
    True

    >>> valid_bool("yes")
    True

    >>> valid_bool("on")
    True

    >>> valid_bool("1")
    True

    >>> valid_bool(12345)
    Traceback (most recent call last):
    ...
    argparse.ArgumentTypeError: 12345

    """
    if isinstance(v, bool):
        return v
    from pyutils.string_utils import to_bool

    try:
        return to_bool(v)
    except Exception as e:
        raise argparse.ArgumentTypeError(v) from e


def valid_ip(ip: str) -> str:
    """
    If the string is a valid IPv4 address, return it.  Otherwise raise
    an ArgumentTypeError.

    >>> valid_ip("1.2.3.4")
    '1.2.3.4'

    >>> valid_ip("localhost")
    Traceback (most recent call last):
    ...
    argparse.ArgumentTypeError: localhost is an invalid IP address

    """
    from pyutils.string_utils import extract_ip_v4

    s = extract_ip_v4(ip.strip())
    if s is not None:
        return s
    msg = f"{ip} is an invalid IP address"
    logger.error(msg)
    raise argparse.ArgumentTypeError(msg)


def valid_mac(mac: str) -> str:
    """
    If the string is a valid MAC address, return it.  Otherwise raise
    an ArgumentTypeError.

    >>> valid_mac('12:23:3A:4F:55:66')
    '12:23:3A:4F:55:66'

    >>> valid_mac('12-23-3A-4F-55-66')
    '12-23-3A-4F-55-66'

    >>> valid_mac('big')
    Traceback (most recent call last):
    ...
    argparse.ArgumentTypeError: big is an invalid MAC address

    """
    from pyutils.string_utils import extract_mac_address

    s = extract_mac_address(mac)
    if s is not None:
        return s
    msg = f"{mac} is an invalid MAC address"
    logger.error(msg)
    raise argparse.ArgumentTypeError(msg)


def valid_percentage(num: str) -> float:
    """
    If the string is a valid percentage, return it.  Otherwise raise
    an ArgumentTypeError.

    >>> valid_percentage("15%")
    15.0

    >>> valid_percentage('40')
    40.0

    >>> valid_percentage('115')
    Traceback (most recent call last):
    ...
    argparse.ArgumentTypeError: 115 is an invalid percentage; expected 0 <= n <= 100.0

    """
    num = num.strip('%')
    n = float(num)
    if 0.0 <= n <= 100.0:
        return n
    msg = f"{num} is an invalid percentage; expected 0 <= n <= 100.0"
    logger.error(msg)
    raise argparse.ArgumentTypeError(msg)


def valid_filename(filename: str) -> str:
    """
    If the string is a valid filename, return it.  Otherwise raise
    an ArgumentTypeError.

    >>> valid_filename('/tmp')
    '/tmp'

    >>> valid_filename('wfwefwefwefwefwefwefwefwef')
    Traceback (most recent call last):
    ...
    argparse.ArgumentTypeError: wfwefwefwefwefwefwefwefwef was not found and is therefore invalid.

    """
    s = filename.strip()
    if os.path.exists(s):
        return s
    msg = f"{filename} was not found and is therefore invalid."
    logger.error(msg)
    raise argparse.ArgumentTypeError(msg)


def valid_date(txt: str) -> datetime.date:
    """If the string is a valid date, return it.  Otherwise raise
    an ArgumentTypeError.

    >>> valid_date('6/5/2021')
    datetime.date(2021, 6, 5)

    # Note: dates like 'next wednesday' work fine, they are just
    # hard to test for without knowing when the testcase will be
    # executed...
    >>> valid_date('next wednesday') # doctest: +ELLIPSIS
    -ANYTHING-
    """
    from pyutils.string_utils import to_date

    date = to_date(txt)
    if date is not None:
        return date
    msg = f'Cannot parse argument as a date: {txt}'
    logger.error(msg)
    raise argparse.ArgumentTypeError(msg)


def valid_datetime(txt: str) -> datetime.datetime:
    """If the string is a valid datetime, return it.  Otherwise raise
    an ArgumentTypeError.

    >>> valid_datetime('6/5/2021 3:01:02')
    datetime.datetime(2021, 6, 5, 3, 1, 2)

    # Again, these types of expressions work fine but are
    # difficult to test with doctests because the answer is
    # relative to the time the doctest is executed.
    >>> valid_datetime('next christmas at 4:15am') # doctest: +ELLIPSIS
    -ANYTHING-
    """
    from pyutils.string_utils import to_datetime

    dt = to_datetime(txt)
    if dt is not None:
        return dt
    msg = f'Cannot parse argument as datetime: {txt}'
    logger.error(msg)
    raise argparse.ArgumentTypeError(msg)


def valid_duration(txt: str) -> datetime.timedelta:
    """If the string is a valid time duration, return a
    datetime.timedelta representing the period of time.  Otherwise
    maybe raise an ArgumentTypeError or potentially just treat the
    time window as zero in length.

    >>> valid_duration('3m')
    datetime.timedelta(seconds=180)

    >>> valid_duration('your mom')
    datetime.timedelta(0)

    """
    from pyutils.datetimez.datetime_utils import parse_duration

    try:
        secs = parse_duration(txt)
        return datetime.timedelta(seconds=secs)
    except Exception as e:
        logger.exception(e)
        raise argparse.ArgumentTypeError(e) from e


if __name__ == '__main__':
    import doctest

    doctest.ELLIPSIS_MARKER = '-ANYTHING-'
    doctest.testmod()
