#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# © Copyright 2021-2023, Scott Gasch

"""
This is a module that offers an opinionated take on how whole program
logging should be initialized and controlled.  It uses the standard
Python :mod:`logging` but gives you control, via commandline config,
to do things such as:

    * Set the logging default level (debug, info, warning, error, critical)
      of the whole program (see: :code:`--logging_level`)... and to override
      the logging level for individual modules/functions based on their names
      (see :code:`--lmodule`),
    * define the logging message format (see :code:`--logging_format` and
      :code:`--logging_date_format`) including easily adding a PID/TID
      marker on all messages to help with multithreaded debugging
      (:code:`--logging_debug_threads`) and force module names of code
      that emits log messages to be included in the format
      (:code:`--logging_debug_modules`),
    * control the destination of logged messages:

        - log to the console/stderr (:code:`--logging_console`) and/or
        - log to a rotated file (:code:`--logging_filename`,
          :code:`--logging_filename_maxsize` and :code:`--logging_filename_count`)
          and/or
        - log to the UNIX syslog (:code:`--logging_syslog` and
          :code:`--logging_syslog_facility`)

    * optionally squelch repeated messages (:code:`--logging_squelch_repeats`),
    * optionally log probalistically (:code:`--logging_probabilistically`),
    * capture printed messages into the info log (:code:`--logging_captures_prints`),
    * and optionally clear unwanted logging handlers added by other imports
      before this one (:code:`--logging_clear_preexisting_handlers`).

To use this functionality, call :meth:`initialize_logging` early
in your program entry point.  If you use the
:meth:`pyutils.bootstrap.initialize` decorator on your program's entry
point, it will call this for you automatically.
"""

import collections
import contextlib
import datetime
import enum
import io
import logging
import os
import sys
from logging.config import fileConfig
from logging.handlers import RotatingFileHandler, SysLogHandler
from typing import Any, Callable, Dict, Iterable, List, Optional

import pytz
from overrides import overrides

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.
from pyutils import argparse_utils, config, misc_utils

cfg = config.add_commandline_args(f"Logging ({__file__})", "Args related to logging")
cfg.add_argument(
    "--logging_config_file",
    type=argparse_utils.valid_filename,
    default=None,
    metavar="FILENAME",
    help="Config file containing the logging setup, see: https://docs.python.org/3/howto/logging.html#logging-advanced-tutorial",
)
cfg.add_argument(
    "--logging_level",
    type=str,
    default="INFO",
    choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    metavar="LEVEL",
    help="The global default level below which to squelch log messages; see also --lmodule",
)
cfg.add_argument(
    "--logging_format",
    type=str,
    default=None,
    help="The format for lines logged via the logger module.  See: https://docs.python.org/3/library/logging.html#formatter-objects",
)
cfg.add_argument(
    "--logging_date_format",
    type=str,
    default="%Y/%m/%dT%H:%M:%S.%f%z",
    metavar="DATEFMT",
    help="The format of any dates in --logging_format.",
)
cfg.add_argument(
    "--logging_console",
    action=argparse_utils.ActionNoYes,
    default=True,
    help="Should we log to the console (stderr)",
)
cfg.add_argument(
    "--logging_filename",
    type=str,
    default=None,
    metavar="FILENAME",
    help="The filename of the logfile to write.",
)
cfg.add_argument(
    "--logging_filename_maxsize",
    type=int,
    default=(1024 * 1024),
    metavar="#BYTES",
    help="The maximum size (in bytes) to write to the logging_filename.",
)
cfg.add_argument(
    "--logging_filename_count",
    type=int,
    default=7,
    metavar="COUNT",
    help="The number of logging_filename copies to keep before deleting.",
)
cfg.add_argument(
    "--logging_syslog",
    action=argparse_utils.ActionNoYes,
    default=False,
    help="Should we log to localhost's syslog.",
)
cfg.add_argument(
    "--logging_syslog_facility",
    type=str,
    default="USER",
    choices=[
        "NOTSET",
        "AUTH",
        "AUTH_PRIV",
        "CRON",
        "DAEMON",
        "FTP",
        "KERN",
        "LPR",
        "MAIL",
        "NEWS",
        "SYSLOG",
        "USER",
        "UUCP",
        "LOCAL0",
        "LOCAL1",
        "LOCAL2",
        "LOCAL3",
        "LOCAL4",
        "LOCAL5",
        "LOCAL6",
        "LOCAL7",
    ],
    metavar="SYSLOG_FACILITY_LIST",
    help="The default syslog message facility identifier",
)
cfg.add_argument(
    "--logging_debug_threads",
    action=argparse_utils.ActionNoYes,
    default=False,
    help="Should we prepend pid/tid data to all log messages?",
)
cfg.add_argument(
    "--logging_debug_modules",
    action=argparse_utils.ActionNoYes,
    default=False,
    help="Should we prepend module/function data to all log messages?",
)
cfg.add_argument(
    "--logging_info_is_print",
    action=argparse_utils.ActionNoYes,
    default=False,
    help="logging.info also prints to stdout.",
)
cfg.add_argument(
    "--logging_squelch_repeats",
    action=argparse_utils.ActionNoYes,
    default=True,
    help="Do we allow code to indicate that it wants to squelch repeated logging messages or should we always log?",
)
cfg.add_argument(
    "--logging_probabilistically",
    action=argparse_utils.ActionNoYes,
    default=True,
    help="Do we allow probabilistic logging (for code that wants it) or should we always log?",
)
# See also: OutputMultiplexer
cfg.add_argument(
    "--logging_captures_prints",
    action=argparse_utils.ActionNoYes,
    default=False,
    help="When calling print, also log.info automatically.",
)
cfg.add_argument(
    "--lmodule",
    type=str,
    metavar="<SCOPE>=<LEVEL>[,<SCOPE>=<LEVEL>...]",
    help=(
        "Allows per-scope logging levels which override the global level set with --logging-level."
        + "Pass a space separated list of <scope>=<level> where <scope> is one of: module, "
        + "module:function, or :function and <level> is a logging level (e.g. INFO, DEBUG...)"
    ),
)
cfg.add_argument(
    "--logging_clear_preexisting_handlers",
    action=argparse_utils.ActionNoYes,
    default=True,
    help=(
        "Should logging code clear preexisting global logging handlers and thus insist that is "
        + "alone can add handlers.  Use this to work around annoying modules that insert global "
        + "handlers with formats and logging levels you might now want.  Caveat emptor, this may "
        + "cause you to miss logging messages."
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

    An example of this from the pyutils code itself can be found in
    :meth:`pyutils.ansi.fg` and :meth:`pyutils.ansi.bg` methods::

        @logging_utils.squelch_repeated_log_messages(1)
        def fg(
            name: Optional[str] = "",
            red: Optional[int] = None,
            green: Optional[int] = None,
            blue: Optional[int] = None,
            *,
            force_16color: bool = False,
            force_216color: bool = False,
        ) -> str:
            ...

    These methods log stuff like "Using 24-bit color strategy" which
    gets old really fast and fills up the logs.  By decorating the methods
    with :code:`@logging_utils.squelch_repeated_log_messages(1)` the code
    is requesting that its logged messages be dropped silently after the
    first one is produced (note the argument 1).

    Users can insist that all logged messages always be reflected in the
    logs using the :code:`--no_logging_squelch_repeats` flag but the default
    behavior is to allow code to request it be squelched.

    :code:`--logging_squelch_repeats` only affects code with this decorator
    on it; it ignores all other code.

    Args:
        squelch_after_n_repeats: the number of repeated messages allowed to
            log before subsequent messages are silently dropped.
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
    :code:`@logging_utils.squelched_logging_ok` decorator (see above);
    all others are ignored.

    This functionality is enabled by default but can be disabled via
    the :code:`--no_logging_squelch_repeats` commandline flag.
    """

    def __init__(self) -> None:
        super().__init__()
        self.counters: collections.Counter = collections.Counter()

    @overrides
    def filter(self, record: logging.LogRecord) -> bool:
        """Should we drop this log message?"""
        id1 = f"{record.module}:{record.funcName}"
        if id1 not in squelched_logging_counts:
            return True
        threshold = squelched_logging_counts[id1]
        logsite = f"{record.pathname}+{record.lineno}+{record.levelno}+{record.msg}"
        count = self.counters[logsite]
        self.counters[logsite] += 1
        return count < threshold


class DynamicPerScopeLoggingLevelFilter(logging.Filter):
    """This filter only allows logging messages from an allow list of
    module names or `module:function` names.  Blocks all others.  This
    filter is used to implement the :code:`--lmodule` commandline option.

    .. note::

        You probably don't need to use this directly, just use
        :code:`--lmodule`.  For example, to set logging level to INFO
        everywhere except "module:function" where it should be DEBUG::

            # myprogram.py --logging_level=INFO --lmodule=module:function=DEBUG

    """

    @staticmethod
    def level_name_to_level(name: str) -> int:
        """Given a level name, return its numberic value."""
        numeric_level = getattr(logging, name, None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid level: {name}")
        return numeric_level

    def __init__(
        self,
        default_logging_level: int,
        per_scope_logging_levels: Optional[str],
    ) -> None:
        """Construct the Filter.

        Args:
            default_logging_level: the logging level of the whole program
            per_scope_logging_levels: optional, comma separated overrides of
                logging level per scope of the format scope=level where
                scope is of the form "module:function" or ":function" and
                level is one of NOTSET, DEBUG, INFO, WARNING, ERROR or
                CRITICAL.
        """
        super().__init__()
        self.valid_levels = set(
            ["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        self.default_logging_level = default_logging_level
        self.level_by_scope = {}
        if per_scope_logging_levels is not None:
            for chunk in per_scope_logging_levels.split(","):
                if "=" not in chunk:
                    print(
                        f'Malformed lmodule directive: "{chunk}", missing "=".  Ignored.',
                        file=sys.stderr,
                    )
                    continue
                try:
                    (scope, level) = chunk.split("=")
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
                f"{record.module}:{record.funcName}",
                f":{record.funcName}",
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
    scope of a particular (marked via decorator) function are not
    deterministic (i.e. they do not always unconditionally log) but rather
    are probabilistic (i.e. they log N% of the time, randomly) when the
    user passes the :code:`--logging_probabilistically` commandline flag
    (which is enabled by default).

    .. note::

        This affects *ALL* logging statements within the marked function.
        If you want it to only affect a subset of logging statements,
        log those statements in a separate function that you invoke
        from within the "too large" scope and mark that separate function
        with the :code:`logging_is_probabilistic` decorator instead.

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
    percent chance).  This filter is used with a decorator (see
    :meth:`logging_is_probabilistic`) to implement the
    :code:`--logging_probabilistically` commandline flag.

    This filter only affects logging messages from functions that have
    been tagged with the `@logging_utils.probabilistic_logging` decorator.
    """

    @overrides
    def filter(self, record: logging.LogRecord) -> bool:
        """Should the message be logged?"""
        identifier = f"{record.module}:{record.funcName}"
        threshold = probabilistic_logging_levels.get(identifier, 100.0)
        return misc_utils.execute_probabilistically(threshold)


class OnlyInfoFilter(logging.Filter):
    """A filter that only logs messages produced at the INFO logging
    level.  This is used by the :code:`--logging_info_is_print`
    commandline option to select a subset of the logging stream to
    send to a stdout handler.
    """

    @overrides
    def filter(self, record: logging.LogRecord):
        return record.levelno == logging.INFO


def prepend_all_logger_messages(
    prefix: str, logger: logging.Logger
) -> logging.LoggerAdapter:
    """Helper method around the creation of a LogAdapter that prepends
    a given string to every log message produced.

    Args:
        prefix: the message to prepend to every log message.
        logger: the logger whose messages to modify.

    Returns:
        A new logger wrapping the old one with the given behavior.
        The old logger will continue to behave as usual; simply drop
        the reference to this wrapper when it's no longer needed.
    """
    return PrependingLogAdapter.wrap_logger(prefix, logger)


class PrependingLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f'{self.extra.get("prefix", "")}{msg}', kwargs

    @staticmethod
    def wrap_logger(prefix: str, logger: logging.Logger) -> logging.LoggerAdapter:
        """Helper method around the creation of a LogAdapter that prepends
        a given string to every log message produced.

        Args:
            prefix: the message to prepend to every log message.
            logger: the logger whose messages to modify.

        Returns:
            A new logger wrapping the old one with the given behavior.
            The old logger will continue to behave as usual; simply drop
            the reference to this wrapper when it's no longer needed.
        """
        assert prefix
        return PrependingLogAdapter(logger, {"prefix": prefix})


def append_all_logger_messages(
    suffix: str, logger: logging.Logger
) -> logging.LoggerAdapter:
    """Helper method around the creation of a LogAdapter that appends
    a given string to every log message produced.

    Args:
        suffix: the message to prepend to every log message.
        logger: the logger whose messages to modify.

    Returns:
        A new logger wrapping the old one with the given behavior.
        The old logger will continue to behave as usual; simply drop
        the reference to this wrapper when it's no longer needed.
    """
    return AppendingLogAdapter.wrap_logger(suffix, logger)


class AppendingLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f'{msg}{self.extra.get("suffix", "")}', kwargs

    @staticmethod
    def wrap_logger(suffix: str, logger: logging.Logger) -> logging.LoggerAdapter:
        """Helper method around the creation of a LogAdapter that appends
        a given string to every log message produced.

        Args:
            suffix: the message to prepend to every log message.
            logger: the logger whose messages to modify.

        Returns:
            A new logger wrapping the old one with the given behavior.
            The old logger will continue to behave as usual; simply drop
            the reference to this wrapper when it's no longer needed.
        """
        assert suffix
        return AppendingLogAdapter(logger, {"suffix": suffix})


class MillisecondAwareFormatter(logging.Formatter):
    """A formatter for adding milliseconds to log messages which, for
    whatever reason, the default Python logger doesn't do.

    .. note::

        You probably don't need to use this directly but it is
        wired in under :meth:`initialize_logging` so that the
        timestamps in log messages have millisecond level
        precision.

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


def _log_about_logging(
    logger,
    default_logging_level,
    preexisting_handlers_count,
    fmt,
    facility_name,
):
    """This is invoked automatically after logging is initialized such
    that the first messages in the log are about how logging itself
    was configured.
    """
    level_name = logging._levelToName.get(
        default_logging_level, str(default_logging_level)
    )
    logger.debug("Initialized global logging; logging level is %s.", level_name)
    if (
        config.config["logging_clear_preexisting_handlers"]
        and preexisting_handlers_count > 0
    ):
        logger.debug(
            "Logging cleared %d global handlers (--logging_clear_preexisting_handlers)",
            preexisting_handlers_count,
        )
    logger.debug('Logging format specification is "%s"', fmt)
    if config.config["logging_debug_threads"]:
        logger.debug(
            "...Logging format spec captures tid/pid. (--logging_debug_threads)"
        )
    if config.config["logging_debug_modules"]:
        logger.debug(
            "...Logging format spec captures files/functions/lineno. (--logging_debug_modules)"
        )
    if config.config["logging_syslog"]:
        logger.debug(
            "Logging to syslog as %s with priority mapping based on level. (--logging_syslog)",
            facility_name,
        )
    if config.config["logging_filename"]:
        logger.debug(
            'Logging to file "%s". (--logging_filename)',
            config.config["logging_filename"],
        )
        logger.debug(
            "...with %d bytes max file size. (--logging_filename_maxsize)",
            config.config["logging_filename_maxsize"],
        )
        logger.debug(
            "...and %d rotating backup file count. (--logging_filename_count)",
            config.config["logging_filename_count"],
        )
    if config.config["logging_console"]:
        logger.debug("Logging to the console (stderr). (--logging_console)")
    if config.config["logging_info_is_print"]:
        logger.debug(
            "Logging logger.info messages will be repeated on stdout. (--logging_info_is_print)"
        )
    if config.config["logging_squelch_repeats"]:
        logger.debug(
            "Logging code allowed to request repeated messages be squelched. (--logging_squelch_repeats)"
        )
    else:
        logger.debug(
            "Logging code forbidden to request messages be squelched; all messages logged. (--no_logging_squelch_repeats)"
        )
    if config.config["logging_probabilistically"]:
        logger.debug(
            "Logging code is allowed to request probabilistic logging. (--logging_probabilistically)"
        )
    else:
        logger.debug(
            "Logging code is forbidden to request probabilistic logging; messages always logged. (--no_logging_probabilistically)"
        )
    if config.config["lmodule"]:
        logger.debug(
            f'Logging dynamic per-module logging enabled. (--lmodule={config.config["lmodule"]})'
        )
    if config.config["logging_captures_prints"]:
        logger.debug(
            "Logging will capture printed data as logger.info messages. (--logging_captures_prints)"
        )


def initialize_logging(logger=None) -> logging.Logger:
    """Initialize logging for the program.  See module level comments
    for information about what functionality this provides and how to
    enable or disable functionality via the commandline.

    If you use the
    :meth:`bootstrap.initialize` decorator on your program's entry point,
    it will call this for you.  See :meth:`pyutils.bootstrap.initialize`
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
    if config.config["logging_clear_preexisting_handlers"]:
        while logger.hasHandlers():
            logger.removeHandler(logger.handlers[0])
            preexisting_handlers_count += 1

    # --logging_config_file pulls logging settings from a config file
    # skipping the rest of this setup.
    if config.config["logging_config_file"] is not None:
        fileConfig(config.config["logging_config_file"])
        return logger

    handlers: List[logging.Handler] = []
    handler: Optional[logging.Handler] = None

    # Global default logging level (--logging_level); messages below
    # this level will be silenced.
    logging_level = config.config["logging_level"]
    assert logging_level
    logging_level = logging_level.upper()
    default_logging_level = getattr(logging, logging_level, None)
    if not isinstance(default_logging_level, int):
        raise ValueError(f'Invalid level: {config.config["logging_level"]}')

    # Custom or default --logging_format?
    if config.config["logging_format"]:
        fmt = config.config["logging_format"]
    elif config.config["logging_syslog"]:
        fmt = "%(levelname).1s:%(filename)s[%(process)d]: %(message)s"
    else:
        fmt = "%(levelname).1s:%(asctime)s: %(message)s"

    # --logging_debug_threads and --logging_debug_modules both affect
    # the format by prepending information about the pid/tid or
    # file/function.
    if config.config["logging_debug_threads"]:
        fmt = f"%(process)d.%(thread)d|{fmt}"
    if config.config["logging_debug_modules"]:
        fmt = f"%(filename)s:%(funcName)s:%(lineno)s|{fmt}"

    # --logging_syslog (optionally with --logging_syslog_facility)
    # sets up for logging to use the standard system syslogd as a
    # sink.
    facility_name = None
    if config.config["logging_syslog"]:
        if sys.platform not in ("win32", "cygwin"):
            if config.config["logging_syslog_facility"]:
                facility_name = "LOG_" + config.config["logging_syslog_facility"]
            facility = SysLogHandler.__dict__.get(facility_name, SysLogHandler.LOG_USER)  # type: ignore
            assert facility is not None
            handler = SysLogHandler(facility=facility, address="/dev/log")
            handler.setFormatter(
                MillisecondAwareFormatter(
                    fmt=fmt,
                    datefmt=config.config["logging_date_format"],
                )
            )
            handlers.append(handler)

    # --logging_filename (with friends --logging_filename_count and
    # --logging_filename_maxsize) set up logging to a file on the
    # filesystem with automatic rotation when it gets too big.
    if config.config["logging_filename"]:
        max_bytes = config.config["logging_filename_maxsize"]
        assert max_bytes and isinstance(max_bytes, int)
        backup_count = config.config["logging_filename_count"]
        assert backup_count and isinstance(backup_count, int)
        handler = RotatingFileHandler(
            config.config["logging_filename"],
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        handler.setFormatter(
            MillisecondAwareFormatter(
                fmt=fmt,
                datefmt=config.config["logging_date_format"],
            )
        )
        handlers.append(handler)

    # --logging_console is, ahem, logging to the console.
    if config.config["logging_console"]:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            MillisecondAwareFormatter(
                fmt=fmt,
                datefmt=config.config["logging_date_format"],
            )
        )
        handlers.append(handler)

    if len(handlers) == 0:
        handlers.append(logging.NullHandler())
    for handler in handlers:
        logger.addHandler(handler)

    # --logging_info_is_print echoes any message to logger.info(x) as
    # a print statement on stdout.
    if config.config["logging_info_is_print"]:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(OnlyInfoFilter())
        logger.addHandler(handler)

    # --logging_squelch_repeats allows code to request repeat logging
    # messages (identical log site and message contents) to be
    # silenced.  Logging code must request this explicitly, it isn't
    # automatic.  This option just allows the silencing to happen.
    if config.config["logging_squelch_repeats"]:
        for handler in handlers:
            handler.addFilter(SquelchRepeatedMessagesFilter())

    # --logging_probabilistically allows code to request
    # non-deterministic logging where messages have some probability
    # of being produced.  Logging code must request this explicitly.
    # This option just allows the non-deterministic behavior to
    # happen.  Disabling it will cause every log message to be
    # produced.
    if config.config["logging_probabilistically"]:
        for handler in handlers:
            handler.addFilter(ProbabilisticFilter())

    # --lmodule is a way to have a special logging level for just on
    # module or one set of modules that is different than the one set
    # globally via --logging_level.
    for handler in handlers:
        handler.addFilter(
            DynamicPerScopeLoggingLevelFilter(
                default_logging_level,
                config.config["lmodule"],
            )
        )
    logger.setLevel(0)
    logger.propagate = False

    # --logging_captures_prints, if set, will capture and log.info
    # anything printed on stdout.
    if config.config["logging_captures_prints"]:
        import builtins

        def print_and_also_log(*arg, **kwarg):
            f = kwarg.get("file", None)
            if f == sys.stderr:
                logger.warning(*arg)
            else:
                logger.info(*arg)
            BUILT_IN_PRINT(*arg, **kwarg)

        builtins.print = print_and_also_log

    # At this point the logger is ready, handlers are set up,
    # etc... so log about the logging configuration.
    _log_about_logging(
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
    if config.config["logging_debug_threads"]:
        from pyutils.parallelize.thread_utils import current_thread_id

        print(f"{current_thread_id()}", end="")
        print(*args, **kwargs)
    else:
        pass


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
            self.f = [open(filename, "wb", buffering=0) for filename in filenames]
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
        from pyutils.string_utils import _sprintf, strip_escape_sequences

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
        buf = _sprintf(*args, end="", sep=sep)
        if sep is None:
            sep = " "
        if end is None:
            end = "\n"
        if end == "\n":
            buf += "\n"
        if self.destination_bitv & self.Destination.FILENAMES and self.f is not None:
            for _ in self.f:
                _.write(buf.encode("utf-8"))
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
        """
        Args:
            destination_bitv: a bitvector that indicates where we should
                send output.  See :class:`OutputMultiplexer` for options.
            logger: optional logger to use for log destination messages.
            filenames: optional filenames to write for filename destination
                messages.
            handles: optional open filehandles to write for filehandle
                destination messages.
        """
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
    info) by calling `/usr/bin/logger`.  This is pretty hacky but used
    by a bunch of (my) code.  Another way to do this would be to use
    :code:`--logging_syslog` and :code:`--logging_syslog_facility` but
    I can't actually say that's easier.

    TODO: this needs to move.
    """
    message = message.replace("'", "'\"'\"'")
    os.system(f"/usr/bin/logger -p local7.info -- '{message}'")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
