#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Utilities related to dates, times, and datetimes."""

import datetime
import enum
import logging
import re
from typing import Any, NewType, Optional, Tuple

import holidays  # type: ignore
import pytz

from pyutils.datetimes import constants

logger = logging.getLogger(__name__)


def is_timezone_aware(dt: datetime.datetime) -> bool:
    """
    Checks whether a datetime is timezone aware or naive.
    See: https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive

    Args:
        dt: the datetime to check for timezone awareness

    Returns:
        True if the datetime argument is timezone aware or
        False if not.

    >>> is_timezone_aware(datetime.datetime.now())
    False

    >>> is_timezone_aware(now_pacific())
    True

    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def is_timezone_naive(dt: datetime.datetime) -> bool:
    """Inverse of :meth:`is_timezone_aware`.
    See: https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive

    Args:
        dt: the datetime to check

    Returns:
        True if the dt argument is timezone naive, False otherwise

    >>> is_timezone_naive(datetime.datetime.now())
    True

    >>> is_timezone_naive(now_pacific())
    False

    """
    return not is_timezone_aware(dt)


def strip_timezone(dt: datetime.datetime) -> datetime.datetime:
    """
    Remove the timezone from a datetime.  Silently ignores datetimes
    which are already timezone naive.

    Args:
        dt: the datetime to remove timezone from

    Returns:
        A datetime identical to dt, the input argument, except for
        that the timezone has been removed.

    See also :meth:`add_timezone`, :meth:`replace_timezone`, :meth:`translate_timezone`.

    .. warning::

        This does not change the hours, minutes, seconds,
        months, days, years, etc... Thus, the instant to which this
        timestamp refers will change when the timezone is added.
        See examples.

    >>> now = now_pacific()
    >>> now.tzinfo == None
    False

    >>> "US/Pacific" in now.tzinfo.__repr__()
    True

    >>> dt = strip_timezone(now)
    >>> dt == now
    False

    >>> dt.tzinfo == None
    True

    >>> dt.hour == now.hour
    True
    """
    if is_timezone_naive(dt):
        return dt
    return replace_timezone(dt, None)


def add_timezone(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    """
    Adds a timezone to a timezone naive datetime.

    Args:
        dt: the datetime to insert a timezone onto
        tz: the timezone to insert

    See also :meth:`replace_timezone`, :meth:`strip_timezone`, :meth:`translate_timezone`.

    Returns:
        A datetime identical to dt, the input datetime, except for
        that a timezone has been added.

    .. warning::

        This doesn't change the hour, minute, second, day, month, etc...
        of the input timezone.  It simply adds a timezone to it.  Adding
        a timezone this way will likely change the instant to which the
        datetime refers.  See examples.

    >>> now = datetime.datetime.now()
    >>> is_timezone_aware(now)
    False

    >>> now_pacific = add_timezone(now, pytz.timezone('US/Pacific'))
    >>> is_timezone_aware(now_pacific)
    True

    >>> "US/Pacific" in now_pacific.tzinfo.__repr__()
    True

    >>> now.hour == now_pacific.hour
    True
    >>> now.minute == now_pacific.minute
    True

    """

    # This doesn't work, tz requires a timezone naive dt.  Two options
    # here:
    #     1. Use strip_timezone and try again.
    #     2. Replace the timezone on your dt object via replace_timezone.
    #        Be aware that this changes the instant to which the dt refers
    #        and, further, can introduce weirdness like UTC offsets that
    #        are weird (e.g. not an even multiple of an hour, etc...)
    if is_timezone_aware(dt):
        if dt.tzinfo == tz:
            return dt
        raise Exception(
            f"{dt} is already timezone aware; use replace_timezone or translate_timezone "
            + "depending on the semantics you want.  See the pydocs / code."
        )
    return dt.replace(tzinfo=tz)


def replace_timezone(
    dt: datetime.datetime, tz: Optional[datetime.tzinfo]
) -> datetime.datetime:
    """
    Replaces the timezone on a timezone aware datetime object directly
    (leaving the year, month, day, hour, minute, second, micro,
    etc... alone).  The same as calling :meth:`strip_timezone` followed
    by :meth:`add_timezone`.

    Works with timezone aware and timezone naive dts but for the
    latter it is probably better to use :meth:`add_timezone` or just
    create it with a `tz` parameter.  Using this can have weird side
    effects like UTC offsets that are not an even multiple of an hour,
    etc...

    Args:
        dt: the datetime whose timezone should be changed
        tz: the new timezone

    Returns:
        The resulting datetime.  Hour, minute, second, etc... are unmodified.
        See warning below.

    See also :meth:`add_timezone`, :meth:`strip_timezone`, :meth:`translate_timezone`.

    .. warning::

        This code isn't changing the hour, minute, second, day, month, etc...
        of the datetime.  It's just messing with the timezone.  Changing
        the timezone without changing the time causes the instant to which
        the datetime refers to change.  For example, if passed 7:01pm PST
        and asked to make it EST, the result will be 7:01pm EST.  See
        examples.

    >>> from pytz import UTC
    >>> d = now_pacific()
    >>> d.tzinfo.tzname(d)[0]     # Note: could be PST or PDT
    'P'
    >>> h = d.hour
    >>> o = replace_timezone(d, UTC)
    >>> o.tzinfo.tzname(o)
    'UTC'
    >>> o.hour == h
    True
    """
    if is_timezone_aware(dt):
        logger.warning(
            "%s already has a timezone; klobbering it anyway.\n  Be aware that this operation changed the instant to which the object refers.",
            dt,
        )
        return datetime.datetime(
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            dt.microsecond,
            tzinfo=tz,
        )
    else:
        if tz:
            return add_timezone(dt, tz)
        else:
            return dt


def replace_time_timezone(t: datetime.time, tz: datetime.tzinfo) -> datetime.time:
    """Replaces the timezone on a datetime.time directly without performing
    any translation.

    Args:
        t: the time to change the timezone on
        tz: the new timezone desired

    Returns:
        A time with hour, minute, second, etc... identical to the input
        time but with timezone replaced.

    .. warning::

        This code isn't changing the hour, minute, second, etc...
        of the time.  It's just messing with the timezone.  Changing
        the timezone without changing the time causes the instant to which
        the datetime refers to change.  For example, if passed 7:01pm PST
        and asked to make it EST, the result will be 7:01pm EST.  See
        examples.

    >>> t = datetime.time(8, 15, 12, 0, pytz.UTC)
    >>> t.tzname()
    'UTC'

    >>> t = replace_time_timezone(t, pytz.timezone('US/Pacific'))
    >>> t.tzname()
    'US/Pacific'
    """
    return t.replace(tzinfo=tz)


def translate_timezone(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    """
    Translates dt into a different timezone by adjusting the year, month,
    day, hour, minute, second, micro, etc... appropriately.  The returned
    dt is the same instant in another timezone.

    Args:
        dt: the datetime whose timezone should be translated.
        tz: the desired timezone

    Returns:
        A new datetime object that represents the same instant as the
        input datetime but in the desired timezone.  Modifies hour, minute,
        seconds, day, etc... as necessary for the instant to be preserved.
        For example, if you pass 11:01pm PST in and ask for it to be
        translated to EST you would get 2:01am the next day EST back
        out.

    See also :meth:`replace_timezone`, :meth:`strip_timezone`.

    >>> import pytz
    >>> d = now_pacific()
    >>> d.tzinfo.tzname(d)[0]     # Note: could be PST or PDT
    'P'
    >>> h = d.hour
    >>> o = translate_timezone(d, pytz.timezone('US/Eastern'))
    >>> o.tzinfo.tzname(o)[0]     # Again, could be EST or EDT
    'E'
    >>> o.hour == h
    False
    >>> expected = h + 3          # Three hours later in E?T than P?T
    >>> expected = expected % 24  # Handle edge case
    >>> expected == o.hour
    True
    """
    return dt.replace().astimezone(tz=tz)


def now() -> datetime.datetime:
    """
    What time is it?  Result is a timezone naive datetime.
    """
    return datetime.datetime.now()


def now_pacific() -> datetime.datetime:
    """
    What time is it?  Result in US/Pacific time (PST/PDT)
    """
    return datetime.datetime.now(pytz.timezone("US/Pacific"))


def date_to_datetime(date: datetime.date) -> datetime.datetime:
    """
    Given a date, return a datetime with hour/min/sec zero (midnight)

    Arg:
        date: the date desired

    Returns:
        A datetime with the same month, day, and year as the input
        date and hours, minutes, seconds set to 12:00:00am.

    >>> import datetime
    >>> date_to_datetime(datetime.date(2021, 12, 25))
    datetime.datetime(2021, 12, 25, 0, 0)
    """
    return datetime.datetime(date.year, date.month, date.day, 0, 0, 0, 0)


def time_to_datetime_today(time: datetime.time) -> datetime.datetime:
    """
    Given a time, returns that time as a datetime with a date component
    set based on the current date.  If the time passed is timezone aware,
    the resulting datetime will also be (and will use the same tzinfo).
    If the time is timezone naive, the datetime returned will be too.

    Args:
        time: the time desired

    Returns:
        datetime with hour, minute, second, timezone set to time and
        day, month, year set to "today".

    >>> t = datetime.time(13, 14, 0)
    >>> d = now_pacific().date()
    >>> dt = time_to_datetime_today(t)
    >>> dt.date() == d
    True

    >>> dt.time() == t
    True

    >>> dt.tzinfo == t.tzinfo
    True

    >>> dt.tzinfo == None
    True

    >>> t = datetime.time(8, 15, 12, 0, pytz.UTC)
    >>> t.tzinfo == None
    False

    >>> dt = time_to_datetime_today(t)
    >>> dt.tzinfo == None
    False

    """
    tz = time.tzinfo
    return datetime.datetime.combine(now_pacific(), time, tz)


def date_and_time_to_datetime(
    date: datetime.date, time: datetime.time
) -> datetime.datetime:
    """
    Given a date and time, merge them and return a datetime.

    Args:
        date: the date component
        time: the time component

    Returns:
        A datetime with the time component set from time and the date
        component set from date.

    >>> import datetime
    >>> d = datetime.date(2021, 12, 25)
    >>> t = datetime.time(12, 30, 0, 0)
    >>> date_and_time_to_datetime(d, t)
    datetime.datetime(2021, 12, 25, 12, 30)
    """
    return datetime.datetime(
        date.year,
        date.month,
        date.day,
        time.hour,
        time.minute,
        time.second,
        time.microsecond,
    )


def datetime_to_date_and_time(
    dt: datetime.datetime,
) -> Tuple[datetime.date, datetime.time]:
    """Return the component date and time objects of a datetime in a
    Tuple given a datetime.

    Args:
        dt: the datetime to decompose

    Returns:
        A tuple whose first element contains a datetime.date that holds
        the day, month, year, etc... from the input dt and whose second
        element contains a datetime.time with hour, minute, second, micros,
        and timezone set from the input dt.

    >>> import datetime
    >>> dt = datetime.datetime(2021, 12, 25, 12, 30)
    >>> (d, t) = datetime_to_date_and_time(dt)
    >>> d
    datetime.date(2021, 12, 25)
    >>> t
    datetime.time(12, 30)
    """
    return (dt.date(), dt.timetz())


def datetime_to_date(dt: datetime.datetime) -> datetime.date:
    """Return just the date part of a datetime.

    Args:
        dt: the datetime

    Returns:
        A datetime.date with month, day and year set from input dt.

    >>> import datetime
    >>> dt = datetime.datetime(2021, 12, 25, 12, 30)
    >>> datetime_to_date(dt)
    datetime.date(2021, 12, 25)
    """
    return datetime_to_date_and_time(dt)[0]


def datetime_to_time(dt: datetime.datetime) -> datetime.time:
    """Return just the time part of a datetime.

    Args:
        dt: the datetime

    Returns:
        A datetime.time with hour, minute, second, micros, and
        timezone set from the input dt.

    >>> import datetime
    >>> dt = datetime.datetime(2021, 12, 25, 12, 30)
    >>> datetime_to_time(dt)
    datetime.time(12, 30)
    """
    return datetime_to_date_and_time(dt)[1]


class TimeUnit(enum.IntEnum):
    """An enum to represent units with which we can compute deltas."""

    MONDAYS = 0
    TUESDAYS = 1
    WEDNESDAYS = 2
    THURSDAYS = 3
    FRIDAYS = 4
    SATURDAYS = 5
    SUNDAYS = 6
    SECONDS = 7
    MINUTES = 8
    HOURS = 9
    DAYS = 10
    WORKDAYS = 11
    WEEKS = 12
    MONTHS = 13
    YEARS = 14

    @classmethod
    def is_valid(cls, value: Any):
        """
        Args:
            value: a value to be checked

        Returns:
            True is input value is a valid TimeUnit, False otherwise.
        """
        if isinstance(value, int):
            return cls(value) is not None
        elif isinstance(value, TimeUnit):
            return cls(value.value) is not None
        elif isinstance(value, str):
            return cls.__members__[value] is not None
        else:
            print(type(value))
            return False


def n_timeunits_from_base(
    count: int, unit: TimeUnit, base: datetime.datetime
) -> datetime.datetime:
    """Return a datetime that is N units before/after a base datetime.
    For example:

        - 3 Wednesdays from base datetime,
        - 2 weeks from base date,
        - 10 years before base datetime,
        - 13 minutes after base datetime, etc...

    Args:
        count: signed number that indicates N units before/after the base.
        unit: the timeunit that we are counting by.
        base: a datetime representing the base date the result should be
            relative to.

    Returns:
        A datetime that is count units before of after the base datetime.

    .. note::

        To indicate before/after the base date, use a positive or
        negative count.

    >>> base = string_to_datetime("2021/09/10 11:24:51AM-0700")[0]

    The next (1) Monday from the base datetime:

    >>> n_timeunits_from_base(+1, TimeUnit.MONDAYS, base)
    datetime.datetime(2021, 9, 13, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Ten (10) years after the base datetime:

    >>> n_timeunits_from_base(10, TimeUnit.YEARS, base)
    datetime.datetime(2031, 9, 10, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Fifty (50) working days (M..F, not counting holidays) after base datetime:

    >>> n_timeunits_from_base(50, TimeUnit.WORKDAYS, base)
    datetime.datetime(2021, 11, 23, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Fifty (50) days (including weekends and holidays) after base datetime:

    >>> n_timeunits_from_base(50, TimeUnit.DAYS, base)
    datetime.datetime(2021, 10, 30, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Fifty (50) months before (note negative count) base datetime:

    >>> n_timeunits_from_base(-50, TimeUnit.MONTHS, base)
    datetime.datetime(2017, 7, 10, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Fifty (50) hours after base datetime:

    >>> n_timeunits_from_base(50, TimeUnit.HOURS, base)
    datetime.datetime(2021, 9, 12, 13, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Fifty (50) minutes before base datetime:

    >>> n_timeunits_from_base(-50, TimeUnit.MINUTES, base)
    datetime.datetime(2021, 9, 10, 10, 34, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Fifty (50) seconds from base datetime:

    >>> n_timeunits_from_base(50, TimeUnit.SECONDS, base)
    datetime.datetime(2021, 9, 10, 11, 25, 41, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Next month corner case -- it will try to make Feb 31, 2022 then count
    backwards.

    >>> base = string_to_datetime("2022/01/31 11:24:51AM-0700")[0]
    >>> n_timeunits_from_base(1, TimeUnit.MONTHS, base)
    datetime.datetime(2022, 2, 28, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    Last month with the same corner case

    >>> base = string_to_datetime("2022/03/31 11:24:51AM-0700")[0]
    >>> n_timeunits_from_base(-1, TimeUnit.MONTHS, base)
    datetime.datetime(2022, 2, 28, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))
    """
    assert TimeUnit.is_valid(unit)
    if count == 0:
        return base

    # N days from base
    if unit == TimeUnit.DAYS:
        timedelta = datetime.timedelta(days=count)
        return base + timedelta

    # N hours from base
    elif unit == TimeUnit.HOURS:
        timedelta = datetime.timedelta(hours=count)
        return base + timedelta

    # N minutes from base
    elif unit == TimeUnit.MINUTES:
        timedelta = datetime.timedelta(minutes=count)
        return base + timedelta

    # N seconds from base
    elif unit == TimeUnit.SECONDS:
        timedelta = datetime.timedelta(seconds=count)
        return base + timedelta

    # N workdays from base
    elif unit == TimeUnit.WORKDAYS:
        if count < 0:
            count = abs(count)
            timedelta = datetime.timedelta(days=-1)
        else:
            timedelta = datetime.timedelta(days=1)
        skips = holidays.US(years=base.year).keys()
        while count > 0:
            old_year = base.year
            base += timedelta
            if base.year != old_year:
                skips = holidays.US(years=base.year).keys()
            if (
                base.weekday() < 5
                and datetime.date(base.year, base.month, base.day) not in skips
            ):
                count -= 1
        return base

    # N weeks from base
    elif unit == TimeUnit.WEEKS:
        timedelta = datetime.timedelta(weeks=count)
        base = base + timedelta
        return base

    # N months from base
    elif unit == TimeUnit.MONTHS:
        month_term = count % 12
        year_term = count // 12
        new_month = base.month + month_term
        if new_month > 12:
            new_month %= 12
            year_term += 1
        new_year = base.year + year_term
        day = base.day
        while True:
            try:
                ret = datetime.datetime(
                    new_year,
                    new_month,
                    day,
                    base.hour,
                    base.minute,
                    base.second,
                    base.microsecond,
                    base.tzinfo,
                )
                break
            except ValueError:
                day -= 1
        return ret

    # N years from base
    elif unit == TimeUnit.YEARS:
        new_year = base.year + count
        return datetime.datetime(
            new_year,
            base.month,
            base.day,
            base.hour,
            base.minute,
            base.second,
            base.microsecond,
            base.tzinfo,
        )

    if unit not in set(
        [
            TimeUnit.MONDAYS,
            TimeUnit.TUESDAYS,
            TimeUnit.WEDNESDAYS,
            TimeUnit.THURSDAYS,
            TimeUnit.FRIDAYS,
            TimeUnit.SATURDAYS,
            TimeUnit.SUNDAYS,
        ]
    ):
        raise ValueError(unit)

    # N weekdays from base (e.g. 4 wednesdays from today)
    direction = 1 if count > 0 else -1
    count = abs(count)
    timedelta = datetime.timedelta(days=direction)
    start = base
    while True:
        dow = base.weekday()
        if dow == unit.value and start != base:
            count -= 1
            if count == 0:
                return base
        base = base + timedelta


def get_format_string(
    *,
    date_time_separator: str = " ",
    include_timezone: bool = True,
    include_dayname: bool = False,
    use_month_abbrevs: bool = False,
    include_seconds: bool = True,
    include_fractional: bool = False,
    twelve_hour: bool = True,
) -> str:
    """
    Helper to return a format string without looking up the documentation
    for strftime.

    Args:
        date_time_separator: character or string to use between the date
            and time outputs.
        include_timezone: whether or not the result should include a timezone
        include_dayname: whether or not the result should incude the dayname
            (e.g. Monday, Wednesday, etc...)
        use_month_abbrevs: whether or not to abbreviate (e.g. Jan) or spell out
            (e.g. January) month names.
        include_seconds: whether or not to include seconds in time.
        include_fractional: whether or not to include micros in time output.
        twelve_hour: use twelve hour (with am/pm) or twenty four hour time format?

    Returns:
        The format string for use with strftime that follows the given
        requirements.

    >>> get_format_string()
    '%Y/%m/%d %I:%M:%S%p%z'

    >>> get_format_string(date_time_separator='@')
    '%Y/%m/%d@%I:%M:%S%p%z'

    >>> get_format_string(include_dayname=True)
    '%a/%Y/%m/%d %I:%M:%S%p%z'

    >>> get_format_string(include_dayname=True, twelve_hour=False)
    '%a/%Y/%m/%d %H:%M:%S%z'

    """
    fstring = ""
    if include_dayname:
        fstring += "%a/"

    if use_month_abbrevs:
        fstring = f"{fstring}%Y/%b/%d{date_time_separator}"
    else:
        fstring = f"{fstring}%Y/%m/%d{date_time_separator}"
    if twelve_hour:
        fstring += "%I:%M"
        if include_seconds:
            fstring += ":%S"
        fstring += "%p"
    else:
        fstring += "%H:%M"
        if include_seconds:
            fstring += ":%S"
    if include_fractional:
        fstring += ".%f"
    if include_timezone:
        fstring += "%z"
    return fstring


def datetime_to_string(
    dt: datetime.datetime,
    *,
    date_time_separator: str = " ",
    include_timezone: bool = True,
    include_dayname: bool = False,
    use_month_abbrevs: bool = False,
    include_seconds: bool = True,
    include_fractional: bool = False,
    twelve_hour: bool = True,
) -> str:
    """
    A nice way to convert a datetime into a string; arguably better than
    just printing it and relying on it __repr__().

    Args:
        dt: the datetime to represent
        date_time_separator: the character or string to separate the date and time
            pieces of the representation.
        include_timezone: should we include a timezone in the representation?
        include_dayname: should we include the dayname (e.g. Mon) in
            the representation or omit it?
        use_month_abbrevs: should we name the month briefly (e.g. Jan) or spell
            it out fully (e.g. January) in the representation?
        include_seconds: should we include seconds in the time?
        include_fractional: should we include micros in the time?
        twelve_hour: should we use twelve or twenty-four hour time format?

    >>> d = string_to_datetime(
    ...                        "2021/09/10 11:24:51AM-0700",
    ...                       )[0]
    >>> d
    datetime.datetime(2021, 9, 10, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))
    >>> datetime_to_string(d)
    '2021/09/10 11:24:51AM-0700'
    >>> datetime_to_string(d, include_dayname=True, include_seconds=False)
    'Fri/2021/09/10 11:24AM-0700'
    """
    fstring = get_format_string(
        date_time_separator=date_time_separator,
        include_timezone=include_timezone,
        include_dayname=include_dayname,
        use_month_abbrevs=use_month_abbrevs,
        include_seconds=include_seconds,
        include_fractional=include_fractional,
        twelve_hour=twelve_hour,
    )
    return dt.strftime(fstring).strip()


def string_to_datetime(
    txt: str,
    *,
    date_time_separator: str = " ",
    include_timezone: bool = True,
    include_dayname: bool = False,
    use_month_abbrevs: bool = False,
    include_seconds: bool = True,
    include_fractional: bool = False,
    twelve_hour: bool = True,
) -> Tuple[datetime.datetime, str]:
    """A nice way to convert a string into a datetime.  Returns both the
    datetime and the format string used to parse it.  Also consider
    :mod:`pyutils.datetimes.dateparse_utils` for a full parser alternative.

    Args:
        txt: the string to be converted into a datetime
        date_time_separator: the character or string between the time and date
            portions.
        include_timezone: does the string include a timezone?
        include_dayname: does the string include a dayname?
        use_month_abbrevs: is the month abbreviated in the string (e.g. Feb)
            or spelled out completely (e.g. February)?
        include_seconds: does the string's time include seconds?
        include_fractional: does the string's time include micros?
        twelve_hour: is the string's time in twelve or twenty-four hour format?

    Returns:
        A tuple containing the datetime parsed from string and the formatting
        string used to parse it.

    >>> d = string_to_datetime(
    ...                        "2021/09/10 11:24:51AM-0700",
    ...                       )
    >>> d
    (datetime.datetime(2021, 9, 10, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200))), '%Y/%m/%d %I:%M:%S%p%z')

    """
    fstring = get_format_string(
        date_time_separator=date_time_separator,
        include_timezone=include_timezone,
        include_dayname=include_dayname,
        use_month_abbrevs=use_month_abbrevs,
        include_seconds=include_seconds,
        include_fractional=include_fractional,
        twelve_hour=twelve_hour,
    )
    return (datetime.datetime.strptime(txt, fstring), fstring)


def timestamp() -> str:
    """
    Returns:
        A timestamp for right now in Pacific timezone.
    """
    ts = datetime.datetime.now(tz=pytz.timezone("US/Pacific"))
    return datetime_to_string(ts, include_timezone=True)


def time_to_string(
    dt: datetime.datetime,
    *,
    include_seconds: bool = True,
    include_fractional: bool = False,
    include_timezone: bool = False,
    twelve_hour: bool = True,
) -> str:
    """A nice way to convert a datetime into a time (only) string.
    This ignores the date part of the datetime completely.

    Args:
        dt: the datetime whose time to represent
        include_seconds: should seconds be included in the output?
        include_fractional: should micros be included in the output?
        include_timezone: should timezone be included in the output?
        twelve_hour: use twelve or twenty-four hour format?

    Returns:
        A string representing the time of the input datetime.

    >>> d = string_to_datetime(
    ...                        "2021/09/10 11:24:51AM-0700",
    ...                       )[0]
    >>> d
    datetime.datetime(2021, 9, 10, 11, 24, 51, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200)))

    >>> time_to_string(d)
    '11:24:51AM'

    >>> time_to_string(d, include_seconds=False)
    '11:24AM'

    >>> time_to_string(d, include_seconds=False, include_timezone=True)
    '11:24AM-0700'

    """
    fstring = ""
    if twelve_hour:
        fstring += "%l:%M"
        if include_seconds:
            fstring += ":%S"
        fstring += "%p"
    else:
        fstring += "%H:%M"
        if include_seconds:
            fstring += ":%S"
    if include_fractional:
        fstring += ".%f"
    if include_timezone:
        fstring += "%z"
    return dt.strftime(fstring).strip()


def seconds_to_timedelta(seconds: int) -> datetime.timedelta:
    """
    Args:
        seconds: a count of seconds

    Returns:
        A datetime.timedelta representing that count of seconds.
    """
    return datetime.timedelta(seconds=seconds)


MinuteOfDay = NewType("MinuteOfDay", int)


def minute_number(hour: int, minute: int) -> MinuteOfDay:
    """
    Convert hour:minute into minute number from start of day.  That is,
    if you imagine a day as a sequence of minutes from minute #0 up
    to minute #1439, what minute number is, e.g., 6:52am?

    Args:
        hour: the hour to convert (0 <= hour <= 23)
        minute: the minute to convert (0 <= minute <= 59)

    Returns:
        The minute number requested.  Raises `ValueError` on bad input.

    >>> minute_number(0, 0)
    0

    >>> minute_number(9, 15)
    555

    >>> minute_number(23, 59)
    1439
    """
    if hour < 0 or hour > 23:
        raise ValueError(f"Bad hour: {hour}.  Expected 0 <= hour <= 23")
    if minute < 0 or minute > 59:
        raise ValueError(f"Bad minute: {minute}.  Expected 0 <= minute <= 59")
    return MinuteOfDay(hour * 60 + minute)


def datetime_to_minute_number(dt: datetime.datetime) -> MinuteOfDay:
    """
    Convert a datetime's time component into a minute number (of
    the day).  Note that this ignores the date part of the datetime
    and only uses the time part.

    Args:
        dt: the datetime whose time is to be converted

    Returns:
        The minute number (of the day) that represents the input datetime's
        time.

    >>> d = string_to_datetime(
    ...                        "2021/09/10 11:24:51AM-0700",
    ...                       )[0]

    >>> datetime_to_minute_number(d)
    684
    """
    return minute_number(dt.hour, dt.minute)


def time_to_minute_number(t: datetime.time) -> MinuteOfDay:
    """
    Convert a datetime.time into a minute number.

    Args:
        t: a datetime.time to convert into a minute number.

    Returns:
        The minute number (of the day) of the input time.

    >>> t = datetime.time(5, 15)
    >>> time_to_minute_number(t)
    315
    """
    return minute_number(t.hour, t.minute)


def minute_number_to_time_string(minute_num: MinuteOfDay) -> str:
    """
    Convert minute number from start of day into hour:minute am/pm
    string.

    Args:
        minute_num: the minute number to convert into a string

    Returns:
        A string of the format "HH:MM[a|p]" that represents the time
        that the input minute_num refers to.

    >>> minute_number_to_time_string(315)
    ' 5:15a'

    >>> minute_number_to_time_string(684)
    '11:24a'
    """
    hour = minute_num // 60
    minute = minute_num % 60
    ampm = "a"
    if hour > 12:
        hour -= 12
        ampm = "p"
    if hour == 12:
        ampm = "p"
    if hour == 0:
        hour = 12
    return f"{hour:2}:{minute:02}{ampm}"


def parse_duration(duration: str, raise_on_error: bool = False) -> int:
    """
    Parse a duration in string form into a delta seconds.

    Args:
        duration: a string form duration, see examples.
        raise_on_error: should we raise on invalid input or just
            return a zero duration?

    Returns:
        A count of seconds represented by the input string.

    >>> parse_duration('15 days, 2 hours')
    1303200

    >>> parse_duration('15d 2h')
    1303200

    >>> parse_duration('100s')
    100

    >>> parse_duration('3min 2sec')
    182

    >>> parse_duration('recent')
    0

    >>> parse_duration('recent', raise_on_error=True)
    Traceback (most recent call last):
    ...
    ValueError: recent is not a valid duration.
    """
    if duration.isdigit():
        return int(duration)

    m = re.match(
        r"(\d+ *d[ays]*)* *(\d+ *h[ours]*)* *(\d+ *m[inutes]*)* *(\d+ *[seconds]*)",
        duration,
    )
    if not m and raise_on_error:
        raise ValueError(f"{duration} is not a valid duration.")

    seconds = 0
    m = re.search(r"(\d+) *d[ays]*", duration)
    if m is not None:
        seconds += int(m.group(1)) * 60 * 60 * 24
    m = re.search(r"(\d+) *h[ours]*", duration)
    if m is not None:
        seconds += int(m.group(1)) * 60 * 60
    m = re.search(r"(\d+) *m[inutes]*", duration)
    if m is not None:
        seconds += int(m.group(1)) * 60
    m = re.search(r"(\d+) *s[econds]*", duration)
    if m is not None:
        seconds += int(m.group(1))
    return seconds


def describe_duration(seconds: int, *, include_seconds: bool = False) -> str:
    """
    Describe a duration represented as a count of seconds nicely.

    Args:
        seconds: the number of seconds in the duration to be represented.
        include_seconds: should we include or drop the seconds part in
            the representation?

    .. note::

        Of course if we drop the seconds part the result is not precise.
        See examples.

    >>> describe_duration(182)
    '3 minutes'

    >>> describe_duration(182, include_seconds=True)
    '3 minutes, and 2 seconds'

    >>> describe_duration(100, include_seconds=True)
    '1 minute, and 40 seconds'

    describe_duration(1303200)
    '15 days, 2 hours'
    """
    days = divmod(seconds, constants.SECONDS_PER_DAY)
    hours = divmod(days[1], constants.SECONDS_PER_HOUR)
    minutes = divmod(hours[1], constants.SECONDS_PER_MINUTE)

    descr = ""
    if days[0] > 1:
        descr = f"{int(days[0])} days, "
    elif days[0] == 1:
        descr = "1 day, "

    if hours[0] > 1:
        descr = descr + f"{int(hours[0])} hours, "
    elif hours[0] == 1:
        descr = descr + "1 hour, "

    if not include_seconds and len(descr) > 0:
        descr = descr + "and "

    if minutes[0] == 1:
        descr = descr + "1 minute"
    else:
        descr = descr + f"{int(minutes[0])} minutes"

    if include_seconds:
        descr = descr + ", "
        if len(descr) > 0:
            descr = descr + "and "
        s = minutes[1]
        if s == 1:
            descr = descr + "1 second"
        else:
            descr = descr + f"{s} seconds"
    return descr


def describe_timedelta(delta: datetime.timedelta) -> str:
    """
    Describe a duration represented by a timedelta object.

    Args:
        delta: the timedelta object that represents the duration to describe.

    Returns:
        A string representation of the input duration.

    .. warning::

        Milliseconds are never included in the string representation of
        durations even through they may be represented by an input
        `datetime.timedelta`.  Not for use when this level of precision
        is needed.

    >>> d = datetime.timedelta(1, 600)
    >>> describe_timedelta(d)
    '1 day, and 10 minutes'
    """
    return describe_duration(int(delta.total_seconds()))  # Note: drops milliseconds


def describe_duration_briefly(seconds: int, *, include_seconds: bool = False) -> str:
    """
    Describe a duration briefly.

    Args:
        seconds: the number of seconds in the duration to describe.
        include_seconds: should we include seconds in our description or omit?

    Returns:
        A string describing the duration represented by the input seconds briefly.

    .. note::

        Of course if we drop the seconds part the result is not precise.
        See examples.

    >>> describe_duration_briefly(182)
    '3m'

    >>> describe_duration_briefly(182, include_seconds=True)
    '3m 2s'

    >>> describe_duration_briefly(100, include_seconds=True)
    '1m 40s'

    describe_duration_briefly(1303200)
    '15d 2h'

    """
    days = divmod(seconds, constants.SECONDS_PER_DAY)
    hours = divmod(days[1], constants.SECONDS_PER_HOUR)
    minutes = divmod(hours[1], constants.SECONDS_PER_MINUTE)

    descr = ""
    if days[0] > 0:
        descr = f"{int(days[0])}d "
    if hours[0] > 0:
        descr = descr + f"{int(hours[0])}h "
    if minutes[0] > 0 or (len(descr) == 0 and not include_seconds):
        descr = descr + f"{int(minutes[0])}m "
    if minutes[1] > 0 and include_seconds:
        descr = descr + f"{int(minutes[1])}s"
    return descr.strip()


def describe_timedelta_briefly(
    delta: datetime.timedelta, *, include_seconds: bool = False
) -> str:
    """
    Describe a duration represented by a timedelta object.

    Args:
        delta: the timedelta to describe briefly
        include_seconds: should we include the second delta?

    Returns:
        A string description of the input timedelta object.

    .. warning::

        Milliseconds are never included in the string representation of
        durations even through they may be represented by an input
        `datetime.timedelta`.  Not for use when this level of precision
        is needed.

    >>> d = datetime.timedelta(1, 600)
    >>> describe_timedelta_briefly(d)
    '1d 10m'
    """
    return describe_duration_briefly(
        int(delta.total_seconds()),
        include_seconds=include_seconds,
    )  # Note: drops milliseconds


# The code to compute easter on a given year was copied from dateutil (pip
# install python-dateutil) and dumped in here to avoid a dependency.  Dateutil
# is an Apache 2.0 LICENSE open source project:

# Copyright 2017- Paul Ganssle <paul@ganssle.io>
# Copyright 2017- dateutil contributors (see AUTHORS file)

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

# The above license applies to all contributions after 2017-12-01, as well as
# all contributions that have been re-licensed (see AUTHORS file for the list of
# contributors who have re-licensed their code).
# --------------------------------------------------------------------------------
# dateutil - Extensions to the standard Python datetime module.

# Copyright (c) 2003-2011 - Gustavo Niemeyer <gustavo@niemeyer.net>
# Copyright (c) 2012-2014 - Tomi Pieviläinen <tomi.pievilainen@iki.fi>
# Copyright (c) 2014-2016 - Yaron de Leeuw <me@jarondl.net>
# Copyright (c) 2015-     - Paul Ganssle <paul@ganssle.io>
# Copyright (c) 2015-     - dateutil contributors (see AUTHORS file)

# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The above BSD License Applies to all code, even that also covered by Apache 2.0.

EASTER_JULIAN = 1
EASTER_ORTHODOX = 2
EASTER_WESTERN = 3


def easter(year: int, method: int = EASTER_WESTERN):
    """
    This method was ported from the work done by GM Arts,
    on top of the algorithm by Claus Tondering, which was
    based in part on the algorithm of Ouding (1940), as
    quoted in "Explanatory Supplement to the Astronomical
    Almanac", P.  Kenneth Seidelmann, editor.

    This algorithm implements three different Easter
    calculation methods:

    1. Original calculation in Julian calendar, valid in
       dates after 326 AD
    2. Original method, with date converted to Gregorian
       calendar, valid in years 1583 to 4099
    3. Revised method, in Gregorian calendar, valid in
       years 1583 to 4099 as well

    These methods are represented by the constants:

    * ``EASTER_JULIAN   = 1``
    * ``EASTER_ORTHODOX = 2``
    * ``EASTER_WESTERN  = 3``

    The default method is method 3.

    More about the algorithm may be found at:

    `GM Arts: Easter Algorithms <http://www.gmarts.org/index.php?go=415>`_

    and

    `The Calendar FAQ: Easter <https://www.tondering.dk/claus/cal/easter.php>`_

    """

    if not (1 <= method <= 3):
        raise ValueError("invalid method")

    # g - Golden year - 1
    # c - Century
    # h - (23 - Epact) mod 30
    # i - Number of days from March 21 to Paschal Full Moon
    # j - Weekday for PFM (0=Sunday, etc)
    # p - Number of days from March 21 to Sunday on or before PFM
    #     (-6 to 28 methods 1 & 3, to 56 for method 2)
    # e - Extra days to add for method 2 (converting Julian
    #     date to Gregorian date)

    y = year
    g = y % 19
    e = 0
    if method < 3:
        # Old method
        i = (19 * g + 15) % 30
        j = (y + y // 4 + i) % 7
        if method == 2:
            # Extra dates to convert Julian to Gregorian date
            e = 10
            if y > 1600:
                e = e + y // 100 - 16 - (y // 100 - 16) // 4
    else:
        # New method
        c = y // 100
        h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
        i = h - (h // 28) * (1 - (h // 28) * (29 // (h + 1)) * ((21 - g) // 11))
        j = (y + y // 4 + i + 2 - c + c // 4) % 7

    # p can be from -6 to 56 corresponding to dates 22 March to 23 May
    # (later dates apply to method 2, although 23 May never actually occurs)
    p = i - j + e
    d = 1 + (p + 27 + (p + 6) // 40) % 31
    m = 3 + (p + 26) // 30
    return datetime.date(int(y), int(m), int(d))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
