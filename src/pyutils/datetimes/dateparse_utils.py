#!/usr/bin/env python3
# type: ignore
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes

# © Copyright 2021-2023, Scott Gasch

"""
Parse dates / datetimes in a variety of formats.  Some examples:

    |    today
    |    tomorrow
    |    yesterday
    |    21:30
    |    12:01am
    |    12:01pm
    |    last Wednesday
    |    this Wednesday
    |    next Wed
    |    this coming Tues
    |    this past Mon
    |    4 days ago
    |    4 Mondays ago
    |    4 months ago
    |    3 days back
    |    13 weeks from now
    |    1 year from now
    |    4 weeks from now
    |    3 saturdays ago
    |    4 months from today
    |    5 years from yesterday
    |    6 weeks from tomorrow
    |    april 15, 2005
    |    april 21
    |    9:30am on last Wednesday
    |    2005/apr/15
    |    2005 apr 15
    |    the 1st wednesday in may
    |    the last sun of june
    |    this easter
    |    last xmas
    |    Christmas, 1999
    |    next MLK day
    |    Halloween, 2020
    |    5 work days after independence day
    |    50 working days from last wed
    |    25 working days before xmas
    |    today +1 week
    |    sunday -3 weeks
    |    3 weeks before xmas, 1999
    |    3 days before new years eve, 2000
    |    july 4th
    |    the ides of march
    |    the nones of april
    |    the kalends of may
    |    4 sundays before veterans' day
    |    xmas eve
    |    this friday at 5pm
    |    presidents day
    |    memorial day, 1921
    |    thanksgiving
    |    2 sun in jun
    |    easter -40 days
    |    2 days before last xmas at 3:14:15.92a
    |    3 weeks after xmas, 1995 at midday
    |    4 months before easter, 1992 at midnight
    |    5 months before halloween, 1995 at noon
    |    4 days before last wednesday
    |    44 months after today
    |    44 years before today
    |    44 weeks ago
    |    15 minutes to 3am
    |    quarter past 4pm
    |    half past 9
    |    4 seconds to midnight
    |    4 seconds to midnight, tomorrow
    |    2021/apr/15T21:30:44.55
    |    2021/apr/15 at 21:30:44.55
    |    2021/4/15 at 21:30:44.55
    |    2021/04/15 at 21:30:44.55Z
    |    2021/04/15 at 21:30:44.55EST
    |    13 days after last memorial day at 12 seconds before 4pm

This code is used by other code in the pyutils library such as
:meth:`pyutils.argparse_utils.valid_datetime`,
:meth:`pyutils.argparse_utils.valid_date`,
:meth:`pyutils.string_utils.to_datetime`
and
:meth:`pyutils.string_utils.to_date`.  This means any of these are
also able to accept and recognize this larger set of date expressions.

See the `unittest <https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=tests/datetimes/dateparse_utils_test.py;h=93c7b96e4c19af217fbafcf1ed5dbde13ec599c5;hb=HEAD>`_ for more examples and the `grammar <https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=src/pyutils/datetimes/dateparse_utils.g4;hb=HEAD>`_ for more details.
"""

import datetime
import functools
import logging
import re
import sys
from typing import Any, Callable, Dict, Optional

import antlr4  # type: ignore
import holidays  # type: ignore
import pytz

from pyutils import bootstrap, decorator_utils
from pyutils.datetimes.dateparse_utilsLexer import dateparse_utilsLexer  # type: ignore
from pyutils.datetimes.dateparse_utilsListener import (
    dateparse_utilsListener,
)  # type: ignore
from pyutils.datetimes.dateparse_utilsParser import (
    dateparse_utilsParser,
)  # type: ignore
from pyutils.datetimes.datetime_utils import (
    TimeUnit,
    date_to_datetime,
    datetime_to_date,
    easter,
    n_timeunits_from_base,
)
from pyutils.security import acl

logger = logging.getLogger(__name__)


def debug_parse(enter_or_exit_f: Callable[[Any, Any], None]):
    @functools.wraps(enter_or_exit_f)
    def debug_parse_wrapper(*args, **kwargs):
        # slf = args[0]
        ctx = args[1]
        depth = ctx.depth()
        logger.debug(
            '  ' * (depth - 1)
            + f'Entering {enter_or_exit_f.__name__} ({ctx.invokingState} / {ctx.exception})'
        )
        for c in ctx.getChildren():
            logger.debug('  ' * (depth - 1) + f'{c} {type(c)}')
        retval = enter_or_exit_f(*args, **kwargs)
        return retval

    return debug_parse_wrapper


class ParseException(Exception):
    """An exception thrown during parsing because of unrecognized input."""

    def __init__(self, message: str) -> None:
        """
        Args:
            message: parse error message description.
        """
        super().__init__()
        self.message = message


class RaisingErrorListener(antlr4.DiagnosticErrorListener):
    """An error listener that raises ParseExceptions."""

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ParseException(msg)

    def reportAmbiguity(
        self, recognizer, dfa, startIndex, stopIndex, exact, ambigAlts, configs
    ):
        pass

    def reportAttemptingFullContext(
        self, recognizer, dfa, startIndex, stopIndex, conflictingAlts, configs
    ):
        pass

    def reportContextSensitivity(
        self, recognizer, dfa, startIndex, stopIndex, prediction, configs
    ):
        pass


@decorator_utils.decorate_matching_methods_with(
    debug_parse,
    acl=acl.StringWildcardBasedACL(
        allowed_patterns=[
            'enter*',
            'exit*',
        ],
        denied_patterns=['enterEveryRule', 'exitEveryRule'],
        order_to_check_allow_deny=acl.Order.DENY_ALLOW,
        default_answer=False,
    ),
)
class DateParser(dateparse_utilsListener):
    """A class to parse dates expressed in human language (English).
    Example usage::

        d = DateParser()
        d.parse('next wednesday')
        dt = d.get_datetime()
        print(dt)
        Wednesday 2022/10/26 00:00:00.000000

    Note that the interface is somewhat klunky here because this class is
    conforming to interfaces auto-generated by ANTLR as it parses the grammar.
    See also :meth:`pyutils.string_utils.to_date`.

    """

    PARSE_TYPE_SINGLE_DATE_EXPR = 1
    PARSE_TYPE_BASE_AND_OFFSET_EXPR = 2
    PARSE_TYPE_SINGLE_TIME_EXPR = 3
    PARSE_TYPE_BASE_AND_OFFSET_TIME_EXPR = 4

    def __init__(self, *, override_now_for_test_purposes=None) -> None:
        """Construct a parser.

        Args:
            override_now_for_test_purposes: passing a value to
                override_now_for_test_purposes can be used to force
                this parser instance to use a custom date/time for its
                idea of "now" so that the code can be more easily
                unittested.  Leave as None for real use cases.
        """
        self.month_name_to_number = {
            'jan': 1,
            'feb': 2,
            'mar': 3,
            'apr': 4,
            'may': 5,
            'jun': 6,
            'jul': 7,
            'aug': 8,
            'sep': 9,
            'oct': 10,
            'nov': 11,
            'dec': 12,
        }

        # Used only for ides/nones.  Month length on a non-leap year.
        self.typical_days_per_month = {
            1: 31,
            2: 28,
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }

        # N.B. day number is also synched with datetime_utils.TimeUnit values
        # which allows expressions like "3 wednesdays from now" to work.
        self.day_name_to_number = {
            'mon': 0,
            'tue': 1,
            'wed': 2,
            'thu': 3,
            'fri': 4,
            'sat': 5,
            'sun': 6,
        }

        # These TimeUnits are defined in datetime_utils and are used as params
        # to datetime_utils.n_timeunits_from_base.
        self.time_delta_unit_to_constant = {
            'hou': TimeUnit.HOURS,
            'min': TimeUnit.MINUTES,
            'sec': TimeUnit.SECONDS,
        }
        self.delta_unit_to_constant = {
            'day': TimeUnit.DAYS,
            'wor': TimeUnit.WORKDAYS,
            'wee': TimeUnit.WEEKS,
            'mon': TimeUnit.MONTHS,
            'yea': TimeUnit.YEARS,
        }
        self.override_now_for_test_purposes = override_now_for_test_purposes

        # Note: _reset defines several class fields.  It is used both here
        # in the c'tor but also in between parse operations to restore the
        # class' state and allow it to be reused.
        #
        self._reset()

    def parse(self, date_string: str) -> Optional[datetime.datetime]:
        """
        Parse a ~free form date/time expression and return a
        timezone agnostic datetime on success.  Also sets
        `self.datetime`, `self.date` and `self.time` which can each be
        accessed other methods on the class: :meth:`get_datetime`,
        :meth:`get_date` and :meth:`get_time`.  Raises a
        `ParseException` with a helpful(?) message on parse error or
        confusion.

        This is the main entrypoint to this class for caller code.

        To get an idea of what expressions can be parsed, check out
        the unittest and the grammar.

        Args:
            date_string: the string to parse

        Returns:
            A datetime.datetime representing the parsed date/time or
            None on error.

        .. note::

            Parsed date expressions without any time part return
            hours = minutes = seconds = microseconds = 0 (i.e. at
            midnight that day).  Parsed time expressions without any
            date part default to date = today.

        Example usage::

            txt = '3 weeks before last tues at 9:15am'
            dp = DateParser()
            dt1 = dp.parse(txt)
            dt2 = dp.get_datetime(tz=pytz.timezone('US/Pacific'))

            # dt1 and dt2 will be identical other than the fact that
            # the latter's tzinfo will be set to PST/PDT.

        """
        date_string = date_string.strip()
        date_string = re.sub(r'\s+', ' ', date_string)
        self._reset()
        listener = RaisingErrorListener()
        input_stream = antlr4.InputStream(date_string)
        lexer = dateparse_utilsLexer(input_stream)
        lexer.removeErrorListeners()
        lexer.addErrorListener(listener)
        stream = antlr4.CommonTokenStream(lexer)
        parser = dateparse_utilsParser(stream)
        parser.removeErrorListeners()
        parser.addErrorListener(listener)
        tree = parser.parse()
        walker = antlr4.ParseTreeWalker()
        walker.walk(self, tree)
        return self.datetime

    def get_date(self) -> Optional[datetime.date]:
        """
        Returns:
            The date part of the last :meth:`parse` operation again
            or None.
        """
        return self.date

    def get_time(self) -> Optional[datetime.time]:
        """
        Returns:
            The time part of the last :meth:`parse` operation again
            or None.
        """
        return self.time

    def get_datetime(
        self, *, tz: Optional[datetime.tzinfo] = None
    ) -> Optional[datetime.datetime]:
        """Get the datetime of the last :meth:`parse` operation again
        ot None.

        Args:
            tz: the timezone to set on output times.  By default we
                return timezone-naive datetime objects.

        Returns:
            the same datetime that :meth:`parse` last did, optionally
            overriding the timezone.  Returns None of no calls to
            :meth:`parse` have yet been made.

        .. note::

            Parsed date expressions without any time part return
            hours = minutes = seconds = microseconds = 0 (i.e. at
            midnight that day).  Parsed time expressions without any
            date part default to date = today.
        """
        dt = self.datetime
        if dt is not None:
            if tz is not None:
                dt = dt.replace(tzinfo=None).astimezone(tz=tz)
        return dt

    # -- helpers --

    def _reset(self):
        """Reset at init and between parses."""
        if self.override_now_for_test_purposes is None:
            self.now_datetime = datetime.datetime.now()
            self.today = datetime.date.today()
        else:
            self.now_datetime = self.override_now_for_test_purposes
            self.today = datetime_to_date(self.override_now_for_test_purposes)
        self.date: Optional[datetime.date] = None
        self.time: Optional[datetime.time] = None
        self.datetime: Optional[datetime.datetime] = None
        self.context: Dict[str, Any] = {}
        self.timedelta = datetime.timedelta(seconds=0)
        self.saw_overt_year = False

    @staticmethod
    def _normalize_special_day_name(name: str) -> str:
        """String normalization / canonicalization for date expressions."""
        name = name.lower()
        name = name.replace("'", '')
        name = name.replace('xmas', 'christmas')
        name = name.replace('mlk', 'martin luther king')
        name = name.replace(' ', '')
        eve = 'eve' if name[-3:] == 'eve' else ''
        name = name[:5] + eve
        name = name.replace('washi', 'presi')
        return name

    def _figure_out_date_unit(self, orig: str) -> TimeUnit:
        """Figure out what unit a date expression piece is talking about."""
        if 'month' in orig:
            return TimeUnit.MONTHS
        txt = orig.lower()[:3]
        if txt in self.day_name_to_number:
            return TimeUnit(self.day_name_to_number[txt])
        elif txt in self.delta_unit_to_constant:
            return TimeUnit(self.delta_unit_to_constant[txt])
        raise ParseException(f'Invalid date unit: {orig}')

    def _figure_out_time_unit(self, orig: str) -> int:
        """Figure out what unit a time expression piece is talking about."""
        txt = orig.lower()[:3]
        if txt in self.time_delta_unit_to_constant:
            return self.time_delta_unit_to_constant[txt]
        raise ParseException(f'Invalid time unit: {orig}')

    def _parse_special_date(self, name: str) -> Optional[datetime.date]:
        """Parse what we think is a special date name and return its datetime
        (or None if it can't be parsed).
        """
        today = self.today
        year = self.context.get('year', today.year)
        name = DateParser._normalize_special_day_name(self.context['special'])

        # Yesterday, today, tomorrow -- ignore any next/last
        if name in {'today', 'now'}:
            return today
        if name == 'yeste':
            return today + datetime.timedelta(days=-1)
        if name == 'tomor':
            return today + datetime.timedelta(days=+1)

        next_last = self.context.get('special_next_last', '')
        if next_last == 'next':
            year += 1
            self.saw_overt_year = True
        elif next_last == 'last':
            year -= 1
            self.saw_overt_year = True

        # Holiday names
        if name == 'easte':
            return easter(year=year)
        elif name == 'hallo':
            return datetime.date(year=year, month=10, day=31)

        for holiday_date, holiday_name in sorted(holidays.US(years=year).items()):
            if 'Observed' not in holiday_name:
                holiday_name = DateParser._normalize_special_day_name(holiday_name)
                if name == holiday_name:
                    return holiday_date
        if name == 'chriseve':
            return datetime.date(year=year, month=12, day=24)
        elif name == 'newyeeve':
            return datetime.date(year=year, month=12, day=31)
        return None

    def _resolve_ides_nones(self, day: str, month_number: int) -> int:
        """Handle date expressions like "the ides of March" which require
        both the "ides" and the month since the definition of the "ides"
        changes based on the length of the month.
        """
        assert 'ide' in day or 'non' in day
        assert month_number in self.typical_days_per_month
        typical_days_per_month = self.typical_days_per_month[month_number]

        # "full" month
        if typical_days_per_month == 31:
            if self.context['day'] == 'ide':
                return 15
            else:
                return 7

        # "hollow" month
        else:
            if self.context['day'] == 'ide':
                return 13
            else:
                return 5

    def _parse_normal_date(self) -> datetime.date:
        if 'dow' in self.context and 'month' not in self.context:
            d = self.today
            while d.weekday() != self.context['dow']:
                d += datetime.timedelta(days=1)
            return d

        if 'month' not in self.context:
            raise ParseException('Missing month')
        if 'day' not in self.context:
            raise ParseException('Missing day')
        if 'year' not in self.context:
            self.context['year'] = self.today.year
            self.saw_overt_year = False
        else:
            self.saw_overt_year = True

        # Handling "ides" and "nones" requires both the day and month.
        if self.context['day'] == 'ide' or self.context['day'] == 'non':
            self.context['day'] = self._resolve_ides_nones(
                self.context['day'], self.context['month']
            )

        return datetime.date(
            year=self.context['year'],
            month=self.context['month'],
            day=self.context['day'],
        )

    @staticmethod
    def _parse_tz(txt: str) -> Any:
        if txt == 'Z':
            txt = 'UTC'

        # Try pytz
        try:
            tz1 = pytz.timezone(txt)
            if tz1 is not None:
                return tz1
        except Exception:
            pass

        # Try constructing an offset in seconds
        try:
            txt_sign = txt[0]
            if txt_sign in {'-', '+'}:
                sign = +1 if txt_sign == '+' else -1
                hour = int(txt[1:3])
                minute = int(txt[-2:])
                offset = sign * (hour * 60 * 60) + sign * (minute * 60)
                tzoffset = datetime.timezone(datetime.timedelta(seconds=offset))
                return tzoffset
        except Exception:
            pass
        return None

    @staticmethod
    def _get_int(txt: str) -> int:
        while not txt[0].isdigit() and txt[0] != '-' and txt[0] != '+':
            txt = txt[1:]
        while not txt[-1].isdigit():
            txt = txt[:-1]
        return int(txt)

    # -- overridden methods invoked by parse walk.  Note: not part of the class'
    # public API(!!) --

    def visitErrorNode(self, node: antlr4.ErrorNode) -> None:
        pass

    def visitTerminal(self, node: antlr4.TerminalNode) -> None:
        pass

    def exitParse(self, ctx: dateparse_utilsParser.ParseContext) -> None:
        """Populate self.datetime."""
        if self.date is None:
            self.date = self.today
        year = self.date.year
        month = self.date.month
        day = self.date.day

        if self.time is None:
            self.time = datetime.time(0, 0, 0)
        hour = self.time.hour
        minute = self.time.minute
        second = self.time.second
        micros = self.time.microsecond

        self.datetime = datetime.datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            micros,
            tzinfo=self.time.tzinfo,
        )

        # Apply resudual adjustments to times here when we have a
        # datetime.
        self.datetime = self.datetime + self.timedelta
        assert self.datetime is not None
        self.time = datetime.time(
            self.datetime.hour,
            self.datetime.minute,
            self.datetime.second,
            self.datetime.microsecond,
            self.datetime.tzinfo,
        )

    def enterDateExpr(self, ctx: dateparse_utilsParser.DateExprContext):
        self.date = None
        if ctx.singleDateExpr() is not None:
            self.main_type = DateParser.PARSE_TYPE_SINGLE_DATE_EXPR
        elif ctx.baseAndOffsetDateExpr() is not None:
            self.main_type = DateParser.PARSE_TYPE_BASE_AND_OFFSET_EXPR

    def enterTimeExpr(self, ctx: dateparse_utilsParser.TimeExprContext):
        self.time = None
        if ctx.singleTimeExpr() is not None:
            self.time_type = DateParser.PARSE_TYPE_SINGLE_TIME_EXPR
        elif ctx.baseAndOffsetTimeExpr() is not None:
            self.time_type = DateParser.PARSE_TYPE_BASE_AND_OFFSET_TIME_EXPR

    def exitDateExpr(self, ctx: dateparse_utilsParser.DateExprContext) -> None:
        """When we leave the date expression, populate self.date."""
        if 'special' in self.context:
            self.date = self._parse_special_date(self.context['special'])
        else:
            self.date = self._parse_normal_date()
        assert self.date is not None

        # For a single date, just return the date we pulled out.
        if self.main_type == DateParser.PARSE_TYPE_SINGLE_DATE_EXPR:
            return

        # Otherwise treat self.date as a base date that we're modifying
        # with an offset.
        if 'delta_int' not in self.context:
            raise ParseException('Missing delta_int?!')
        count = self.context['delta_int']
        if count == 0:
            return

        # Adjust count's sign based on the presence of 'before' or 'after'.
        if 'delta_before_after' in self.context:
            before_after = self.context['delta_before_after'].lower()
            if before_after in {'before', 'until', 'til', 'to'}:
                count = -count

        # What are we counting units of?
        if 'delta_unit' not in self.context:
            raise ParseException('Missing delta_unit?!')
        unit = self.context['delta_unit']
        dt = n_timeunits_from_base(count, TimeUnit(unit), date_to_datetime(self.date))
        self.date = datetime_to_date(dt)

    def exitTimeExpr(self, ctx: dateparse_utilsParser.TimeExprContext) -> None:
        # Simple time?
        self.time = datetime.time(
            self.context['hour'],
            self.context['minute'],
            self.context['seconds'],
            self.context['micros'],
            tzinfo=self.context.get('tz', None),
        )
        if self.time_type == DateParser.PARSE_TYPE_SINGLE_TIME_EXPR:
            return

        # If we get here there (should be) a relative adjustment to
        # the time.
        if 'nth' in self.context:
            count = self.context['nth']
        elif 'time_delta_int' in self.context:
            count = self.context['time_delta_int']
        else:
            raise ParseException('Missing delta in relative time.')
        if count == 0:
            return

        # Adjust count's sign based on the presence of 'before' or 'after'.
        if 'time_delta_before_after' in self.context:
            before_after = self.context['time_delta_before_after'].lower()
            if before_after in {'before', 'until', 'til', 'to'}:
                count = -count

        # What are we counting units of... assume minutes.
        if 'time_delta_unit' not in self.context:
            self.timedelta += datetime.timedelta(minutes=count)
        else:
            unit = self.context['time_delta_unit']
            if unit == TimeUnit.SECONDS:
                self.timedelta += datetime.timedelta(seconds=count)
            elif unit == TimeUnit.MINUTES:
                self.timedelta = datetime.timedelta(minutes=count)
            elif unit == TimeUnit.HOURS:
                self.timedelta = datetime.timedelta(hours=count)
            else:
                raise ParseException(f'Invalid Unit: "{unit}"')

    def exitDeltaPlusMinusExpr(
        self, ctx: dateparse_utilsParser.DeltaPlusMinusExprContext
    ) -> None:
        try:
            n = ctx.nth()
            if n is None:
                raise ParseException(f'Bad N in Delta +/- Expr: {ctx.getText()}')
            n = n.getText()
            n = DateParser._get_int(n)
            unit = self._figure_out_date_unit(ctx.deltaUnit().getText().lower())
        except Exception as e:
            raise ParseException(f'Invalid Delta +/-: {ctx.getText()}') from e
        else:
            self.context['delta_int'] = n
            self.context['delta_unit'] = unit

    def exitNextLastUnit(self, ctx: dateparse_utilsParser.DeltaUnitContext) -> None:
        try:
            unit = self._figure_out_date_unit(ctx.getText().lower())
        except Exception as e:
            raise ParseException(f'Bad delta unit: {ctx.getText()}') from e
        else:
            self.context['delta_unit'] = unit

    def exitDeltaNextLast(
        self, ctx: dateparse_utilsParser.DeltaNextLastContext
    ) -> None:
        try:
            txt = ctx.getText().lower()
        except Exception as e:
            raise ParseException(f'Bad next/last: {ctx.getText()}') from e
        if 'month' in self.context or 'day' in self.context or 'year' in self.context:
            raise ParseException(
                'Next/last expression expected to be relative to today.'
            )
        if txt[:4] == 'next':
            self.context['delta_int'] = +1
            self.context['day'] = self.now_datetime.day
            self.context['month'] = self.now_datetime.month
            self.context['year'] = self.now_datetime.year
            self.saw_overt_year = True
        elif txt[:4] == 'last':
            self.context['delta_int'] = -1
            self.context['day'] = self.now_datetime.day
            self.context['month'] = self.now_datetime.month
            self.context['year'] = self.now_datetime.year
            self.saw_overt_year = True
        else:
            raise ParseException(f'Bad next/last: {ctx.getText()}')

    def exitCountUnitsBeforeAfterTimeExpr(
        self, ctx: dateparse_utilsParser.CountUnitsBeforeAfterTimeExprContext
    ) -> None:
        if 'nth' not in self.context:
            raise ParseException(f'Bad count expression: {ctx.getText()}')
        try:
            unit = self._figure_out_time_unit(ctx.deltaTimeUnit().getText().lower())
            self.context['time_delta_unit'] = unit
        except Exception as e:
            raise ParseException(f'Bad delta unit: {ctx.getText()}') from e
        if 'time_delta_before_after' not in self.context:
            raise ParseException(f'Bad Before/After: {ctx.getText()}')

    def exitDeltaTimeFraction(
        self, ctx: dateparse_utilsParser.DeltaTimeFractionContext
    ) -> None:
        try:
            txt = ctx.getText().lower()[:4]
            if txt == 'quar':
                self.context['time_delta_int'] = 15
                self.context['time_delta_unit'] = TimeUnit.MINUTES
            elif txt == 'half':
                self.context['time_delta_int'] = 30
                self.context['time_delta_unit'] = TimeUnit.MINUTES
            else:
                raise ParseException(f'Bad time fraction {ctx.getText()}')
        except Exception as e:
            raise ParseException(f'Bad time fraction {ctx.getText()}') from e

    def exitDeltaBeforeAfter(
        self, ctx: dateparse_utilsParser.DeltaBeforeAfterContext
    ) -> None:
        try:
            txt = ctx.getText().lower()
        except Exception as e:
            raise ParseException(f'Bad delta before|after: {ctx.getText()}') from e
        else:
            self.context['delta_before_after'] = txt

    def exitDeltaTimeBeforeAfter(
        self, ctx: dateparse_utilsParser.DeltaBeforeAfterContext
    ) -> None:
        try:
            txt = ctx.getText().lower()
        except Exception as e:
            raise ParseException(f'Bad delta before|after: {ctx.getText()}') from e
        else:
            self.context['time_delta_before_after'] = txt

    def exitNthWeekdayInMonthMaybeYearExpr(
        self, ctx: dateparse_utilsParser.NthWeekdayInMonthMaybeYearExprContext
    ) -> None:
        """Do a bunch of work to convert expressions like...

        'the 2nd Friday of June' -and-
        'the last Wednesday in October'

        ...into base + offset expressions instead.
        """
        try:
            if 'nth' not in self.context:
                raise ParseException(f'Missing nth number: {ctx.getText()}')
            n = self.context['nth']
            if n < 1 or n > 5:  # months never have more than 5 Foodays
                if n != -1:
                    raise ParseException(f'Invalid nth number: {ctx.getText()}')
            del self.context['nth']
            self.context['delta_int'] = n

            year = self.context.get('year', self.today.year)
            if 'month' not in self.context:
                raise ParseException(f'Missing month expression: {ctx.getText()}')
            month = self.context['month']

            dow = self.context['dow']
            del self.context['dow']
            self.context['delta_unit'] = dow

            # For the nth Fooday in Month, start at the last day of
            # the previous month count ahead N Foodays.  For the last
            # Fooday in Month, start at the last of the month and
            # count back one Fooday.
            if n == -1:
                month += 1
                if month == 13:
                    month = 1
                    year += 1
                tmp_date = datetime.date(year=year, month=month, day=1)
                tmp_date = tmp_date - datetime.timedelta(days=1)

                # The delta adjustment code can handle the case where
                # the last day of the month is the day we're looking
                # for already.
            else:
                tmp_date = datetime.date(year=year, month=month, day=1)
                tmp_date = tmp_date - datetime.timedelta(days=1)

            self.context['year'] = tmp_date.year
            self.context['month'] = tmp_date.month
            self.context['day'] = tmp_date.day
            self.main_type = DateParser.PARSE_TYPE_BASE_AND_OFFSET_EXPR
        except Exception as e:
            raise ParseException(
                f'Invalid nthWeekday expression: {ctx.getText()}'
            ) from e

    def exitFirstLastWeekdayInMonthMaybeYearExpr(
        self,
        ctx: dateparse_utilsParser.FirstLastWeekdayInMonthMaybeYearExprContext,
    ) -> None:
        self.exitNthWeekdayInMonthMaybeYearExpr(ctx)

    def exitNth(self, ctx: dateparse_utilsParser.NthContext) -> None:
        try:
            i = DateParser._get_int(ctx.getText())
        except Exception as e:
            raise ParseException(f'Bad nth expression: {ctx.getText()}') from e
        else:
            self.context['nth'] = i

    def exitFirstOrLast(self, ctx: dateparse_utilsParser.FirstOrLastContext) -> None:
        try:
            txt = ctx.getText()
            if txt == 'first':
                txt = 1
            elif txt == 'last':
                txt = -1
            else:
                raise ParseException(f'Bad first|last expression: {ctx.getText()}')
        except Exception as e:
            raise ParseException(f'Bad first|last expression: {ctx.getText()}') from e
        else:
            self.context['nth'] = txt

    def exitDayName(self, ctx: dateparse_utilsParser.DayNameContext) -> None:
        try:
            dow = ctx.getText().lower()[:3]
            dow = self.day_name_to_number.get(dow, None)
        except Exception as e:
            raise ParseException('Bad day of week') from e
        else:
            self.context['dow'] = dow

    def exitDayOfMonth(self, ctx: dateparse_utilsParser.DayOfMonthContext) -> None:
        try:
            day = ctx.getText().lower()
            if day[:3] == 'ide':
                self.context['day'] = 'ide'
                return
            if day[:3] == 'non':
                self.context['day'] = 'non'
                return
            if day[:3] == 'kal':
                self.context['day'] = 1
                return
            day = DateParser._get_int(day)
            if day < 1 or day > 31:
                raise ParseException(f'Bad dayOfMonth expression: {ctx.getText()}')
        except Exception as e:
            raise ParseException(f'Bad dayOfMonth expression: {ctx.getText()}') from e
        self.context['day'] = day

    def exitMonthName(self, ctx: dateparse_utilsParser.MonthNameContext) -> None:
        try:
            month = ctx.getText()
            while month[0] == '/' or month[0] == '-':
                month = month[1:]
            month = month[:3].lower()
            month = self.month_name_to_number.get(month, None)
            if month is None:
                raise ParseException(f'Bad monthName expression: {ctx.getText()}')
        except Exception as e:
            raise ParseException(f'Bad monthName expression: {ctx.getText()}') from e
        else:
            self.context['month'] = month

    def exitMonthNumber(self, ctx: dateparse_utilsParser.MonthNumberContext) -> None:
        try:
            month = DateParser._get_int(ctx.getText())
            if month < 1 or month > 12:
                raise ParseException(f'Bad monthNumber expression: {ctx.getText()}')
        except Exception as e:
            raise ParseException(f'Bad monthNumber expression: {ctx.getText()}') from e
        else:
            self.context['month'] = month

    def exitYear(self, ctx: dateparse_utilsParser.YearContext) -> None:
        try:
            year = DateParser._get_int(ctx.getText())
            if year < 1:
                raise ParseException(f'Bad year expression: {ctx.getText()}')
        except Exception as e:
            raise ParseException(f'Bad year expression: {ctx.getText()}') from e
        else:
            self.saw_overt_year = True
            self.context['year'] = year

    def exitSpecialDateMaybeYearExpr(
        self, ctx: dateparse_utilsParser.SpecialDateMaybeYearExprContext
    ) -> None:
        try:
            special = ctx.specialDate().getText().lower()
            self.context['special'] = special
        except Exception as e:
            raise ParseException(
                f'Bad specialDate expression: {ctx.specialDate().getText()}'
            ) from e
        try:
            mod = ctx.thisNextLast()
            if mod is not None:
                if mod.THIS() is not None:
                    self.context['special_next_last'] = 'this'
                elif mod.NEXT() is not None:
                    self.context['special_next_last'] = 'next'
                elif mod.LAST() is not None:
                    self.context['special_next_last'] = 'last'
        except Exception as e:
            raise ParseException(
                f'Bad specialDateNextLast expression: {ctx.getText()}'
            ) from e

    def exitNFoosFromTodayAgoExpr(
        self, ctx: dateparse_utilsParser.NFoosFromTodayAgoExprContext
    ) -> None:
        d = self.now_datetime
        try:
            count = DateParser._get_int(ctx.unsignedInt().getText())
            unit = ctx.deltaUnit().getText().lower()
            ago_from_now = ctx.AGO_FROM_NOW().getText()
        except Exception as e:
            raise ParseException(f'Bad NFoosFromTodayAgoExpr: {ctx.getText()}') from e

        if "ago" in ago_from_now or "back" in ago_from_now:
            count = -count

        unit = self._figure_out_date_unit(unit)
        d = n_timeunits_from_base(count, TimeUnit(unit), d)
        self.context['year'] = d.year
        self.context['month'] = d.month
        self.context['day'] = d.day

    def exitDeltaRelativeToTodayExpr(
        self, ctx: dateparse_utilsParser.DeltaRelativeToTodayExprContext
    ) -> None:
        # When someone says "next week" they mean a week from now.
        # Likewise next month or last year.  These expressions are now
        # +/- delta.
        #
        # But when someone says "this Friday" they mean "this coming
        # Friday".  It would be weird to say "this Friday" if today
        # was already Friday but I'm parsing it to mean: the next day
        # that is a Friday.  So when you say "next Friday" you mean
        # the Friday after this coming Friday, or 2 Fridays from now.
        #
        # This set handles this weirdness.
        weekdays = set(
            [
                TimeUnit.MONDAYS,
                TimeUnit.TUESDAYS,
                TimeUnit.WEDNESDAYS,
                TimeUnit.THURSDAYS,
                TimeUnit.FRIDAYS,
                TimeUnit.SATURDAYS,
                TimeUnit.SUNDAYS,
            ]
        )
        d = self.now_datetime
        try:
            mod = ctx.thisNextLast()
            unit = ctx.deltaUnit().getText().lower()
            unit = self._figure_out_date_unit(unit)
            if mod.LAST():
                count = -1
            elif mod.THIS():
                if unit in weekdays:
                    count = +1
                else:
                    count = 0
            elif mod.NEXT():
                if unit in weekdays:
                    count = +2
                else:
                    count = +1
            else:
                raise ParseException(f'Bad This/Next/Last modifier: {mod}')
        except Exception as e:
            raise ParseException(
                f'Bad DeltaRelativeToTodayExpr: {ctx.getText()}'
            ) from e
        d = n_timeunits_from_base(count, TimeUnit(unit), d)
        self.context['year'] = d.year
        self.context['month'] = d.month
        self.context['day'] = d.day

    def exitSpecialTimeExpr(
        self, ctx: dateparse_utilsParser.SpecialTimeExprContext
    ) -> None:
        try:
            txt = ctx.specialTime().getText().lower()
        except Exception as e:
            raise ParseException(f'Bad special time expression: {ctx.getText()}') from e
        else:
            if txt in {'noon', 'midday'}:
                self.context['hour'] = 12
                self.context['minute'] = 0
                self.context['seconds'] = 0
                self.context['micros'] = 0
            elif txt == 'midnight':
                self.context['hour'] = 0
                self.context['minute'] = 0
                self.context['seconds'] = 0
                self.context['micros'] = 0
            else:
                raise ParseException(f'Bad special time expression: {txt}')

        try:
            tz = ctx.tzExpr().getText()
            self.context['tz'] = DateParser._parse_tz(tz)
        except Exception:
            pass

    def exitTwelveHourTimeExpr(
        self, ctx: dateparse_utilsParser.TwelveHourTimeExprContext
    ) -> None:
        try:
            hour = ctx.hour().getText()
            while not hour[-1].isdigit():
                hour = hour[:-1]
            hour = DateParser._get_int(hour)
        except Exception as e:
            raise ParseException(f'Bad hour: {ctx.hour().getText()}') from e
        if hour <= 0 or hour > 12:
            raise ParseException(f'Bad hour (out of range): {hour}')

        try:
            minute = DateParser._get_int(ctx.minute().getText())
        except Exception:
            minute = 0
        if minute < 0 or minute > 59:
            raise ParseException(f'Bad minute (out of range): {minute}')
        self.context['minute'] = minute

        try:
            seconds = DateParser._get_int(ctx.second().getText())
        except Exception:
            seconds = 0
        if seconds < 0 or seconds > 59:
            raise ParseException(f'Bad second (out of range): {seconds}')
        self.context['seconds'] = seconds

        try:
            micros = DateParser._get_int(ctx.micros().getText())
        except Exception:
            micros = 0
        if micros < 0 or micros > 1000000:
            raise ParseException(f'Bad micros (out of range): {micros}')
        self.context['micros'] = micros

        try:
            ampm = ctx.ampm().getText()
        except Exception as e:
            raise ParseException(f'Bad ampm: {ctx.ampm().getText()}') from e
        if hour == 12:
            hour = 0
        if ampm[0] == 'p':
            hour += 12
        self.context['hour'] = hour

        try:
            tz = ctx.tzExpr().getText()
            self.context['tz'] = DateParser._parse_tz(tz)
        except Exception:
            pass

    def exitTwentyFourHourTimeExpr(
        self, ctx: dateparse_utilsParser.TwentyFourHourTimeExprContext
    ) -> None:
        try:
            hour = ctx.hour().getText()
            while not hour[-1].isdigit():
                hour = hour[:-1]
            hour = DateParser._get_int(hour)
        except Exception as e:
            raise ParseException(f'Bad hour: {ctx.hour().getText()}') from e
        if hour < 0 or hour > 23:
            raise ParseException(f'Bad hour (out of range): {hour}')
        self.context['hour'] = hour

        try:
            minute = DateParser._get_int(ctx.minute().getText())
        except Exception:
            minute = 0
        if minute < 0 or minute > 59:
            raise ParseException(f'Bad minute (out of range): {ctx.getText()}')
        self.context['minute'] = minute

        try:
            seconds = DateParser._get_int(ctx.second().getText())
        except Exception:
            seconds = 0
        if seconds < 0 or seconds > 59:
            raise ParseException(f'Bad second (out of range): {ctx.getText()}')
        self.context['seconds'] = seconds

        try:
            micros = DateParser._get_int(ctx.micros().getText())
        except Exception:
            micros = 0
        if micros < 0 or micros >= 1000000:
            raise ParseException(f'Bad micros (out of range): {ctx.getText()}')
        self.context['micros'] = micros

        try:
            tz = ctx.tzExpr().getText()
            self.context['tz'] = DateParser._parse_tz(tz)
        except Exception:
            pass


@bootstrap.initialize
def main() -> None:
    parser = DateParser()
    for line in sys.stdin:
        line = line.strip()
        line = re.sub(r"#.*$", "", line)
        if re.match(r"^ *$", line) is not None:
            continue
        try:
            dt = parser.parse(line)
        except Exception:
            logger.exception("Could not parse supposed date expression: %s", line)
            print("Unrecognized.")
        else:
            assert dt is not None
            print(dt.strftime('%A %Y/%m/%d %H:%M:%S.%f %Z(%z)'))
    sys.exit(0)


if __name__ == "__main__":
    main()
