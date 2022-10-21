#!/usr/bin/env python3

"""Wrapper that adds exclusive locks, timeouts, timestamp accounting,
max frequency, logging, etc... to running cron jobs.
"""

import datetime
import logging
import os
import sys
from typing import Optional

from pyutils import bootstrap, config, exec_utils, stopwatch
from pyutils.datetimez import datetime_utils
from pyutils.files import file_utils, lockfile

logger = logging.getLogger(__name__)

cfg = config.add_commandline_args(
    f'Python Cron Runner ({__file__})',
    'Wrapper for cron commands with locking, timeouts, and accounting.',
)
cfg.add_argument(
    '--lockfile',
    default=None,
    metavar='LOCKFILE_PATH',
    help='Path to the lockfile to use to ensure that two instances of a command do not execute contemporaneously.',
)
cfg.add_argument(
    '--lockfile_audit_record',
    default=None,
    metavar='LOCKFILE_AUDIT_RECORD_FILENAME',
    help='Path to a record of when the logfile was held/released and for what reason',
)
cfg.add_argument(
    '--timeout',
    type=str,
    metavar='TIMEOUT',
    default=None,
    help='Maximum time for lock acquisition + command execution.  Undecorated for seconds but "3m" or "1h 15m" work too.',
)
cfg.add_argument(
    '--timestamp',
    type=str,
    metavar='TIMESTAMP_FILE',
    default=None,
    help='The /timestamp/TIMESTAMP_FILE file tracking the work being done; files\' mtimes will be set to the last successful run of a command for accounting purposes.',
)
cfg.add_argument(
    '--max_frequency',
    type=str,
    metavar='FREQUENCY',
    default=None,
    help='The maximum frequency with which to do this work; even if the wrapper is invoked more often than this it will not run the command.  Requires --timestamp.  Undecorated for seconds but "3h" or "1h 15m" work too.',
)
cfg.add_argument(
    '--command',
    nargs='*',
    required=True,
    type=str,
    metavar='COMMANDLINE',
    help='The commandline to run under a lock.',
)
config.overwrite_argparse_epilog(
    """
cron.py's exit value:

   -1000 = some internal error occurred (see exception log).
       0 = we exited early due to not enough time passage since the last
           invocation of --command.
    1000 = we could not obtain the lockfile; someone else owns it.
 else = if the --command was run successfully, cron.py will exit with
        the same code that the subcommand exited with.
"""
)


def run_command(timeout: Optional[int], timestamp_file: Optional[str]) -> int:
    """Run cron command"""
    cmd = ' '.join(config.config['command'])
    logger.info('cron cmd = "%s"', cmd)
    logger.debug('shell environment:')
    for var in os.environ:
        val = os.environ[var]
        logger.debug('%s = %s', var, val)
    logger.debug('____ (↓↓↓ output from the subprocess appears below here ↓↓↓) ____')
    try:
        with stopwatch.Timer() as t:
            ret = exec_utils.cmd_exitcode(cmd, timeout)
        logger.debug(
            f'____ (↑↑↑ subprocess finished in {t():.2f}s, exit value was {ret} ↑↑↑) ____'
        )
        if timestamp_file is not None and os.path.exists(timestamp_file):
            logger.debug('Touching %s', timestamp_file)
            file_utils.touch_file(timestamp_file)
        return ret
    except Exception as e:
        logger.exception(e)
        print('Cron subprocess failed, giving up.', file=sys.stderr)
        logger.warning('Cron subprocess failed, giving up')
        return -1000


@bootstrap.initialize
def main() -> int:
    """Entry point"""
    if config.config['timestamp']:
        timestamp_file = f"/timestamps/{config.config['timestamp']}"
        if not file_utils.does_file_exist(timestamp_file):
            logger.error(
                '--timestamp argument\'s target file (%s) must already exist.',
                timestamp_file,
            )
            sys.exit(-1)
    else:
        timestamp_file = None
        if config.config['max_frequency']:
            config.error(
                'The --max_frequency argument requires the --timestamp argument.'
            )

    now = datetime.datetime.now()
    if timestamp_file is not None and os.path.exists(timestamp_file):
        max_frequency = config.config['max_frequency']
        if max_frequency is not None:
            max_delta = datetime_utils.parse_duration(max_frequency)
            if max_delta > 0:
                mtime = file_utils.get_file_mtime_as_datetime(timestamp_file)
                delta = now - mtime
                if delta.total_seconds() < max_delta:
                    logger.info(
                        "It's only been %s since we last ran successfully; bailing out.",
                        datetime_utils.describe_duration_briefly(delta.total_seconds()),
                    )
                    sys.exit(0)

    timeout = config.config['timeout']
    if timeout is not None:
        timeout = datetime_utils.parse_duration(timeout)
        assert timeout > 0
        logger.debug('Timeout is %ss', timeout)
        lockfile_expiration = datetime.datetime.now().timestamp() + timeout
    else:
        logger.debug('Timeout not specified; no lockfile expiration.')
        lockfile_expiration = None

    lockfile_path = config.config['lockfile']
    if lockfile_path is not None:
        logger.debug('Attempting to acquire lockfile %s...', lockfile_path)
        try:
            with lockfile.LockFile(
                lockfile_path,
                do_signal_cleanup=True,
                override_command=' '.join(config.config['command']),
                expiration_timestamp=lockfile_expiration,
            ) as lf:
                record = config.config['lockfile_audit_record']
                cmd = ' '.join(config.config['command'])
                if record:
                    start = lf.locktime
                    with open(record, 'a') as wf:
                        print(f'{lockfile_path}, ACQUIRE, {start}, {cmd}', file=wf)
                retval = run_command(timeout, timestamp_file)
                if record:
                    end = datetime.datetime.now().timestamp()
                    duration = datetime_utils.describe_duration_briefly(end - start)
                    with open(record, 'a') as wf:
                        print(
                            f'{lockfile_path}, RELEASE({duration}), {end}, {cmd}',
                            file=wf,
                        )
                return retval
        except lockfile.LockFileException as e:
            logger.exception(e)
            msg = f'Failed to acquire {lockfile_path}, giving up.'
            logger.error(msg)
            print(msg, file=sys.stderr)
            return 1000
    else:
        logger.debug('No lockfile indicated; not locking anything.')
        return run_command(timeout, timestamp_file)


if __name__ == '__main__':
    # Insist that our logger.whatever('messages') make their way into
    # syslog with a facility=LOG_CRON, please.  Yes, this is hacky.
    sys.argv.append('--logging_syslog')
    sys.argv.append('--logging_syslog_facility=CRON')
    main()
