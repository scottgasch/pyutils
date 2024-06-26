#!/usr/bin/env python3

"""
A smart, fast test runner.  Used in a git pre-commit hook.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from overrides import overrides

from pyutils import ansi, bootstrap, config, dict_utils, exec_utils, text_utils
from pyutils.files import file_utils
from pyutils.parallelize import parallelize as par
from pyutils.parallelize import smart_future, thread_utils

logger = logging.getLogger(__name__)
args = config.add_commandline_args(
    f"Run Tests Driver ({__file__})", f"Args related to {__file__}"
)
args.add_argument("--unittests", "-u", action="store_true", help="Run unittests.")
args.add_argument("--doctests", "-d", action="store_true", help="Run doctests.")
args.add_argument(
    "--integration", "-i", action="store_true", help="Run integration tests."
)
args.add_argument(
    "--all",
    "-a",
    action="store_true",
    help="Run unittests, doctests and integration tests.  Equivalient to -u -d -i",
)
args.add_argument(
    "--coverage",
    "-c",
    action="store_true",
    help="Run tests and capture code coverage data",
)
args.add_argument(
    "--show_failures",
    action="store_true",
    help="Should we show failure messages in the output?",
)
args.add_argument(
    "--keep_going",
    action="store_true",
    help="Should we keep going after encountering an error?",
)

HOME = os.environ["HOME"]

# These tests will be run twice in --coverage mode: once to get code
# coverage and then again with not coverage enabeled.  This is because
# they pay attention to code performance which is adversely affected
# by coverage.
PERF_SENSATIVE_TESTS = set(["string_utils_test.py"])
TESTS_TO_SKIP = set(
    [
        "zookeeper_test.py",
        "zookeeper.py",
        "dateparse_utils_test.py",
        "run_tests.py",
        "camera_utils.py",
        "geocode.py",
    ]
)

ROOT = ".."


@dataclass
class TestingParameters:
    halt_on_error: bool
    """Should we stop as soon as one error has occurred?"""

    halt_event: threading.Event
    """An event that, when set, indicates to stop ASAP."""


@dataclass
class TestToRun:
    name: str
    """The name of the test"""

    kind: str
    """The kind of the test"""

    cmdline: str
    """The command line to execute"""


@dataclass
class TestResults:
    name: str
    """The name of this test / set of tests."""

    tests_executed: Dict[str, float]
    """Tests that were executed."""

    tests_succeeded: List[str]
    """Tests that succeeded."""

    tests_failed: List[str]
    """Tests that failed."""

    tests_timed_out: List[str]
    """Tests that timed out."""

    def __add__(self, other):
        merged = dict_utils.coalesce(
            [self.tests_executed, other.tests_executed],
            aggregation_function=dict_utils.raise_on_duplicated_keys,
        )
        self.tests_executed = merged
        self.tests_succeeded.extend(other.tests_succeeded)
        self.tests_failed.extend(other.tests_failed)
        self.tests_timed_out.extend(other.tests_timed_out)
        return self

    __radd__ = __add__

    @staticmethod
    def empty_test_results(suite_name: str) -> TestResults:
        return TestResults(
            name=suite_name,
            tests_executed={},
            tests_succeeded=[],
            tests_failed=[],
            tests_timed_out=[],
        )

    @staticmethod
    def single_test_succeeded(name: str) -> TestResults:
        return TestResults(name, {}, [name], [], [])

    @staticmethod
    def single_test_failed(name: str) -> TestResults:
        return TestResults(
            name,
            {},
            [],
            [name],
            [],
        )

    @staticmethod
    def single_test_timed_out(name: str) -> TestResults:
        return TestResults(
            name,
            {},
            [],
            [],
            [name],
        )

    def __repr__(self) -> str:
        out = f"{self.name}: "
        out += f'{ansi.fg("green")}'
        out += f"{len(self.tests_succeeded)}/{len(self.tests_executed)} passed"
        out += f"{ansi.reset()}.\n"
        tests_with_known_status = len(self.tests_succeeded)

        if len(self.tests_failed) > 0:
            out += f'  ..{ansi.fg("red")}'
            out += f"{len(self.tests_failed)} tests failed"
            out += f"{ansi.reset()}:\n"
            for test in self.tests_failed:
                out += f"    {test}\n"
            tests_with_known_status += len(self.tests_failed)

        if len(self.tests_timed_out) > 0:
            out += f'  ..{ansi.fg("lightning yellow")}'
            out += f"{len(self.tests_timed_out)} tests timed out"
            out += f"{ansi.reset()}:\n"
            for test in self.tests_failed:
                out += f"    {test}\n"
            tests_with_known_status += len(self.tests_timed_out)

        missing = len(self.tests_executed) - tests_with_known_status
        if missing:
            out += f'  ..{ansi.fg("lightning yellow")}'
            out += f"{missing} tests aborted early"
            out += f"{ansi.reset()}\n"
        return out

    def _key(self) -> Tuple[str, Tuple, Tuple, Tuple]:
        return (
            self.name,
            tuple(self.tests_succeeded),
            tuple(self.tests_failed),
            tuple(self.tests_timed_out),
        )

    def __hash__(self) -> int:
        return hash(self._key())


class TestRunner(ABC, thread_utils.ThreadWithReturnValue):
    """A Base class for something that runs a test."""

    def __init__(self, params: TestingParameters):
        """Create a TestRunner.

        Args:
            params: Test running paramters.

        """
        super().__init__(self, target=self.begin, args=[params])
        self.params = params
        self.test_results = TestResults.empty_test_results(self.get_name())
        self.lock = threading.Lock()

    @abstractmethod
    def get_name(self) -> str:
        """The name of this test collection."""
        pass

    def get_status(self) -> TestResults:
        """Ask the TestRunner for its status."""
        with self.lock:
            return self.test_results

    @abstractmethod
    def begin(self, params: TestingParameters) -> TestResults:
        """Start execution."""
        pass


class TemplatedTestRunner(TestRunner, ABC):
    """A TestRunner that has a recipe for executing the tests."""

    def __init__(self, params: TestingParameters):
        super().__init__(params)

        # Note: because of @parallelize on run_tests it actually
        # returns a SmartFuture with a TestResult inside of it.
        # That's the reason for this Any business.
        self.running: List[Any] = []
        self.already_cancelled = False

    @abstractmethod
    def identify_tests(self) -> List[TestToRun]:
        """Return a list of tuples (test, cmdline) that should be executed."""
        pass

    @abstractmethod
    def run_test(self, test: TestToRun) -> TestResults:
        """Run a single test and return its TestResults."""
        pass

    def check_for_abort(self) -> bool:
        """Periodically called to check to see if we need to stop."""

        if self.params.halt_event.is_set():
            logger.debug("Thread %s saw halt event; exiting.", self.get_name())
            return True

        if self.params.halt_on_error and len(self.test_results.tests_failed) > 0:
            logger.debug("Thread %s saw abnormal results; exiting.", self.get_name())
            return True
        return False

    def persist_output(self, test: TestToRun, message: str, output: str) -> None:
        """Called to save the output of a test run."""

        dest = f"{test.name}-output.txt"
        with open(f"./test_output/{dest}", "w") as wf:
            print(message, file=wf)
            print("-" * len(message), file=wf)
            wf.write(output)

    def execute_commandline(
        self,
        test: TestToRun,
        *,
        timeout: float = 120.0,
    ) -> TestResults:
        """Execute a particular commandline to run a test."""

        msg = f"{self.get_name()}: {test.name} ({test.cmdline}) "
        try:
            output = exec_utils.cmd(
                test.cmdline,
                timeout_seconds=timeout,
            )
            if "***Test Failed***" in output:
                msg += "failed; doctest failure message detected."
                logger.error(msg)
                self.persist_output(test, msg, output)
                if config.config["show_failures"]:
                    print(f"Failure message:\n\n{output}")
                return TestResults.single_test_failed(test.name)

            msg += "succeeded."
            self.persist_output(test, msg, output)
            logger.debug(msg)
            return TestResults.single_test_succeeded(test.name)

        except subprocess.TimeoutExpired as e:
            msg += f"timed out after {e.timeout:.1f} seconds."
            logger.error(msg)
            logger.debug(
                "%s: %s output when it timed out: %s",
                self.get_name(),
                test.name,
                e.output,
            )
            if config.config["show_failures"]:
                print("Timeout message:\n\n" + f"{e.output.decode('utf-8')}")
            self.persist_output(test, msg, e.output.decode("utf-8"))
            return TestResults.single_test_timed_out(test.name)

        except subprocess.CalledProcessError as e:
            msg += f"failed with exit code {e.returncode}."
            logger.error(msg)
            logger.debug(
                "%s: %s output when it failed: %s", self.get_name(), test.name, e.output
            )
            if config.config["show_failures"]:
                print(
                    f"Failure exit value {e.returncode} message:\n\n"
                    + f"{e.output.decode('utf-8')}"
                )
            self.persist_output(test, msg, e.output.decode("utf-8"))
            return TestResults.single_test_failed(test.name)

    def callback(self):
        if not self.already_cancelled and self.check_for_abort():
            logger.debug(
                "%s: aborting %d running futures to exit early.",
                self.get_name(),
                len(self.running),
            )
            for x in self.running:
                x.wrapped_future.cancel()

    @overrides
    def begin(self, params: TestingParameters) -> TestResults:
        logger.debug("Thread %s started.", self.get_name())
        interesting_tests = self.identify_tests()
        logger.debug(
            "%s: Identified %d tests to be run.",
            self.get_name(),
            len(interesting_tests),
        )

        for test_to_run in interesting_tests:
            self.running.append(self.run_test(test_to_run))
            logger.debug(
                "%s: Test %s started in the background.",
                self.get_name(),
                test_to_run.name,
            )
            self.test_results.tests_executed[test_to_run.name] = time.time()

        already_seen = set()
        for result in smart_future.wait_any(
            self.running, timeout=1.0, callback=self.callback, log_exceptions=False
        ):
            if result and result not in already_seen:
                logger.debug("Test %s finished.", result.name)
                self.test_results += result
                already_seen.add(result)

            if self.check_for_abort():
                logger.error("%s: exiting early.", self.get_name())
                return self.test_results

        logger.debug("%s: executed all tests and returning normally", self.get_name())
        return self.test_results


class UnittestTestRunner(TemplatedTestRunner):
    """Run all known Unittests."""

    @overrides
    def get_name(self) -> str:
        return "Unittests"

    @overrides
    def identify_tests(self) -> List[TestToRun]:
        ret = []
        for test in file_utils.get_matching_files_recursive(ROOT, "*_test.py"):
            basename = file_utils.without_path(test)
            if basename in TESTS_TO_SKIP:
                continue
            if config.config["coverage"]:
                ret.append(
                    TestToRun(
                        name=basename,
                        kind="unittest capturing coverage",
                        cmdline=f"coverage run --source ../src {test} --unittests_ignore_perf 2>&1",
                    )
                )
                if basename in PERF_SENSATIVE_TESTS:
                    ret.append(
                        TestToRun(
                            name=f"{basename}_no_coverage",
                            kind="unittest w/o coverage to record perf",
                            cmdline=f"{test} 2>&1",
                        )
                    )
            else:
                ret.append(
                    TestToRun(
                        name=basename,
                        kind="unittest",
                        cmdline=f"{test} 2>&1",
                    )
                )
        return ret

    @par.parallelize
    def run_test(self, test: TestToRun) -> TestResults:
        return self.execute_commandline(test)


class DoctestTestRunner(TemplatedTestRunner):
    """Run all known Doctests."""

    @overrides
    def get_name(self) -> str:
        return "Doctests"

    @overrides
    def identify_tests(self) -> List[TestToRun]:
        ret = []
        out = exec_utils.cmd(f'/usr/bin/grep -lR "^ *import doctest" {ROOT}/*')
        for test in out.split("\n"):
            if re.match(r".*\.py$", test):
                basename = file_utils.without_path(test)
                if basename in TESTS_TO_SKIP:
                    continue
                if config.config["coverage"]:
                    ret.append(
                        TestToRun(
                            name=basename,
                            kind="doctest capturing coverage",
                            cmdline=f"coverage run --source ../src {test} 2>&1",
                        )
                    )
                    if basename in PERF_SENSATIVE_TESTS:
                        ret.append(
                            TestToRun(
                                name=f"{basename}_no_coverage",
                                kind="doctest w/o coverage to record perf",
                                cmdline=f"python3 {test} 2>&1",
                            )
                        )
                else:
                    ret.append(
                        TestToRun(
                            name=basename,
                            kind="doctest",
                            cmdline=f"python3 {test} 2>&1",
                        )
                    )
        return ret

    @par.parallelize
    def run_test(self, test: TestToRun) -> TestResults:
        return self.execute_commandline(test)


class IntegrationTestRunner(TemplatedTestRunner):
    """Run all know Integration tests."""

    @overrides
    def get_name(self) -> str:
        return "Integration Tests"

    @overrides
    def identify_tests(self) -> List[TestToRun]:
        ret = []
        for test in file_utils.get_matching_files_recursive(ROOT, "*_itest.py"):
            basename = file_utils.without_path(test)
            if basename in TESTS_TO_SKIP:
                continue
            if config.config["coverage"]:
                ret.append(
                    TestToRun(
                        name=basename,
                        kind="integration test capturing coverage",
                        cmdline=f"coverage run --source ../src {test} 2>&1",
                    )
                )
                if basename in PERF_SENSATIVE_TESTS:
                    ret.append(
                        TestToRun(
                            name=f"{basename}_no_coverage",
                            kind="integration test w/o coverage to capture perf",
                            cmdline=f"{test} 2>&1",
                        )
                    )
            else:
                ret.append(
                    TestToRun(
                        name=basename, kind="integration test", cmdline=f"{test} 2>&1"
                    )
                )
        return ret

    @par.parallelize
    def run_test(self, test: TestToRun) -> TestResults:
        return self.execute_commandline(test)


def test_results_report(results: Dict[str, Optional[TestResults]]) -> int:
    """Give a final report about the tests that were run."""
    total_problems = 0
    for result in results.values():
        if result is None:
            print("Unexpected unhandled exception in test runner!!!")
            total_problems += 1
        else:
            print(result, end="")
            total_problems += len(result.tests_failed)
            total_problems += len(result.tests_timed_out)

    if total_problems > 0:
        print(
            f"{ansi.bold()}Test output / logging can be found under ./test_output{ansi.reset()}"
        )
    return total_problems


def code_coverage_report():
    """Give a final code coverage report."""
    text_utils.header("Code Coverage")
    exec_utils.cmd("coverage combine .coverage*")
    out = exec_utils.cmd(
        "coverage report --omit=config-3.*.py,*_test.py,*_itest.py --sort=-cover"
    )
    print(out)
    print(
        f"""To recall this report w/o re-running the tests:

    $ {ansi.bold()}coverage report --omit=config-3.*.py,*_test.py,*_itest.py --sort=-cover{ansi.reset()}

...from the 'tests' directory.  Note that subsequent calls to
run_tests.py with --coverage will klobber previous results.  See:

    https://coverage.readthedocs.io/en/6.2/
"""
    )


@bootstrap.initialize
def main() -> Optional[int]:
    saw_flag = False
    threads: List[TestRunner] = []

    halt_event = threading.Event()
    halt_event.clear()
    params = TestingParameters(
        halt_on_error=not config.config["keep_going"],
        halt_event=halt_event,
    )

    if config.config["coverage"]:
        logger.debug('Clearing existing coverage data via "coverage erase".')
        exec_utils.cmd("coverage erase")
    if config.config["unittests"] or config.config["all"]:
        saw_flag = True
        threads.append(UnittestTestRunner(params))
    if config.config["doctests"] or config.config["all"]:
        saw_flag = True
        threads.append(DoctestTestRunner(params))
    if config.config["integration"] or config.config["all"]:
        saw_flag = True
        threads.append(IntegrationTestRunner(params))

    if not saw_flag:
        config.print_usage()
        config.error("One of --unittests, --doctests or --integration is required.", 1)

    for thread in threads:
        thread.start()

    start_time = time.time()
    last_update = start_time
    results: Dict[str, Optional[TestResults]] = {}
    still_running = {}

    while len(results) != len(threads):
        started = 0
        done = 0
        failed = 0

        for thread in threads:
            tid = thread.name
            tr = thread.get_status()
            started += len(tr.tests_executed)
            failed += len(tr.tests_failed) + len(tr.tests_timed_out)
            done += failed + len(tr.tests_succeeded)
            running = set(tr.tests_executed.keys())
            running -= set(tr.tests_failed)
            running -= set(tr.tests_succeeded)
            running -= set(tr.tests_timed_out)
            running_with_start_time = {
                test: tr.tests_executed[test] for test in running
            }
            still_running[tid] = running_with_start_time

            # Maybe print tests that are still running.
            now = time.time()
            if now - start_time > 5.0:
                if now - last_update > 3.0:
                    last_update = now
                    update = []
                    for _, running_dict in still_running.items():
                        for test_name, start_time in running_dict.items():
                            if now - start_time > 10.0:
                                update.append(f"{test_name}@{now-start_time:.1f}s")
                            else:
                                update.append(test_name)
                    print(f"\r{ansi.clear_line()}")
                    if len(update) < 4:
                        print(f'Still running: {",".join(update)}')
                    else:
                        print(f"Still running: {len(update)} tests.")

            # Maybe signal the other threads to stop too.
            if not thread.is_alive():
                if tid not in results:
                    result = thread.join()
                    if result:
                        results[tid] = result
                        if (
                            not config.config["keep_going"]
                            and (len(result.tests_failed) + len(result.tests_timed_out))
                            > 0
                        ):
                            logger.error(
                                "Thread %s returned abnormal results; killing the others.",
                                thread.get_name(),
                            )
                            halt_event.set()
                    else:
                        logger.error(
                            "Thread %s took an unhandled exception... bug in run_tests.py?!  Aborting.",
                            tid,
                        )
                        halt_event.set()
                        results[tid] = None

        color = ansi.fg("green")
        if failed > 0:
            color = ansi.fg("red")

        if started > 0:
            percent_done = done / started * 100.0
        else:
            percent_done = 0.0

        if percent_done < 100.0:
            try:
                width = text_utils.get_console_rows_columns().columns - 18
                if width < 10:
                    width = 40
            except Exception:
                width = 68

            print(
                text_utils.bar_graph_string(
                    done,
                    started,
                    text=text_utils.BarGraphText.FRACTION,
                    width=width,
                    fgcolor=color,
                ),
                end="",
                flush=True,
            )
            print(f"  {color}{now - start_time:.1f}s{ansi.reset()}", end="\r")
        time.sleep(0.1)

    print(f"{ansi.clear_line()}\n{ansi.underline()}Final Report:{ansi.reset()}")
    if config.config["coverage"]:
        code_coverage_report()
    print(f"Test suite runtime: {time.time() - start_time:.1f}s")
    total_problems = test_results_report(results)
    if total_problems > 0:
        logging.error(
            "Exiting with non-zero return code %d due to problems.", total_problems
        )
    return total_problems


if __name__ == "__main__":
    main()
