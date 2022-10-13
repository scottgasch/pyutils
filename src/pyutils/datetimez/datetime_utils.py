#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Utilities related to dates, times, and datetimes."""

import datetime
import enum
import logging
import re
from typing import Any, NewType, Optional, Tuple

import holidays  # type: ignore
import pytz

from pyutils.datetimez import constants

logger = logging.getLogger(__name__)


def is_timezone_aware(dt: datetime.datetime) -> bool:
    """Returns true if the datetime argument is timezone aware or
    False if not.

    See: https://docs.python.org/3/library/datetime.html
    #determining-if-an-object-is-aware-or-naive

    Args:
        dt: The datetime object to check

    >>> is_timezone_aware(datetime.datetime.now())
    False

    >>> is_timezone_aware(now_pacific())
    True

    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def is_timezone_naive(dt: datetime.datetime) -> bool:
    """Inverse of is_timezone_aware -- returns true if the dt argument
    is timezone naive.

    See: https://docs.python.org/3/library/datetime.html
    #determining-if-an-object-is-aware-or-naive

    Args:
        dt: The datetime object to check

    >>> is_timezone_naive(datetime.datetime.now())
    True

    >>> is_timezone_naive(now_pacific())
    False

    """
    return not is_timezone_aware(dt)


def strip_timezone(dt: datetime.datetime) -> datetime.datetime:
    """Remove the timezone from a datetime.

    .. warning::

        This does not change the hours, minutes, seconds,
        months, days, years, etc... Thus the instant to which this
        timestamp refers will change.  Silently ignores datetimes
        which are already timezone naive.

    >>> now = now_pacific()
    >>> now.tzinfo == None
    False

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
    Adds a timezone to a timezone naive datetime.  This does not
    change the instant to which the timestamp refers.  See also:
    replace_timezone.

    >>> now = datetime.datetime.now()
    >>> is_timezone_aware(now)
    False

    >>> now_pacific = add_timezone(now, pytz.timezone('US/Pacific'))
    >>> is_timezone_aware(now_pacific)
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
            f'{dt} is already timezone aware; use replace_timezone or translate_timezone '
            + 'depending on the semantics you want.  See the pydocs / code.'
        )
    return dt.replace(tzinfo=tz)


def replace_timezone(
    dt: datetime.datetime, tz: Optional[datetime.tzinfo]
) -> datetime.datetime:
    """Replaces the timezone on a timezone aware datetime object directly
    (leaving the year, month, day, hour, minute, second, micro,
    etc... alone).

    Works with timezone aware and timezone naive dts but for the
    latter it is probably better to use add_timezone or just create it
    with a tz parameter.  Using this can have weird side effects like
    UTC offsets that are not an even multiple of an hour, etc...

    .. warning::

        This changes the instant to which this dt refers.

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
            '%s already has a timezone; klobbering it anyway.\n  Be aware that this operation changed the instant to which the object refers.',
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

    .. warning::

        Note that, as above, this will change the instant to
        which the time refers.

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

    >>> import datetime
    >>> dt = datetime.datetime(2021, 12, 25, 12, 30)
    >>> datetime_to_date(dt)
    datetime.date(2021, 12, 25)

    """
    return datetime_to_date_and_time(dt)[0]


def datetime_to_time(dt: datetime.datetime) -> datetime.time:
    """Return just the time part of a datetime.

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
    e.g.  3 Wednesdays from base datetime, 2 weeks from base date, 10
    years before base datetime, 13 minutes after base datetime, etc...
    Note: to indicate before/after the base date, use a positive or
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
    date_time_separator=" ",
    include_timezone=True,
    include_dayname=False,
    use_month_abbrevs=False,
    include_seconds=True,
    include_fractional=False,
    twelve_hour=True,
) -> str:
    """
    Helper to return a format string without looking up the documentation
    for strftime.

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
    date_time_separator=" ",
    include_timezone=True,
    include_dayname=False,
    use_month_abbrevs=False,
    include_seconds=True,
    include_fractional=False,
    twelve_hour=True,
) -> str:
    """
    A nice way to convert a datetime into a string; arguably better than
    just printing it and relying on it __repr__().

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
    date_time_separator=" ",
    include_timezone=True,
    include_dayname=False,
    use_month_abbrevs=False,
    include_seconds=True,
    include_fractional=False,
    twelve_hour=True,
) -> Tuple[datetime.datetime, str]:
    """A nice way to convert a string into a datetime.  Returns both the
    datetime and the format string used to parse it.  Also consider
    dateparse.dateparse_utils for a full parser alternative.

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
    """Return a timestamp for right now in Pacific timezone."""
    ts = datetime.datetime.now(tz=pytz.timezone("US/Pacific"))
    return datetime_to_string(ts, include_timezone=True)


def time_to_string(
    dt: datetime.datetime,
    *,
    include_seconds=True,
    include_fractional=False,
    include_timezone=False,
    twelve_hour=True,
) -> str:
    """A nice way to convert a datetime into a time (only) string.
    This ignores the date part of the datetime.

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
    """Convert a delta in seconds into a timedelta."""
    return datetime.timedelta(seconds=seconds)


MinuteOfDay = NewType("MinuteOfDay", int)


def minute_number(hour: int, minute: int) -> MinuteOfDay:
    """
    Convert hour:minute into minute number from start of day.

    >>> minute_number(0, 0)
    0

    >>> minute_number(9, 15)
    555

    >>> minute_number(23, 59)
    1439

    """
    return MinuteOfDay(hour * 60 + minute)


def datetime_to_minute_number(dt: datetime.datetime) -> MinuteOfDay:
    """
    Convert a datetime into a minute number (of the day).  Note that
    this ignores the date part of the datetime and only uses the time
    part.

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

    >>> t = datetime.time(5, 15)
    >>> time_to_minute_number(t)
    315

    """
    return minute_number(t.hour, t.minute)


def minute_number_to_time_string(minute_num: MinuteOfDay) -> str:
    """
    Convert minute number from start of day into hour:minute am/pm
    string.

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


def parse_duration(duration: str, raise_on_error=False) -> int:
    """
    Parse a duration in string form into a delta seconds.

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
        r'(\d+ *d[ays]*)* *(\d+ *h[ours]*)* *(\d+ *m[inutes]*)* *(\d+ *[seconds]*)',
        duration,
    )
    if not m and raise_on_error:
        raise ValueError(f'{duration} is not a valid duration.')

    seconds = 0
    m = re.search(r'(\d+) *d[ays]*', duration)
    if m is not None:
        seconds += int(m.group(1)) * 60 * 60 * 24
    m = re.search(r'(\d+) *h[ours]*', duration)
    if m is not None:
        seconds += int(m.group(1)) * 60 * 60
    m = re.search(r'(\d+) *m[inutes]*', duration)
    if m is not None:
        seconds += int(m.group(1)) * 60
    m = re.search(r'(\d+) *s[econds]*', duration)
    if m is not None:
        seconds += int(m.group(1))
    return seconds


def describe_duration(seconds: int, *, include_seconds=False) -> str:
    """
    Describe a duration represented as a count of seconds nicely.

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
        descr = descr + ', '
        if len(descr) > 0:
            descr = descr + 'and '
        s = minutes[1]
        if s == 1:
            descr = descr + '1 second'
        else:
            descr = descr + f'{s} seconds'
    return descr


def describe_timedelta(delta: datetime.timedelta) -> str:
    """
    Describe a duration represented by a timedelta object.

    >>> d = datetime.timedelta(1, 600)
    >>> describe_timedelta(d)
    '1 day, and 10 minutes'

    """
    return describe_duration(int(delta.total_seconds()))  # Note: drops milliseconds


def describe_duration_briefly(seconds: int, *, include_seconds=False) -> str:
    """
    Describe a duration briefly.

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

    descr = ''
    if days[0] > 0:
        descr = f'{int(days[0])}d '
    if hours[0] > 0:
        descr = descr + f'{int(hours[0])}h '
    if minutes[0] > 0 or (len(descr) == 0 and not include_seconds):
        descr = descr + f'{int(minutes[0])}m '
    if minutes[1] > 0 and include_seconds:
        descr = descr + f'{int(minutes[1])}s'
    return descr.strip()


def describe_timedelta_briefly(delta: datetime.timedelta) -> str:
    """
    Describe a duration represented by a timedelta object.

    >>> d = datetime.timedelta(1, 600)
    >>> describe_timedelta_briefly(d)
    '1d 10m'

    """
    return describe_duration_briefly(
        int(delta.total_seconds())
    )  # Note: drops milliseconds


if __name__ == '__main__':
    import doctest

    doctest.testmod()
