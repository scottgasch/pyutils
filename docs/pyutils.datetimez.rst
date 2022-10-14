yutils.datetimez package
=========================

Submodules
----------

pyutils.datetimez.constants module
----------------------------------

A set of date and time related constants.

.. automodule:: pyutils.datetimez.constants
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.datetimez.dateparse\_utils module
-----------------------------------------

The dateparse\_utils.DateParser class uses an English language grammar
(see dateparse\_utils.g4) to parse free form English text into a Python
datetime.  It can handle somewhat complex constructs such as: "20 days
from next Wed at 3pm", "last Christmas", and "The 2nd Sunday in May,
2022".  See the dateparse_utils_test.py for more examples.

This code is used by other code in the pyutils library; for example,
when using argparse_utils.py to pass an argument of type datetime it
allows the user to use free form english expressions.

.. automodule:: pyutils.datetimez.dateparse_utils
   :members:
   :undoc-members:
   :exclude-members: enterAmpm,
                     enterBaseAndOffsetDateExpr,
                     enterBaseAndOffsetTimeExpr,
                     enterBaseDate,
                     enterBaseTime,
                     enterCountUnitsBeforeAfterTimeExpr,
                     enterDateExpr,
                     enterDayMonthMaybeYearExpr,
                     enterDayName,
                     enterDayOfMonth,
                     enterDdiv,
                     enterDeltaBeforeAfter,
                     enterDeltaDateExprRelativeToTodayImplied,
                     enterDeltaNextLast,enterDeltaPlusMinusExpr,
                     enterDeltaPlusMinusTimeExpr,
                     enterDeltaRelativeToTodayExpr,
                     enterDeltaTimeBeforeAfter,
                     enterDeltaTimeFraction,
                     enterDeltaTimeUnit,
                     enterDeltaUnit,
                     enterDtdiv,
                     enterFirstLastWeekdayInMonthMaybeYearExpr,
                     enterFirstOrLast,
                     enterFractionBeforeAfterTimeExpr,
                     enterHour,
                     enterLtz,
                     enterMicros,
                     enterMinute,
                     enterMonthDayMaybeYearExpr,
                     enterMonthExpr,
                     enterMonthName,
                     enterMonthNumber,
                     enterNFoosFromTodayAgoExpr,
                     enterNth,
                     enterNthWeekdayInMonthMaybeYearExpr,
                     enterNtz,
                     enterParse,
                     enterSecond,
                     enterSingleDateExpr,
                     enterSingleTimeExpr,
                     enterSpecialDate,
                     enterSpecialDateMaybeYearExpr,
                     enterSpecialTime,
                     enterSpecialTimeExpr,
                     enterTddiv,
                     enterTdiv,
                     enterThisNextLast,
                     enterTimeExpr,
                     enterTwelveHourTimeExpr,
                     enterTwentyFourHourTimeExpr,
                     enterTzExpr,
                     enterUnsignedInt,
                     enterYear,
                     enterYearMonthDayExpr,
                     exitAmpm,
                     exitBaseAndOffsetDateExpr,
                     exitBaseAndOffsetTimeExpr,
                     exitBaseDate,
                     exitBaseTime,
                     exitCountUnitsBeforeAfterTimeExpr,
                     exitDateExpr,
                     exitDayMonthMaybeYearExpr,
                     exitDayName,
                     exitDayOfMonth,
                     exitDdiv,
                     exitDeltaBeforeAfter,
                     exitDeltaDateExprRelativeToTodayImplied,
                     exitDeltaNextLast,
                     exitDeltaPlusMinusExpr,
                     exitDeltaPlusMinusTimeExpr,
                     exitDeltaRelativeToTodayExpr,
                     exitDeltaTimeBeforeAfter,
                     exitDeltaTimeFraction,
                     exitDeltaTimeUnit,
                     exitDeltaUnit,
                     exitDtdiv,
                     exitFirstLastWeekdayInMonthMaybeYearExpr,
                     exitFirstOrLast,
                     exitFractionBeforeAfterTimeExpr,
                     exitHour,
                     exitLtz,
                     exitMicros,
                     exitMinute,
                     exitMonthDayMaybeYearExpr,
                     exitMonthExpr,
                     exitMonthName
                     exitMonthName,
                     exitMonthName,
                     exitMonthNumber,
                     exitMonthNumber,
                     exitNFoosFromTodayAgoExpr,
                     exitNextLastUnit,
                     exitNth,
                     exitNthWeekdayInMonthMaybeYearExpr,
                     exitNtz,
                     exitParse,
                     exitSecond,
                     exitSingleDateExpr,
                     exitSingleTimeExpr,
                     exitSpecialDate,
                     exitSpecialDateMaybeYearExpr,
                     exitSpecialTime,
                     exitSpecialTimeExpr,
                     exitTddiv,
                     exitTdiv,
                     exitThisNextLast,
                     exitTimeExpr,
                     exitTwelveHourTimeExpr,
                     exitTwentyFourHourTimeExpr,
                     exitTzExpr,
                     exitUnsignedInt,
                     exitYear,
                     exitYearMonthDayExpr,
                     main,
                     visitErrorNode,
                     visitTerminal

pyutils.datetimez.dateparse\_utilsLexer module
----------------------------------------------

This code is auto-generated by ANTLR from the dateparse\_utils.g4
grammar.

pyutils.datetimez.dateparse\_utilsListener module
-------------------------------------------------

This code is auto-generated by ANTLR from the dateparse\_utils.g4
grammar.

pyutils.datetimez.dateparse\_utilsParser module
-----------------------------------------------

This code is auto-generated by ANTLR from the dateparse\_utils.g4
grammar.

pyutils.datetimez.datetime\_utils module
----------------------------------------

This is a set of utilities for dealing with Python datetimes and
dates.  It supports operations such as checking timezones,
manipulating timezones, easy formatting, and using offsets with
datetimes.

.. automodule:: pyutils.datetimez.datetime_utils
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

This module contains utilities for dealing with Python datetimes.

.. automodule:: pyutils.datetimez
   :members:
   :undoc-members:
   :show-inheritance:
