#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""The MIT License (MIT)

Copyright (c) 2016-2020 Davide Zanotti

Modifications Copyright (c) 2021-2022 Scott Gasch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This class is based on:
https://github.com/daveoncode/python-string-utils.  See `NOTICE
<https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=NOTICE;hb=HEAD>`__
in the root of this module for a detailed enumeration of what work is
Davide's and what work was added by Scott.

"""

import base64
import contextlib  # type: ignore
import datetime
import io
import json
import logging
import numbers
import random
import re
import string
import unicodedata
import warnings
from itertools import zip_longest
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
)
from uuid import uuid4

from pyutils import list_utils

logger = logging.getLogger(__name__)

NUMBER_RE = re.compile(r"^([+\-]?)((\d+)(\.\d+)?([e|E]\d+)?|\.\d+)$")

HEX_NUMBER_RE = re.compile(r"^([+|-]?)0[x|X]([0-9A-Fa-f]+)$")

OCT_NUMBER_RE = re.compile(r"^([+|-]?)0[O|o]([0-7]+)$")

BIN_NUMBER_RE = re.compile(r"^([+|-]?)0[B|b]([0|1]+)$")

URLS_RAW_STRING = (
    r"([a-z-]+://)"  # scheme
    r"([a-z_\d-]+:[a-z_\d-]+@)?"  # user:password
    r"(www\.)?"  # www.
    r"((?<!\.)[a-z\d]+[a-z\d.-]+\.[a-z]{2,6}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|localhost)"  # domain
    r"(:\d{2,})?"  # port number
    r"(/[a-z\d_%+-]*)*"  # folders
    r"(\.[a-z\d_%+-]+)*"  # file extension
    r"(\?[a-z\d_+%-=]*)?"  # query string
    r"(#\S*)?"  # hash
)

URL_RE = re.compile(rf"^{URLS_RAW_STRING}$", re.IGNORECASE)

URLS_RE = re.compile(rf"({URLS_RAW_STRING})", re.IGNORECASE)

ESCAPED_AT_SIGN = re.compile(r'(?!"[^"]*)@+(?=[^"]*")|\\@')

EMAILS_RAW_STRING = (
    r"[a-zA-Z\d._\+\-'`!%#$&*/=\?\^\{\}\|~\\]+@[a-z\d-]+\.?[a-z\d-]+\.[a-z]{2,4}"
)

EMAIL_RE = re.compile(rf"^{EMAILS_RAW_STRING}$")

EMAILS_RE = re.compile(rf"({EMAILS_RAW_STRING})")

CAMEL_CASE_TEST_RE = re.compile(r"^[a-zA-Z]*([a-z]+[A-Z]+|[A-Z]+[a-z]+)[a-zA-Z\d]*$")

CAMEL_CASE_REPLACE_RE = re.compile(r"([a-z]|[A-Z]+)(?=[A-Z])")

SNAKE_CASE_TEST_RE = re.compile(
    r"^([a-z]+\d*_[a-z\d_]*|_+[a-z\d]+[a-z\d_]*)$", re.IGNORECASE
)

SNAKE_CASE_TEST_DASH_RE = re.compile(
    r"([a-z]+\d*-[a-z\d-]*|-+[a-z\d]+[a-z\d-]*)$", re.IGNORECASE
)

SNAKE_CASE_REPLACE_RE = re.compile(r"(_)([a-z\d])")

SNAKE_CASE_REPLACE_DASH_RE = re.compile(r"(-)([a-z\d])")

CREDIT_CARDS = {
    "VISA": re.compile(r"^4\d{12}(?:\d{3})?$"),
    "MASTERCARD": re.compile(r"^5[1-5]\d{14}$"),
    "AMERICAN_EXPRESS": re.compile(r"^3[47]\d{13}$"),
    "DINERS_CLUB": re.compile(r"^3(?:0[0-5]|[68]\d)\d{11}$"),
    "DISCOVER": re.compile(r"^6(?:011|5\d{2})\d{12}$"),
    "JCB": re.compile(r"^(?:2131|1800|35\d{3})\d{11}$"),
}

JSON_WRAPPER_RE = re.compile(r"^\s*[\[{]\s*(.*)\s*[\}\]]\s*$", re.MULTILINE | re.DOTALL)

UUID_RE = re.compile(
    r"^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$", re.IGNORECASE
)

UUID_HEX_OK_RE = re.compile(
    r"^[a-f\d]{8}-?[a-f\d]{4}-?[a-f\d]{4}-?[a-f\d]{4}-?[a-f\d]{12}$",
    re.IGNORECASE,
)

SHALLOW_IP_V4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

ANYWHERE_IP_V4_RE = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

IP_V6_RE = re.compile(r"^([a-z\d]{0,4}:){7}[a-z\d]{0,4}$", re.IGNORECASE)

ANYWHERE_IP_V6_RE = re.compile(r"([a-z\d]{0,4}:){7}[a-z\d]{0,4}", re.IGNORECASE)

MAC_ADDRESS_RE = re.compile(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", re.IGNORECASE)

ANYWHERE_MAC_ADDRESS_RE = re.compile(
    r"([0-9A-F]{2}[:-]){5}([0-9A-F]{2})", re.IGNORECASE
)

WORDS_COUNT_RE = re.compile(r"\W*[^\W_]+\W*", re.IGNORECASE | re.MULTILINE | re.UNICODE)

HTML_RE = re.compile(
    r"((<([a-z]+:)?[a-z]+[^>]*/?>)(.*?(</([a-z]+:)?[a-z]+>))?|<!--.*-->|<!doctype.*>)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

HTML_TAG_ONLY_RE = re.compile(
    r"(<([a-z]+:)?[a-z]+[^>]*/?>|</([a-z]+:)?[a-z]+>|<!--.*-->|<!doctype.*>)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

SPACES_RE = re.compile(r"\s")

NO_LETTERS_OR_NUMBERS_RE = re.compile(r"[^\w\d]+|_+", re.IGNORECASE | re.UNICODE)

MARGIN_RE = re.compile(r"^[^\S\r\n]+")

ESCAPE_SEQUENCE_RE = re.compile(r"\x1B\[[^A-Za-z]*[A-Za-z]")

NUM_SUFFIXES = {
    "Pb": (1024**5),
    "P": (1024**5),
    "Tb": (1024**4),
    "T": (1024**4),
    "Gb": (1024**3),
    "G": (1024**3),
    "Mb": (1024**2),
    "M": (1024**2),
    "Kb": (1024**1),
    "K": (1024**1),
}

UNIT_WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]

TENS_WORDS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]

MAGNITUDE_SCALES = [
    "hundred",
    "thousand",
    "million",
    "billion",
    "trillion",
    "quadrillion",
]

NUM_WORDS = {}
NUM_WORDS["and"] = (1, 0)
for i, word in enumerate(UNIT_WORDS):
    NUM_WORDS[word] = (1, i)
for i, word in enumerate(TENS_WORDS):
    NUM_WORDS[word] = (1, i * 10)
for i, word in enumerate(MAGNITUDE_SCALES):
    if i == 0:
        NUM_WORDS[word] = (100, 0)
    else:
        NUM_WORDS[word] = (10 ** (i * 3), 0)
NUM_WORDS['score'] = (20, 0)


def is_none_or_empty(in_str: Optional[str]) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the input string is either None or an empty string,
        False otherwise.

    See also :meth:`is_string` and :meth:`is_empty_string`.

    >>> is_none_or_empty("")
    True
    >>> is_none_or_empty(None)
    True
    >>> is_none_or_empty("   \t   ")
    True
    >>> is_none_or_empty('Test')
    False
    """
    return in_str is None or len(in_str.strip()) == 0


def is_string(in_str: Any) -> bool:
    """
    Args:
        in_str: the object to test

    Returns:
        True if the object is a string and False otherwise.

    See also :meth:`is_empty_string`, :meth:`is_none_or_empty`.

    >>> is_string('test')
    True
    >>> is_string(123)
    False
    >>> is_string(100.3)
    False
    >>> is_string([1, 2, 3])
    False
    """
    return isinstance(in_str, str)


def is_empty_string(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string is empty and False otherwise.

    See also :meth:`is_none_or_empty`, :meth:`is_full_string`.
    """
    return is_empty(in_str)


def is_empty(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string is empty and false otherwise.

    See also :meth:`is_none_or_empty`, :meth:`is_full_string`.

    >>> is_empty('')
    True
    >>> is_empty('    \t\t    ')
    True
    >>> is_empty('test')
    False
    >>> is_empty(100.88)
    False
    >>> is_empty([1, 2, 3])
    False
    """
    return is_string(in_str) and in_str.strip() == ""


def is_full_string(in_str: Any) -> bool:
    """
    Args:
        in_str: the object to test

    Returns:
        True if the object is a string and is not empty ('') and
        is not only composed of whitespace.

    See also :meth:`is_string`, :meth:`is_empty_string`, :meth:`is_none_or_empty`.

    >>> is_full_string('test!')
    True
    >>> is_full_string('')
    False
    >>> is_full_string('      ')
    False
    >>> is_full_string(100.999)
    False
    >>> is_full_string({"a": 1, "b": 2})
    False
    """
    return is_string(in_str) and in_str.strip() != ""


def is_number(in_str: str) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string contains a valid numberic value and
        False otherwise.

    See also :meth:`is_integer_number`, :meth:`is_decimal_number`,
    :meth:`is_hexidecimal_integer_number`, :meth:`is_octal_integer_number`,
    etc...

    >>> is_number(100.5)
    Traceback (most recent call last):
    ...
    ValueError: 100.5
    >>> is_number("100.5")
    True
    >>> is_number("test")
    False
    >>> is_number("99")
    True
    >>> is_number([1, 2, 3])
    Traceback (most recent call last):
    ...
    ValueError: [1, 2, 3]
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return NUMBER_RE.match(in_str) is not None


def is_integer_number(in_str: str) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string contains a valid (signed or unsigned,
        decimal, hex, or octal, regular or scientific) integral
        expression and False otherwise.

    See also :meth:`is_number`, :meth:`is_decimal_number`,
    :meth:`is_hexidecimal_integer_number`, :meth:`is_octal_integer_number`,
    etc...

    >>> is_integer_number('42')
    True
    >>> is_integer_number('42.0')
    False
    """
    return (
        (is_number(in_str) and "." not in in_str)
        or is_hexidecimal_integer_number(in_str)
        or is_octal_integer_number(in_str)
        or is_binary_integer_number(in_str)
    )


def is_hexidecimal_integer_number(in_str: str) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string is a hex integer number and False otherwise.

    See also :meth:`is_integer_number`, :meth:`is_decimal_number`,
    :meth:`is_octal_integer_number`, :meth:`is_binary_integer_number`, etc...

    >>> is_hexidecimal_integer_number('0x12345')
    True
    >>> is_hexidecimal_integer_number('0x1A3E')
    True
    >>> is_hexidecimal_integer_number('1234')  # Needs 0x
    False
    >>> is_hexidecimal_integer_number('-0xff')
    True
    >>> is_hexidecimal_integer_number('test')
    False
    >>> is_hexidecimal_integer_number(12345)  # Not a string
    Traceback (most recent call last):
    ...
    ValueError: 12345
    >>> is_hexidecimal_integer_number(101.4)
    Traceback (most recent call last):
    ...
    ValueError: 101.4
    >>> is_hexidecimal_integer_number(0x1A3E)
    Traceback (most recent call last):
    ...
    ValueError: 6718
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return HEX_NUMBER_RE.match(in_str) is not None


def is_octal_integer_number(in_str: str) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string is a valid octal integral number and False otherwise.

    See also :meth:`is_integer_number`, :meth:`is_decimal_number`,
    :meth:`is_hexidecimal_integer_number`, :meth:`is_binary_integer_number`,
    etc...

    >>> is_octal_integer_number('0o777')
    True
    >>> is_octal_integer_number('-0O115')
    True
    >>> is_octal_integer_number('0xFF')  # Not octal, needs 0o
    False
    >>> is_octal_integer_number('7777')  # Needs 0o
    False
    >>> is_octal_integer_number('test')
    False
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return OCT_NUMBER_RE.match(in_str) is not None


def is_binary_integer_number(in_str: str) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string contains a binary integral number and False otherwise.

    See also :meth:`is_integer_number`, :meth:`is_decimal_number`,
    :meth:`is_hexidecimal_integer_number`, :meth:`is_octal_integer_number`,
    etc...

    >>> is_binary_integer_number('0b10111')
    True
    >>> is_binary_integer_number('-0b111')
    True
    >>> is_binary_integer_number('0B10101')
    True
    >>> is_binary_integer_number('0b10102')
    False
    >>> is_binary_integer_number('0xFFF')
    False
    >>> is_binary_integer_number('test')
    False
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return BIN_NUMBER_RE.match(in_str) is not None


def to_int(in_str: str) -> int:
    """
    Args:
        in_str: the string to convert

    Returns:
        The integral value of the string or raises on error.

    See also :meth:`is_integer_number`, :meth:`is_decimal_number`,
    :meth:`is_hexidecimal_integer_number`, :meth:`is_octal_integer_number`,
    :meth:`is_binary_integer_number`, etc...

    >>> to_int('1234')
    1234
    >>> to_int('0x1234')
    4660
    >>> to_int('0b01101')
    13
    >>> to_int('0o777')
    511
    >>> to_int('test')
    Traceback (most recent call last):
    ...
    ValueError: invalid literal for int() with base 10: 'test'
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    if is_binary_integer_number(in_str):
        return int(in_str, 2)
    if is_octal_integer_number(in_str):
        return int(in_str, 8)
    if is_hexidecimal_integer_number(in_str):
        return int(in_str, 16)
    return int(in_str)


def number_string_to_integer(in_str: str) -> int:
    """Convert a string containing a written-out number into an int.

    Args:
        in_str: the string containing the long-hand written out integer number
            in English.  See examples below.

    Returns:
        The integer whose value was parsed from in_str.

    See also :meth:`integer_to_number_string`.

    .. warning::
        This code only handles integers; it will not work with decimals / floats.

    >>> number_string_to_integer("one hundred fifty two")
    152

    >>> number_string_to_integer("ten billion two hundred million fifty four thousand three")
    10200054003

    >>> number_string_to_integer("four-score and 7")
    87

    >>> number_string_to_integer("fifty xyzzy three")
    Traceback (most recent call last):
    ...
    ValueError: Unknown word: xyzzy
    """
    if isinstance(in_str, int):
        return int(in_str)

    current = result = 0
    in_str = in_str.replace('-', ' ')
    for w in in_str.split():
        if w not in NUM_WORDS:
            if is_integer_number(w):
                current += int(w)
                continue
            else:
                raise ValueError("Unknown word: " + w)
        scale, increment = NUM_WORDS[w]
        current = current * scale + increment
        if scale > 100:
            result += current
            current = 0
    return result + current


def integer_to_number_string(num: int) -> str:
    """
    Opposite of :meth:`number_string_to_integer`; converts a number to a written out
    longhand format in English.

    Args:
        num: the integer number to convert

    Returns:
        The long-hand written out English form of the number.  See examples below.

    See also :meth:`number_string_to_integer`.

    .. warning::
        This method does not handle decimals or floats, only ints.

    >>> integer_to_number_string(9)
    'nine'

    >>> integer_to_number_string(42)
    'forty two'

    >>> integer_to_number_string(123219982)
    'one hundred twenty three million two hundred nineteen thousand nine hundred eighty two'
    """

    if num < 20:
        return UNIT_WORDS[num]
    if num < 100:
        ret = TENS_WORDS[num // 10]
        leftover = num % 10
        if leftover != 0:
            ret += ' ' + UNIT_WORDS[leftover]
        return ret

    # If num > 100 go find the highest chunk and convert that, then recursively
    # convert the rest.  NUM_WORDS contains items like 'thousand' -> (1000, 0).
    # The second item in the tuple is an increment that can be ignored; the first
    # is the numeric "scale" of the entry.  So find the greatest entry in NUM_WORDS
    # still less than num.  For 123,456 it would be thousand.  Then pull out the
    # 123, convert it, and append "thousand".  Then do the rest.
    scales = {}
    for name, val in NUM_WORDS.items():
        if val[0] <= num:
            scales[name] = val[0]
    scale = max(scales.items(), key=lambda _: _[1])

    # scale[1] = numeric magnitude (e.g. 1000)
    # scale[0] = name (e.g. "thousand")
    ret = integer_to_number_string(num // scale[1]) + ' ' + scale[0]
    leftover = num % scale[1]
    if leftover != 0:
        ret += ' ' + integer_to_number_string(leftover)
    return ret


def is_decimal_number(in_str: str) -> bool:
    """
    Args:
        in_str: the string to check

    Returns:
        True if the given string represents a decimal or False
        otherwise.  A decimal may be signed or unsigned or use
        a "scientific notation".

    See also :meth:`is_integer_number`.

    .. note::
        We do not consider integers without a decimal point
        to be decimals; they return False (see example).

    >>> is_decimal_number('42.0')
    True
    >>> is_decimal_number('42')
    False
    """
    return is_number(in_str) and "." in in_str


def strip_escape_sequences(in_str: str) -> str:
    """
    Args:
        in_str: the string to strip of escape sequences.

    Returns:
        in_str with escape sequences removed.

    See also: :mod:`pyutils.ansi`.

    .. note::
        What is considered to be an "escape sequence" is defined
        by a regular expression.  While this gets common ones,
        there may exist valid sequences that it doesn't match.

    >>> strip_escape_sequences('\x1B[12;11;22mthis is a test!')
    'this is a test!'
    """
    in_str = ESCAPE_SEQUENCE_RE.sub("", in_str)
    return in_str


def add_thousands_separator(
    in_str: str, *, separator_char: str = ',', places: int = 3
) -> str:
    """
    Args:
        in_str: string or number to which to add thousands separator(s)
        separator_char: the separator character to add (defaults to comma)
        places: add a separator every N places (defaults to three)

    Returns:
        A numeric string with thousands separators added appropriately.

    >>> add_thousands_separator('12345678')
    '12,345,678'
    >>> add_thousands_separator(12345678)
    '12,345,678'
    >>> add_thousands_separator(12345678.99)
    '12,345,678.99'
    >>> add_thousands_separator('test')
    Traceback (most recent call last):
    ...
    ValueError: test

    """
    if isinstance(in_str, numbers.Number):
        in_str = f'{in_str}'
    if is_number(in_str):
        return _add_thousands_separator(
            in_str, separator_char=separator_char, places=places
        )
    raise ValueError(in_str)


def _add_thousands_separator(in_str: str, *, separator_char=',', places=3) -> str:
    """Internal helper"""
    decimal_part = ""
    if '.' in in_str:
        (in_str, decimal_part) = in_str.split('.')
    tmp = [iter(in_str[::-1])] * places
    ret = separator_char.join("".join(x) for x in zip_longest(*tmp, fillvalue=""))[::-1]
    if len(decimal_part) > 0:
        ret += '.'
        ret += decimal_part
    return ret


def is_url(in_str: Any, allowed_schemes: Optional[List[str]] = None) -> bool:
    """
    Args:
        in_str: the string to test
        allowed_schemes: an optional list of allowed schemes (e.g.
            ['http', 'https', 'ftp'].  If passed, only URLs that
            begin with the one of the schemes passed will be considered
            to be valid.  Otherwise, any scheme:// will be considered
            valid.

    Returns:
        True if in_str contains a valid URL and False otherwise.

    >>> is_url('http://www.mysite.com')
    True
    >>> is_url('https://mysite.com')
    True
    >>> is_url('.mysite.com')
    False
    >>> is_url('scheme://username:password@www.domain.com:8042/folder/subfolder/file.extension?param=value&param2=value2#hash')
    True
    """
    if not is_full_string(in_str):
        return False

    valid = URL_RE.match(in_str) is not None

    if allowed_schemes:
        return valid and any([in_str.startswith(s) for s in allowed_schemes])
    return valid


def is_email(in_str: Any) -> bool:
    """
    Args:
        in_str: the email address to check

    Returns: True if the in_str contains a valid email (as defined by
        https://tools.ietf.org/html/rfc3696#section-3) or False
        otherwise.

    >>> is_email('my.email@the-provider.com')
    True
    >>> is_email('@gmail.com')
    False
    """
    if not is_full_string(in_str) or len(in_str) > 320 or in_str.startswith("."):
        return False

    try:
        # we expect 2 tokens, one before "@" and one after, otherwise
        # we have an exception and the email is not valid.
        head, tail = in_str.split("@")

        # head's size must be <= 64, tail <= 255, head must not start
        # with a dot or contain multiple consecutive dots.
        if len(head) > 64 or len(tail) > 255 or head.endswith(".") or (".." in head):
            return False

        # removes escaped spaces, so that later on the test regex will
        # accept the string.
        head = head.replace("\\ ", "")
        if head.startswith('"') and head.endswith('"'):
            head = head.replace(" ", "")[1:-1]
        return EMAIL_RE.match(head + "@" + tail) is not None

    except ValueError:
        # borderline case in which we have multiple "@" signs but the
        # head part is correctly escaped.
        if ESCAPED_AT_SIGN.search(in_str) is not None:
            # replace "@" with "a" in the head
            return is_email(ESCAPED_AT_SIGN.sub("a", in_str))
        return False


def suffix_string_to_number(in_str: str) -> Optional[int]:
    """Takes a string like "33Gb" and converts it into a number (of bytes)
    like 34603008.

    Args:
        in_str: the string with a suffix to be interpreted and removed.

    Returns:
        An integer number of bytes or None to indicate an error.

    See also :meth:`number_to_suffix_string`.

    >>> suffix_string_to_number('1Mb')
    1048576
    >>> suffix_string_to_number('13.1Gb')
    14066017894
    """

    def suffix_capitalize(s: str) -> str:
        if len(s) == 1:
            return s.upper()
        elif len(s) == 2:
            return f"{s[0].upper()}{s[1].lower()}"
        return suffix_capitalize(s[0:1])

    if is_string(in_str):
        if is_integer_number(in_str):
            return to_int(in_str)
        suffixes = [in_str[-2:], in_str[-1:]]
        rest = [in_str[:-2], in_str[:-1]]
        for x in range(len(suffixes)):
            s = suffixes[x]
            s = suffix_capitalize(s)
            multiplier = NUM_SUFFIXES.get(s, None)
            if multiplier is not None:
                r = rest[x]
                if is_integer_number(r):
                    return to_int(r) * multiplier
                if is_decimal_number(r):
                    return int(float(r) * multiplier)
    return None


def number_to_suffix_string(num: int) -> Optional[str]:
    """Take a number (of bytes) and returns a string like "43.8Gb".

    Args:
        num: an integer number of bytes

    Returns:
        A string with a suffix representing num bytes concisely or
        None to indicate an error.

    See also: :meth:`suffix_string_to_number`.

    >>> number_to_suffix_string(14066017894)
    '13.1Gb'
    >>> number_to_suffix_string(1024 * 1024)
    '1.0Mb'
    """
    d = 0.0
    suffix = None
    for (sfx, size) in NUM_SUFFIXES.items():
        if num >= size:
            d = num / size
            suffix = sfx
            break
    if suffix is not None:
        return f"{d:.1f}{suffix}"
    else:
        return f'{num:d}'


def is_credit_card(in_str: Any, card_type: str = None) -> bool:
    """
    Args:
        in_str: a string to check
        card_type: if provided, contains the card type to validate
            with.  Otherwise, all known credit card number types will
            be accepted.

            Supported card types are the following:

            * VISA
            * MASTERCARD
            * AMERICAN_EXPRESS
            * DINERS_CLUB
            * DISCOVER
            * JCB

    Returns:
        True if in_str is a valid credit card number.

    .. warning::
        This code is not verifying the authenticity of the credit card (i.e.
        not checking whether it's a real card that can be charged); rather
        it's only checking that the number follows the "rules" for numbering
        established by credit card issuers.

    """
    if not is_full_string(in_str):
        return False

    if card_type is not None:
        if card_type not in CREDIT_CARDS:
            raise KeyError(
                f'Invalid card type "{card_type}". Valid types are: {CREDIT_CARDS.keys()}'
            )
        return CREDIT_CARDS[card_type].match(in_str) is not None
    for c in CREDIT_CARDS:
        if CREDIT_CARDS[c].match(in_str) is not None:
            return True
    return False


def is_camel_case(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the string is formatted as camel case and False otherwise.
        A string is considered camel case when:

        * it's composed only by letters ([a-zA-Z]) and optionally numbers ([0-9])
        * it contains both lowercase and uppercase letters
        * it does not start with a number

    See also :meth:`is_snake_case`, :meth:`is_slug`, and :meth:`camel_case_to_snake_case`.
    """
    return is_full_string(in_str) and CAMEL_CASE_TEST_RE.match(in_str) is not None


def is_snake_case(in_str: Any, *, separator: str = "_") -> bool:
    """
    Args:
        in_str: the string to test
        separator: the snake case separator character to use

    Returns: True if the string is snake case and False otherwise.  A
        string is considered snake case when:

        * it's composed only by lowercase/uppercase letters and digits
        * it contains at least one underscore (or provided separator)
        * it does not start with a number

    See also :meth:`is_camel_case`, :meth:`is_slug`, and :meth:`snake_case_to_camel_case`.

    >>> is_snake_case('this_is_a_test')
    True
    >>> is_snake_case('___This_Is_A_Test_1_2_3___')
    True
    >>> is_snake_case('this-is-a-test')
    False
    >>> is_snake_case('this-is-a-test', separator='-')
    True
    """
    if is_full_string(in_str):
        re_map = {"_": SNAKE_CASE_TEST_RE, "-": SNAKE_CASE_TEST_DASH_RE}
        re_template = r"([a-z]+\d*{sign}[a-z\d{sign}]*|{sign}+[a-z\d]+[a-z\d{sign}]*)"
        r = re_map.get(
            separator,
            re.compile(re_template.format(sign=re.escape(separator)), re.IGNORECASE),
        )
        return r.match(in_str) is not None
    return False


def is_json(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if the in_str contains valid JSON and False otherwise.

    >>> is_json('{"name": "Peter"}')
    True
    >>> is_json('[1, 2, 3]')
    True
    >>> is_json('{nope}')
    False
    """
    if is_full_string(in_str) and JSON_WRAPPER_RE.match(in_str) is not None:
        try:
            return isinstance(json.loads(in_str), (dict, list))
        except (TypeError, ValueError, OverflowError):
            pass
    return False


def is_uuid(in_str: Any, allow_hex: bool = False) -> bool:
    """
    Args:
        in_str: the string to test
        allow_hex: should we allow hexidecimal digits in valid uuids?

    Returns:
        True if the in_str contains a valid UUID and False otherwise.

    See also :meth:`generate_uuid`.

    >>> is_uuid('6f8aa2f9-686c-4ac3-8766-5712354a04cf')
    True
    >>> is_uuid('6f8aa2f9686c4ac387665712354a04cf')
    False
    >>> is_uuid('6f8aa2f9686c4ac387665712354a04cf', allow_hex=True)
    True
    """
    # string casting is used to allow UUID itself as input data type
    s = str(in_str)
    if allow_hex:
        return UUID_HEX_OK_RE.match(s) is not None
    return UUID_RE.match(s) is not None


def is_ip_v4(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if in_str contains a valid IPv4 address and False otherwise.

    See also :meth:`extract_ip_v4`, :meth:`is_ip_v6`, :meth:`extract_ip_v6`,
    and :meth:`is_ip`.

    >>> is_ip_v4('255.200.100.75')
    True
    >>> is_ip_v4('nope')
    False
    >>> is_ip_v4('255.200.100.999')  # 999 out of range
    False
    """
    if not is_full_string(in_str) or SHALLOW_IP_V4_RE.match(in_str) is None:
        return False

    # checks that each entry in the ip is in the valid range (0 to 255)
    for token in in_str.split("."):
        if not 0 <= int(token) <= 255:
            return False
    return True


def extract_ip_v4(in_str: Any) -> Optional[str]:
    """
    Args:
        in_str: the string to extract an IPv4 address from.

    Returns:
        The first extracted IPv4 address from in_str or None if
        none were found or an error occurred.

    See also :meth:`is_ip_v4`, :meth:`is_ip_v6`, :meth:`extract_ip_v6`,
    and :meth:`is_ip`.

    >>> extract_ip_v4('   The secret IP address: 127.0.0.1 (use it wisely)   ')
    '127.0.0.1'
    >>> extract_ip_v4('Your mom dresses you funny.')
    """
    if not is_full_string(in_str):
        return None
    m = ANYWHERE_IP_V4_RE.search(in_str)
    if m is not None:
        return m.group(0)
    return None


def is_ip_v6(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test.

    Returns:
        True if in_str contains a valid IPv6 address and False otherwise.

    See also :meth:`is_ip_v4`, :meth:`extract_ip_v4`, :meth:`extract_ip_v6`,
    and :meth:`is_ip`.

    >>> is_ip_v6('2001:db8:85a3:0000:0000:8a2e:370:7334')
    True
    >>> is_ip_v6('2001:db8:85a3:0000:0000:8a2e:370:?')    # invalid "?"
    False
    """
    return is_full_string(in_str) and IP_V6_RE.match(in_str) is not None


def extract_ip_v6(in_str: Any) -> Optional[str]:
    """
    Args:
        in_str: the string from which to extract an IPv6 address.

    Returns:
        The first IPv6 address found in in_str or None if no address
        was found or an error occurred.

    See also :meth:`is_ip_v4`, :meth:`is_ip_v6`, :meth:`extract_ip_v4`,
    and :meth:`is_ip`.

    >>> extract_ip_v6('IP: 2001:db8:85a3:0000:0000:8a2e:370:7334')
    '2001:db8:85a3:0000:0000:8a2e:370:7334'
    >>> extract_ip_v6("(and she's ugly too, btw)")
    """
    if not is_full_string(in_str):
        return None
    m = ANYWHERE_IP_V6_RE.search(in_str)
    if m is not None:
        return m.group(0)
    return None


def is_ip(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test.

    Returns:
        True if in_str contains a valid IP address (either IPv4 or
        IPv6).

    See also :meth:`is_ip_v4`, :meth:`is_ip_v6`, :meth:`extract_ip_v6`,
    and :meth:`extract_ip_v4`.

    >>> is_ip('255.200.100.75')
    True
    >>> is_ip('2001:db8:85a3:0000:0000:8a2e:370:7334')
    True
    >>> is_ip('1.2.3')
    False
    >>> is_ip('1.2.3.999')
    False
    """
    return is_ip_v6(in_str) or is_ip_v4(in_str)


def extract_ip(in_str: Any) -> Optional[str]:
    """
    Args:
        in_str: the string from which to extract in IP address.

    Returns:
        The first IP address (IPv4 or IPv6) found in in_str or
        None to indicate none found or an error condition.

    See also :meth:`is_ip_v4`, :meth:`is_ip_v6`, :meth:`extract_ip_v6`,
    and :meth:`extract_ip_v4`.

    >>> extract_ip('Attacker: 255.200.100.75')
    '255.200.100.75'
    >>> extract_ip('Remote host: 2001:db8:85a3:0000:0000:8a2e:370:7334')
    '2001:db8:85a3:0000:0000:8a2e:370:7334'
    >>> extract_ip('1.2.3')
    """
    ip = extract_ip_v4(in_str)
    if ip is None:
        ip = extract_ip_v6(in_str)
    return ip


def is_mac_address(in_str: Any) -> bool:
    """
    Args:
        in_str: the string to test

    Returns:
        True if in_str is a valid MAC address False otherwise.

    See also :meth:`extract_mac_address`, :meth:`is_ip`, etc...

    >>> is_mac_address("34:29:8F:12:0D:2F")
    True
    >>> is_mac_address('34:29:8f:12:0d:2f')
    True
    >>> is_mac_address('34-29-8F-12-0D-2F')
    True
    >>> is_mac_address("test")
    False
    """
    return is_full_string(in_str) and MAC_ADDRESS_RE.match(in_str) is not None


def extract_mac_address(in_str: Any, *, separator: str = ":") -> Optional[str]:
    """
    Args:
        in_str: the string from which to extract a MAC address.
        separator: the MAC address hex byte separator to use.

    Returns:
        The first MAC address found in in_str or None to indicate no
        match or an error.

    See also :meth:`is_mac_address`, :meth:`is_ip`, and :meth:`extract_ip`.

    >>> extract_mac_address(' MAC Address: 34:29:8F:12:0D:2F')
    '34:29:8F:12:0D:2F'

    >>> extract_mac_address('? (10.0.0.30) at d8:5d:e2:34:54:86 on em0 expires in 1176 seconds [ethernet]')
    'd8:5d:e2:34:54:86'
    """
    if not is_full_string(in_str):
        return None
    in_str.strip()
    m = ANYWHERE_MAC_ADDRESS_RE.search(in_str)
    if m is not None:
        mac = m.group(0)
        mac.replace(":", separator)
        mac.replace("-", separator)
        return mac
    return None


def is_slug(in_str: Any, separator: str = "-") -> bool:
    """
    Args:
        in_str: string to test
        separator: the slug character to use

    Returns:
        True if in_str is a slug string and False otherwise.

    See also :meth:`is_camel_case`, :meth:`is_snake_case`, and :meth:`slugify`.

    >>> is_slug('my-blog-post-title')
    True
    >>> is_slug('My blog post title')
    False
    """
    if not is_full_string(in_str):
        return False
    rex = r"^([a-z\d]+" + re.escape(separator) + r"*?)*[a-z\d]$"
    return re.match(rex, in_str) is not None


def contains_html(in_str: str) -> bool:
    """
    Args:
        in_str: the string to check for tags in

    Returns:
        True if the given string contains HTML/XML tags and False
        otherwise.

    See also :meth:`strip_html`.

    .. warning::
        By design, this function matches ANY type of tag, so don't expect
        to use it as an HTML validator.  It's a quick sanity check at
        best.  See something like BeautifulSoup for a more full-featuered
        HTML parser.

    >>> contains_html('my string is <strong>bold</strong>')
    True
    >>> contains_html('my string is not bold')
    False

    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return HTML_RE.search(in_str) is not None


def words_count(in_str: str) -> int:
    """
    Args:
        in_str: the string to count words in

    Returns:
        The number of words contained in the given string.

    .. note::
        This method is "smart" in that it does consider only sequences
        of one or more letter and/or numbers to be "words".  Thus a
        string like this: "! @ # % ... []" will return zero.  Moreover
        it is aware of punctuation, so the count for a string like
        "one,two,three.stop" will be 4 not 1 (even if there are no spaces
        in the string).

    >>> words_count('hello world')
    2
    >>> words_count('one,two,three.stop')
    4
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return len(WORDS_COUNT_RE.findall(in_str))


def word_count(in_str: str) -> int:
    """
    Args:
        in_str: the string to count words in

    Returns:
        The number of words contained in the given string.

    .. note::
        This method is "smart" in that it does consider only sequences
        of one or more letter and/or numbers to be "words".  Thus a
        string like this: "! @ # % ... []" will return zero.  Moreover
        it is aware of punctuation, so the count for a string like
        "one,two,three.stop" will be 4 not 1 (even if there are no spaces
        in the string).

    >>> word_count('hello world')
    2
    >>> word_count('one,two,three.stop')
    4
    """
    return words_count(in_str)


def generate_uuid(omit_dashes: bool = False) -> str:
    """
    Args:
        omit_dashes: should we omit the dashes in the generated UUID?

    Returns:
        A generated UUID string (using `uuid.uuid4()`) with or without
        dashes per the omit_dashes arg.

    See also :meth:`is_uuid`, :meth:`generate_random_alphanumeric_string`.

    generate_uuid() # possible output: '97e3a716-6b33-4ab9-9bb1-8128cb24d76b'
    generate_uuid(omit_dashes=True) # possible output: '97e3a7166b334ab99bb18128cb24d76b'
    """
    uid = uuid4()
    if omit_dashes:
        return uid.hex
    return str(uid)


def generate_random_alphanumeric_string(size: int) -> str:
    """
    Args:
        size: number of characters to generate

    Returns:
        A string of the specified size containing random characters
        (uppercase/lowercase ascii letters and digits).

    See also :meth:`asciify`, :meth:`generate_uuid`.

    >>> random.seed(22)
    >>> generate_random_alphanumeric_string(9)
    '96ipbNClS'
    """
    if size < 1:
        raise ValueError("size must be >= 1")
    chars = string.ascii_letters + string.digits
    buffer = [random.choice(chars) for _ in range(size)]
    return from_char_list(buffer)


def reverse(in_str: str) -> str:
    """
    Args:
        in_str: the string to reverse

    Returns:
        The reversed (chracter by character) string.

    >>> reverse('test')
    'tset'
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return in_str[::-1]


def camel_case_to_snake_case(in_str: str, *, separator: str = "_"):
    """
    Args:
        in_str: the camel case string to convert
        separator: the snake case separator character to use

    Returns:
        A snake case string equivalent to the camel case input or the
        original string if it is not a valid camel case string or some
        other error occurs.

    See also :meth:`is_camel_case`, :meth:`is_snake_case`, and :meth:`is_slug`.

    >>> camel_case_to_snake_case('MacAddressExtractorFactory')
    'mac_address_extractor_factory'
    >>> camel_case_to_snake_case('Luke Skywalker')
    'Luke Skywalker'
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    if not is_camel_case(in_str):
        return in_str
    return CAMEL_CASE_REPLACE_RE.sub(lambda m: m.group(1) + separator, in_str).lower()


def snake_case_to_camel_case(
    in_str: str, *, upper_case_first: bool = True, separator: str = "_"
) -> str:
    """
    Args:
        in_str: the snake case string to convert
        upper_case_first: should we capitalize the first letter?
        separator: the separator character to use

    Returns:
        A camel case string that is equivalent to the snake case string
        provided or the original string back again if it is not valid
        snake case or another error occurs.

    See also :meth:`is_camel_case`, :meth:`is_snake_case`, and :meth:`is_slug`.

    >>> snake_case_to_camel_case('this_is_a_test')
    'ThisIsATest'
    >>> snake_case_to_camel_case('Han Solo')
    'Han Solo'
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    if not is_snake_case(in_str, separator=separator):
        return in_str
    tokens = [s.title() for s in in_str.split(separator) if is_full_string(s)]
    if not upper_case_first:
        tokens[0] = tokens[0].lower()
    return from_char_list(tokens)


def to_char_list(in_str: str) -> List[str]:
    """
    Args:
        in_str: the string to split into a char list

    Returns:
        A list of strings of length one each.

    See also :meth:`from_char_list`.

    >>> to_char_list('test')
    ['t', 'e', 's', 't']
    """
    if not is_string(in_str):
        return []
    return list(in_str)


def from_char_list(in_list: List[str]) -> str:
    """
    Args:
        in_list: A list of characters to convert into a string.

    Returns:
        The string resulting from gluing the characters in in_list
        together.

    See also :meth:`to_char_list`.

    >>> from_char_list(['t', 'e', 's', 't'])
    'test'
    """
    return "".join(in_list)


def shuffle(in_str: str) -> Optional[str]:
    """
    Args:
        in_str: a string to shuffle randomly by character

    Returns:
        A new string containing same chars of the given one but in
        a randomized order.  Note that in rare cases this could result
        in the same original string as no check is done.  Returns
        None to indicate error conditions.

    >>> random.seed(22)
    >>> shuffle('awesome')
    'meosaew'
    """
    if not is_string(in_str):
        return None
    chars = to_char_list(in_str)
    random.shuffle(chars)
    return from_char_list(chars)


def scramble(in_str: str) -> Optional[str]:
    """
    Args:
        in_str: a string to shuffle randomly by character

    Returns:
        A new string containing same chars of the given one but in
        a randomized order.  Note that in rare cases this could result
        in the same original string as no check is done.  Returns
        None to indicate error conditions.

    See also :mod:`pyutils.unscrambler`.

    >>> random.seed(22)
    >>> scramble('awesome')
    'meosaew'
    """
    return shuffle(in_str)


def strip_html(in_str: str, keep_tag_content: bool = False) -> str:
    """
    Args:
        in_str: the string to strip tags from
        keep_tag_content: should we keep the inner contents of tags?

    Returns:
        A string with all HTML tags removed (optionally with tag contents
        preserved).

    See also :meth:`contains_html`.

    .. note::
        This method uses simple regular expressions to strip tags and is
        not a full fledged HTML parser by any means.  Consider using
        something like BeautifulSoup if your needs are more than this
        simple code can fulfill.

    >>> strip_html('test: <a href="foo/bar">click here</a>')
    'test: '
    >>> strip_html('test: <a href="foo/bar">click here</a>', keep_tag_content=True)
    'test: click here'
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    r = HTML_TAG_ONLY_RE if keep_tag_content else HTML_RE
    return r.sub("", in_str)


def asciify(in_str: str) -> str:
    """
    Args:
        in_str: the string to asciify.

    Returns:
        An output string roughly equivalent to the original string
        where all content to are ascii-only.  This is accomplished
        by translating all non-ascii chars into their closest possible
        ASCII representation (eg: ó -> o, Ë -> E, ç -> c...).

    See also :meth:`to_ascii`, :meth:`generate_random_alphanumeric_string`.

    .. warning::
        Some chars may be lost if impossible to translate.

    >>> asciify('èéùúòóäåëýñÅÀÁÇÌÍÑÓË')
    'eeuuooaaeynAAACIINOE'
    """
    if not is_string(in_str):
        raise ValueError(in_str)

    # "NFKD" is the algorithm which is able to successfully translate
    # the most of non-ascii chars.
    normalized = unicodedata.normalize("NFKD", in_str)

    # encode string forcing ascii and ignore any errors
    # (unrepresentable chars will be stripped out)
    ascii_bytes = normalized.encode("ascii", "ignore")

    # turns encoded bytes into an utf-8 string
    return ascii_bytes.decode("utf-8")


def slugify(in_str: str, *, separator: str = "-") -> str:
    """
    Args:
        in_str: the string to slugify
        separator: the character to use during sligification (default
            is a dash)

    Returns:
        The converted string.  The returned string has the following properties:

        * it has no spaces
        * all letters are in lower case
        * all punctuation signs and non alphanumeric chars are removed
        * words are divided using provided separator
        * all chars are encoded as ascii (by using :meth:`asciify`)
        * is safe for URL

    See also :meth:`is_slug` and :meth:`asciify`.

    >>> slugify('Top 10 Reasons To Love Dogs!!!')
    'top-10-reasons-to-love-dogs'
    >>> slugify('Mönstér Mägnët')
    'monster-magnet'
    """
    if not is_string(in_str):
        raise ValueError(in_str)

    # replace any character that is NOT letter or number with spaces
    out = NO_LETTERS_OR_NUMBERS_RE.sub(" ", in_str.lower()).strip()

    # replace spaces with join sign
    out = SPACES_RE.sub(separator, out)

    # normalize joins (remove duplicates)
    out = re.sub(re.escape(separator) + r"+", separator, out)
    return asciify(out)


def to_bool(in_str: str) -> bool:
    """
    Args:
        in_str: the string to convert to boolean

    Returns:
        A boolean equivalent of the original string based on its contents.
        All conversion is case insensitive.  A positive boolean (True) is
        returned if the string value is any of the following:

        * "true"
        * "t"
        * "1"
        * "yes"
        * "y"
        * "on"

        Otherwise False is returned.

    See also :mod:`pyutils.argparse_utils`.

    >>> to_bool('True')
    True

    >>> to_bool('1')
    True

    >>> to_bool('yes')
    True

    >>> to_bool('no')
    False

    >>> to_bool('huh?')
    False

    >>> to_bool('on')
    True
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    return in_str.lower() in set(["true", "1", "yes", "y", "t", "on"])


def to_date(in_str: str) -> Optional[datetime.date]:
    """
    Args:
        in_str: the string to convert into a date

    Returns:
        The datetime.date the string contained or None to indicate
        an error.  This parser is relatively clever; see
        :class:`datetimes.dateparse_utils` docs for details.

    See also: :mod:`pyutils.datetimes.dateparse_utils`, :meth:`extract_date`,
    :meth:`is_valid_date`, :meth:`to_datetime`, :meth:`valid_datetime`.

    >>> to_date('9/11/2001')
    datetime.date(2001, 9, 11)
    >>> to_date('xyzzy')
    """
    import pyutils.datetimes.dateparse_utils as du

    try:
        d = du.DateParser()  # type: ignore
        d.parse(in_str)
        return d.get_date()
    except du.ParseException:  # type: ignore
        pass
    return None


def extract_date(in_str: Any) -> Optional[datetime.datetime]:
    """Finds and extracts a date from the string, if possible.

    Args:
        in_str: the string to extract a date from

    Returns:
        a datetime if date was found, otherwise None

    See also: :mod:`pyutils.datetimes.dateparse_utils`, :meth:`to_date`,
    :meth:`is_valid_date`, :meth:`to_datetime`, :meth:`valid_datetime`.

    >>> extract_date("filename.txt    dec 13, 2022")
    datetime.datetime(2022, 12, 13, 0, 0)

    >>> extract_date("Dear Santa, please get me a pony.")

    """
    import itertools

    import pyutils.datetimes.dateparse_utils as du

    d = du.DateParser()  # type: ignore
    chunks = in_str.split()
    for ngram in itertools.chain(
        list_utils.ngrams(chunks, 5),
        list_utils.ngrams(chunks, 4),
        list_utils.ngrams(chunks, 3),
        list_utils.ngrams(chunks, 2),
    ):
        try:
            expr = " ".join(ngram)
            logger.debug("Trying %s", expr)
            if d.parse(expr):
                return d.get_datetime()
        except du.ParseException:  # type: ignore
            pass
    return None


def is_valid_date(in_str: str) -> bool:
    """
    Args:
        in_str: the string to check

    Returns:
        True if the string represents a valid date that we can recognize
        and False otherwise.  This parser is relatively clever; see
        :class:`datetimes.dateparse_utils` docs for details.

    See also: :mod:`pyutils.datetimes.dateparse_utils`, :meth:`to_date`,
    :meth:`extract_date`, :meth:`to_datetime`, :meth:`valid_datetime`.

    >>> is_valid_date('1/2/2022')
    True
    >>> is_valid_date('christmas')
    True
    >>> is_valid_date('next wednesday')
    True
    >>> is_valid_date('xyzzy')
    False
    """
    import pyutils.datetimes.dateparse_utils as dp

    try:
        d = dp.DateParser()  # type: ignore
        _ = d.parse(in_str)
        return True
    except dp.ParseException:  # type: ignore
        pass
    return False


def to_datetime(in_str: str) -> Optional[datetime.datetime]:
    """
    Args:
        in_str: string to parse into a datetime

    Returns:
        A python datetime parsed from in_str or None to indicate
        an error.  This parser is relatively clever; see
        :class:`datetimes.dateparse_utils` docs for details.

    See also: :mod:`pyutils.datetimes.dateparse_utils`, :meth:`to_date`,
    :meth:`extract_date`, :meth:`valid_datetime`.

    >>> to_datetime('7/20/1969 02:56 GMT')
    datetime.datetime(1969, 7, 20, 2, 56, tzinfo=<StaticTzInfo 'GMT'>)
    """
    import pyutils.datetimes.dateparse_utils as dp

    try:
        d = dp.DateParser()  # type: ignore
        dt = d.parse(in_str)
        if isinstance(dt, datetime.datetime):
            return dt
    except Exception:
        pass
    return None


def valid_datetime(in_str: str) -> bool:
    """
    Args:
        in_str: the string to check

    Returns:
        True if in_str contains a valid datetime and False otherwise.
        This parser is relatively clever; see
        :class:`datetimes.dateparse_utils` docs for details.

    >>> valid_datetime('next wednesday at noon')
    True
    >>> valid_datetime('3 weeks ago at midnight')
    True
    >>> valid_datetime('next easter at 5:00 am')
    True
    >>> valid_datetime('sometime soon')
    False
    """
    _ = to_datetime(in_str)
    if _ is not None:
        return True
    return False


def squeeze(in_str: str, character_to_squeeze: str = ' ') -> str:
    """
    Args:
        in_str: the string to squeeze
        character_to_squeeze: the character to remove runs of
            more than one in a row (default = space)

    Returns: A "squeezed string" where runs of more than one
        character_to_squeeze into one.

    >>> squeeze(' this        is       a    test    ')
    ' this is a test '

    >>> squeeze('one|!||!|two|!||!|three', character_to_squeeze='|!|')
    'one|!|two|!|three'

    """
    return re.sub(
        r'(' + re.escape(character_to_squeeze) + r')+',
        character_to_squeeze,
        in_str,
    )


def dedent(in_str: str) -> Optional[str]:
    """
    Args:
        in_str: the string to dedent

    Returns:
        A string with tab indentation removed or None on error.

    See also :meth:`indent`.

    >>> dedent('\t\ttest\\n\t\ting')
    'test\\ning'
    """
    if not is_string(in_str):
        return None
    line_separator = '\n'
    lines = [MARGIN_RE.sub('', line) for line in in_str.split(line_separator)]
    return line_separator.join(lines)


def indent(in_str: str, amount: int) -> str:
    """
    Args:
        in_str: the string to indent
        amount: count of spaces to indent each line by

    Returns:
        An indented string created by prepending amount spaces.

    See also :meth:`dedent`.

    >>> indent('This is a test', 4)
    '    This is a test'
    """
    if not is_string(in_str):
        raise ValueError(in_str)
    line_separator = '\n'
    lines = [" " * amount + line for line in in_str.split(line_separator)]
    return line_separator.join(lines)


def _sprintf(*args, **kwargs) -> str:
    """Internal helper."""
    ret = ""

    sep = kwargs.pop("sep", None)
    if sep is not None:
        if not isinstance(sep, str):
            raise TypeError("sep must be None or a string")

    end = kwargs.pop("end", None)
    if end is not None:
        if not isinstance(end, str):
            raise TypeError("end must be None or a string")

    if kwargs:
        raise TypeError("invalid keyword arguments to sprint()")

    if sep is None:
        sep = " "
    if end is None:
        end = "\n"
    for n, arg in enumerate(args):
        if n:
            ret += sep
        if isinstance(arg, str):
            ret += arg
        else:
            ret += str(arg)
    ret += end
    return ret


def strip_ansi_sequences(in_str: str) -> str:
    """
    Args:
        in_str: the string to strip

    Returns:
        in_str with recognized ANSI escape sequences removed.

    See also :mod:`pyutils.ansi`.

    .. warning::
        This method works by using a regular expression.
        It works for all ANSI escape sequences I've tested with but
        may miss some; caveat emptor.

    >>> import ansi as a
    >>> s = a.fg('blue') + 'blue!' + a.reset()
    >>> len(s)   # '\x1b[38;5;21mblue!\x1b[m'
    18
    >>> len(strip_ansi_sequences(s))
    5
    >>> strip_ansi_sequences(s)
    'blue!'

    """
    return re.sub(r'\x1b\[[\d+;]*[a-z]', '', in_str)


class SprintfStdout(contextlib.AbstractContextManager):
    """
    A context manager that captures outputs to stdout to a buffer
    without printing them.

    >>> with SprintfStdout() as buf:
    ...     print("test")
    ...     print("1, 2, 3")
    ...
    >>> print(buf(), end='')
    test
    1, 2, 3
    """

    def __init__(self) -> None:
        self.destination = io.StringIO()
        self.recorder: contextlib.redirect_stdout

    def __enter__(self) -> Callable[[], str]:
        self.recorder = contextlib.redirect_stdout(self.destination)
        self.recorder.__enter__()
        return lambda: self.destination.getvalue()

    def __exit__(self, *args) -> Literal[False]:
        self.recorder.__exit__(*args)
        self.destination.seek(0)
        return False


def capitalize_first_letter(in_str: str) -> str:
    """
    Args:
        in_str: the string to capitalize

    Returns:
        in_str with the first character capitalized.

    >>> capitalize_first_letter('test')
    'Test'
    >>> capitalize_first_letter("ALREADY!")
    'ALREADY!'
    """
    return in_str[0].upper() + in_str[1:]


def it_they(n: int) -> str:
    """
    Args:
        n: how many of them are there?

    Returns:
        'it' if n is one or 'they' otherwize.

    See also :meth:`is_are`, :meth:`pluralize`, :meth:`make_contractions`,
    :meth:`thify`.

    Suggested usage::

        n = num_files_saved_to_tmp()
        print(f'Saved file{pluralize(n)} successfully.')
        print(f'{it_they(n)} {is_are(n)} located in /tmp.')

    >>> it_they(1)
    'it'
    >>> it_they(100)
    'they'
    """
    if n == 1:
        return "it"
    return "they"


def is_are(n: int) -> str:
    """
    Args:
        n: how many of them are there?

    Returns:
        'is' if n is one or 'are' otherwize.

    See also :meth:`it_they`, :meth:`pluralize`, :meth:`make_contractions`,
    :meth:`thify`.

    Suggested usage::

        n = num_files_saved_to_tmp()
        print(f'Saved file{pluralize(n)} successfully.')
        print(f'{it_they(n)} {is_are(n)} located in /tmp.')

    >>> is_are(1)
    'is'
    >>> is_are(2)
    'are'

    """
    if n == 1:
        return "is"
    return "are"


def pluralize(n: int) -> str:
    """
    Args:
        n: how many of them are there?

    Returns:
        's' if n is greater than one otherwize ''.

    See also :meth:`it_they`, :meth:`is_are`, :meth:`make_contractions`,
    :meth:`thify`.

    Suggested usage::

        n = num_files_saved_to_tmp()
        print(f'Saved file{pluralize(n)} successfully.')
        print(f'{it_they(n)} {is_are(n)} located in /tmp.')

    >>> pluralize(15)
    's'
    >>> count = 1
    >>> print(f'There {is_are(count)} {count} file{pluralize(count)}.')
    There is 1 file.
    >>> count = 4
    >>> print(f'There {is_are(count)} {count} file{pluralize(count)}.')
    There are 4 files.
    """
    if n == 1:
        return ""
    return "s"


def make_contractions(txt: str) -> str:
    """This code glues words in txt together to form (English)
    contractions.

    Args:
        txt: the input text to be contractionized.

    Returns:
        Output text identical to original input except for any
        recognized contractions are formed.

    See also :meth:`it_they`, :meth:`is_are`, :meth:`make_contractions`.

    .. note::
        The order in which we create contractions is defined by the
        implementation and what I thought made more sense when writing
        this code.

    >>> make_contractions('It is nice today.')
    "It's nice today."

    >>> make_contractions('I can    not even...')
    "I can't even..."

    >>> make_contractions('She could not see!')
    "She couldn't see!"

    >>> make_contractions('But she will not go.')
    "But she won't go."

    >>> make_contractions('Verily, I shall not.')
    "Verily, I shan't."

    >>> make_contractions('No you cannot.')
    "No you can't."

    >>> make_contractions('I said you can not go.')
    "I said you can't go."
    """

    first_second = [
        (
            [
                'are',
                'could',
                'did',
                'has',
                'have',
                'is',
                'must',
                'should',
                'was',
                'were',
                'would',
            ],
            ['(n)o(t)'],
        ),
        (
            [
                "I",
                "you",
                "he",
                "she",
                "it",
                "we",
                "they",
                "how",
                "why",
                "when",
                "where",
                "who",
                "there",
            ],
            ['woul(d)', 'i(s)', 'a(re)', 'ha(s)', 'ha(ve)', 'ha(d)', 'wi(ll)'],
        ),
    ]

    # Special cases: can't, shan't and won't.
    txt = re.sub(r'\b(can)\s*no(t)\b', r"\1'\2", txt, count=0, flags=re.IGNORECASE)
    txt = re.sub(
        r'\b(sha)ll\s*(n)o(t)\b', r"\1\2'\3", txt, count=0, flags=re.IGNORECASE
    )
    txt = re.sub(
        r'\b(w)ill\s*(n)(o)(t)\b',
        r"\1\3\2'\4",
        txt,
        count=0,
        flags=re.IGNORECASE,
    )

    for first_list, second_list in first_second:
        for first in first_list:
            for second in second_list:
                # Disallow there're/where're.  They're valid English
                # but sound weird.
                if (first in set(['there', 'where'])) and second == 'a(re)':
                    continue

                pattern = fr'\b({first})\s+{second}\b'
                if second == '(n)o(t)':
                    replacement = r"\1\2'\3"
                else:
                    replacement = r"\1'\2"
                txt = re.sub(pattern, replacement, txt, count=0, flags=re.IGNORECASE)

    return txt


def thify(n: int) -> str:
    """
    Args:
        n: how many of them are there?

    Returns:
        The proper cardinal suffix for a number.

    See also :meth:`it_they`, :meth:`is_are`, :meth:`make_contractions`.

    Suggested usage::

        attempt_count = 0
        while True:
            attempt_count += 1
            if try_the_thing():
                break
            print(f'The {attempt_count}{thify(attempt_count)} failed, trying again.')

    >>> thify(1)
    'st'
    >>> thify(33)
    'rd'
    >>> thify(16)
    'th'
    """
    digit = str(n)
    assert is_integer_number(digit)
    digit = digit[-1:]
    if digit == "1":
        return "st"
    elif digit == "2":
        return "nd"
    elif digit == "3":
        return "rd"
    else:
        return "th"


def ngrams(txt: str, n: int):
    """
    Args:
        txt: the string to create ngrams using
        n: how many words per ngram created?

    Returns:
        Generates the ngrams from the input string.

    See also :meth:`ngrams_presplit`, :meth:`bigrams`, :meth:`trigrams`.

    >>> [x for x in ngrams('This is a test', 2)]
    ['This is', 'is a', 'a test']
    """
    words = txt.split()
    for ngram in ngrams_presplit(words, n):
        ret = ''
        for w in ngram:
            ret += f'{w} '
        yield ret.strip()


def ngrams_presplit(words: Sequence[str], n: int):
    """
    Same as :meth:`ngrams` but with the string pre-split.

    See also :meth:`ngrams`, :meth:`bigrams`, :meth:`trigrams`.
    """
    return list_utils.ngrams(words, n)


def bigrams(txt: str):
    """Generates the bigrams (n=2) of the given string.

    See also :meth:`ngrams`, :meth:`trigrams`.

    >>> [x for x in bigrams('this is a test')]
    ['this is', 'is a', 'a test']
    """
    return ngrams(txt, 2)


def trigrams(txt: str):
    """Generates the trigrams (n=3) of the given string.

    See also :meth:`ngrams`, :meth:`bigrams`.
    """
    return ngrams(txt, 3)


def shuffle_columns_into_list(
    input_lines: Sequence[str], column_specs: Iterable[Iterable[int]], delim: str = ''
) -> Iterable[str]:
    """Helper to shuffle / parse columnar data and return the results as a
    list.

    Args:
        input_lines: A sequence of strings that represents text that
            has been broken into columns by the caller
        column_specs: an iterable collection of numeric sequences that
            indicate one or more column numbers to copy to form the Nth
            position in the output list.  See example below.
        delim: for column_specs that indicate we should copy more than
            one column from the input into this position, use delim to
            separate source data.  Defaults to ''.

    Returns:
        A list of string created by following the instructions set forth
        in column_specs.

    See also :meth:`shuffle_columns_into_dict`.

    >>> cols = '-rwxr-xr-x 1 scott wheel 3.1K Jul  9 11:34 acl_test.py'.split()
    >>> shuffle_columns_into_list(
    ...     cols,
    ...     [ [8], [2, 3], [5, 6, 7] ],
    ...     delim='!',
    ... )
    ['acl_test.py', 'scott!wheel', 'Jul!9!11:34']
    """
    out = []

    # Column specs map input lines' columns into outputs.
    # [col1, col2...]
    for spec in column_specs:
        hunk = ''
        for n in spec:
            hunk = hunk + delim + input_lines[n]
        hunk = hunk.strip(delim)
        out.append(hunk)
    return out


def shuffle_columns_into_dict(
    input_lines: Sequence[str],
    column_specs: Iterable[Tuple[str, Iterable[int]]],
    delim: str = '',
) -> Dict[str, str]:
    """Helper to shuffle / parse columnar data and return the results
    as a dict.

    Args:
        input_lines: a sequence of strings that represents text that
            has been broken into columns by the caller
        column_specs: instructions for what dictionary keys to apply
            to individual or compound input column data.  See example
            below.
        delim: when forming compound output data by gluing more than
            one input column together, use this character to separate
            the source data.  Defaults to ''.

    Returns:
        A dict formed by applying the column_specs instructions.

    See also :meth:`shuffle_columns_into_list`, :meth:`interpolate_using_dict`.

    >>> cols = '-rwxr-xr-x 1 scott wheel 3.1K Jul  9 11:34 acl_test.py'.split()
    >>> shuffle_columns_into_dict(
    ...     cols,
    ...     [ ('filename', [8]), ('owner', [2, 3]), ('mtime', [5, 6, 7]) ],
    ...     delim='!',
    ... )
    {'filename': 'acl_test.py', 'owner': 'scott!wheel', 'mtime': 'Jul!9!11:34'}
    """
    out = {}

    # Column specs map input lines' columns into outputs.
    # "key", [col1, col2...]
    for spec in column_specs:
        hunk = ''
        for n in spec[1]:
            hunk = hunk + delim + input_lines[n]
        hunk = hunk.strip(delim)
        out[spec[0]] = hunk
    return out


def interpolate_using_dict(txt: str, values: Dict[str, str]) -> str:
    """
    Interpolate a string with data from a dict.

    Args:
        txt: the mad libs template
        values: what you and your kids chose for each category.

    See also :meth:`shuffle_columns_into_list`, :meth:`shuffle_columns_into_dict`.

    >>> interpolate_using_dict('This is a {adjective} {noun}.',
    ...                        {'adjective': 'good', 'noun': 'example'})
    'This is a good example.'
    """
    return _sprintf(txt.format(**values), end='')


def to_ascii(txt: str):
    """
    Args:
        txt: the input data to encode

    Returns:
        txt encoded as an ASCII byte string.

    See also :meth:`to_base64`, :meth:`to_bitstring`, :meth:`to_bytes`,
    :meth:`generate_random_alphanumeric_string`, :meth:`asciify`.

    >>> to_ascii('test')
    b'test'

    >>> to_ascii(b'1, 2, 3')
    b'1, 2, 3'
    """
    if isinstance(txt, str):
        return txt.encode('ascii')
    if isinstance(txt, bytes):
        return txt
    raise Exception('to_ascii works with strings and bytes')


def to_base64(
    txt: str, *, encoding: str = 'utf-8', errors: str = 'surrogatepass'
) -> bytes:
    """
    Args:
        txt: the input data to encode
        encoding: the encoding to use during conversion
        errors: how to handle encoding errors

    Returns:
        txt encoded with a 64-chracter alphabet.  Similar to and compatible
        with uuencode/uudecode.

    See also :meth:`is_base64`, :meth:`to_ascii`, :meth:`to_bitstring`,
    :meth:`from_base64`.

    >>> to_base64('hello?')
    b'aGVsbG8/\\n'
    """
    return base64.encodebytes(txt.encode(encoding, errors))


def is_base64(txt: str) -> bool:
    """
    Args:
        txt: the string to check

    Returns:
        True if txt is a valid base64 encoded string.  This assumes
        txt was encoded with Python's standard base64 alphabet which
        is the same as what uuencode/uudecode uses).

    See also :meth:`to_base64`, :meth:`from_base64`.

    >>> is_base64('test')    # all letters in the b64 alphabet
    True

    >>> is_base64('another test, how do you like this one?')
    False

    >>> is_base64(b'aGVsbG8/\\n')    # Ending newline is ok.
    True

    """
    a = string.ascii_uppercase + string.ascii_lowercase + string.digits + '+/'
    alphabet = set(a.encode('ascii'))
    for char in to_ascii(txt.strip()):
        if char not in alphabet:
            return False
    return True


def from_base64(
    b64: bytes, encoding: str = 'utf-8', errors: str = 'surrogatepass'
) -> str:
    """
    Args:
        b64: bytestring of 64-bit encoded data to decode / convert.
        encoding: the encoding to use during conversion
        errors: how to handle encoding errors

    Returns:
        The decoded form of b64 as a normal python string.  Similar to
        and compatible with uuencode / uudecode.

    See also :meth:`to_base64`, :meth:`is_base64`.

    >>> from_base64(b'aGVsbG8/\\n')
    'hello?'
    """
    return base64.decodebytes(b64).decode(encoding, errors)


def chunk(txt: str, chunk_size: int):
    """
    Args:
        txt: a string to be chunked into evenly spaced pieces.
        chunk_size: the size of each chunk to make

    Returns:
        The original string chunked into evenly spaced pieces.

    >>> ' '.join(chunk('010011011100010110101010101010101001111110101000', 8))
    '01001101 11000101 10101010 10101010 10011111 10101000'
    """
    if len(txt) % chunk_size != 0:
        msg = f'String to chunk\'s length ({len(txt)} is not an even multiple of chunk_size ({chunk_size})'
        logger.warning(msg)
        warnings.warn(msg, stacklevel=2)
    for x in range(0, len(txt), chunk_size):
        yield txt[x : x + chunk_size]


def to_bitstring(txt: str, *, delimiter: str = '') -> str:
    """
    Args:
        txt: the string to convert into a bitstring
        delimiter: character to insert between adjacent bytes.  Note that
            only bitstrings with delimiter='' are interpretable by
            :meth:`from_bitstring`.

    Returns:
        txt converted to ascii/binary and then chopped into bytes.

    See also :meth:`to_base64`, :meth:`from_bitstring`, :meth:`is_bitstring`,
    :meth:`chunk`.

    >>> to_bitstring('hello?')
    '011010000110010101101100011011000110111100111111'

    >>> to_bitstring('test', delimiter=' ')
    '01110100 01100101 01110011 01110100'

    >>> to_bitstring(b'test')
    '01110100011001010111001101110100'
    """
    etxt = to_ascii(txt)
    bits = bin(int.from_bytes(etxt, 'big'))
    bits = bits[2:]
    return delimiter.join(chunk(bits.zfill(8 * ((len(bits) + 7) // 8)), 8))


def is_bitstring(txt: str) -> bool:
    """
    Args:
        txt: the string to check

    Returns:
        True if txt is a recognized bitstring and False otherwise.
        Note that if delimiter is non empty this code will not
        recognize the bitstring.

    See also :meth:`to_base64`, :meth:`from_bitstring`, :meth:`to_bitstring`,
    :meth:`chunk`.

    >>> is_bitstring('011010000110010101101100011011000110111100111111')
    True

    >>> is_bitstring('1234')
    False
    """
    return is_binary_integer_number(f'0b{txt}')


def from_bitstring(
    bits: str, encoding: str = 'utf-8', errors: str = 'surrogatepass'
) -> str:
    """
    Args:
        bits: the bitstring to convert back into a python string
        encoding: the encoding to use during conversion
        errors: how to handle encoding errors

    Returns:
        The regular python string represented by bits.  Note that this
        code does not work with to_bitstring when delimiter is non-empty.

    See also :meth:`to_base64`, :meth:`to_bitstring`, :meth:`is_bitstring`,
    :meth:`chunk`.

    >>> from_bitstring('011010000110010101101100011011000110111100111111')
    'hello?'
    """
    n = int(bits, 2)
    return n.to_bytes((n.bit_length() + 7) // 8, 'big').decode(encoding, errors) or '\0'


def ip_v4_sort_key(txt: str) -> Optional[Tuple[int, ...]]:
    """
    Args:
        txt: an IP address to chunk up for sorting purposes

    Returns:
        A tuple of IP components arranged such that the sorting of
        IP addresses using a normal comparator will do something sane
        and desireable.

    See also :meth:`is_ip_v4`.

    >>> ip_v4_sort_key('10.0.0.18')
    (10, 0, 0, 18)

    >>> ips = ['10.0.0.10', '100.0.0.1', '1.2.3.4', '10.0.0.9']
    >>> sorted(ips, key=lambda x: ip_v4_sort_key(x))
    ['1.2.3.4', '10.0.0.9', '10.0.0.10', '100.0.0.1']
    """
    if not is_ip_v4(txt):
        print(f"not IP: {txt}")
        return None
    return tuple(int(x) for x in txt.split('.'))


def path_ancestors_before_descendants_sort_key(volume: str) -> Tuple[str, ...]:
    """
    Args:
        volume: the string to chunk up for sorting purposes

    Returns:
        A tuple of volume's components such that the sorting of
        volumes using a normal comparator will do something sane
        and desireable.

    See also :mod:`pyutils.files.file_utils`.

    >>> path_ancestors_before_descendants_sort_key('/usr/local/bin')
    ('usr', 'local', 'bin')

    >>> paths = ['/usr/local', '/usr/local/bin', '/usr']
    >>> sorted(paths, key=lambda x: path_ancestors_before_descendants_sort_key(x))
    ['/usr', '/usr/local', '/usr/local/bin']
    """
    return tuple(x for x in volume.split('/') if len(x) > 0)


def replace_all(in_str: str, replace_set: str, replacement: str) -> str:
    """
    Execute several replace operations in a row.

    Args:
        in_str: the string in which to replace characters
        replace_set: the set of target characters to replace
        replacement: the character to replace any member of replace_set
            with

    See also :meth:`replace_nth`.

    Returns:
        The string with replacements executed.

    >>> s = 'this_is a-test!'
    >>> replace_all(s, ' _-!', '')
    'thisisatest'
    """
    for char in replace_set:
        in_str = in_str.replace(char, replacement)
    return in_str


def replace_nth(in_str: str, source: str, target: str, nth: int):
    """
    Replaces the nth occurrance of a substring within a string.

    Args:
        in_str: the string in which to run the replacement
        source: the substring to replace
        target: the replacement text
        nth: which occurrance of source to replace?

    See also :meth:`replace_all`.

    >>> replace_nth('this is a test', ' ', '-', 3)
    'this is a-test'
    """
    where = [m.start() for m in re.finditer(source, in_str)][nth - 1]
    before = in_str[:where]
    after = in_str[where:]
    after = after.replace(source, target, 1)
    return before + after


if __name__ == '__main__':
    import doctest

    doctest.testmod()
