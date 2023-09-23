#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""dateparse_utils unittest."""

import datetime
import random
import re
import unittest

import pytz

import pyutils.datetimes.dateparse_utils as du
import pyutils.unittest_utils as uu

parsable_expressions = [
    ("today", datetime.datetime(2021, 7, 2)),
    ("tomorrow", datetime.datetime(2021, 7, 3)),
    ("yesterday", datetime.datetime(2021, 7, 1)),
    ("21:30", datetime.datetime(2021, 7, 2, 21, 30, 0, 0)),
    (
        "21:30 EST",
        datetime.datetime(2021, 7, 2, 21, 30, 0, 0, tzinfo=pytz.timezone("EST")),
    ),
    (
        "21:30 -0500",
        datetime.datetime(2021, 7, 2, 21, 30, 0, 0, tzinfo=pytz.timezone("EST")),
    ),
    ("12:01am", datetime.datetime(2021, 7, 2, 0, 1, 0, 0)),
    ("12:02p", datetime.datetime(2021, 7, 2, 12, 2, 0, 0)),
    ("0:03", datetime.datetime(2021, 7, 2, 0, 3, 0, 0)),
    ("last wednesday", datetime.datetime(2021, 6, 30)),
    ("this wed", datetime.datetime(2021, 7, 7)),
    ("next wed", datetime.datetime(2021, 7, 14)),
    ("this coming tues", datetime.datetime(2021, 7, 6)),
    ("this past monday", datetime.datetime(2021, 6, 28)),
    ("4 days ago", datetime.datetime(2021, 6, 28)),
    ("4 mondays ago", datetime.datetime(2021, 6, 7)),
    ("4 months ago", datetime.datetime(2021, 3, 2)),
    ("3 days back", datetime.datetime(2021, 6, 29)),
    ("13 weeks from now", datetime.datetime(2021, 10, 1)),
    ("1 year from now", datetime.datetime(2022, 7, 2)),
    ("4 weeks from now", datetime.datetime(2021, 7, 30)),
    ("3 saturdays ago", datetime.datetime(2021, 6, 12)),
    ("4 months from today", datetime.datetime(2021, 11, 2)),
    ("4 years from yesterday", datetime.datetime(2025, 7, 1)),
    ("4 weeks from tomorrow", datetime.datetime(2021, 7, 31)),
    ("april 15, 2005", datetime.datetime(2005, 4, 15)),
    ("april 14", datetime.datetime(2021, 4, 14)),
    ("9:30am on last wednesday", datetime.datetime(2021, 6, 30, 9, 30)),
    ("2005/apr/15", datetime.datetime(2005, 4, 15)),
    ("2005 apr 15", datetime.datetime(2005, 4, 15)),
    ("the 1st wednesday in may", datetime.datetime(2021, 5, 5)),
    ("last sun of june", datetime.datetime(2021, 6, 27)),
    ("this Easter", datetime.datetime(2021, 4, 4)),
    ("last christmas", datetime.datetime(2020, 12, 25)),
    ("last Xmas", datetime.datetime(2020, 12, 25)),
    ("xmas, 1999", datetime.datetime(1999, 12, 25)),
    ("next mlk day", datetime.datetime(2022, 1, 17)),
    ("Halloween, 2020", datetime.datetime(2020, 10, 31)),
    ("5 work days after independence day", datetime.datetime(2021, 7, 12)),
    ("50 working days from last wed", datetime.datetime(2021, 9, 10)),
    ("25 working days before columbus day", datetime.datetime(2021, 9, 3)),
    ("today +1 week", datetime.datetime(2021, 7, 9)),
    ("sunday -3 weeks", datetime.datetime(2021, 6, 13)),
    ("4 weeks before xmas, 1999", datetime.datetime(1999, 11, 27)),
    ("3 days before new years eve, 2000", datetime.datetime(2000, 12, 28)),
    ("july 4th", datetime.datetime(2021, 7, 4)),
    ("the ides of march", datetime.datetime(2021, 3, 15)),
    ("the nones of april", datetime.datetime(2021, 4, 5)),
    ("the kalends of may", datetime.datetime(2021, 5, 1)),
    ("9/11/2001", datetime.datetime(2001, 9, 11)),
    ("4 sundays before veterans' day", datetime.datetime(2021, 10, 17)),
    ("xmas eve", datetime.datetime(2021, 12, 24)),
    ("this friday at 5pm", datetime.datetime(2021, 7, 9, 17, 0, 0)),
    ("presidents day", datetime.datetime(2021, 2, 15)),
    ("memorial day, 1921", datetime.datetime(1921, 5, 30)),
    ("today -4 wednesdays", datetime.datetime(2021, 6, 9)),
    ("thanksgiving", datetime.datetime(2021, 11, 25)),
    ("2 sun in jun", datetime.datetime(2021, 6, 13)),
    ("easter -40 days", datetime.datetime(2021, 2, 23)),
    ("easter +39 days", datetime.datetime(2021, 5, 13)),
    ("2nd Sunday in May, 2022", datetime.datetime(2022, 5, 8)),
    ("1st tuesday in nov, 2024", datetime.datetime(2024, 11, 5)),
    (
        "2 days before last xmas at 3:14:15.92a",
        datetime.datetime(2020, 12, 23, 3, 14, 15, 92),
    ),
    (
        "3 weeks after xmas, 1995 at midday",
        datetime.datetime(1996, 1, 15, 12, 0, 0),
    ),
    (
        "4 months before easter, 1992 at midnight",
        datetime.datetime(1991, 12, 19),
    ),
    (
        "5 months before halloween, 1995 at noon",
        datetime.datetime(1995, 5, 31, 12),
    ),
    ("4 days before last wednesday", datetime.datetime(2021, 6, 26)),
    ("44 months after today", datetime.datetime(2025, 3, 2)),
    ("44 years before today", datetime.datetime(1977, 7, 2)),
    ("44 weeks ago", datetime.datetime(2020, 8, 28)),
    ("15 minutes to 3am", datetime.datetime(2021, 7, 2, 2, 45)),
    ("quarter past 4pm", datetime.datetime(2021, 7, 2, 16, 15)),
    ("half past 9", datetime.datetime(2021, 7, 2, 9, 30)),
    ("4 seconds to midnight", datetime.datetime(2021, 7, 1, 23, 59, 56)),
    (
        "4 seconds to midnight, tomorrow",
        datetime.datetime(2021, 7, 2, 23, 59, 56),
    ),
    ("2021/apr/15T21:30:44.55", datetime.datetime(2021, 4, 15, 21, 30, 44, 55)),
    (
        "2021/apr/15 at 21:30:44.55",
        datetime.datetime(2021, 4, 15, 21, 30, 44, 55),
    ),
    (
        "2021/4/15 at 21:30:44.55",
        datetime.datetime(2021, 4, 15, 21, 30, 44, 55),
    ),
    (
        "2021/04/15 at 21:30:44.55",
        datetime.datetime(2021, 4, 15, 21, 30, 44, 55),
    ),
    (
        "2021/04/15 at 21:30:44.55Z",
        datetime.datetime(2021, 4, 15, 21, 30, 44, 55, tzinfo=pytz.timezone("UTC")),
    ),
    (
        "2021/04/15 at 21:30:44.55EST",
        datetime.datetime(2021, 4, 15, 21, 30, 44, 55, tzinfo=pytz.timezone("EST")),
    ),
    (
        "13 days after last memorial day at 12 seconds before 4pm",
        datetime.datetime(2020, 6, 7, 15, 59, 48),
    ),
    (
        "    2     days     before   yesterday    at   9am      ",
        datetime.datetime(2021, 6, 29, 9),
    ),
    ("-3 days before today", datetime.datetime(2021, 7, 5)),
    (
        "3 days before yesterday at midnight EST",
        datetime.datetime(2021, 6, 28, tzinfo=pytz.timezone("EST")),
    ),
]


class TestDateparseUtils(unittest.TestCase):
    @uu.check_method_for_perf_regressions
    def test_dateparsing(self):
        dp = du.DateParser(override_now_for_test_purposes=datetime.datetime(2021, 7, 2))

        for (txt, expected_dt) in parsable_expressions:
            try:
                actual_dt = dp.parse(txt)
                self.assertIsNotNone(actual_dt)
                self.assertEqual(
                    actual_dt,
                    expected_dt,
                    f'"{txt}", got "{actual_dt}" while expecting "{expected_dt}"',
                )
            except du.ParseException:
                self.fail(f'Expected "{txt}" to parse successfully.')

    def test_whitespace_handling(self):
        dp = du.DateParser(override_now_for_test_purposes=datetime.datetime(2021, 7, 2))

        for (txt, expected_dt) in parsable_expressions:
            try:
                txt = f" {txt} "
                i = random.randint(2, 5)
                replacement = " " * i
                txt = re.sub(r"\s", replacement, txt)
                actual_dt = dp.parse(txt)
                self.assertIsNotNone(actual_dt)
                self.assertEqual(
                    actual_dt,
                    expected_dt,
                    f'"{txt}", got "{actual_dt}" while expecting "{expected_dt}"',
                )
            except du.ParseException:
                self.fail(f'Expected "{txt}" to parse successfully.')


if __name__ == "__main__":
    unittest.main()
