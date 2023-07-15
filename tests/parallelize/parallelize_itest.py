#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""parallelize integration test."""

import logging
import sys

from pyutils import bootstrap, decorator_utils
from pyutils.parallelize import executors
from pyutils.parallelize import parallelize as p
from pyutils.parallelize import smart_future

logger = logging.getLogger(__name__)


@p.parallelize(method=p.Method.THREAD)
def compute_factorial_thread(n):
    total = 1
    for x in range(2, n):
        total *= x
    return total


@p.parallelize(method=p.Method.PROCESS)
def compute_factorial_process(n):
    total = 1
    for x in range(2, n):
        total *= x
    return total


@p.parallelize(method=p.Method.REMOTE)
def compute_factorial_remote(n):
    total = 1
    for x in range(2, n):
        total *= x
    return total


@decorator_utils.timed
def test_thread_parallelization() -> None:
    results = []
    for _ in range(50):
        f = compute_factorial_thread(_)
        results.append(f)
    smart_future.wait_all(results)
    for future in results:
        print(f'Thread: {future}')
    texecutor = executors.DefaultExecutors().thread_pool()
    texecutor.shutdown()


@decorator_utils.timed
def test_process_parallelization() -> None:
    results = []
    for _ in range(50):
        results.append(compute_factorial_process(_))
    for future in smart_future.wait_any(results):
        print(f'Process: {future}')
    pexecutor = executors.DefaultExecutors().process_pool()
    pexecutor.shutdown()


@decorator_utils.timed
def test_remote_parallelization() -> None:
    results = []
    for _ in range(10):
        results.append(compute_factorial_remote(_))
    for result in smart_future.wait_any(results):
        print(result)
    rexecutor = executors.DefaultExecutors().remote_pool()
    rexecutor.shutdown()


@bootstrap.initialize
def main() -> None:
    test_thread_parallelization()
    test_process_parallelization()
    test_remote_parallelization()
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.exception(e)
        sys.exit(1)
