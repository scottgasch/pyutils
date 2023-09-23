#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""string_utils unittest."""

import unittest

from pyutils import bootstrap
from pyutils import string_utils as su
from pyutils import unittest_utils as uu
from pyutils.ansi import bg, fg, reset


@uu.check_all_methods_for_perf_regressions()
class TestStringUtils(unittest.TestCase):
    def test_is_none_or_empty(self):
        self.assertTrue(su.is_none_or_empty(None))
        self.assertTrue(su.is_none_or_empty(""))
        self.assertTrue(su.is_none_or_empty("\n"))
        self.assertTrue(su.is_none_or_empty('       '))
        self.assertTrue(su.is_none_or_empty('     \n  \r  \t     '))
        self.assertFalse(su.is_none_or_empty("Covfefe"))
        self.assertFalse(su.is_none_or_empty("1234"))

    def test_is_string(self):
        self.assertTrue(su.is_string("test"))
        self.assertTrue(su.is_string(""))
        self.assertFalse(su.is_string(bytes(0x1234)))
        self.assertFalse(su.is_string(1234))

    def test_is_empty_string(self):
        self.assertTrue(su.is_empty_string(''))
        self.assertTrue(su.is_empty_string('    \t\t  \n    \r      '))
        self.assertFalse(su.is_empty_string(' this is a test '))
        self.assertFalse(su.is_empty_string(22))

    def test_is_full_string(self):
        self.assertFalse(su.is_full_string(''))
        self.assertFalse(su.is_full_string('    \t\t  \n    \r      '))
        self.assertTrue(su.is_full_string(' this is a test '))
        self.assertFalse(su.is_full_string(22))

    def test_is_number(self):
        self.assertTrue(su.is_number("1234"))
        self.assertTrue(su.is_number("-1234"))
        self.assertTrue(su.is_number("1234.55"))
        self.assertTrue(su.is_number("-1234.55"))
        self.assertTrue(su.is_number("+1234"))
        self.assertTrue(su.is_number("+1234.55"))
        self.assertTrue(su.is_number("-0.8485996602e10"))
        self.assertTrue(su.is_number("-0.8485996602E10"))
        self.assertFalse(su.is_number("-0.8485996602t10"))
        self.assertFalse(su.is_number("  1234  "))
        self.assertFalse(su.is_number(" 1234"))
        self.assertFalse(su.is_number("1234 "))
        self.assertFalse(su.is_number("fifty"))

    def test_is_integer_number(self):
        self.assertTrue(su.is_integer_number("1234"))
        self.assertTrue(su.is_integer_number("-1234"))
        self.assertFalse(su.is_integer_number("1234.55"))
        self.assertFalse(su.is_integer_number("-1234.55"))
        self.assertTrue(su.is_integer_number("+1234"))
        self.assertTrue(su.is_integer_number("0x1234"))
        self.assertTrue(su.is_integer_number("0xdeadbeef"))
        self.assertFalse(su.is_integer_number("+1234.55"))
        self.assertTrue(su.is_octal_integer_number("+0o777"))
        self.assertFalse(su.is_integer_number("-0.8485996602e10"))
        self.assertFalse(su.is_integer_number("-0.8485996602E10"))
        self.assertFalse(su.is_integer_number("-0.8485996602t10"))
        self.assertFalse(su.is_integer_number("  1234  "))
        self.assertFalse(su.is_integer_number(" 1234"))
        self.assertFalse(su.is_integer_number("1234 "))
        self.assertFalse(su.is_integer_number("fifty"))

    def test_is_hexidecimal_integer_number(self):
        self.assertTrue(su.is_hexidecimal_integer_number("0x1234"))
        self.assertTrue(su.is_hexidecimal_integer_number("0X1234"))
        self.assertTrue(su.is_hexidecimal_integer_number("0x1234D"))
        self.assertTrue(su.is_hexidecimal_integer_number("0xF1234"))
        self.assertTrue(su.is_hexidecimal_integer_number("0xe1234"))
        self.assertTrue(su.is_hexidecimal_integer_number("0x1234a"))
        self.assertTrue(su.is_hexidecimal_integer_number("0xdeadbeef"))
        self.assertTrue(su.is_hexidecimal_integer_number("-0xdeadbeef"))
        self.assertTrue(su.is_hexidecimal_integer_number("+0xdeadbeef"))
        self.assertFalse(su.is_hexidecimal_integer_number("0xH1234"))
        self.assertFalse(su.is_hexidecimal_integer_number("0x1234H"))
        self.assertFalse(su.is_hexidecimal_integer_number("nine"))

    def test_is_octal_integer_number(self):
        self.assertTrue(su.is_octal_integer_number("0o111"))
        self.assertTrue(su.is_octal_integer_number("0O111"))
        self.assertTrue(su.is_octal_integer_number("-0o111"))
        self.assertTrue(su.is_octal_integer_number("+0o777"))
        self.assertFalse(su.is_octal_integer_number("-+0o111"))
        self.assertFalse(su.is_octal_integer_number("0o181"))
        self.assertFalse(su.is_octal_integer_number("0o1a1"))
        self.assertFalse(su.is_octal_integer_number("one"))

    def test_is_binary_integer_number(self):
        self.assertTrue(su.is_binary_integer_number("0b10100101110"))
        self.assertTrue(su.is_binary_integer_number("+0b10100101110"))
        self.assertTrue(su.is_binary_integer_number("-0b10100101110"))
        self.assertTrue(su.is_binary_integer_number("0B10100101110"))
        self.assertTrue(su.is_binary_integer_number("+0B10100101110"))
        self.assertTrue(su.is_binary_integer_number("-0B10100101110"))
        self.assertFalse(su.is_binary_integer_number("-0B10100101110  "))
        self.assertFalse(su.is_binary_integer_number("  -0B10100101110"))
        self.assertFalse(su.is_binary_integer_number("-0B10100 101110"))
        self.assertFalse(su.is_binary_integer_number("0b10100201110"))
        self.assertFalse(su.is_binary_integer_number("0b10100101e110"))
        self.assertFalse(su.is_binary_integer_number("fred"))

    def test_to_int(self):
        self.assertEqual(su.to_int("1234"), 1234)
        self.assertEqual(su.to_int("0x1234"), 4660)
        self.assertEqual(su.to_int("0o777"), 511)
        self.assertEqual(su.to_int("0b111"), 7)

    def test_is_decimal_number(self):
        self.assertTrue(su.is_decimal_number('4.3'))
        self.assertTrue(su.is_decimal_number('.3'))
        self.assertTrue(su.is_decimal_number('0.3'))
        self.assertFalse(su.is_decimal_number('3.'))
        self.assertTrue(su.is_decimal_number('3.0'))
        self.assertTrue(su.is_decimal_number('3.0492949249e20'))
        self.assertFalse(su.is_decimal_number('3'))
        self.assertFalse(su.is_decimal_number('0x11'))

    def test_strip_escape_sequences(self):
        s = f' {fg("red")}  this is a test  {bg("white")}  this is a test  {reset()}  '
        self.assertEqual(
            su.strip_escape_sequences(s),
            '   this is a test    this is a test    ',
        )
        s = ' this is another test '
        self.assertEqual(su.strip_escape_sequences(s), s)

    def test_is_url(self):
        self.assertTrue(su.is_url("http://host.domain/uri/uri#shard?param=value+s"))
        self.assertTrue(su.is_url("http://127.0.0.1/uri/uri#shard?param=value+s"))
        self.assertTrue(
            su.is_url("http://user:pass@127.0.0.1:81/uri/uri#shard?param=value+s")
        )
        self.assertTrue(su.is_url("ftp://127.0.0.1/uri/uri"))

    def test_is_email(self):
        self.assertTrue(su.is_email('scott@gasch.org'))
        self.assertTrue(su.is_email('scott.gasch@gmail.com'))
        self.assertFalse(su.is_email('@yahoo.com'))
        self.assertFalse(su.is_email('indubidibly'))
        self.assertFalse(su.is_email('frank997!!@foobar.excellent'))

    def test_suffix_string_to_number(self):
        self.assertEqual(1024, su.suffix_string_to_number('1Kb'))
        self.assertEqual(1024 * 1024, su.suffix_string_to_number('1Mb'))
        self.assertEqual(1024, su.suffix_string_to_number('1k'))
        self.assertEqual(1024, su.suffix_string_to_number('1kb'))
        self.assertEqual(None, su.suffix_string_to_number('1Jl'))
        self.assertEqual(None, su.suffix_string_to_number('undeniable'))

    def test_number_to_suffix_string(self):
        self.assertEqual('1.0Kb', su.number_to_suffix_string(1024))
        self.assertEqual('1.0Mb', su.number_to_suffix_string(1024 * 1024))
        self.assertEqual('123', su.number_to_suffix_string(123))

    def test_is_credit_card(self):
        self.assertTrue(su.is_credit_card('4242424242424242'))
        self.assertTrue(su.is_credit_card('5555555555554444'))
        self.assertTrue(su.is_credit_card('378282246310005'))
        self.assertTrue(su.is_credit_card('6011111111111117'))
        self.assertTrue(su.is_credit_card('4000000360000006'))
        self.assertFalse(su.is_credit_card('8000000360110099'))
        self.assertFalse(su.is_credit_card(''))

    def test_is_camel_case(self):
        self.assertFalse(su.is_camel_case('thisisatest'))
        self.assertTrue(su.is_camel_case('thisIsATest'))
        self.assertFalse(su.is_camel_case('this_is_a_test'))

    def test_is_snake_case(self):
        self.assertFalse(su.is_snake_case('thisisatest'))
        self.assertFalse(su.is_snake_case('thisIsATest'))
        self.assertTrue(su.is_snake_case('this_is_a_test'))

    def test_sprintf_context(self):
        with su.SprintfStdout() as buf:
            print("This is a test.")
            print("This is another one.")
        self.assertEqual('This is a test.\nThis is another one.\n', buf())


if __name__ == '__main__':
    bootstrap.initialize(unittest.main)()
