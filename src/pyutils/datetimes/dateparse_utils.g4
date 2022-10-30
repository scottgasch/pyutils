//  © Copyright 2021-2022, Scott Gasch
//
// antlr4 -Dlanguage=Python3 ./dateparse_utils.g4
//
// Hi, self.  In ANTLR grammars, there are two separate types of symbols: those
// for the lexer and those for the parser.  The former begin with a CAPITAL
// whereas the latter begin with lowercase.  The order of the lexer symbols
// is the order that the lexer will recognize them in.  There's a good tutorial
// on this stuff at:
//
//    https://tomassetti.me/antlr-mega-tutorial/
//
// There are also a zillion premade grammars at:
//
//    https://github.com/antlr/grammars-v4

grammar dateparse_utils;

parse
    : SPACE* dateExpr
    | SPACE* timeExpr
    | SPACE* dateExpr SPACE* dtdiv? SPACE* timeExpr
    | SPACE* timeExpr SPACE* tddiv? SPACE+ dateExpr
    ;

dateExpr
    : singleDateExpr
    | baseAndOffsetDateExpr
    ;

timeExpr
    : singleTimeExpr
    | baseAndOffsetTimeExpr
    ;

singleTimeExpr
    : twentyFourHourTimeExpr
    | twelveHourTimeExpr
    | specialTimeExpr
    ;

twentyFourHourTimeExpr
    : hour ((SPACE|tdiv)+ minute ((SPACE|tdiv)+ second ((SPACE|tdiv)+ micros)? )? )? SPACE* tzExpr?
    ;

twelveHourTimeExpr
    : hour ((SPACE|tdiv)+ minute ((SPACE|tdiv)+ second ((SPACE|tdiv)+ micros)? )? )? SPACE* ampm SPACE* tzExpr?
    ;

ampm: ('a'|'am'|'p'|'pm'|'AM'|'PM'|'A'|'P');

singleDateExpr
    : monthDayMaybeYearExpr
    | dayMonthMaybeYearExpr
    | yearMonthDayExpr
    | specialDateMaybeYearExpr
    | nthWeekdayInMonthMaybeYearExpr
    | firstLastWeekdayInMonthMaybeYearExpr
    | deltaDateExprRelativeToTodayImplied
    | dayName (SPACE|ddiv)+ monthDayMaybeYearExpr (SPACE|ddiv)* singleTimeExpr*
    | dayName
    ;

monthDayMaybeYearExpr
    : monthExpr (SPACE|ddiv)+ dayOfMonth ((SPACE|ddiv)+ year)?
    ;

dayMonthMaybeYearExpr
    : dayOfMonth (SPACE|ddiv)+ monthName ((SPACE|ddiv)+ year)?
    ;

yearMonthDayExpr
    : year (SPACE|ddiv)+ monthExpr (SPACE|ddiv)+ dayOfMonth
    ;

nthWeekdayInMonthMaybeYearExpr
    : nth SPACE+ dayName SPACE+ ('in'|'of') SPACE+ monthName ((ddiv|SPACE)+ year)?
    ;

firstLastWeekdayInMonthMaybeYearExpr
    : firstOrLast SPACE+ dayName (SPACE+ ('in'|'of'))? SPACE+ monthName ((ddiv|SPACE)+ year)?
    ;

specialDateMaybeYearExpr
    : (thisNextLast SPACE+)? specialDate ((SPACE|ddiv)+ year)?
    ;

thisNextLast: (THIS|NEXT|LAST) ;

baseAndOffsetDateExpr
    : baseDate SPACE+ deltaPlusMinusExpr
    | deltaPlusMinusExpr SPACE+ baseDate
    ;

deltaDateExprRelativeToTodayImplied
    : nFoosFromTodayAgoExpr
    | deltaRelativeToTodayExpr
    ;

deltaRelativeToTodayExpr
    : thisNextLast SPACE+ deltaUnit
    ;

nFoosFromTodayAgoExpr
    : unsignedInt SPACE+ deltaUnit SPACE+ AGO_FROM_NOW
    ;

baseDate: singleDateExpr ;

baseAndOffsetTimeExpr
    : deltaPlusMinusTimeExpr SPACE+ baseTime
    | baseTime SPACE+ deltaPlusMinusTimeExpr
    ;

baseTime: singleTimeExpr ;

deltaPlusMinusExpr
    : nth SPACE+ deltaUnit (SPACE+ deltaBeforeAfter)?
    ;

deltaNextLast
    : (NEXT|LAST) ;

deltaPlusMinusTimeExpr
    : countUnitsBeforeAfterTimeExpr
    | fractionBeforeAfterTimeExpr
    ;

countUnitsBeforeAfterTimeExpr
    : nth (SPACE+ deltaTimeUnit)? SPACE+ deltaTimeBeforeAfter
    ;

fractionBeforeAfterTimeExpr
    : deltaTimeFraction SPACE+ deltaTimeBeforeAfter
    ;

deltaUnit: (YEAR|MONTH|WEEK|DAY|WEEKDAY|WORKDAY) ;

deltaTimeUnit: (SECOND|MINUTE|HOUR|WORKDAY) ;

deltaBeforeAfter: (BEFORE|AFTER) ;

deltaTimeBeforeAfter: (BEFORE|AFTER) ;

monthExpr
    : monthName
    | monthNumber
    ;

year: DIGIT DIGIT DIGIT DIGIT ;

specialDate: SPECIAL_DATE ;

dayOfMonth
    : DIGIT DIGIT? ('st'|'ST'|'nd'|'ND'|'rd'|'RD'|'th'|'TH')?
    | KALENDS (SPACE+ 'of')?
    | IDES (SPACE+ 'of')?
    | NONES (SPACE+ 'of')?
    ;

firstOrLast: (FIRST|LAST) ;

nth: (DASH|PLUS)? DIGIT+ ('st'|'ST'|'nd'|'ND'|'rd'|'RD'|'th'|'TH')? ;

unsignedInt: DIGIT+ ;

deltaTimeFraction: DELTA_TIME_FRACTION ;

specialTimeExpr: specialTime (SPACE+ tzExpr)? ;

specialTime: SPECIAL_TIME ;

dayName: WEEKDAY ;

monthName: MONTH_NAME ;

monthNumber: DIGIT DIGIT? ;

hour: DIGIT DIGIT? ;

minute: DIGIT DIGIT ;

second: DIGIT DIGIT ;

micros: DIGIT DIGIT? DIGIT? DIGIT? DIGIT? DIGIT? DIGIT? ;

ddiv: (SLASH|DASH|',') ;

tdiv: (COLON|DOT) ;

dtdiv: ('T'|'t'|'at'|'AT'|','|';') ;

tddiv: ('on'|'ON'|','|';') ;

tzExpr
    : ntz
    | ltz
    ;

ntz: (PLUS|DASH) DIGIT DIGIT COLON? DIGIT DIGIT ;

ltz: UPPERCASE_STRING ;

// ----------------------------------

SPACE: [ \t\r\n] ;

COMMENT: '#' ~[\r\n]* -> skip ;

THE: ('the'|'The') SPACE* -> skip ;

DASH: '-' ;

PLUS: '+' ;

SLASH: '/' ;

DOT: '.' ;

COLON: ':' ;

MONTH_NAME: (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC) ;

JAN : 'jan'
    | 'Jan'
    | 'JAN'
    | 'January'
    | 'january'
    ;

FEB : 'feb'
    | 'Feb'
    | 'FEB'
    | 'February'
    | 'february'
    ;

MAR : 'mar'
    | 'Mar'
    | 'MAR'
    | 'March'
    | 'march'
    ;

APR : 'apr'
    | 'Apr'
    | 'APR'
    | 'April'
    | 'april'
    ;

MAY : 'may'
    | 'May'
    | 'MAY'
    ;

JUN : 'jun'
    | 'Jun'
    | 'JUN'
    | 'June'
    | 'june'
    ;

JUL : 'jul'
    | 'Jul'
    | 'JUL'
    | 'July'
    | 'july'
    ;

AUG : 'aug'
    | 'Aug'
    | 'AUG'
    | 'August'
    | 'august'
    ;

SEP : 'sep'
    | 'Sep'
    | 'SEP'
    | 'sept'
    | 'Sept'
    | 'SEPT'
    | 'September'
    | 'september'
    ;

OCT : 'oct'
    | 'Oct'
    | 'OCT'
    | 'October'
    | 'october'
    ;

NOV : 'nov'
    | 'Nov'
    | 'NOV'
    | 'November'
    | 'november'
    ;

DEC : 'dec'
    | 'Dec'
    | 'DEC'
    | 'December'
    | 'december'
    ;

WEEKDAY: (SUN|MON|TUE|WED|THU|FRI|SAT) ;

SUN : 'sun'
    | 'Sun'
    | 'SUN'
    | 'suns'
    | 'Suns'
    | 'SUNS'
    | 'sunday'
    | 'Sunday'
    | 'sundays'
    | 'Sundays'
    ;

MON : 'mon'
    | 'Mon'
    | 'MON'
    | 'mons'
    | 'Mons'
    | 'MONS'
    | 'monday'
    | 'Monday'
    | 'mondays'
    | 'Mondays'
    ;

TUE : 'tue'
    | 'Tue'
    | 'TUE'
    | 'tues'
    | 'Tues'
    | 'TUES'
    | 'tuesday'
    | 'Tuesday'
    | 'tuesdays'
    | 'Tuesdays'
    ;

WED : 'wed'
    | 'Wed'
    | 'WED'
    | 'weds'
    | 'Weds'
    | 'WEDS'
    | 'wednesday'
    | 'Wednesday'
    | 'wednesdays'
    | 'Wednesdays'
    ;

THU : 'thu'
    | 'Thu'
    | 'THU'
    | 'thur'
    | 'Thur'
    | 'THUR'
    | 'thurs'
    | 'Thurs'
    | 'THURS'
    | 'thursday'
    | 'Thursday'
    | 'thursdays'
    | 'Thursdays'
    ;

FRI : 'fri'
    | 'Fri'
    | 'FRI'
    | 'fris'
    | 'Fris'
    | 'FRIS'
    | 'friday'
    | 'Friday'
    | 'fridays'
    | 'Fridays'
    ;

SAT : 'sat'
    | 'Sat'
    | 'SAT'
    | 'sats'
    | 'Sats'
    | 'SATS'
    | 'saturday'
    | 'Saturday'
    | 'saturdays'
    | 'Saturdays'
    ;

WEEK
    : 'week'
    | 'Week'
    | 'weeks'
    | 'Weeks'
    | 'wks'
    ;

DAY
    : 'day'
    | 'Day'
    | 'days'
    | 'Days'
    ;

HOUR
    : 'hour'
    | 'Hour'
    | 'hours'
    | 'Hours'
    | 'hrs'
    ;

MINUTE
    : 'min'
    | 'Min'
    | 'MIN'
    | 'mins'
    | 'Mins'
    | 'MINS'
    | 'minute'
    | 'Minute'
    | 'minutes'
    | 'Minutes'
    ;

SECOND
    : 'sec'
    | 'Sec'
    | 'SEC'
    | 'secs'
    | 'Secs'
    | 'SECS'
    | 'second'
    | 'Second'
    | 'seconds'
    | 'Seconds'
    ;

MONTH
    : 'month'
    | 'Month'
    | 'months'
    | 'Months'
    ;

YEAR
    : 'year'
    | 'Year'
    | 'years'
    | 'Years'
    | 'yrs'
    ;

SPECIAL_DATE
    : TODAY
    | YESTERDAY
    | TOMORROW
    | NEW_YEARS_EVE
    | NEW_YEARS_DAY
    | MARTIN_LUTHER_KING_DAY
    | PRESIDENTS_DAY
    | EASTER
    | MEMORIAL_DAY
    | INDEPENDENCE_DAY
    | LABOR_DAY
    | COLUMBUS_DAY
    | VETERANS_DAY
    | HALLOWEEN
    | THANKSGIVING_DAY
    | CHRISTMAS_EVE
    | CHRISTMAS
    ;

SPECIAL_TIME
    : NOON
    | MIDNIGHT
    ;

NOON
    : ('noon'|'Noon'|'midday'|'Midday')
    ;

MIDNIGHT
    : ('midnight'|'Midnight')
    ;

// today
TODAY
    : ('today'|'Today'|'now'|'Now')
    ;

// yeste
YESTERDAY
    : ('yesterday'|'Yesterday')
    ;

// tomor
TOMORROW
    : ('tomorrow'|'Tomorrow')
    ;

// easte
EASTER
    : 'easter' SUN?
    | 'Easter' SUN?
    ;

// newye
NEW_YEARS_DAY
    : 'new years'
    | 'New Years'
    | 'new years day'
    | 'New Years Day'
    | 'new year\'s'
    | 'New Year\'s'
    | 'new year\'s day'
    | 'New year\'s Day'
    ;

// newyeeve
NEW_YEARS_EVE
    : 'nye'
    | 'NYE'
    | 'new years eve'
    | 'New Years Eve'
    | 'new year\'s eve'
    | 'New Year\'s Eve'
    ;

// chris
CHRISTMAS
    : 'christmas'
    | 'Christmas'
    | 'christmas day'
    | 'Christmas Day'
    | 'xmas'
    | 'Xmas'
    | 'xmas day'
    | 'Xmas Day'
    ;

// chriseve
CHRISTMAS_EVE
    : 'christmas eve'
    | 'Christmas Eve'
    | 'xmas eve'
    | 'Xmas Eve'
    ;

// mlk
MARTIN_LUTHER_KING_DAY
    : 'martin luther king day'
    | 'Martin Luther King Day'
    | 'mlk day'
    | 'MLK Day'
    | 'MLK day'
    | 'mlk'
    | 'MLK'
    ;

// memor
MEMORIAL_DAY
    : 'memorial'
    | 'Memorial'
    | 'memorial day'
    | 'Memorial Day'
    ;

// indep
INDEPENDENCE_DAY
    : 'independence day'
    | 'Independence day'
    | 'Independence Day'
    ;

// labor
LABOR_DAY
    : 'labor'
    | 'Labor'
    | 'labor day'
    | 'Labor Day'
    ;

// presi
PRESIDENTS_DAY
    : 'presidents\' day'
    | 'president\'s day'
    | 'presidents day'
    | 'presidents'
    | 'president\'s'
    | 'presidents\''
    | 'Presidents\' Day'
    | 'President\'s Day'
    | 'Presidents Day'
    | 'Presidents'
    | 'President\'s'
    | 'Presidents\''
    ;

// colum
COLUMBUS_DAY
    : 'columbus'
    | 'columbus day'
    | 'indiginous peoples day'
    | 'indiginous peoples\' day'
    | 'Columbus'
    | 'Columbus Day'
    | 'Indiginous Peoples Day'
    | 'Indiginous Peoples\' Day'
    ;

// veter
VETERANS_DAY
    : 'veterans'
    | 'veterans day'
    | 'veterans\' day'
    | 'Veterans'
    | 'Veterans Day'
    | 'Veterans\' Day'
    ;

// hallo
HALLOWEEN
    : 'halloween'
    | 'Halloween'
    ;

// thank
THANKSGIVING_DAY
    : 'thanksgiving'
    | 'thanksgiving day'
    | 'Thanksgiving'
    | 'Thanksgiving Day'
    ;

FIRST: ('first'|'First') ;

LAST: ('last'|'Last'|'this past') ;

THIS: ('this'|'This'|'this coming') ;

NEXT: ('next'|'Next') ;

AGO_FROM_NOW: (AGO|FROM_NOW) ;

AGO: ('ago'|'Ago'|'back'|'Back') ;

FROM_NOW: ('from now'|'From Now') ;

BEFORE: ('to'|'To'|'before'|'Before'|'til'|'until'|'Until') ;

AFTER: ('after'|'After'|'from'|'From'|'past'|'Past') ;

DELTA_TIME_FRACTION: ('quarter'|'Quarter'|'half'|'Half') ;

DIGIT: ('0'..'9') ;

IDES: ('ides'|'Ides') ;

NONES: ('nones'|'Nones') ;

KALENDS: ('kalends'|'Kalends') ;

WORKDAY
    : 'workday'
    | 'workdays'
    | 'work days'
    | 'working days'
    | 'Workday'
    | 'Workdays'
    | 'Work Days'
    | 'Working Days'
    ;

UPPERCASE_STRING: [A-Z]+ ;
