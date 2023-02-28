#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-nested-blocks

# © Copyright 2021-2023, Scott Gasch

"""
This module defines a :class:`BaseExecutor` interface and three
implementations:

    - :class:`ThreadExecutor`
    - :class:`ProcessExecutor`
    - :class:`RemoteExecutor`

The :class:`ThreadExecutor` is used to dispatch work to background
threads in the same Python process for parallelized work.  Of course,
until the Global Interpreter Lock (GIL) bottleneck is resolved, this
is not terribly useful for compute-bound code.  But it's good for
work that is mostly I/O bound.

The :class:`ProcessExecutor` is used to dispatch work to other
processes on the same machine and is more useful for compute-bound
workloads.

The :class:`RemoteExecutor` is used in conjunection with `ssh`,
the `cloudpickle` dependency, and `remote_worker.py <https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=src/pyutils/remote_worker.py;hb=HEAD>`_ file
to dispatch work to a set of remote worker machines on your
network.  You can configure this pool via a JSON configuration file,
an example of which `can be found in examples <https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=examples/parallelize_config/.remote_worker_records;hb=HEAD>`_.

Finally, this file defines a :class:`DefaultExecutors` pool that
contains a pre-created and ready instance of each of the three
executors discussed.  It has the added benefit of being automatically
cleaned up at process termination time.

See instructions in :mod:`pyutils.parallelize.parallelize` for
setting up and using the framework.
"""

from __future__ import annotations

import concurrent.futures as fut
import logging
import os
import platform
import random
import subprocess
import threading
import time
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

import cloudpickle  # type: ignore
from overrides import overrides

import pyutils.types.histogram as hist
from pyutils import (
    argparse_utils,
    config,
    dataclass_utils,
    math_utils,
    persistent,
    string_utils,
)
from pyutils.ansi import bg, fg, reset, underline
from pyutils.decorator_utils import singleton
from pyutils.exec_utils import cmd_exitcode, cmd_in_background, run_silently
from pyutils.parallelize.thread_utils import background_thread
from pyutils.types import type_utils

logger = logging.getLogger(__name__)

parser = config.add_commandline_args(
    f"Executors ({__file__})", "Args related to processing executors."
)
parser.add_argument(
    '--executors_threadpool_size',
    type=int,
    metavar='#THREADS',
    help='Number of threads in the default threadpool, leave unset for default',
    default=None,
)
parser.add_argument(
    '--executors_processpool_size',
    type=int,
    metavar='#PROCESSES',
    help='Number of processes in the default processpool, leave unset for default',
    default=None,
)
parser.add_argument(
    '--executors_schedule_remote_backups',
    default=True,
    action=argparse_utils.ActionNoYes,
    help='Should we schedule duplicative backup work if a remote bundle is slow',
)
parser.add_argument(
    '--executors_max_bundle_failures',
    type=int,
    default=3,
    metavar='#FAILURES',
    help='Maximum number of failures before giving up on a bundle',
)
parser.add_argument(
    '--remote_worker_records_file',
    type=str,
    metavar='FILENAME',
    help='Path of the remote worker records file (JSON)',
    default=f'{os.environ.get("HOME", ".")}/.remote_worker_records',
)
parser.add_argument(
    '--remote_worker_helper_path',
    type=str,
    metavar='PATH_TO_REMOTE_WORKER_PY',
    help='Path to remote_worker.py on remote machines',
    default=f'source py39-venv/bin/activate && {os.environ["HOME"]}/pyutils/src/pyutils/remote_worker.py',
)


SSH = '/usr/bin/ssh -oForwardX11=no'
SCP = '/usr/bin/scp -C'


def _make_cloud_pickle(fun, *args, **kwargs):
    """Internal helper to create cloud pickles."""
    logger.debug("Making cloudpickled bundle at %s", fun.__name__)
    return cloudpickle.dumps((fun, args, kwargs))


class BaseExecutor(ABC):
    """The base executor interface definition.  The interface for
    :class:`ProcessExecutor`, :class:`RemoteExecutor`, and
    :class:`ThreadExecutor`.
    """

    def __init__(self, *, title=''):
        """
        Args:
            title: the name of this executor.
        """
        self.title = title
        self.histogram = hist.SimpleHistogram(
            hist.SimpleHistogram.n_evenly_spaced_buckets(int(0), int(500), 50)
        )
        self.task_count = 0

    @abstractmethod
    def submit(self, function: Callable, *args, **kwargs) -> fut.Future:
        """Submit work for the executor to do.

        Args:
            function: the Callable to be executed.
            *args: the arguments to function
            **kwargs: the arguments to function

        Returns:
            A concurrent :class:`Future` representing the result of the
            work.
        """
        pass

    @abstractmethod
    def shutdown(self, *, wait: bool = True, quiet: bool = False) -> None:
        """Shutdown the executor.

        Args:
            wait: wait for the shutdown to complete before returning?
            quiet: keep it quiet, please.
        """
        pass

    def shutdown_if_idle(self, *, quiet: bool = False) -> bool:
        """Shutdown the executor and return True if the executor is idle
        (i.e. there are no pending or active tasks).  Return False
        otherwise.  Note: this should only be called by the launcher
        process.

        Args:
            quiet: keep it quiet, please.

        Returns:
            True if the executor could be shut down because it has no
            pending work, False otherwise.
        """
        if self.task_count == 0:
            self.shutdown(wait=True, quiet=quiet)
            return True
        return False

    def adjust_task_count(self, delta: int) -> None:
        """Change the task count.  Note: do not call this method from a
        worker, it should only be called by the launcher process /
        thread / machine.

        Args:
            delta: the delta value by which to adjust task count.
        """
        self.task_count += delta
        logger.debug('Adjusted task count by %d to %d.', delta, self.task_count)

    def get_task_count(self) -> int:
        """Change the task count.  Note: do not call this method from a
        worker, it should only be called by the launcher process /
        thread / machine.

        Returns:
            The executor's current task count.
        """
        return self.task_count


class ThreadExecutor(BaseExecutor):
    """A threadpool executor.  This executor uses Python threads to
    schedule tasks.  Note that, at least as of python3.10, because of
    the global lock in the interpreter itself, these do not
    parallelize very well so this class is useful mostly for non-CPU
    intensive tasks.

    See also :class:`ProcessExecutor` and :class:`RemoteExecutor`.
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Args:
            max_workers: maximum number of threads to create in the pool.
        """
        super().__init__()
        workers = None
        if max_workers is not None:
            workers = max_workers
        elif 'executors_threadpool_size' in config.config:
            workers = config.config['executors_threadpool_size']
        if workers is not None:
            logger.debug('Creating threadpool executor with %d workers', workers)
        else:
            logger.debug('Creating a default sized threadpool executor')
        self._thread_pool_executor = fut.ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="thread_executor_helper"
        )
        self.already_shutdown = False

    # This is run on a different thread; do not adjust task count here.
    @staticmethod
    def _run_local_bundle(fun, *args, **kwargs):
        logger.debug("Running local bundle at %s", fun.__name__)
        result = fun(*args, **kwargs)
        return result

    @overrides
    def submit(self, function: Callable, *args, **kwargs) -> fut.Future:
        if self.already_shutdown:
            raise Exception('Submitted work after shutdown.')
        self.adjust_task_count(+1)
        newargs = []
        newargs.append(function)
        for arg in args:
            newargs.append(arg)
        start = time.time()
        result = self._thread_pool_executor.submit(
            ThreadExecutor._run_local_bundle, *newargs, **kwargs
        )
        result.add_done_callback(lambda _: self.histogram.add_item(time.time() - start))
        result.add_done_callback(lambda _: self.adjust_task_count(-1))
        return result

    @overrides
    def shutdown(self, *, wait: bool = True, quiet: bool = False) -> None:
        if not self.already_shutdown:
            logger.debug('Shutting down threadpool executor %s', self.title)
            self._thread_pool_executor.shutdown(wait)
            if not quiet:
                print(self.histogram.__repr__(label_formatter='%ds'))
            self.already_shutdown = True


class ProcessExecutor(BaseExecutor):
    """An executor which runs tasks in child processes.

    See also :class:`ThreadExecutor` and :class:`RemoteExecutor`.
    """

    def __init__(self, max_workers=None):
        """
        Args:
            max_workers: the max number of worker processes to create.
        """
        super().__init__()
        workers = None
        if max_workers is not None:
            workers = max_workers
        elif 'executors_processpool_size' in config.config:
            workers = config.config['executors_processpool_size']
        if workers is not None:
            logger.debug('Creating processpool executor with %d workers.', workers)
        else:
            logger.debug('Creating a default sized processpool executor')
        self._process_executor = fut.ProcessPoolExecutor(
            max_workers=workers,
        )
        self.already_shutdown = False

    # This is run in another process; do not adjust task count here.
    @staticmethod
    def _run_cloud_pickle(pickle):
        fun, args, kwargs = cloudpickle.loads(pickle)
        logger.debug("Running pickled bundle at %s", fun.__name__)
        result = fun(*args, **kwargs)
        return result

    @overrides
    def submit(self, function: Callable, *args, **kwargs) -> fut.Future:
        if self.already_shutdown:
            raise Exception('Submitted work after shutdown.')
        start = time.time()
        self.adjust_task_count(+1)
        pickle = _make_cloud_pickle(function, *args, **kwargs)
        result = self._process_executor.submit(
            ProcessExecutor._run_cloud_pickle, pickle
        )
        result.add_done_callback(lambda _: self.histogram.add_item(time.time() - start))
        result.add_done_callback(lambda _: self.adjust_task_count(-1))
        return result

    @overrides
    def shutdown(self, *, wait: bool = True, quiet: bool = False) -> None:
        if not self.already_shutdown:
            logger.debug('Shutting down processpool executor %s', self.title)
            self._process_executor.shutdown(wait)
            if not quiet:
                print(self.histogram.__repr__(label_formatter='%ds'))
            self.already_shutdown = True

    def __getstate__(self):
        state = self.__dict__.copy()
        state['_process_executor'] = None
        return state


class RemoteExecutorException(Exception):
    """Thrown when a bundle cannot be executed despite several retries."""

    pass


@dataclass
class RemoteWorkerRecord:
    """A record of info about a remote worker."""

    username: str
    """Username we can ssh into on this machine to run work."""

    machine: str
    """Machine address / name."""

    weight: int
    """Relative probability for the weighted policy to select this
    machine for scheduling work."""

    count: int
    """If this machine is selected, what is the maximum number of task
    that it can handle?"""

    def __hash__(self):
        return hash((self.username, self.machine))

    def __repr__(self):
        return f'{self.username}@{self.machine}'


@dataclass
class BundleDetails:
    """All info necessary to define some unit of work that needs to be
    done, where it is being run, its state, whether it is an original
    bundle of a backup bundle, how many times it has failed, etc...
    """

    pickled_code: bytes
    """The code to run, cloud pickled"""

    uuid: str
    """A unique identifier"""

    function_name: str
    """The name of the function we pickled"""

    worker: Optional[RemoteWorkerRecord]
    """The remote worker running this bundle or None if none (yet)"""

    username: Optional[str]
    """The remote username running this bundle or None if none (yet)"""

    machine: Optional[str]
    """The remote machine running this bundle or None if none (yet)"""

    controller: str
    """The controller machine"""

    code_file: str
    """A unique filename to hold the work to be done"""

    result_file: str
    """Where the results should be placed / read from"""

    pid: int
    """The process id of the local subprocess watching the ssh connection
    to the remote machine"""

    start_ts: float
    """Starting time"""

    end_ts: float
    """Ending time"""

    slower_than_local_p95: bool
    """Currently slower then 95% of other bundles on remote host"""

    slower_than_global_p95: bool
    """Currently slower than 95% of other bundles globally"""

    src_bundle: Optional[BundleDetails]
    """If this is a backup bundle, this points to the original bundle
    that it's backing up.  None otherwise."""

    is_cancelled: threading.Event
    """An event that can be signaled to indicate this bundle is cancelled.
    This is set when another copy (backup or original) of this work has
    completed successfully elsewhere."""

    was_cancelled: bool
    """True if this bundle was cancelled, False if it finished normally"""

    backup_bundles: Optional[List[BundleDetails]]
    """If we've created backups of this bundle, this is the list of them"""

    failure_count: int
    """How many times has this bundle failed already?"""

    def __repr__(self):
        uuid = self.uuid
        if uuid[-9:-2] == '_backup':
            uuid = uuid[:-9]
            suffix = f'{uuid[-6:]}_b{self.uuid[-1:]}'
        else:
            suffix = uuid[-6:]

        # We colorize the uuid based on some bits from it to make them
        # stand out in the logging and help a reader correlate log messages
        # related to the same bundle.
        colorz = [
            fg('violet red'),
            fg('red'),
            fg('orange'),
            fg('peach orange'),
            fg('yellow'),
            fg('marigold yellow'),
            fg('green yellow'),
            fg('tea green'),
            fg('cornflower blue'),
            fg('turquoise blue'),
            fg('tropical blue'),
            fg('lavender purple'),
            fg('medium purple'),
        ]
        c = colorz[int(uuid[-2:], 16) % len(colorz)]
        function_name = (
            self.function_name if self.function_name is not None else 'nofname'
        )
        machine = self.machine if self.machine is not None else 'nomachine'
        return f'{c}{suffix}/{function_name}/{machine}{reset()}'


class RemoteExecutorStatus:
    """A status 'scoreboard' for a remote executor tracking various
    metrics and able to render a periodic dump of global state.
    """

    def __init__(self, total_worker_count: int) -> None:
        """
        Args:
            total_worker_count: number of workers in the pool
        """
        self.worker_count: int = total_worker_count
        self.known_workers: Set[RemoteWorkerRecord] = set()
        self.start_time: float = time.time()
        self.start_per_bundle: Dict[str, Optional[float]] = defaultdict(float)
        self.end_per_bundle: Dict[str, float] = defaultdict(float)
        self.finished_bundle_timings_per_worker: Dict[
            RemoteWorkerRecord, math_utils.NumericPopulation
        ] = {}
        self.in_flight_bundles_by_worker: Dict[RemoteWorkerRecord, Set[str]] = {}
        self.bundle_details_by_uuid: Dict[str, BundleDetails] = {}
        self.finished_bundle_timings: math_utils.NumericPopulation = (
            math_utils.NumericPopulation()
        )
        self.last_periodic_dump: Optional[float] = None
        self.total_bundles_submitted: int = 0

        # Protects reads and modification using self.  Also used
        # as a memory fence for modifications to bundle.
        self.lock: threading.Lock = threading.Lock()

    def record_acquire_worker(self, worker: RemoteWorkerRecord, uuid: str) -> None:
        """Record that bundle with uuid is assigned to a particular worker.

        Args:
            worker: the record of the worker to which uuid is assigned
            uuid: the uuid of a bundle that has been assigned to a worker
        """
        with self.lock:
            self.record_acquire_worker_already_locked(worker, uuid)

    def record_acquire_worker_already_locked(
        self, worker: RemoteWorkerRecord, uuid: str
    ) -> None:
        """Same as above but an entry point that doesn't acquire the lock
        for codepaths where it's already held."""
        assert self.lock.locked()
        self.known_workers.add(worker)
        self.start_per_bundle[uuid] = None
        x = self.in_flight_bundles_by_worker.get(worker, set())
        x.add(uuid)
        self.in_flight_bundles_by_worker[worker] = x

    def record_bundle_details(self, details: BundleDetails) -> None:
        """Register the details about a bundle of work."""
        with self.lock:
            self.record_bundle_details_already_locked(details)

    def record_bundle_details_already_locked(self, details: BundleDetails) -> None:
        """Same as above but for codepaths that already hold the lock."""
        assert self.lock.locked()
        self.bundle_details_by_uuid[details.uuid] = details

    def record_release_worker(
        self,
        worker: RemoteWorkerRecord,
        uuid: str,
        was_cancelled: bool,
    ) -> None:
        """Record that a bundle has released a worker."""
        with self.lock:
            self.record_release_worker_already_locked(worker, uuid, was_cancelled)

    def record_release_worker_already_locked(
        self,
        worker: RemoteWorkerRecord,
        uuid: str,
        was_cancelled: bool,
    ) -> None:
        """Same as above but for codepaths that already hold the lock."""
        assert self.lock.locked()
        ts = time.time()
        self.end_per_bundle[uuid] = ts
        self.in_flight_bundles_by_worker[worker].remove(uuid)
        if not was_cancelled:
            start = self.start_per_bundle[uuid]
            assert start is not None
            bundle_latency = ts - start
            x = self.finished_bundle_timings_per_worker.get(
                worker, math_utils.NumericPopulation()
            )
            x.add_number(bundle_latency)
            self.finished_bundle_timings_per_worker[worker] = x
            self.finished_bundle_timings.add_number(bundle_latency)

    def record_processing_began(self, uuid: str):
        """Record when work on a bundle begins."""
        with self.lock:
            self.start_per_bundle[uuid] = time.time()

    def total_in_flight(self) -> int:
        """How many bundles are in flight currently?"""
        assert self.lock.locked()
        total_in_flight = 0
        for worker in self.known_workers:
            total_in_flight += len(self.in_flight_bundles_by_worker[worker])
        return total_in_flight

    def total_idle(self) -> int:
        """How many idle workers are there currently?"""
        assert self.lock.locked()
        return self.worker_count - self.total_in_flight()

    def __repr__(self):
        assert self.lock.locked()
        ts = time.time()
        total_finished = len(self.finished_bundle_timings)
        total_in_flight = self.total_in_flight()
        ret = f'\n\n{underline()}Remote Executor Pool Status{reset()}: '
        qall_median = None
        qall_p95 = None
        if len(self.finished_bundle_timings) > 1:
            qall_median = self.finished_bundle_timings.get_median()
            qall_p95 = self.finished_bundle_timings.get_percentile(95)
            ret += (
                f'⏱=∀p50:{qall_median:.1f}s, ∀p95:{qall_p95:.1f}s, total={ts-self.start_time:.1f}s, '
                f'✅={total_finished}/{self.total_bundles_submitted}, '
                f'💻n={total_in_flight}/{self.worker_count}\n'
            )
        else:
            ret += (
                f'⏱={ts-self.start_time:.1f}s, '
                f'✅={total_finished}/{self.total_bundles_submitted}, '
                f'💻n={total_in_flight}/{self.worker_count}\n'
            )

        for worker in self.known_workers:
            ret += f'  {fg("lightning yellow")}{worker.machine}{reset()}: '
            timings = self.finished_bundle_timings_per_worker.get(
                worker, math_utils.NumericPopulation()
            )
            count = len(timings)
            qworker_median = None
            qworker_p95 = None
            if count > 1:
                qworker_median = timings.get_median()
                qworker_p95 = timings.get_percentile(95)
                ret += f' 💻p50: {qworker_median:.1f}s, 💻p95: {qworker_p95:.1f}s\n'
            else:
                ret += '\n'
            if count > 0:
                ret += f'    ...finished {count} total bundle(s) so far\n'
            in_flight = len(self.in_flight_bundles_by_worker[worker])
            if in_flight > 0:
                ret += f'    ...{in_flight} bundles currently in flight:\n'
                for bundle_uuid in self.in_flight_bundles_by_worker[worker]:
                    details = self.bundle_details_by_uuid.get(bundle_uuid, None)
                    pid = str(details.pid) if (details and details.pid != 0) else "TBD"
                    if self.start_per_bundle[bundle_uuid] is not None:
                        sec = ts - self.start_per_bundle[bundle_uuid]
                        ret += f'       (pid={pid}): {details} for {sec:.1f}s so far '
                    else:
                        ret += f'       {details} setting up / copying data...'
                        sec = 0.0

                    if qworker_p95 is not None:
                        if sec > qworker_p95:
                            ret += f'{bg("red")}>💻p95{reset()} '
                            if details is not None:
                                details.slower_than_local_p95 = True
                        else:
                            if details is not None:
                                details.slower_than_local_p95 = False

                    if qall_p95 is not None:
                        if sec > qall_p95:
                            ret += f'{bg("red")}>∀p95{reset()} '
                            if details is not None:
                                details.slower_than_global_p95 = True
                        else:
                            details.slower_than_global_p95 = False
                    ret += '\n'
        return ret

    def periodic_dump(self, total_bundles_submitted: int) -> None:
        assert self.lock.locked()
        self.total_bundles_submitted = total_bundles_submitted
        ts = time.time()
        if self.last_periodic_dump is None or ts - self.last_periodic_dump > 5.0:
            print(self)
            self.last_periodic_dump = ts


class RemoteWorkerSelectionPolicy(ABC):
    """An interface definition of a policy for selecting a remote worker."""

    def __init__(self):
        self.workers: Optional[List[RemoteWorkerRecord]] = None

    def register_worker_pool(self, workers: List[RemoteWorkerRecord]):
        self.workers = workers

    @abstractmethod
    def is_worker_available(self) -> bool:
        pass

    @abstractmethod
    def acquire_worker(self, machine_to_avoid=None) -> Optional[RemoteWorkerRecord]:
        pass


class WeightedRandomRemoteWorkerSelectionPolicy(RemoteWorkerSelectionPolicy):
    """A remote worker selector that uses weighted RNG."""

    @overrides
    def is_worker_available(self) -> bool:
        if self.workers:
            for worker in self.workers:
                if worker.count > 0:
                    return True
        return False

    @overrides
    def acquire_worker(self, machine_to_avoid=None) -> Optional[RemoteWorkerRecord]:
        grabbag = []
        if self.workers:
            for worker in self.workers:
                if worker.machine != machine_to_avoid:
                    if worker.count > 0:
                        for _ in range(worker.count * worker.weight):
                            grabbag.append(worker)

        if len(grabbag) == 0:
            logger.debug(
                'There are no available workers that avoid %s', machine_to_avoid
            )
            if self.workers:
                for worker in self.workers:
                    if worker.count > 0:
                        for _ in range(worker.count * worker.weight):
                            grabbag.append(worker)

        if len(grabbag) == 0:
            logger.warning('There are no available workers?!')
            return None

        worker = random.sample(grabbag, 1)[0]
        assert worker.count > 0
        worker.count -= 1
        logger.debug('Selected worker %s', worker)
        return worker


class RoundRobinRemoteWorkerSelectionPolicy(RemoteWorkerSelectionPolicy):
    """A remote worker selector that just round robins."""

    def __init__(self) -> None:
        super().__init__()
        self.index = 0

    @overrides
    def is_worker_available(self) -> bool:
        if self.workers:
            for worker in self.workers:
                if worker.count > 0:
                    return True
        return False

    @overrides
    def acquire_worker(
        self, machine_to_avoid: str = None
    ) -> Optional[RemoteWorkerRecord]:
        if self.workers:
            x = self.index
            while True:
                worker = self.workers[x]
                if worker.count > 0:
                    worker.count -= 1
                    x += 1
                    if x >= len(self.workers):
                        x = 0
                    self.index = x
                    logger.debug('Selected worker %s', worker)
                    return worker
                x += 1
                if x >= len(self.workers):
                    x = 0
                if x == self.index:
                    logger.warning('Unexpectedly could not find a worker, retrying...')
                    return None
        return None


class RemoteExecutor(BaseExecutor):
    """An executor that uses processes on remote machines to do work.
    To do so, it requires that a pool of remote workers to be properly
    configured.  See instructions in
    :class:`pyutils.parallelize.parallelize`.

    Each machine in a worker pool has a *weight* and a *count*.  A
    *weight* captures the relative speed of a processor on that worker
    and a *count* captures the number of synchronous tasks the worker
    can accept (i.e. the number of cpus on the machine).

    To dispatch work to a remote machine, this class pickles the code
    to be executed remotely using `cloudpickle`.  For that to work,
    the remote machine should be running the same version of Python as
    this machine, ideally in a virtual environment with the same
    import libraries installed.  Differences in operating system
    and/or processor architecture don't seem to matter for most code,
    though.

    .. warning::

        Mismatches in Python version or in the version numbers of
        third-party libraries between machines can cause problems
        when trying to unpickle and run code remotely.

    Work to be dispatched is represented in this code by creating a
    "bundle".  Each bundle is assigned to a remote worker based on
    heuristics captured in a :class:`RemoteWorkerSelectionPolicy`.  In
    general, it attempts to load all workers in the pool and maximize
    throughput.  Once assigned to a remote worker, pickled code is
    copied to that worker via `scp` and a remote command is issued via
    `ssh` to execute a :file:`remote_worker.py` process on the remote
    machine.  This process unpickles the code, runs it, and produces a
    result which is then copied back to the local machine (again via
    `scp`) where it can be processed by local code.

    You can and probably must override the path of
    :file:`remote_worker.py` on your pool machines using the
    `--remote_worker_helper_path` commandline argument (or by just
    changing the default in code, see above in this file's code).

    During remote work execution, this local machine acts as a
    controller dispatching all work to the network, copying pickled
    tasks out, and copying results back in.  It may also be a worker
    in the pool but do not underestimate the cost of being a
    controller -- it takes some cpu and a lot of network bandwidth.
    The work dispatcher logic attempts to detect when a controller is
    also a worker and reduce its load.

    Some redundancy and safety provisions are made when scheduling
    tasks to the worker pool; e.g. slower than expected tasks have
    redundant backups tasks created, especially if there are otherwise
    idle workers.  If a task fails repeatedly, the dispatcher consider
    it poisoned and give up on it.

    .. warning::

        This executor probably only makes sense to use with
        computationally expensive tasks such as jobs that will execute
        for ~30 seconds or longer.

        The network overhead and latency of copying work from the
        controller (local) machine to the remote workers and copying
        results back again is relatively high.  Especially at startup,
        the network can become a bottleneck.  Future versions of this
        code may attempt to split the responsibility of being a
        controller (distributing work to pool machines).

    Instructions for how to set this up are provided in
    :class:`pyutils.parallelize.parallelize`.

    See also :class:`ProcessExecutor` and :class:`ThreadExecutor`.

    """

    def __init__(
        self,
        workers: List[RemoteWorkerRecord],
        policy: RemoteWorkerSelectionPolicy,
    ) -> None:
        """
        Args:
            workers: A list of remote workers we can call on to do tasks.
            policy: A policy for selecting remote workers for tasks.
        """

        super().__init__()
        self.workers = workers
        self.policy = policy
        self.worker_count = 0
        for worker in self.workers:
            self.worker_count += worker.count
        if self.worker_count <= 0:
            msg = f"We need somewhere to schedule work; count was {self.worker_count}"
            logger.critical(msg)
            raise RemoteExecutorException(msg)
        self.policy.register_worker_pool(self.workers)
        self.cv = threading.Condition()
        logger.debug(
            'Creating %d local threads, one per remote worker.', self.worker_count
        )
        self._helper_executor = fut.ThreadPoolExecutor(
            thread_name_prefix="remote_executor_helper",
            max_workers=self.worker_count,
        )
        self.status = RemoteExecutorStatus(self.worker_count)
        self.total_bundles_submitted = 0
        self.backup_lock = threading.Lock()
        self.last_backup = None
        (
            self.heartbeat_thread,
            self.heartbeat_stop_event,
        ) = self._run_periodic_heartbeat()
        self.already_shutdown = False

    @background_thread
    def _run_periodic_heartbeat(self, stop_event: threading.Event) -> None:
        """
        We create a background thread to invoke :meth:`_heartbeat` regularly
        while we are scheduling work.  It does some accounting such as
        looking for slow bundles to tag for backup creation, checking for
        unexpected failures, and printing a fancy message on stdout.
        """
        while not stop_event.is_set():
            time.sleep(5.0)
            logger.debug('Running periodic heartbeat code...')
            self._heartbeat()
        logger.debug('Periodic heartbeat thread shutting down.')

    def _heartbeat(self) -> None:
        # Note: this is invoked on a background thread, not an
        # executor thread.  Be careful what you do with it b/c it
        # needs to get back and dump status again periodically.
        with self.status.lock:
            self.status.periodic_dump(self.total_bundles_submitted)

            # Look for bundles to reschedule via executor.submit
            if config.config['executors_schedule_remote_backups']:
                self._maybe_schedule_backup_bundles()

    def _maybe_schedule_backup_bundles(self):
        """Maybe schedule backup bundles if we see a very slow bundle."""

        assert self.status.lock.locked()
        num_done = len(self.status.finished_bundle_timings)
        num_idle_workers = self.worker_count - self.task_count
        now = time.time()
        if (
            num_done >= 2
            and num_idle_workers > 0
            and (self.last_backup is None or (now - self.last_backup > 9.0))
            and self.backup_lock.acquire(blocking=False)
        ):
            try:
                assert self.backup_lock.locked()

                bundle_to_backup = None
                best_score = None
                for (
                    worker,
                    bundle_uuids,
                ) in self.status.in_flight_bundles_by_worker.items():

                    # Prefer to schedule backups of bundles running on
                    # slower machines.
                    base_score = 0
                    for record in self.workers:
                        if worker.machine == record.machine:
                            temp_score = float(record.weight)
                            temp_score = 1.0 / temp_score
                            temp_score *= 200.0
                            base_score = int(temp_score)
                            break

                    for uuid in bundle_uuids:
                        bundle = self.status.bundle_details_by_uuid.get(uuid, None)
                        if (
                            bundle is not None
                            and bundle.src_bundle is None
                            and bundle.backup_bundles is not None
                        ):
                            score = base_score

                            # Schedule backups of bundles running
                            # longer; especially those that are
                            # unexpectedly slow.
                            start_ts = self.status.start_per_bundle[uuid]
                            if start_ts is not None:
                                runtime = now - start_ts
                                score += runtime
                                logger.debug(
                                    'score[%s] => %.1f  # latency boost', bundle, score
                                )

                                if bundle.slower_than_local_p95:
                                    score += runtime / 2
                                    logger.debug(
                                        'score[%s] => %.1f  # >worker p95',
                                        bundle,
                                        score,
                                    )

                                if bundle.slower_than_global_p95:
                                    score += runtime / 4
                                    logger.debug(
                                        'score[%s] => %.1f  # >global p95',
                                        bundle,
                                        score,
                                    )

                            # Prefer backups of bundles that don't
                            # have backups already.
                            backup_count = len(bundle.backup_bundles)
                            if backup_count == 0:
                                score *= 2
                            elif backup_count == 1:
                                score /= 2
                            elif backup_count == 2:
                                score /= 8
                            else:
                                score = 0
                            logger.debug(
                                'score[%s] => %.1f  # {backup_count} dup backup factor',
                                bundle,
                                score,
                            )

                            if score != 0 and (
                                best_score is None or score > best_score
                            ):
                                bundle_to_backup = bundle
                                assert bundle is not None
                                assert bundle.backup_bundles is not None
                                assert bundle.src_bundle is None
                                best_score = score

                # Note: this is all still happening on the heartbeat
                # runner thread.  That's ok because
                # _schedule_backup_for_bundle uses the executor to
                # submit the bundle again which will cause it to be
                # picked up by a worker thread and allow this thread
                # to return to run future heartbeats.
                if bundle_to_backup is not None:
                    self.last_backup = now
                    logger.info(
                        '=====> SCHEDULING BACKUP %s (score=%.1f) <=====',
                        bundle_to_backup,
                        best_score,
                    )
                    self._schedule_backup_for_bundle(bundle_to_backup)
            finally:
                self.backup_lock.release()

    def _is_worker_available(self) -> bool:
        """Is there a worker available currently?"""
        return self.policy.is_worker_available()

    def _acquire_worker(
        self, machine_to_avoid: str = None
    ) -> Optional[RemoteWorkerRecord]:
        """Try to acquire a worker."""
        return self.policy.acquire_worker(machine_to_avoid)

    def _find_available_worker_or_block(
        self, machine_to_avoid: str = None
    ) -> RemoteWorkerRecord:
        """Find a worker or block until one becomes available."""
        with self.cv:
            while not self._is_worker_available():
                self.cv.wait()
            worker = self._acquire_worker(machine_to_avoid)
            if worker is not None:
                return worker
        msg = "We should never reach this point in the code"
        logger.critical(msg)
        raise Exception(msg)

    def _release_worker(self, bundle: BundleDetails, *, was_cancelled=True) -> None:
        """Release a previously acquired worker."""
        worker = bundle.worker
        assert worker is not None
        logger.debug('Released worker %s', worker)
        self.status.record_release_worker(
            worker,
            bundle.uuid,
            was_cancelled,
        )
        with self.cv:
            worker.count += 1
            self.cv.notify()
        self.adjust_task_count(-1)

    def _check_if_cancelled(self, bundle: BundleDetails) -> bool:
        """See if a particular bundle is cancelled.  Do not block."""
        with self.status.lock:
            if bundle.is_cancelled.wait(timeout=0.0):
                logger.debug('Bundle %s is cancelled, bail out.', bundle.uuid)
                bundle.was_cancelled = True
                return True
        return False

    def _launch(self, bundle: BundleDetails, override_avoid_machine=None) -> Any:
        """Find a worker for bundle or block until one is available."""

        self.adjust_task_count(+1)
        uuid = bundle.uuid
        controller = bundle.controller
        avoid_machine = override_avoid_machine
        is_original = bundle.src_bundle is None

        # Try not to schedule a backup on the same host as the original.
        if avoid_machine is None and bundle.src_bundle is not None:
            avoid_machine = bundle.src_bundle.machine
        worker = None
        while worker is None:
            worker = self._find_available_worker_or_block(avoid_machine)
        assert worker is not None

        # Ok, found a worker.
        bundle.worker = worker
        machine = bundle.machine = worker.machine
        username = bundle.username = worker.username
        self.status.record_acquire_worker(worker, uuid)
        logger.debug('%s: Running bundle on %s...', bundle, worker)

        # Before we do any work, make sure the bundle is still viable.
        # It may have been some time between when it was submitted and
        # now due to lack of worker availability and someone else may
        # have already finished it.
        if self._check_if_cancelled(bundle):
            try:
                return self._process_work_result(bundle)
            except Exception:
                logger.warning(
                    '%s: bundle says it\'s cancelled upfront but no results?!', bundle
                )
                self._release_worker(bundle)
                if is_original:
                    # Weird.  We are the original owner of this
                    # bundle.  For it to have been cancelled, a backup
                    # must have already started and completed before
                    # we even for started.  Moreover, the backup says
                    # it is done but we can't find the results it
                    # should have copied over.  Reschedule the whole
                    # thing.
                    logger.exception(
                        '%s: We are the original owner thread and yet there are '
                        'no results for this bundle.  This is unexpected and bad. '
                        'Attempting an emergency retry...',
                        bundle,
                    )
                    return self._emergency_retry_nasty_bundle(bundle)
                else:
                    # We're a backup and our bundle is cancelled
                    # before we even got started.  Do nothing and let
                    # the original bundle's thread worry about either
                    # finding the results or complaining about it.
                    return None

        # Send input code / data to worker machine if it's not local.
        if controller not in machine:
            try:
                cmd = (
                    f'{SCP} {bundle.code_file} {username}@{machine}:{bundle.code_file}'
                )
                start_ts = time.time()
                logger.info("%s: Copying work to %s via %s.", bundle, worker, cmd)
                run_silently(cmd)
                xfer_latency = time.time() - start_ts
                logger.debug(
                    "%s: Copying to %s took %.1fs.", bundle, worker, xfer_latency
                )
            except Exception:
                self._release_worker(bundle)
                if is_original:
                    # Weird.  We tried to copy the code to the worker
                    # and it failed...  And we're the original bundle.
                    # We have to retry.
                    logger.exception(
                        "%s: Failed to send instructions to the worker machine?! "
                        "This is not expected; we\'re the original bundle so this shouldn\'t "
                        "be a race condition.  Attempting an emergency retry...",
                        bundle,
                    )
                    return self._emergency_retry_nasty_bundle(bundle)
                else:
                    # This is actually expected; we're a backup.
                    # There's a race condition where someone else
                    # already finished the work and removed the source
                    # code_file before we could copy it.  Ignore.
                    logger.warning(
                        '%s: Failed to send instructions to the worker machine... '
                        'We\'re a backup and this may be caused by the original (or '
                        'some other backup) already finishing this work.  Ignoring.',
                        bundle,
                    )
                    return None

        # Kick off the work.  Note that if this fails we let
        # _wait_for_process deal with it.
        self.status.record_processing_began(uuid)
        helper_path = config.config['remote_worker_helper_path']
        cmd = (
            f'{SSH} {bundle.username}@{bundle.machine} '
            f'"{helper_path} --code_file {bundle.code_file} --result_file {bundle.result_file}"'
        )
        logger.debug(
            '%s: Executing %s in the background to kick off work...', bundle, cmd
        )
        p = cmd_in_background(cmd, silent=True)
        bundle.pid = p.pid
        logger.debug(
            '%s: Local ssh process pid=%d; remote worker is %s.', bundle, p.pid, machine
        )
        return self._wait_for_process(p, bundle, 0)

    def _wait_for_process(
        self, p: Optional[subprocess.Popen], bundle: BundleDetails, depth: int
    ) -> Any:
        """At this point we've copied the bundle's pickled code to the remote
        worker and started an ssh process that should be invoking the
        remote worker to have it execute the user's code.  See how
        that's going and wait for it to complete or fail.  Note that
        this code is recursive: there are codepaths where we decide to
        stop waiting for an ssh process (because another backup seems
        to have finished) but then fail to fetch or parse the results
        from that backup and thus call ourselves to continue waiting
        on an active ssh process.  This is the purpose of the depth
        argument: to curtail potential infinite recursion by giving up
        eventually.

        Args:
            p: the Popen record of the ssh job
            bundle: the bundle of work being executed remotely
            depth: how many retries we've made so far.  Starts at zero.

        """

        machine = bundle.machine
        assert p is not None
        pid = p.pid  # pid of the ssh process
        if depth > 3:
            logger.error(
                "I've gotten repeated errors waiting on this bundle; giving up on pid=%d",
                pid,
            )
            p.terminate()
            self._release_worker(bundle)
            return self._emergency_retry_nasty_bundle(bundle)

        # Spin until either the ssh job we scheduled finishes the
        # bundle or some backup worker signals that they finished it
        # before we could.
        while True:
            try:
                p.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                if self._check_if_cancelled(bundle):
                    logger.info(
                        '%s: looks like another worker finished bundle...', bundle
                    )
                    break
            else:
                logger.info("%s: pid %d (%s) is finished!", bundle, pid, machine)
                p = None
                break

        # If we get here we believe the bundle is done; either the ssh
        # subprocess finished (hopefully successfully) or we noticed
        # that some other worker seems to have completed the bundle
        # before us and we're bailing out.
        try:
            ret = self._process_work_result(bundle)
            if ret is not None and p is not None:
                p.terminate()
            return ret

        # Something went wrong; e.g. we could not copy the results
        # back, cleanup after ourselves on the remote machine, or
        # unpickle the results we got from the remove machine.  If we
        # still have an active ssh subprocess, keep waiting on it.
        # Otherwise, time for an emergency reschedule.
        except Exception:
            logger.exception('%s: Something unexpected just happened...', bundle)
            if p is not None:
                logger.warning(
                    "%s: Failed to wrap up \"done\" bundle, re-waiting on active ssh.",
                    bundle,
                )
                return self._wait_for_process(p, bundle, depth + 1)
            else:
                self._release_worker(bundle)
                return self._emergency_retry_nasty_bundle(bundle)

    def _process_work_result(self, bundle: BundleDetails) -> Any:
        """A bundle seems to be completed.  Check on the results."""

        with self.status.lock:
            is_original = bundle.src_bundle is None
            was_cancelled = bundle.was_cancelled
            username = bundle.username
            machine = bundle.machine
            result_file = bundle.result_file
            code_file = bundle.code_file

            # Whether original or backup, if we finished first we must
            # fetch the results if the computation happened on a
            # remote machine.
            bundle.end_ts = time.time()
            if not was_cancelled:
                assert bundle.machine is not None
                if bundle.controller not in bundle.machine:
                    cmd = f'{SCP} {username}@{machine}:{result_file} {result_file} 2>/dev/null'
                    logger.info(
                        "%s: Fetching results back from %s@%s via %s",
                        bundle,
                        username,
                        machine,
                        cmd,
                    )

                    # If either of these throw they are handled in
                    # _wait_for_process.
                    attempts = 0
                    while True:
                        try:
                            run_silently(cmd)
                        except Exception as e:
                            attempts += 1
                            if attempts >= 3:
                                raise e
                        else:
                            break

                    # Cleanup remote /tmp files.
                    run_silently(
                        f'{SSH} {username}@{machine}'
                        f' "/bin/rm -f {code_file} {result_file}"'
                    )
                    logger.debug(
                        'Fetching results back took %.2fs', time.time() - bundle.end_ts
                    )
                dur = bundle.end_ts - bundle.start_ts
                self.histogram.add_item(dur)

        # Only the original worker should unpickle the file contents
        # though since it's the only one whose result matters.  The
        # original is also the only job that may delete result_file
        # from disk.  Note that the original may have been cancelled
        # if one of the backups finished first; it still must read the
        # result from disk.  It still does that here with is_cancelled
        # set.
        if is_original:
            logger.debug("%s: Unpickling %s.", bundle, result_file)
            try:
                with open(result_file, 'rb') as rb:
                    serialized = rb.read()
                result = cloudpickle.loads(serialized)
            except Exception as e:
                logger.exception('Failed to load %s... this is bad news.', result_file)
                self._release_worker(bundle)

                # Re-raise the exception; the code in _wait_for_process may
                # decide to _emergency_retry_nasty_bundle here.
                raise e
            logger.debug('Removing local (master) %s and %s.', code_file, result_file)
            os.remove(result_file)
            os.remove(code_file)

            # Notify any backups that the original is done so they
            # should stop ASAP.  Do this whether or not we
            # finished first since there could be more than one
            # backup.
            if bundle.backup_bundles is not None:
                for backup in bundle.backup_bundles:
                    logger.debug(
                        '%s: Notifying backup %s that it\'s cancelled',
                        bundle,
                        backup.uuid,
                    )
                    backup.is_cancelled.set()

        # This is a backup job and, by now, we have already fetched
        # the bundle results.
        else:
            # Backup results don't matter, they just need to leave the
            # result file in the right place for their originals to
            # read/unpickle later.
            result = None

            # Tell the original to stop if we finished first.
            if not was_cancelled:
                orig_bundle = bundle.src_bundle
                assert orig_bundle is not None
                logger.debug(
                    '%s: Notifying original %s we beat them to it.',
                    bundle,
                    orig_bundle.uuid,
                )
                orig_bundle.is_cancelled.set()
        self._release_worker(bundle, was_cancelled=was_cancelled)
        return result

    def _create_original_bundle(self, pickle, function_name: str):
        """Creates a bundle that is not a backup of any other bundle but
        rather represents a user task.
        """

        uuid = string_utils.generate_uuid(omit_dashes=True)
        code_file = f'/tmp/{uuid}.code.bin'
        result_file = f'/tmp/{uuid}.result.bin'

        logger.debug('Writing pickled code to %s', code_file)
        with open(code_file, 'wb') as wb:
            wb.write(pickle)

        bundle = BundleDetails(
            pickled_code=pickle,
            uuid=uuid,
            function_name=function_name,
            worker=None,
            username=None,
            machine=None,
            controller=platform.node(),
            code_file=code_file,
            result_file=result_file,
            pid=0,
            start_ts=time.time(),
            end_ts=0.0,
            slower_than_local_p95=False,
            slower_than_global_p95=False,
            src_bundle=None,
            is_cancelled=threading.Event(),
            was_cancelled=False,
            backup_bundles=[],
            failure_count=0,
        )
        self.status.record_bundle_details(bundle)
        logger.debug('%s: Created an original bundle', bundle)
        return bundle

    def _create_backup_bundle(self, src_bundle: BundleDetails):
        """Creates a bundle that is a backup of another bundle that is
        running too slowly."""

        assert self.status.lock.locked()
        assert src_bundle.backup_bundles is not None
        n = len(src_bundle.backup_bundles)
        uuid = src_bundle.uuid + f'_backup#{n}'

        backup_bundle = BundleDetails(
            pickled_code=src_bundle.pickled_code,
            uuid=uuid,
            function_name=src_bundle.function_name,
            worker=None,
            username=None,
            machine=None,
            controller=src_bundle.controller,
            code_file=src_bundle.code_file,
            result_file=src_bundle.result_file,
            pid=0,
            start_ts=time.time(),
            end_ts=0.0,
            slower_than_local_p95=False,
            slower_than_global_p95=False,
            src_bundle=src_bundle,
            is_cancelled=threading.Event(),
            was_cancelled=False,
            backup_bundles=None,  # backup backups not allowed
            failure_count=0,
        )
        src_bundle.backup_bundles.append(backup_bundle)
        self.status.record_bundle_details_already_locked(backup_bundle)
        logger.debug('%s: Created a backup bundle', backup_bundle)
        return backup_bundle

    def _schedule_backup_for_bundle(self, src_bundle: BundleDetails):
        """Schedule a backup of src_bundle."""

        assert self.status.lock.locked()
        assert src_bundle is not None
        backup_bundle = self._create_backup_bundle(src_bundle)
        logger.debug(
            '%s/%s: Scheduling backup for execution...',
            backup_bundle.uuid,
            backup_bundle.function_name,
        )
        self._helper_executor.submit(self._launch, backup_bundle)

        # Results from backups don't matter; if they finish first
        # they will move the result_file to this machine and let
        # the original pick them up and unpickle them (and return
        # a result).

    def _emergency_retry_nasty_bundle(
        self, bundle: BundleDetails
    ) -> Optional[fut.Future]:
        """Something unexpectedly failed with bundle.  Either retry it
        from the beginning or throw in the towel and give up on it."""

        is_original = bundle.src_bundle is None
        bundle.worker = None
        avoid_last_machine = bundle.machine
        bundle.machine = None
        bundle.username = None
        bundle.failure_count += 1
        if is_original:
            retry_limit = 3
        else:
            retry_limit = 2

        if bundle.failure_count > retry_limit:
            logger.error(
                '%s: Tried this bundle too many times already (%dx); giving up.',
                bundle,
                retry_limit,
            )
            if is_original:
                raise RemoteExecutorException(
                    f'{bundle}: This bundle can\'t be completed despite several backups and retries',
                )
            logger.error(
                '%s: At least it\'s only a backup; better luck with the others.',
                bundle,
            )
            return None
        else:
            msg = f'>>> Emergency rescheduling {bundle} because of unexected errors (wtf?!) <<<'
            logger.warning(msg)
            warnings.warn(msg)
            return self._launch(bundle, avoid_last_machine)

    @overrides
    def submit(self, function: Callable, *args, **kwargs) -> fut.Future:
        """Submit work to be done.  This is the user entry point of this
        class."""
        if self.already_shutdown:
            raise Exception('Submitted work after shutdown.')
        pickle = _make_cloud_pickle(function, *args, **kwargs)
        bundle = self._create_original_bundle(pickle, function.__name__)
        self.total_bundles_submitted += 1
        return self._helper_executor.submit(self._launch, bundle)

    @overrides
    def shutdown(self, *, wait: bool = True, quiet: bool = False) -> None:
        """Shutdown the executor."""
        if not self.already_shutdown:
            logging.debug('Shutting down RemoteExecutor %s', self.title)
            self.heartbeat_stop_event.set()
            self.heartbeat_thread.join()
            self._helper_executor.shutdown(wait)
            if not quiet:
                print(self.histogram.__repr__(label_formatter='%ds'))
            self.already_shutdown = True


class RemoteWorkerPoolProvider:
    @abstractmethod
    def get_remote_workers(self) -> List[RemoteWorkerRecord]:
        pass


@persistent.persistent_autoloaded_singleton()  # type: ignore
class ConfigRemoteWorkerPoolProvider(
    RemoteWorkerPoolProvider, persistent.JsonFileBasedPersistent
):
    def __init__(self, json_remote_worker_pool: Dict[str, Any]):
        self.remote_worker_pool: List[RemoteWorkerRecord] = []
        for record in json_remote_worker_pool['remote_worker_records']:
            self.remote_worker_pool.append(
                dataclass_utils.dataclass_from_dict(RemoteWorkerRecord, record)
            )
        assert len(self.remote_worker_pool) > 0

    @overrides
    def get_remote_workers(self) -> List[RemoteWorkerRecord]:
        return self.remote_worker_pool

    @overrides
    def get_persistent_data(self) -> List[RemoteWorkerRecord]:
        return self.remote_worker_pool

    @staticmethod
    @overrides
    def get_filename() -> str:
        return type_utils.unwrap_optional(config.config['remote_worker_records_file'])

    @staticmethod
    @overrides
    def should_we_load_data(filename: str) -> bool:
        return True

    @staticmethod
    @overrides
    def should_we_save_data(filename: str) -> bool:
        return False


@singleton
class DefaultExecutors(object):
    """A container for a default thread, process and remote executor.
    These are not created until needed and we take care to clean up
    before process exit automatically for the caller's convenience.
    Instead of creating your own executor, consider using the one
    from this pool.  e.g.::

        @par.parallelize(method=par.Method.PROCESS)
        def do_work(
            solutions: List[Work],
            shard_num: int,
            ...
        ):
            <do the work>


        def start_do_work(all_work: List[Work]):
            shards = []
            logger.debug('Sharding work into groups of 10.')
            for subset in list_utils.shard(all_work, 10):
                shards.append([x for x in subset])

            logger.debug('Kicking off helper pool.')
            try:
                for n, shard in enumerate(shards):
                    results.append(
                        do_work(
                            shard, n, shared_cache.get_name(), max_letter_pop_per_word
                        )
                    )
                smart_future.wait_all(results)
            finally:
                # Note: if you forget to do this it will clean itself up
                # during program termination including tearing down any
                # active ssh connections.
                executors.DefaultExecutors().process_pool().shutdown()
    """

    def __init__(self):
        self.thread_executor: Optional[ThreadExecutor] = None
        self.process_executor: Optional[ProcessExecutor] = None
        self.remote_executor: Optional[RemoteExecutor] = None

    @staticmethod
    def _ping(host) -> bool:
        logger.debug('RUN> ping -c 1 %s', host)
        try:
            x = cmd_exitcode(
                f'ping -c 1 {host} >/dev/null 2>/dev/null', timeout_seconds=1.0
            )
            return x == 0
        except Exception:
            return False

    def thread_pool(self) -> ThreadExecutor:
        if self.thread_executor is None:
            self.thread_executor = ThreadExecutor()
        return self.thread_executor

    def process_pool(self) -> ProcessExecutor:
        if self.process_executor is None:
            self.process_executor = ProcessExecutor()
        return self.process_executor

    def remote_pool(self) -> RemoteExecutor:
        if self.remote_executor is None:
            logger.info('Looking for some helper machines...')
            provider = ConfigRemoteWorkerPoolProvider()
            all_machines = provider.get_remote_workers()
            pool = []

            # Make sure we can ping each machine.
            for record in all_machines:
                if self._ping(record.machine):
                    logger.info('%s is alive / responding to pings', record.machine)
                    pool.append(record)

            # The controller machine has a lot to do; go easy on it.
            for record in pool:
                if record.machine == platform.node() and record.count > 1:
                    logger.info('Reducing workload for %s.', record.machine)
                    record.count = max(int(record.count / 2), 1)

            policy = WeightedRandomRemoteWorkerSelectionPolicy()
            policy.register_worker_pool(pool)
            self.remote_executor = RemoteExecutor(pool, policy)
        return self.remote_executor

    def shutdown(self) -> None:
        if self.thread_executor is not None:
            self.thread_executor.shutdown(wait=True, quiet=True)
            self.thread_executor = None
        if self.process_executor is not None:
            self.process_executor.shutdown(wait=True, quiet=True)
            self.process_executor = None
        if self.remote_executor is not None:
            self.remote_executor.shutdown(wait=True, quiet=True)
            self.remote_executor = None
