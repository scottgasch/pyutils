#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
If you decorate your main method (i.e. program entry point) like this::

    @bootstrap.initialize
    def main():
        whatever

...you will get:

    * automatic support for :py:mod:`pyutils.config` (argument parsing, see
      that module for details),
    * The ability to break into pdb on unhandled exceptions (which is
      enabled/disabled via the commandline flag :code:`--debug_unhandled_exceptions`),
    * automatic logging support from :py:mod:`pyutils.logging_utils` controllable
      via several commandline flags,
    * the ability to optionally enable whole-program code profiling and reporting
      when you run your code using commandline flag :code:`--run_profiler`,
    * the ability to optionally enable import auditing via the commandline flag
      :code:`--audit_import_events`.  This logs a message whenever a module is imported
      *after* the bootstrap module itself is loaded.  Note that other modules may
      already be loaded when bootstrap is loaded and these imports will not be
      logged.  If you're trying to debug import events or dependency problems,
      I suggest putting bootstrap very early in your import list and using this
      flag.
    * optional memory profiling for your program set via the commandline flag
      :code:`--trace_memory`.  This provides a report of python memory utilization
      at program termination time.
    * the ability to set the global random seed via commandline flag for
      reproducable runs (as long as subsequent code doesn't reset the seed)
      using the :code:`--set_random_seed` flag,
    * automatic program timing and reporting logged to the INFO log,
    * more verbose error handling and reporting.

"""

import functools
import importlib
import importlib.abc
import logging
import os
import sys
import uuid
from inspect import stack

from pyutils import config, logging_utils
from pyutils.argparse_utils import ActionNoYes

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.


logger = logging.getLogger(__name__)

cfg = config.add_commandline_args(
    f"Bootstrap ({__file__})",
    "Args related to python program bootstrapper and Swiss army knife",
)
cfg.add_argument(
    "--debug_unhandled_exceptions",
    action=ActionNoYes,
    default=False,
    help="Break into pdb on top level unhandled exceptions.",
)
cfg.add_argument(
    "--show_random_seed",
    action=ActionNoYes,
    default=False,
    help="Should we display (and log.debug) the global random seed?",
)
cfg.add_argument(
    "--set_random_seed",
    type=int,
    nargs=1,
    default=None,
    metavar="SEED_INT",
    help="Override the global random seed with a particular number.",
)
cfg.add_argument(
    "--dump_all_objects",
    action=ActionNoYes,
    default=False,
    help="Should we dump the Python import tree before main?",
)
cfg.add_argument(
    "--audit_import_events",
    action=ActionNoYes,
    default=False,
    help="Should we audit all import events?",
)
cfg.add_argument(
    "--run_profiler",
    action=ActionNoYes,
    default=False,
    help="Should we run cProfile on this code?",
)
cfg.add_argument(
    "--trace_memory",
    action=ActionNoYes,
    default=False,
    help="Should we record/report on memory utilization?",
)

ORIGINAL_EXCEPTION_HOOK = sys.excepthook


def handle_uncaught_exception(exc_type, exc_value, exc_tb):
    """
    Top-level exception handler for exceptions that make it past any exception
    handlers in the python code being run.  Logs the error and stacktrace then
    maybe attaches a debugger.

    """
    msg = f"Unhandled top level exception {exc_type}"
    logger.exception(msg)
    print(msg, file=sys.stderr)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    else:
        import io
        import traceback

        tb_output = io.StringIO()
        traceback.print_tb(exc_tb, None, tb_output)
        print(tb_output.getvalue(), file=sys.stderr)
        logger.error(tb_output.getvalue())
        tb_output.close()

        # stdin or stderr is redirected, just do the normal thing
        if not sys.stderr.isatty() or not sys.stdin.isatty():
            ORIGINAL_EXCEPTION_HOOK(exc_type, exc_value, exc_tb)

        else:  # a terminal is attached and stderr isn't redirected, maybe debug.
            if config.config["debug_unhandled_exceptions"]:
                logger.info("Invoking the debugger...")
                import pdb

                pdb.pm()
            else:
                ORIGINAL_EXCEPTION_HOOK(exc_type, exc_value, exc_tb)


class ImportInterceptor(importlib.abc.MetaPathFinder):
    """An interceptor that always allows module load events but dumps a
    record into the log and onto stdout when modules are loaded and
    produces an audit of who imported what at the end of the run.  It
    can't see any load events that happen before it, though, so move
    bootstrap up in your __main__'s import list just temporarily to
    get a good view.

    """

    def __init__(self):
        from pyutils.collectionz.trie import Trie

        self.module_by_filename_cache = {}
        self.repopulate_modules_by_filename()
        self.tree = Trie()
        self.tree_node_by_module = {}

    def repopulate_modules_by_filename(self):
        self.module_by_filename_cache.clear()
        for (
            _,
            mod,
        ) in sys.modules.copy().items():  # copy here because modules is volatile
            if hasattr(mod, "__file__"):
                fname = getattr(mod, "__file__")
            else:
                fname = "unknown"
            self.module_by_filename_cache[fname] = mod

    @staticmethod
    def should_ignore_filename(filename: str) -> bool:
        return "importlib" in filename or "six.py" in filename

    def find_module(self, fullname, path):
        raise Exception(
            "This method has been deprecated since Python 3.4, please upgrade."
        )

    def find_spec(self, loaded_module, path=None, _=None):
        s = stack()
        for x in range(3, len(s)):
            filename = s[x].filename
            if ImportInterceptor.should_ignore_filename(filename):
                continue

            loading_function = s[x].function
            if filename in self.module_by_filename_cache:
                loading_module = self.module_by_filename_cache[filename]
            else:
                self.repopulate_modules_by_filename()
                loading_module = self.module_by_filename_cache.get(filename, "unknown")

            path = self.tree_node_by_module.get(loading_module, [])
            path.extend([loaded_module])
            self.tree.insert(path)
            self.tree_node_by_module[loading_module] = path

            msg = f"*** Import {loaded_module} from {filename}:{s[x].lineno} in {loading_module}::{loading_function}"
            logger.debug(msg)
            print(msg)
            return
        msg = f"*** Import {loaded_module} from ?????"
        logger.debug(msg)
        print(msg)

    def invalidate_caches(self):
        pass

    def find_importer(self, module: str):
        if module in self.tree_node_by_module:
            node = self.tree_node_by_module[module]
            return node
        return []


# Audit import events?  Note: this runs early in the lifetime of the
# process (assuming that import bootstrap happens early); config has
# (probably) not yet been loaded or parsed the commandline.  Also,
# some things have probably already been imported while we weren't
# watching so this information may be incomplete.
#
# Also note: move bootstrap up in the global import list to catch
# more import events and have a more complete record.
IMPORT_INTERCEPTOR = None
for arg in sys.argv:
    if arg == "--audit_import_events":
        IMPORT_INTERCEPTOR = ImportInterceptor()
        sys.meta_path.insert(0, IMPORT_INTERCEPTOR)


def dump_all_objects() -> None:
    """Helper code to dump all known python objects."""

    messages = {}
    all_modules = sys.modules
    for obj in object.__subclasses__():
        if not hasattr(obj, "__name__"):
            continue
        klass = obj.__name__
        if not hasattr(obj, "__module__"):
            continue
        class_mod_name = obj.__module__
        if class_mod_name in all_modules:
            mod = all_modules[class_mod_name]
            if not hasattr(mod, "__name__"):
                mod_name = class_mod_name
            else:
                mod_name = mod.__name__
            if hasattr(mod, "__file__"):
                mod_file = mod.__file__
            else:
                mod_file = "unknown"
            if IMPORT_INTERCEPTOR is not None:
                import_path = IMPORT_INTERCEPTOR.find_importer(mod_name)
            else:
                import_path = "unknown"
            msg = f"{class_mod_name}::{klass} ({mod_file})"
            if import_path != "unknown" and len(import_path) > 0:
                msg += f" imported by {import_path}"
            messages[f"{class_mod_name}::{klass}"] = msg
    for x in sorted(messages.keys()):
        logger.debug(messages[x])
        print(messages[x])


def initialize(entry_point):
    """
    Do whole program setup and instrumentation.  See module comments for
    details.  To use::

        from pyutils import bootstrap

        @bootstrap.initialize
        def main():
            whatever

        if __name__ == '__main__':
            main()
    """

    @functools.wraps(entry_point)
    def initialize_wrapper(*args, **kwargs):
        # Hook top level unhandled exceptions, maybe invoke debugger.
        if sys.excepthook == sys.__excepthook__:
            sys.excepthook = handle_uncaught_exception

        # Try to figure out the name of the program entry point.  Then
        # parse configuration (based on cmdline flags, environment vars
        # etc...)
        entry_filename = None
        entry_descr = None
        try:
            entry_filename = entry_point.__code__.co_filename
            entry_descr = repr(entry_point.__code__)
        except Exception:
            if (
                "__globals__" in entry_point.__dict__
                and "__file__" in entry_point.__globals__
            ):
                entry_filename = entry_point.__globals__["__file__"]
                entry_descr = entry_filename
        config.parse(entry_filename)

        if config.config["trace_memory"]:
            import tracemalloc

            tracemalloc.start()

        # Initialize logging... and log some remembered messages from
        # config module.  Also logs about the logging config if we're
        # in debug mode.
        logging_utils.initialize_logging(logging.getLogger())
        config.late_logging()

        # Log some info about the python interpreter itself if we're
        # in debug mode.
        logger.debug(
            "Platform: %s, maxint=0x%x, byteorder=%s",
            sys.platform,
            sys.maxsize,
            sys.byteorder,
        )
        logger.debug("Python interpreter version: %s", sys.version)
        logger.debug("Python implementation: %s", sys.implementation)
        logger.debug("Python C API version: %s", sys.api_version)
        if __debug__:
            logger.debug("Python interpreter running in __debug__ mode.")
        else:
            logger.debug("Python interpreter running in optimized mode.")
        logger.debug("Python path: %s", sys.path)

        # Dump some info about the physical machine we're running on
        # if we're ing debug mode.
        if "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
            logger.debug(
                "Physical memory: %.1fGb",
                os.sysconf("SC_PAGE_SIZE")
                * os.sysconf("SC_PHYS_PAGES")
                / float(1024**3),
            )
        logger.debug("Logical processors: %s", os.cpu_count())

        # Allow programs that don't bother to override the random seed
        # to be replayed via the commandline.
        import random

        random_seed = config.config["set_random_seed"]
        if random_seed is not None:
            random_seed = random_seed[0]
        else:
            random_seed = int.from_bytes(os.urandom(4), "little")
        if config.config["show_random_seed"]:
            msg = f"Global random seed is: {random_seed}"
            logger.debug(msg)
            print(msg)
        random.seed(random_seed)

        # Give each run a unique identifier if we're in debug mode.
        logger.debug("This run's UUID: %s", str(uuid.uuid4()))

        # Do it, invoke the user's code.  Pay attention to how long it takes.
        logger.debug(
            "Starting %s (program entry point) ---------------------- ", entry_descr
        )
        ret = None
        from pyutils import stopwatch

        if config.config["run_profiler"]:
            import cProfile
            from pstats import SortKey

            with stopwatch.Timer() as t:
                cProfile.runctx(
                    "ret = entry_point(*args, **kwargs)",
                    globals(),
                    locals(),
                    None,
                    SortKey.CUMULATIVE,
                )
        else:
            with stopwatch.Timer() as t:
                ret = entry_point(*args, **kwargs)

        logger.debug("%s (program entry point) returned %s.", entry_descr, ret)

        if config.config["trace_memory"]:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")
            print()
            print("--trace_memory's top 10 memory using files:")
            for stat in top_stats[:10]:
                print(stat)

        if config.config["dump_all_objects"]:
            dump_all_objects()

        if config.config["audit_import_events"]:
            if IMPORT_INTERCEPTOR is not None:
                print(IMPORT_INTERCEPTOR.tree)

        walltime = t()
        (utime, stime, cutime, cstime, elapsed_time) = os.times()
        logger.debug(
            "\n"
            "user: %.4fs\n"
            "system: %.4fs\n"
            "child user: %.4fs\n"
            "child system: %.4fs\n"
            "machine uptime: %.4fs\n"
            "walltime: %.4fs",
            utime,
            stime,
            cutime,
            cstime,
            elapsed_time,
            walltime,
        )

        # If it doesn't return cleanly, call attention to the return value.
        if ret is not None and ret != 0:
            logger.error("Exit %s", ret)
        else:
            logger.debug("Exit %s", ret)
        sys.exit(ret)

    return initialize_wrapper
