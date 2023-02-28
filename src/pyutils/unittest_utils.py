#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""Helpers for unittests.

.. warning::

    When you import this we automatically wrap the standard Python
    `unittest.main` with a call to :meth:`pyutils.bootstrap.initialize`
    so that we get logger config, commandline args, logging control,
    etc... this works fine but may be unexpected behavior.
"""

import contextlib
import functools
import inspect
import logging
import os
import pickle
import random
import statistics
import tempfile
import time
import unittest
import warnings
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional

from pyutils import bootstrap, config, function_utils

logger = logging.getLogger(__name__)
cfg = config.add_commandline_args(
    f"Logging ({__file__})", "Args related to function decorators"
)
cfg.add_argument(
    "--unittests_ignore_perf",
    action="store_true",
    default=False,
    help="Ignore unittest perf regression in @check_method_for_perf_regressions",
)
cfg.add_argument(
    "--unittests_num_perf_samples",
    type=int,
    default=50,
    help="The count of perf timing samples we need to see before blocking slow runs on perf grounds",
)
cfg.add_argument(
    "--unittests_drop_perf_traces",
    type=str,
    nargs=1,
    default=None,
    help="The identifier (i.e. file!test_fixture) for which we should drop all perf data",
)
cfg.add_argument(
    "--unittests_persistance_strategy",
    choices=["FILE", "DATABASE"],
    default="FILE",
    help="Should we persist perf data in a file or db?",
)
cfg.add_argument(
    "--unittests_perfdb_filename",
    type=str,
    metavar="FILENAME",
    default=f'{os.environ["HOME"]}/.python_unittest_performance_db',
    help="File in which to store perf data (iff --unittests_persistance_strategy is FILE)",
)
cfg.add_argument(
    "--unittests_perfdb_spec",
    type=str,
    metavar="DBSPEC",
    default="mariadb+pymysql://python_unittest:<PASSWORD>@db.house:3306/python_unittest_performance",
    help="Db connection spec for perf data (iff --unittest_persistance_strategy is DATABASE)",
)

unittest.main = bootstrap.initialize(unittest.main)


class PerfRegressionDataPersister(ABC):
    """A base class that defines an interface for dealing with
    persisting perf regression data.
    """

    @abstractmethod
    def load_performance_data(self, method_id: str) -> Dict[str, List[float]]:
        """Load the historical performance data for the supplied method.

        Args:
            method_id: the method for which we want historical perf data.
        """
        pass

    @abstractmethod
    def save_performance_data(self, method_id: str, data: Dict[str, List[float]]):
        """Save the historical performance data of the supplied method.

        Args:
            method_id: the method whose historical perf data we're saving.
            data: the historical performance data being persisted.
        """
        pass

    @abstractmethod
    def delete_performance_data(self, method_id: str):
        """Delete the historical performance data of the supplied method.

        Args:
            method_id: the method whose data should be erased.
        """
        pass


class FileBasedPerfRegressionDataPersister(PerfRegressionDataPersister):
    """A perf regression data persister that uses files."""

    def __init__(self, filename: str):
        """
        Args:
            filename: the filename to save/load historical performance data
        """
        super().__init__()
        self.filename = filename
        self.traces_to_delete: List[str] = []

    def load_performance_data(self, method_id: str) -> Dict[str, List[float]]:
        with open(self.filename, "rb") as f:
            return pickle.load(f)

    def save_performance_data(self, method_id: str, data: Dict[str, List[float]]):
        for trace in self.traces_to_delete:
            if trace in data:
                data[trace] = []

        with open(self.filename, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

    def delete_performance_data(self, method_id: str):
        self.traces_to_delete.append(method_id)


# class DatabasePerfRegressionDataPersister(PerfRegressionDataPersister):
#    """A perf regression data persister that uses a database backend."""
#
#    def __init__(self, dbspec: str):
#        super().__init__()
#        self.dbspec = dbspec
#        self.engine = sa.create_engine(self.dbspec)
#        self.conn = self.engine.connect()
#
#    def load_performance_data(self, method_id: str) -> Dict[str, List[float]]:
#        results = self.conn.execute(
#            sa.text(f'SELECT * FROM runtimes_by_function WHERE function = "{method_id}";')
#        )
#        ret: Dict[str, List[float]] = {method_id: []}
#        for result in results.all():
#            ret[method_id].append(result['runtime'])
#        results.close()
#        return ret
#
#    def save_performance_data(self, method_id: str, data: Dict[str, List[float]]):
#        self.delete_performance_data(method_id)
#        for (mid, perf_data) in data.items():
#            sql = 'INSERT INTO runtimes_by_function (function, runtime) VALUES '
#            for perf in perf_data:
#                self.conn.execute(sql + f'("{mid}", {perf});')
#
#    def delete_performance_data(self, method_id: str):
#        sql = f'DELETE FROM runtimes_by_function WHERE function = "{method_id}"'
#        self.conn.execute(sql)


def check_method_for_perf_regressions(func: Callable) -> Callable:
    """This decorator is meant to be used on a method in a class that
    subclasses :class:`unittest.TestCase`.  When decorated, method
    execution timing (i.e. performance) will be measured and compared
    with a database of historical performance for the same method.
    The wrapper will then fail the test with a perf-related message if
    it has become too slow.

    See also :meth:`check_all_methods_for_perf_regressions`.

    Example usage::

        class TestMyClass(unittest.TestCase):

            @check_method_for_perf_regressions
            def test_some_part_of_my_class(self):
                ...

    """

    @functools.wraps(func)
    def wrapper_perf_monitor(*args, **kwargs):
        if config.config["unittests_ignore_perf"]:
            return func(*args, **kwargs)

        if config.config["unittests_persistance_strategy"] == "FILE":
            filename = config.config["unittests_perfdb_filename"]
            helper = FileBasedPerfRegressionDataPersister(filename)
        elif config.config["unittests_persistance_strategy"] == "DATABASE":
            raise NotImplementedError(
                "Persisting to a database is not implemented in this version"
            )
        else:
            raise Exception("Unknown/unexpected --unittests_persistance_strategy value")

        func_id = function_utils.function_identifier(func)
        func_name = func.__name__
        logger.debug("Watching %s's performance...", func_name)
        logger.debug('Canonical function identifier = "%s"', func_id)

        try:
            perfdb = helper.load_performance_data(func_id)
        except Exception:
            msg = "Unable to load perfdb; skipping it..."
            logger.exception(msg)
            warnings.warn(msg)
            perfdb = {}

        # cmdline arg to forget perf traces for function
        drop_id = config.config["unittests_drop_perf_traces"]
        if drop_id is not None:
            helper.delete_performance_data(drop_id)

        # Run the wrapped test paying attention to latency.
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time

        # See if it was unexpectedly slow.
        hist = perfdb.get(func_id, [])
        if len(hist) < config.config["unittests_num_perf_samples"]:
            hist.append(run_time)
            logger.debug("Still establishing a perf baseline for %s", func_name)
        else:
            stdev = statistics.stdev(hist)
            logger.debug("For %s, performance stdev=%.2f", func_name, stdev)
            slowest = hist[-1]
            logger.debug("For %s, slowest perf on record is %.2fs", func_name, slowest)
            limit = slowest + stdev * 4
            logger.debug("For %s, max acceptable runtime is %.2fs", func_name, limit)
            logger.debug(
                "For %s, actual observed runtime was %.2fs", func_name, run_time
            )
            if run_time > limit:
                msg = f"""{func_id} performance has regressed unacceptably.
{slowest:f}s is the slowest runtime on record in {len(hist)} perf samples.
It just ran in {run_time:f}s which is 4+ stdevs slower than the slowest.
Here is the current, full db perf timing distribution:

"""
                for x in hist:
                    msg += f"{x:f}\n"
                logger.error(msg)
                slf = args[0]  # Peek at the wrapped function's self ref.
                slf.fail(msg)  # ...to fail the testcase.
            else:
                hist.append(run_time)

        # Don't spam the database with samples; just pick a random
        # sample from what we have and store that back.
        n = min(config.config["unittests_num_perf_samples"], len(hist))
        hist = random.sample(hist, n)
        hist.sort()
        perfdb[func_id] = hist
        helper.save_performance_data(func_id, perfdb)
        return value

    return wrapper_perf_monitor


def check_all_methods_for_perf_regressions(prefix: str = "test_"):
    """This decorator is meant to apply to classes that subclass from
    :class:`unittest.TestCase` and, when applied, has the affect of
    decorating each method that matches the `prefix` given with the
    :meth:`check_method_for_perf_regressions` wrapper (see above).
    This wrapper causes us to measure perf and fail tests that regress
    perf dramatically.

    Args:
        prefix: the prefix of method names to check for regressions

    See also :meth:`check_method_for_perf_regressions` to check only
    a single method.

    Example usage.  By decorating the class, all methods with names
    that begin with `test_` will be perf monitored::

        import pyutils.unittest_utils as uu

        @uu.check_all_methods_for_perf_regressions()
        class TestMyClass(unittest.TestCase):

            def test_some_part_of_my_class(self):
                ...

            def test_som_other_part_of_my_class(self):
                ...
    """

    def decorate_the_testcase(cls):
        if issubclass(cls, unittest.TestCase):
            for name, m in inspect.getmembers(cls, inspect.isfunction):
                if name.startswith(prefix):
                    setattr(cls, name, check_method_for_perf_regressions(m))
                    logger.debug("Wrapping %s:%s.", cls.__name__, name)
        return cls

    return decorate_the_testcase


class RecordStdout(contextlib.AbstractContextManager):
    """
    Records what is emitted to stdout into a buffer instead.

    >>> with RecordStdout() as record:
    ...     print("This is a test!")
    >>> print({record().readline()})
    {'This is a test!\\n'}
    >>> record().close()
    """

    def __init__(self) -> None:
        super().__init__()
        self.destination = tempfile.SpooledTemporaryFile(mode="r+")
        self.recorder: Optional[contextlib.redirect_stdout] = None

    def __enter__(self) -> Callable[[], tempfile.SpooledTemporaryFile]:
        self.recorder = contextlib.redirect_stdout(self.destination)
        assert self.recorder is not None
        self.recorder.__enter__()
        return lambda: self.destination

    def __exit__(self, *args) -> Literal[False]:
        assert self.recorder is not None
        self.recorder.__exit__(*args)
        self.destination.seek(0)
        return False


class RecordStderr(contextlib.AbstractContextManager):
    """
    Record what is emitted to stderr.

    >>> import sys
    >>> with RecordStderr() as record:
    ...     print("This is a test!", file=sys.stderr)
    >>> print({record().readline()})
    {'This is a test!\\n'}
    >>> record().close()
    """

    def __init__(self) -> None:
        super().__init__()
        self.destination = tempfile.SpooledTemporaryFile(mode="r+")
        self.recorder: Optional[contextlib.redirect_stdout[Any]] = None

    def __enter__(self) -> Callable[[], tempfile.SpooledTemporaryFile]:
        self.recorder = contextlib.redirect_stderr(self.destination)  # type: ignore
        assert self.recorder is not None
        self.recorder.__enter__()
        return lambda: self.destination

    def __exit__(self, *args) -> Literal[False]:
        assert self.recorder is not None
        self.recorder.__exit__(*args)
        self.destination.seek(0)
        return False


class RecordMultipleStreams(contextlib.AbstractContextManager):
    """
    Record the output to more than one stream.

    Example usage::

        with RecordMultipleStreams(sys.stdout, sys.stderr) as r:
            print("This is a test!", file=sys.stderr)
            print("This is too", file=sys.stdout)

        print(r().readlines())
        r().close()

    """

    def __init__(self, *files) -> None:
        super().__init__()
        self.files = [*files]
        self.destination = tempfile.SpooledTemporaryFile(mode="r+")
        self.saved_writes: List[Callable[..., Any]] = []

    def __enter__(self) -> Callable[[], tempfile.SpooledTemporaryFile]:
        for f in self.files:
            self.saved_writes.append(f.write)
            f.write = self.destination.write
        return lambda: self.destination

    def __exit__(self, *args) -> Literal[False]:
        for f in self.files:
            f.write = self.saved_writes.pop()
        self.destination.seek(0)
        return False


if __name__ == "__main__":
    import doctest

    doctest.testmod()
