#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# © Copyright 2021-2022, Scott Gasch

"""Utilities related to logging.  To use it you must invoke
:meth:`initialize_logging`.  If you use the
:meth:`bootstrap.initialize` decorator on your program's entry point,
it will call this for you.  See :meth:`python_modules.bootstrap.initialize`
for more details.  If you use this you get:

* Ability to set logging level,
* ability to define the logging format,
* ability to tee all logging on stderr,
* ability to tee all logging into a file,
* ability to rotate said file as it grows,
* ability to tee all logging into the system log (syslog) and
  define the facility and level used to do so,
* easy automatic pid/tid stamp on logging for debugging threads,
* ability to squelch repeated log messages,
* ability to log probabilistically in code,
* ability to only see log messages from a particular module or
  function,
* ability to clear logging handlers added by earlier loaded modules.

All of these are controlled via commandline arguments to your program,
see the code below for details.
"""

import collections
import contextlib
import datetime
import enum
import io
import logging
import os
import random
import sys
from logging.config import fileConfig
from logging.handlers import RotatingFileHandler, SysLogHandler
from typing import Any, Callable, Dict, Iterable, List, Optional

import pytz
from overrides import overrides

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.
from pyutils import argparse_utils, config

cfg = config.add_commandline_args(f'Logging ({__file__})', 'Args related to logging')
cfg.add_argument(
    '--logging_config_file',
    type=argparse_utils.valid_filename,
    default=None,
    metavar='FILENAME',
    help='Config file containing the logging setup, see: https://docs.python.org/3/howto/logging.html#logging-advanced-tutorial',
)
cfg.add_argument(
    '--logging_level',
    type=str,
    default='INFO',
    choices=['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    metavar='LEVEL',
    help='The global default level below which to squelch log messages; see also --lmodule',
)
cfg.add_argument(
    '--logging_format',
    type=str,
    default=None,
    help='The format for lines logged via the logger module.  See: https://docs.python.org/3/library/logging.html#formatter-objects',
)
cfg.add_argument(
    '--logging_date_format',
    type=str,
    default='%Y/%m/%dT%H:%M:%S.%f%z',
    metavar='DATEFMT',
    help='The format of any dates in --logging_format.',
)
cfg.add_argument(
    '--logging_console',
    action=argparse_utils.ActionNoYes,
    default=True,
    help='Should we log to the console (stderr)',
)
cfg.add_argument(
    '--logging_filename',
    type=str,
    default=None,
    metavar='FILENAME',
    help='The filename of the logfile to write.',
)
cfg.add_argument(
    '--logging_filename_maxsize',
    type=int,
    default=(1024 * 1024),
    metavar='#BYTES',
    help='The maximum size (in bytes) to write to the logging_filename.',
)
cfg.add_argument(
    '--logging_filename_count',
    type=int,
    default=7,
    metavar='COUNT',
    help='The number of logging_filename copies to keep before deleting.',
)
cfg.add_argument(
    '--logging_syslog',
    action=argparse_utils.ActionNoYes,
    default=False,
    help='Should we log to localhost\'s syslog.',
)
cfg.add_argument(
    '--logging_syslog_facility',
    type=str,
    default='USER',
    choices=[
        'NOTSET',
        'AUTH',
        'AUTH_PRIV',
        'CRON',
        'DAEMON',
        'FTP',
        'KERN',
        'LPR',
        'MAIL',
        'NEWS',
        'SYSLOG',
        'USER',
        'UUCP',
        'LOCAL0',
        'LOCAL1',
        'LOCAL2',
        'LOCAL3',
        'LOCAL4',
        'LOCAL5',
        'LOCAL6',
        'LOCAL7',
    ],
    metavar='SYSLOG_FACILITY_LIST',
    help='The default syslog message facility identifier',
)
cfg.add_argument(
    '--logging_debug_threads',
    action=argparse_utils.ActionNoYes,
    default=False,
    help='Should we prepend pid/tid data to all log messages?',
)
cfg.add_argument(
    '--logging_debug_modules',
    action=argparse_utils.ActionNoYes,
    default=False,
    help='Should we prepend module/function data to all log messages?',
)
cfg.add_argument(
    '--logging_info_is_print',
    action=argparse_utils.ActionNoYes,
    default=False,
    help='logging.info also prints to stdout.',
)
cfg.add_argument(
    '--logging_squelch_repeats',
    action=argparse_utils.ActionNoYes,
    default=True,
    help='Do we allow code to indicate that it wants to squelch repeated logging messages or should we always log?',
)
cfg.add_argument(
    '--logging_probabilistically',
    action=argparse_utils.ActionNoYes,
    default=True,
    help='Do we allow probabilistic logging (for code that wants it) or should we always log?',
)
# See also: OutputMultiplexer
cfg.add_argument(
    '--logging_captures_prints',
    action=argparse_utils.ActionNoYes,
    default=False,
    help='When calling print, also log.info automatically.',
)
cfg.add_argument(
    '--lmodule',
    type=str,
    metavar='<SCOPE>=<LEVEL>[,<SCOPE>=<LEVEL>...]',
    help=(
        'Allows per-scope logging levels which override the global level set with --logging-level.'
        + 'Pass a space separated list of <scope>=<level> where <scope> is one of: module, '
        + 'module:function, or :function and <level> is a logging level (e.g. INFO, DEBUG...)'
    ),
)
cfg.add_argument(
    '--logging_clear_preexisting_handlers',
    action=argparse_utils.ActionNoYes,
    default=True,
    help=(
        'Should logging code clear preexisting global logging handlers and thus insist that is '
        + 'alone can add handlers.  Use this to work around annoying modules that insert global '
        + 'handlers with formats and logging levels you might now want.  Caveat emptor, this may '
        + 'cause you to miss logging messages.'
    ),
)

BUILT_IN_PRINT = print
LOGGING_INITIALIZED = False


# A map from logging_callsite_id -> count of logged messages.
squelched_logging_counts: Dict[str, int] = {}


def squelch_repeated_log_messages(squelch_after_n_repeats: int) -> Callable:
    """
    A decorator that marks a function as interested in having the logging
    messages that it produces be squelched (ignored) after it logs the
    same message more than N times.

    .. note::

        This decorator affects *ALL* logging messages produced
        within the decorated function.  That said, messages must be
        identical in order to be squelched.  For example, if the same line
        of code produces different messages (because of, e.g., a format
        string), the messages are considered to be different.

    """

    def squelch_logging_wrapper(f: Callable):
        from pyutils import function_utils

        identifier = function_utils.function_identifier(f)
        squelched_logging_counts[identifier] = squelch_after_n_repeats
        return f

    return squelch_logging_wrapper


class SquelchRepeatedMessagesFilter(logging.Filter):
    """A filter that only logs messages from a given site with the same
    (exact) message at the same logging level N times and ignores
    subsequent attempts to log.

    This filter only affects logging messages that repeat more than a
    threshold number of times from functions that are tagged with the
    @logging_utils.squelched_logging_ok decorator (see above); others
    are ignored.

    This functionality is enabled by default but can be disabled via
    the :code:`--no_logging_squelch_repeats` commandline flag.
    """

    def __init__(self) -> None:
        super().__init__()
        self.counters: collections.Counter = collections.Counter()

    @overrides
    def filter(self, record: logging.LogRecord) -> bool:
        id1 = f'{record.module}:{record.funcName}'
        if id1 not in squelched_logging_counts:
            return True
        threshold = squelched_logging_counts[id1]
        logsite = f'{record.pathname}+{record.lineno}+{record.levelno}+{record.msg}'
        count = self.counters[logsite]
        self.counters[logsite] += 1
        return count < threshold


class DynamicPerScopeLoggingLevelFilter(logging.Filter):
    """This filter only allows logging messages from an allow list of
    module names or module:function names.  Blocks all others.
    """

    @staticmethod
    def level_name_to_level(name: str) -> int:
        numeric_level = getattr(logging, name, None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid level: {name}')
        return numeric_level

    def __init__(
        self,
        default_logging_level: int,
        per_scope_logging_levels: str,
    ) -> None:
        super().__init__()
        self.valid_levels = set(
            ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        )
        self.default_logging_level = default_logging_level
        self.level_by_scope = {}
        if per_scope_logging_levels is not None:
            for chunk in per_scope_logging_levels.split(','):
                if '=' not in chunk:
                    print(
                        f'Malformed lmodule directive: "{chunk}", missing "=".  Ignored.',
                        file=sys.stderr,
                    )
                    continue
                try:
                    (scope, level) = chunk.split('=')
                except ValueError:
                    print(
                        f'Malformed lmodule directive: "{chunk}".  Ignored.',
                        file=sys.stderr,
                    )
                    continue
                scope = scope.strip()
                level = level.strip().upper()
                if level not in self.valid_levels:
                    print(
                        f'Malformed lmodule directive: "{chunk}", bad level.  Ignored.',
                        file=sys.stderr,
                    )
                    continue
                self.level_by_scope[
                    scope
                ] = DynamicPerScopeLoggingLevelFilter.level_name_to_level(level)

    @overrides
    def filter(self, record: logging.LogRecord) -> bool:
        """Decides whether or not to log based on an allow list."""

        # First try to find a logging level by scope (--lmodule)
        if len(self.level_by_scope) > 0:
            min_level = None
            for scope in (
                record.module,
                f'{record.module}:{record.funcName}',
                f':{record.funcName}',
            ):
                level = self.level_by_scope.get(scope, None)
                if level is not None:
                    if min_level is None or level < min_level:
                        min_level = level

            # If we found one, use it instead of the global default level.
            if min_level is not None:
                return record.levelno >= min_level

        # Otherwise, use the global logging level (--logging_level)
        return record.levelno >= self.default_logging_level


# A map from function_identifier -> probability of logging (0.0%..100.0%)
probabilistic_logging_levels: Dict[str, float] = {}


def logging_is_probabilistic(probability_of_logging: float) -> Callable:
    """A decorator that indicates that all logging statements within the
    scope of a particular (marked) function are not deterministic
    (i.e. they do not always unconditionally log) but rather are
    probabilistic (i.e. they log N% of the time, randomly).

    .. note::
        This affects *ALL* logging statements within the marked function.

    That this functionality can be disabled (forcing all logged
    messages to produce output) via the
    :code:`--no_logging_probabilistically` cmdline argument.
    """

    def probabilistic_logging_wrapper(f: Callable):
        from pyutils import function_utils

        identifier = function_utils.function_identifier(f)
        probabilistic_logging_levels[identifier] = probability_of_logging
        return f

    return probabilistic_logging_wrapper


class ProbabilisticFilter(logging.Filter):
    """
    A filter that logs messages probabilistically (i.e. randomly at some
    percent chance).

    This filter only affects logging messages from functions that have
    been tagged with the @logging_utils.probabilistic_logging decorator.
    """

    @overrides
    def filter(self, record: logging.LogRecord) -> bool:
        id1 = f'{record.module}:{record.funcName}'
        if id1 not in probabilistic_logging_levels:
            return True
        threshold = probabilistic_logging_levels[id1]
        return (random.random() * 100.0) <= threshold


class OnlyInfoFilter(logging.Filter):
    """A filter that only logs messages produced at the INFO logging
    level.  This is used by the ::code`--logging_info_is_print`
    commandline option to select a subset of the logging stream to
    send to a stdout handler.
    """

    @overrides
    def filter(self, record: logging.LogRecord):
        return record.levelno == logging.INFO


class MillisecondAwareFormatter(logging.Formatter):
    """
    A formatter for adding milliseconds to log messages which, for
    whatever reason, the default python logger doesn't do.
    """

    converter = datetime.datetime.fromtimestamp  # type: ignore

    @overrides
    def formatTime(self, record, datefmt=None):
        ct = MillisecondAwareFormatter.converter(
            record.created, pytz.timezone("US/Pacific")
        )
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime("%Y-%m-%d %H:%M:%S")
            s = f"{t},{record.msecs:%03d}"
        return s


def log_about_logging(
    logger,
    default_logging_level,
    preexisting_handlers_count,
    fmt,
    facility_name,
):
    """Some of the initial messages in the debug log are about how we
    have set up logging itself."""

    level_name = logging._levelToName.get(
        default_logging_level, str(default_logging_level)
    )
    logger.debug('Initialized global logging; default logging level is %s.', level_name)
    if (
        config.config['logging_clear_preexisting_handlers']
        and preexisting_handlers_count > 0
    ):
        logger.debug(
            'Logging cleared %d global handlers (--logging_clear_preexisting_handlers)',
            preexisting_handlers_count,
        )
    logger.debug('Logging format specification is "%s"', fmt)
    if config.config['logging_debug_threads']:
        logger.debug(
            '...Logging format spec captures tid/pid. (--logging_debug_threads)'
        )
    if config.config['logging_debug_modules']:
        logger.debug(
            '...Logging format spec captures files/functions/lineno. (--logging_debug_modules)'
        )
    if config.config['logging_syslog']:
        logger.debug(
            'Logging to syslog as %s with priority mapping based on level. (--logging_syslog)',
            facility_name,
        )
    if config.config['logging_filename']:
        logger.debug(
            'Logging to file "%s". (--logging_filename)',
            config.config["logging_filename"],
        )
        logger.debug(
            '...with %d bytes max file size. (--logging_filename_maxsize)',
            config.config["logging_filename_maxsize"],
        )
        logger.debug(
            '...and %d rotating backup file count. (--logging_filename_count)',
            config.config["logging_filename_count"],
        )
    if config.config['logging_console']:
        logger.debug('Logging to the console (stderr). (--logging_console)')
    if config.config['logging_info_is_print']:
        logger.debug(
            'Logging logger.info messages will be repeated on stdout. (--logging_info_is_print)'
        )
    if config.config['logging_squelch_repeats']:
        logger.debug(
            'Logging code allowed to request repeated messages be squelched. (--logging_squelch_repeats)'
        )
    else:
        logger.debug(
            'Logging code forbidden to request messages be squelched; all messages logged. (--no_logging_squelch_repeats)'
        )
    if config.config['logging_probabilistically']:
        logger.debug(
            'Logging code is allowed to request probabilistic logging. (--logging_probabilistically)'
        )
    else:
        logger.debug(
            'Logging code is forbidden to request probabilistic logging; messages always logged. (--no_logging_probabilistically)'
        )
    if config.config['lmodule']:
        logger.debug(
            f'Logging dynamic per-module logging enabled. (--lmodule={config.config["lmodule"]})'
        )
    if config.config['logging_captures_prints']:
        logger.debug(
            'Logging will capture printed data as logger.info messages. (--logging_captures_prints)'
        )


def initialize_logging(logger=None) -> logging.Logger:
    """Initialize logging for the program.  This must be called if you want
    to use any of the functionality provided by this module such as:

    * Ability to set logging level,
    * ability to define the logging format,
    * ability to tee all logging on stderr,
    * ability to tee all logging into a file,
    * ability to rotate said file as it grows,
    * ability to tee all logging into the system log (syslog) and
      define the facility and level used to do so,
    * easy automatic pid/tid stamp on logging for debugging threads,
    * ability to squelch repeated log messages,
    * ability to log probabilistically in code,
    * ability to only see log messages from a particular module or
      function,
    * ability to clear logging handlers added by earlier loaded modules.

    All of these are controlled via commandline arguments to your program,
    see the code below for details.

    If you use the
    :meth:`bootstrap.initialize` decorator on your program's entry point,
    it will call this for you.  See :meth:`python_modules.bootstrap.initialize`
    for more details.
    """
    global LOGGING_INITIALIZED
    if LOGGING_INITIALIZED:
        return logging.getLogger()
    LOGGING_INITIALIZED = True

    if logger is None:
        logger = logging.getLogger()

    # --logging_clear_preexisting_handlers removes logging handlers
    # that were registered by global statements during imported module
    # setup.
    preexisting_handlers_count = 0
    assert config.has_been_parsed()
    if config.config['logging_clear_preexisting_handlers']:
        while logger.hasHandlers():
            logger.removeHandler(logger.handlers[0])
            preexisting_handlers_count += 1

    # --logging_config_file pulls logging settings from a config file
    # skipping the rest of this setup.
    if config.config['logging_config_file'] is not None:
        fileConfig(config.config['logging_config_file'])
        return logger

    handlers: List[logging.Handler] = []
    handler: Optional[logging.Handler] = None

    # Global default logging level (--logging_level); messages below
    # this level will be silenced.
    default_logging_level = getattr(
        logging, config.config['logging_level'].upper(), None
    )
    if not isinstance(default_logging_level, int):
        raise ValueError(f'Invalid level: {config.config["logging_level"]}')

    # Custom or default --logging_format?
    if config.config['logging_format']:
        fmt = config.config['logging_format']
    else:
        if config.config['logging_syslog']:
            fmt = '%(levelname).1s:%(filename)s[%(process)d]: %(message)s'
        else:
            fmt = '%(levelname).1s:%(asctime)s: %(message)s'

    # --logging_debug_threads and --logging_debug_modules both affect
    # the format by prepending information about the pid/tid or
    # file/function.
    if config.config['logging_debug_threads']:
        fmt = f'%(process)d.%(thread)d|{fmt}'
    if config.config['logging_debug_modules']:
        fmt = f'%(filename)s:%(funcName)s:%(lineno)s|{fmt}'

    # --logging_syslog (optionally with --logging_syslog_facility)
    # sets up for logging to use the standard system syslogd as a
    # sink.
    facility_name = None
    if config.config['logging_syslog']:
        if sys.platform not in ('win32', 'cygwin'):
            if config.config['logging_syslog_facility']:
                facility_name = 'LOG_' + config.config['logging_syslog_facility']
            facility = SysLogHandler.__dict__.get(facility_name, SysLogHandler.LOG_USER)  # type: ignore
            assert facility is not None
            handler = SysLogHandler(facility=facility, address='/dev/log')
            handler.setFormatter(
                MillisecondAwareFormatter(
                    fmt=fmt,
                    datefmt=config.config['logging_date_format'],
                )
            )
            handlers.append(handler)

    # --logging_filename (with friends --logging_filename_count and
    # --logging_filename_maxsize) set up logging to a file on the
    # filesystem with automatic rotation when it gets too big.
    if config.config['logging_filename']:
        handler = RotatingFileHandler(
            config.config['logging_filename'],
            maxBytes=config.config['logging_filename_maxsize'],
            backupCount=config.config['logging_filename_count'],
        )
        handler.setFormatter(
            MillisecondAwareFormatter(
                fmt=fmt,
                datefmt=config.config['logging_date_format'],
            )
        )
        handlers.append(handler)

    # --logging_console is, ahem, logging to the console.
    if config.config['logging_console']:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            MillisecondAwareFormatter(
                fmt=fmt,
                datefmt=config.config['logging_date_format'],
            )
        )
        handlers.append(handler)

    if len(handlers) == 0:
        handlers.append(logging.NullHandler())
    for handler in handlers:
        logger.addHandler(handler)

    # --logging_info_is_print echoes any message to logger.info(x) as
    # a print statement on stdout.
    if config.config['logging_info_is_print']:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(OnlyInfoFilter())
        logger.addHandler(handler)

    # --logging_squelch_repeats allows code to request repeat logging
    # messages (identical log site and message contents) to be
    # silenced.  Logging code must request this explicitly, it isn't
    # automatic.  This option just allows the silencing to happen.
    if config.config['logging_squelch_repeats']:
        for handler in handlers:
            handler.addFilter(SquelchRepeatedMessagesFilter())

    # --logging_probabilistically allows code to request
    # non-deterministic logging where messages have some probability
    # of being produced.  Logging code must request this explicitly.
    # This option just allows the non-deterministic behavior to
    # happen.  Disabling it will cause every log message to be
    # produced.
    if config.config['logging_probabilistically']:
        for handler in handlers:
            handler.addFilter(ProbabilisticFilter())

    # --lmodule is a way to have a special logging level for just on
    # module or one set of modules that is different than the one set
    # globally via --logging_level.
    for handler in handlers:
        handler.addFilter(
            DynamicPerScopeLoggingLevelFilter(
                default_logging_level,
                config.config['lmodule'],
            )
        )
    logger.setLevel(0)
    logger.propagate = False

    # --logging_captures_prints, if set, will capture and log.info
    # anything printed on stdout.
    if config.config['logging_captures_prints']:
        import builtins

        def print_and_also_log(*arg, **kwarg):
            f = kwarg.get('file', None)
            if f == sys.stderr:
                logger.warning(*arg)
            else:
                logger.info(*arg)
            BUILT_IN_PRINT(*arg, **kwarg)

        builtins.print = print_and_also_log

    # At this point the logger is ready, handlers are set up,
    # etc... so log about the logging configuration.
    log_about_logging(
        logger,
        default_logging_level,
        preexisting_handlers_count,
        fmt,
        facility_name,
    )
    return logger


def get_logger(name: str = ""):
    """Get the global logger"""
    logger = logging.getLogger(name)
    return initialize_logging(logger)


def tprint(*args, **kwargs) -> None:
    """Legacy function for printing a message augmented with thread id
    still needed by some code.  Please use --logging_debug_threads in
    new code.
    """
    if config.config['logging_debug_threads']:
        from pyutils.parallelize.thread_utils import current_thread_id

        print(f'{current_thread_id()}', end="")
        print(*args, **kwargs)
    else:
        pass


def dprint(*args, **kwargs) -> None:
    """Legacy function used to print to stderr still needed by some code.
    Please just use normal logging with --logging_console which
    accomplishes the same thing in new code.
    """
    print(*args, file=sys.stderr, **kwargs)


class OutputMultiplexer(object):
    """A class that broadcasts printed messages to several sinks
    (including various logging levels, different files, different file
    handles, the house log, etc...).  See also
    :class:`OutputMultiplexerContext` for an easy usage pattern.
    """

    class Destination(enum.IntEnum):
        """Bits in the destination_bitv bitvector.  Used to indicate the
        output destination."""

        # fmt: off
        LOG_DEBUG = 0x01     #  ⎫
        LOG_INFO = 0x02      #  ⎪
        LOG_WARNING = 0x04   #  ⎬ Must provide logger to the c'tor.
        LOG_ERROR = 0x08     #  ⎪
        LOG_CRITICAL = 0x10  #  ⎭
        FILENAMES = 0x20     # Must provide a filename to the c'tor.
        FILEHANDLES = 0x40   # Must provide a handle to the c'tor.
        HLOG = 0x80
        ALL_LOG_DESTINATIONS = (
            LOG_DEBUG | LOG_INFO | LOG_WARNING | LOG_ERROR | LOG_CRITICAL
        )
        ALL_OUTPUT_DESTINATIONS = 0x8F
        # fmt: on

    def __init__(
        self,
        destination_bitv: int,
        *,
        logger=None,
        filenames: Optional[Iterable[str]] = None,
        handles: Optional[Iterable[io.TextIOWrapper]] = None,
    ):
        """
        Constructs the OutputMultiplexer instance.

        Args:
            destination_bitv: a bitvector where each bit represents an
                output destination.  Multiple bits may be set.
            logger: if LOG_* bits are set, you must pass a logger here.
            filenames: if FILENAMES bit is set, this should be a list of
                files you'd like to output into.  This code handles opening
                and closing said files.
            handles: if FILEHANDLES bit is set, this should be a list of
                already opened filehandles you'd like to output into.  The
                handles will remain open after the scope of the multiplexer.
        """
        if logger is None:
            logger = logging.getLogger(None)
        self.logger = logger

        self.f: Optional[List[Any]] = None
        if filenames is not None:
            self.f = [open(filename, 'wb', buffering=0) for filename in filenames]
        else:
            if destination_bitv & OutputMultiplexer.Destination.FILENAMES:
                raise ValueError("Filenames argument is required if bitv & FILENAMES")
            self.f = None

        self.h: Optional[List[Any]] = None
        if handles is not None:
            self.h = list(handles)
        else:
            if destination_bitv & OutputMultiplexer.Destination.FILEHANDLES:
                raise ValueError("Handle argument is required if bitv & FILEHANDLES")
            self.h = None

        self.set_destination_bitv(destination_bitv)

    def get_destination_bitv(self):
        """Where are we outputting?"""
        return self.destination_bitv

    def set_destination_bitv(self, destination_bitv: int):
        """Change the output destination_bitv to the one provided."""
        if destination_bitv & self.Destination.FILENAMES and self.f is None:
            raise ValueError("Filename argument is required if bitv & FILENAMES")
        if destination_bitv & self.Destination.FILEHANDLES and self.h is None:
            raise ValueError("Handle argument is required if bitv & FILEHANDLES")
        self.destination_bitv = destination_bitv

    def print(self, *args, **kwargs):
        """Produce some output to all sinks."""
        from pyutils.string_utils import sprintf, strip_escape_sequences

        end = kwargs.pop("end", None)
        if end is not None:
            if not isinstance(end, str):
                raise TypeError("end must be None or a string")
        sep = kwargs.pop("sep", None)
        if sep is not None:
            if not isinstance(sep, str):
                raise TypeError("sep must be None or a string")
        if kwargs:
            raise TypeError("invalid keyword arguments to print()")
        buf = sprintf(*args, end="", sep=sep)
        if sep is None:
            sep = " "
        if end is None:
            end = "\n"
        if end == '\n':
            buf += '\n'
        if self.destination_bitv & self.Destination.FILENAMES and self.f is not None:
            for _ in self.f:
                _.write(buf.encode('utf-8'))
                _.flush()

        if self.destination_bitv & self.Destination.FILEHANDLES and self.h is not None:
            for _ in self.h:
                _.write(buf)
                _.flush()

        buf = strip_escape_sequences(buf)
        if self.logger is not None:
            if self.destination_bitv & self.Destination.LOG_DEBUG:
                self.logger.debug(buf)
            if self.destination_bitv & self.Destination.LOG_INFO:
                self.logger.info(buf)
            if self.destination_bitv & self.Destination.LOG_WARNING:
                self.logger.warning(buf)
            if self.destination_bitv & self.Destination.LOG_ERROR:
                self.logger.error(buf)
            if self.destination_bitv & self.Destination.LOG_CRITICAL:
                self.logger.critical(buf)
        if self.destination_bitv & self.Destination.HLOG:
            hlog(buf)

    def close(self):
        """Close all open files."""
        if self.f is not None:
            for _ in self.f:
                _.close()


class OutputMultiplexerContext(OutputMultiplexer, contextlib.ContextDecorator):
    """
    A context that uses an :class:`OutputMultiplexer`.  e.g.::

        with OutputMultiplexerContext(
                OutputMultiplexer.LOG_INFO |
                OutputMultiplexer.LOG_DEBUG |
                OutputMultiplexer.FILENAMES |
                OutputMultiplexer.FILEHANDLES,
                filenames = [ '/tmp/foo.log', '/var/log/bar.log' ],
                handles = [ f, g ]
            ) as mplex:
                mplex.print("This is a log message!")
    """

    def __init__(
        self,
        destination_bitv: OutputMultiplexer.Destination,
        *,
        logger=None,
        filenames=None,
        handles=None,
    ):
        super().__init__(
            destination_bitv,
            logger=logger,
            filenames=filenames,
            handles=handles,
        )

    def __enter__(self):
        return self

    def __exit__(self, etype, value, traceback) -> bool:
        super().close()
        if etype is not None:
            return False
        return True


def hlog(message: str) -> None:
    """Write a message to the house log (syslog facility local7 priority
    info) by calling /usr/bin/logger.  This is pretty hacky but used
    by a bunch of code.  Another way to do this would be to use
    :code:`--logging_syslog` and :code:`--logging_syslog_facility` but
    I can't actually say that's easier.
    """
    message = message.replace("'", "'\"'\"'")
    os.system(f"/usr/bin/logger -p local7.info -- '{message}'")


if __name__ == '__main__':
    import doctest

    doctest.testmod()
