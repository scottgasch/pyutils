#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""A simple utility to unpickle some code, run it, and pickle the
results.  Please don't unpickle (or run!) code you do not know.
"""

import logging
import os
import signal
import sys
import threading
import time
from typing import Optional

import cloudpickle  # type: ignore
import psutil  # type: ignore

from pyutils import argparse_utils, bootstrap, config
from pyutils.parallelize.thread_utils import background_thread
from pyutils.stopwatch import Timer

logger = logging.getLogger(__file__)

cfg = config.add_commandline_args(
    f"Remote Worker ({__file__})",
    "Helper to run pickled code remotely and return results",
)
cfg.add_argument(
    '--code_file',
    type=str,
    required=True,
    metavar='FILENAME',
    help='The location of the bundle of code to execute.',
)
cfg.add_argument(
    '--result_file',
    type=str,
    required=True,
    metavar='FILENAME',
    help='The location where we should write the computation results.',
)
cfg.add_argument(
    '--watch_for_cancel',
    action=argparse_utils.ActionNoYes,
    default=True,
    help='Should we watch for the cancellation of our parent ssh process?',
)


@background_thread
def watch_for_cancel(terminate_event: threading.Event) -> None:
    logger.debug('Starting up background thread...')
    p = psutil.Process(os.getpid())
    while True:
        saw_sshd = False
        ancestors = p.parents()
        for ancestor in ancestors:
            name = ancestor.name()
            pid = ancestor.pid
            logger.debug('Ancestor process %s (pid=%d)', name, pid)
            if 'ssh' in name.lower():
                saw_sshd = True
                break
        if not saw_sshd:
            logger.error(
                'Did not see sshd in our ancestors list?!  Committing suicide.'
            )
            os.system('pstree')
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5.0)
            os.kill(os.getpid(), signal.SIGKILL)
            sys.exit(-1)
        if terminate_event.is_set():
            return
        time.sleep(1.0)


def cleanup_and_exit(
    thread: Optional[threading.Thread],
    stop_thread: Optional[threading.Event],
    exit_code: int,
) -> None:
    if stop_thread is not None:
        stop_thread.set()
        assert thread is not None
        thread.join()
    sys.exit(exit_code)


@bootstrap.initialize
def main() -> None:
    in_file = config.config['code_file']
    assert in_file and type(in_file) == str
    out_file = config.config['result_file']
    assert out_file and type(out_file) == str

    thread = None
    stop_thread = None
    if config.config['watch_for_cancel']:
        (thread, stop_thread) = watch_for_cancel()

    logger.debug('Reading %s.', in_file)
    try:
        with open(in_file, 'rb') as rb:
            serialized = rb.read()
    except Exception as e:
        logger.exception(e)
        logger.critical('Problem reading %s. Aborting.', in_file)
        cleanup_and_exit(thread, stop_thread, 1)

    logger.debug('Deserializing %s', in_file)
    try:
        fun, args, kwargs = cloudpickle.loads(serialized)
    except Exception as e:
        logger.exception(e)
        logger.critical('Problem deserializing %s. Aborting.', in_file)
        cleanup_and_exit(thread, stop_thread, 2)

    logger.debug('Invoking user code...')
    with Timer() as t:
        ret = fun(*args, **kwargs)
    logger.debug('User code took %.1fs', t())

    logger.debug('Serializing results')
    try:
        serialized = cloudpickle.dumps(ret)
    except Exception as e:
        logger.exception(e)
        logger.critical('Could not serialize result (%s). Aborting.', type(ret))
        cleanup_and_exit(thread, stop_thread, 3)

    logger.debug('Writing %s', out_file)
    try:
        with open(out_file, 'wb') as wb:
            wb.write(serialized)
    except Exception as e:
        logger.exception(e)
        logger.critical('Error writing %s. Aborting.', out_file)
        cleanup_and_exit(thread, stop_thread, 4)
    cleanup_and_exit(thread, stop_thread, 0)


if __name__ == '__main__':
    main()
