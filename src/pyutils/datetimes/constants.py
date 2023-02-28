#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Universal date/time constants."""

from typing import Final

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

# Date/time based constants
SECONDS_PER_MINUTE: Final = 60
SECONDS_PER_HOUR: Final = 60 * SECONDS_PER_MINUTE
SECONDS_PER_DAY: Final = 24 * SECONDS_PER_HOUR
SECONDS_PER_WEEK: Final = 7 * SECONDS_PER_DAY
MINUTES_PER_HOUR: Final = 60
MINUTES_PER_DAY: Final = 24 * MINUTES_PER_HOUR
MINUTES_PER_WEEK: Final = 7 * MINUTES_PER_DAY
HOURS_PER_DAY: Final = 24
HOURS_PER_WEEK: Final = 7 * HOURS_PER_DAY
DAYS_PER_WEEK: Final = 7
