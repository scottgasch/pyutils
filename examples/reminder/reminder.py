#!/usr/bin/env python3

"""
Reminders for upcoming important dates.
"""

import datetime
import logging
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional

from pyutils import argparse_utils, bootstrap, config, persistent, string_utils
from pyutils.ansi import fg, reset
from pyutils.datetimes import dateparse_utils as dateparse
from pyutils.files import file_utils

logger = logging.getLogger(__name__)
cfg = config.add_commandline_args(
    f"Main ({__file__})", "Reminder of events, birthdays and anniversaries."
)
cfg.add_argument(
    "--reminder_filename",
    type=argparse_utils.valid_filename,
    default=".reminder",
    metavar="FILENAME",
    help="Override the .reminder filepath",
)
cfg.add_argument(
    "--reminder_cache_file",
    type=str,
    default=f'{os.environ["HOME"]}/.reminder_cache',
    metavar="FILENAME",
    help="Override the .reminder cache location",
)
cfg.add_argument(
    "-n", "--count", type=int, metavar="COUNT", help="How many events to remind about"
)
cfg.add_argument(
    "--days_ahead",
    type=int,
    metavar="#DAYS",
    help="How many days ahead to remind about",
)
cfg.add_argument(
    "-d",
    "--date",
    "--dates",
    action="store_true",
    help="Also include the date along with the n day countdown",
)
cfg.add_argument(
    "--override_timestamp",
    nargs=1,
    type=argparse_utils.valid_datetime,
    help="Don't use the current datetime, use this one instead.",
    metavar="DATE/TIME STRING",
    default=None,
)


# This decorator handles caching this object's state on disk and feeding the
# state back to new instances of this object at initialization time.  It also
# makes sure that this object is a global singleton in the program.
@persistent.persistent_autoloaded_singleton()
class Reminder(object):
    MODE_EVENT = 0
    MODE_BIRTHDAY = 1
    MODE_ANNIVERSARY = 2

    def __init__(
        self, cached_state: Optional[Dict[datetime.date, List[str]]] = None
    ) -> None:
        if not config.config["override_timestamp"]:
            self.today = datetime.date.today()
        else:
            self.today = config.config["override_timestamp"][0].date()
            logger.debug(
                'Overriding "now" with %s because of commandline argument.',
                self.today,
            )
        if cached_state is not None:
            self.label_by_date = cached_state
            return
        self.label_by_date: Dict[datetime.date, List[str]] = defaultdict(list)
        self.read_file(config.config["reminder_filename"])

    def handle_event_by_adjusting_year_to_now(
        self,
        parsing_mode: int,
        orig_date: datetime.date,
        orig_label: str,
        saw_overt_year: bool,
    ) -> None:
        for year in (self.today.year, self.today.year + 1):
            label = orig_label
            if saw_overt_year:
                delta = year - orig_date.year
                if parsing_mode == Reminder.MODE_BIRTHDAY:
                    if delta != 0:
                        label += f" ({delta} year{string_utils.pluralize(delta)} old)"
                elif parsing_mode == Reminder.MODE_ANNIVERSARY:
                    if delta != 0:
                        label += f" ({delta}{string_utils.thify(delta)} anniversary)"
            dt = datetime.date(
                year=year,
                month=orig_date.month,
                day=orig_date.day,
            )
            logger.debug("Date in %d: %s", year, dt)
            self.label_by_date[dt].append(label)
            logger.debug("%s => %s", dt, label)

    def handle_event_with_fixed_year(
        self,
        orig_date: datetime.date,
        orig_label: str,
    ) -> None:
        logger.debug("Fixed date event...")
        self.label_by_date[orig_date].append(orig_label)
        logger.debug("%s => %s", orig_date, orig_label)

    def read_file(self, filename: str) -> None:
        logger.debug("Reading %s:", filename)
        date_parser = dateparse.DateParser()
        parsing_mode = Reminder.MODE_EVENT
        with open(filename) as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            line = re.sub(r"#.*$", "", line)
            if re.match(r"^ *$", line) is not None:
                continue
            logger.debug("> %s", line)
            try:
                if "=" in line:
                    label, date = line.split("=")
                else:
                    print(f"Skipping unparsable line: {line}", file=sys.stderr)
                    logger.error("Skipping malformed line: %s", line)
                    continue

                if label == "type":
                    if "event" in date:
                        parsing_mode = Reminder.MODE_EVENT
                        logger.debug("--- EVENT MODE ---")
                    elif "birthday" in date:
                        parsing_mode = Reminder.MODE_BIRTHDAY
                        logger.debug("--- BIRTHDAY MODE ---")
                    elif "anniversary" in date:
                        parsing_mode = Reminder.MODE_ANNIVERSARY
                        logger.debug("--- ANNIVERSARY MODE ---")
                else:
                    date_parser.parse(date)
                    orig_date = date_parser.get_date()
                    if orig_date is None:
                        print(f"Skipping unparsable date: {line}", file=sys.stderr)
                        logger.error("Skipping line with unparsable date")
                        continue
                    logger.debug("Original date: %s", orig_date)

                    overt_year = date_parser.saw_overt_year
                    if parsing_mode in (
                        Reminder.MODE_BIRTHDAY,
                        Reminder.MODE_ANNIVERSARY,
                    ) or (parsing_mode == Reminder.MODE_EVENT and not overt_year):
                        self.handle_event_by_adjusting_year_to_now(
                            parsing_mode, orig_date, label, overt_year
                        )
                    else:
                        self.handle_event_with_fixed_year(orig_date, label)

            except Exception:
                logger.exception("Skipping malformed line: %s", line)
                print(f"Skipping unparsable line: {line}", file=sys.stderr)

    def remind(
        self, count: Optional[int], days_ahead: Optional[int], say_date: bool
    ) -> None:
        need_both = False
        if count is not None and days_ahead is not None:
            need_both = True
            seen = 0

        for date in sorted(self.label_by_date.keys()):
            delta = date - self.today
            d = delta.days
            if d >= 0:
                if days_ahead is not None:
                    if d > days_ahead:
                        if not need_both:
                            return
                        seen |= 1
                        if seen == 3:
                            return
                labels = self.label_by_date[date]
                for label in labels:
                    if d > 1:
                        if d <= 3:
                            msg = f"{fg('blaze orange')}{d} days{reset()} until {label}"
                        elif d <= 7:
                            msg = f"{fg('peach orange')}{d} days{reset()} until {label}"
                        else:
                            msg = f"{d} days until {label}"
                    elif d == 1:
                        msg = f"{fg('outrageous orange')}Tomorrow{reset()} is {label}"
                    else:
                        assert d == 0
                        msg = f"{fg('red')}Today{reset()} is {label}"
                    if say_date:
                        msg += f" {fg('battleship gray')}on {date.strftime('%A, %B %-d')}{reset()}"
                    print(msg)
                    if count is not None:
                        count -= 1
                        if count <= 0:
                            if not need_both:
                                return
                            seen |= 2
                            if seen == 3:
                                return

    @classmethod
    def load(cls):
        if not config.config["override_timestamp"]:
            now = datetime.datetime.now()
        else:
            now = config.config["override_timestamp"][0]
            logger.debug(
                'Overriding "now" with %s because of commandline argument.', now
            )

        cache_ts = file_utils.get_file_mtime_as_datetime(
            config.config["reminder_cache_file"]
        )
        if cache_ts is None:
            return None

        # If the cache was already written today...
        if (
            now.day == cache_ts.day
            and now.month == cache_ts.month
            and now.year == cache_ts.year
        ):
            reminder_ts = file_utils.get_file_mtime_as_datetime(
                config.config["reminder_filename"]
            )

            # ...and the .reminder file wasn't updated since the cache write...
            if reminder_ts <= cache_ts:
                import pickle

                with open(config.config["reminder_cache_file"], "rb") as rf:
                    reminder_data = pickle.load(rf)
                    return cls(reminder_data)
        return None

    def save(self):
        import pickle

        with open(config.config["reminder_cache_file"], "wb") as wf:
            pickle.dump(
                self.label_by_date,
                wf,
                pickle.HIGHEST_PROTOCOL,
            )


@bootstrap.initialize
def main() -> None:
    reminder = Reminder()
    count = config.config["count"]
    days_ahead = config.config["days_ahead"]
    reminder.remind(count, days_ahead, config.config["date"])
    return None


if __name__ == "__main__":
    main()
