#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# © Copyright 2022, Scott Gasch

"""
This is a module for making it easier to deal with Zookeeper / Kazoo.
Apache Zookeeper (https://zookeeper.apache.org/) is a consistent centralized
datastore.  :mod:`pyutils.config` optionally uses it to save/read program
configuration.  But it's also very useful for things like distributed
master election, locking, etc...
"""


import datetime
import functools
import logging
import os
import platform
import sys
import threading
from typing import Any, Callable, Optional

from kazoo.client import KazooClient
from kazoo.exceptions import CancelledError
from kazoo.protocol.states import KazooState
from kazoo.recipe.lease import NonBlockingLease

from pyutils import argparse_utils, config
from pyutils.files import file_utils

logger = logging.getLogger(__name__)

cfg = config.add_commandline_args(
    f'Zookeeper ({__file__})',
    'Args related python-zookeeper interactions',
)
cfg.add_argument(
    '--zookeeper_nodes',
    type=str,
    default=None,
    help='Comma separated host:port or ip:port address(es)',
)
cfg.add_argument(
    '--zookeeper_client_cert_path',
    type=argparse_utils.valid_filename,
    default=None,
    metavar='FILENAME',
    help='Path to file containing client certificate.',
)
cfg.add_argument(
    '--zookeeper_client_passphrase',
    type=str,
    default=None,
    metavar='PASSPHRASE',
    help='Pass phrase for unlocking the client certificate.',
)


# On module load, grab what we presume to be our process' program name.
# This is used, by default, to construct internal zookeeper paths (e.g.
# to identify a lease or election).
PROGRAM_NAME: str = os.path.basename(sys.argv[0])


def get_started_zk_client() -> KazooClient:
    """
    Returns:
        A zk client library reference that has been connected and started
        using the commandline provided address, certificates and passphrase.
    """
    zk = KazooClient(
        hosts=config.config['zookeeper_nodes'],
        use_ssl=True,
        verify_certs=False,
        keyfile=config.config['zookeeper_client_cert_path'],
        keyfile_password=config.config['zookeeper_client_passphrase'],
        certfile=config.config['zookeeper_client_cert_path'],
    )
    zk.start()
    logger.debug('We have an active zookeeper connection.')
    return zk


class RenewableReleasableLease(NonBlockingLease):
    """This is a hacky subclass of kazoo.recipe.lease.NonBlockingLease
    (see https://kazoo.readthedocs.io/en/latest/api/recipe/lease.html#kazoo.recipe.lease.NonBlockingLease) that adds some behaviors:

        + Ability to renew the lease if it's already held without
          going through the effort of reobtaining the same lease
          name.

        + Ability to release the lease if it's held and not yet
          expired.

    It also is more picky than the base class in terms of when it
    evaluates to "True" (indicating that the lease is held); it will
    begin to evaluate to "False" as soon as the lease has expired even
    if you used to hold it.  This means client code should be aware
    that the lease can disappear (expire) while held and it also means
    that the performance of evaulating the lease (i.e. if lease:)
    requires a round trip to zookeeper every time.

    Note that it is not valid to release the lease more than once
    (since you no longer have it the second time).  The code ignores
    the 2nd..nth attempt.  It's also not possible to reobtain an
    expired or released lease by calling renew.  Go create a new lease
    object at that point.  Finally, note that when you renew the lease
    it will evaluate to False briefly as it is reobtained.
    """

    def __init__(
        self,
        client: KazooClient,
        path: str,
        duration: datetime.timedelta,
        identifier: str = None,
        utcnow=datetime.datetime.utcnow,
    ):
        """Construct the RenewableReleasableLease.

        Args:
            client: a KazooClient that is connected and started
            path: the path to the lease in zookeeper
            duration: duration during which the lease is reserved
            identifier: unique name to use for this lease holder.
                Reuse in order to renew the lease.
            utcnow: clock function, by default returning
                :meth:`datetime.datetime.utcnow`. Used for testing.

        """
        super().__init__(client, path, duration, identifier, utcnow)
        self.client = client
        self.path = path
        self.identifier = identifier
        self.utcnow = utcnow

    def release(self) -> bool:
        """Release the lease, if it's presently being held.

        Returns:
            True if the lease was successfully released,
            False otherwise.
        """
        self.client.ensure_path(self.path)
        holder_path = self.path + "/lease_holder"
        lock = self.client.Lock(self.path, self.identifier)
        try:
            with lock:
                if not self._is_lease_held_pre_locked():
                    logger.debug("Can't release lease; I don't have it!")
                    return False

                now = self.utcnow()
                if self.client.exists(holder_path):
                    self.client.delete(holder_path)
                end_lease = now.strftime(self._date_format)

                # Release by moving end to now.
                data = {
                    'version': self._version,
                    'holder': self.identifier,
                    'end': end_lease,
                }
                self.client.create(holder_path, self._encode(data))
                self.obtained = False
                logger.debug('Successfully released lease')
                return True

        except CancelledError as e:
            logger.debug('Exception %s in zookeeper?', e)
        return False

    def try_renew(self, duration: datetime.timedelta) -> bool:
        """Attempt to renew a lease that is currently held.  Note that
        this will cause self to evaluate to False briefly as the lease
        is renewed.

        Args:
            duration: the amount of additional time to add to the
                current lease expiration.

        Returns:
            True if the lease was successfully renewed,
            False otherwise.
        """

        if not self.obtained:
            return False
        self.obtained = False
        self._attempt_obtaining(
            self.client, self.path, duration, self.identifier, self.utcnow
        )
        return self.obtained

    def _is_lease_held_pre_locked(self) -> bool:
        self.client.ensure_path(self.path)
        holder_path = self.path + "/lease_holder"
        now = self.utcnow()
        if self.client.exists(holder_path):
            raw, _ = self.client.get(holder_path)
            data = self._decode(raw)
            if data["version"] != self._version:
                return False
            current_end = datetime.datetime.strptime(data['end'], self._date_format)
            if data['holder'] == self.identifier and now <= current_end:
                logger.debug('Yes, we hold the lease and it isn\'t expired.')
                return True
        return False

    def __bool__(self):
        """
        .. note:

            This implementation differs from that of the base class in
            that it probes zookeeper to ensure that the lease is not yet
            expired and is therefore more expensive.

        """
        if not self.obtained:
            return False
        lock = self.client.Lock(self.path, self.identifier)
        try:
            with lock:
                ret = self._is_lease_held_pre_locked()
        except CancelledError:
            return False
        return ret


def obtain_lease(
    f: Optional[Callable] = None,
    *,
    lease_id: str = PROGRAM_NAME,
    contender_id: str = platform.node(),
    duration: datetime.timedelta = datetime.timedelta(minutes=5),
    also_pass_lease: bool = False,
    also_pass_zk_client: bool = False,
):
    """Obtain an exclusive lease identified by the lease_id name
    before invoking a function or skip invoking the function if the
    lease cannot be obtained.

    Note that we use a hacky "RenewableReleasableLease" and not the
    kazoo NonBlockingLease because the former allows us to release the
    lease when the user code returns whereas the latter does not.

    Args:
        lease_id: string identifying the lease to obtain
        contender_id: string identifying who's attempting to obtain
        duration: how long should the lease be held, if obtained?
        also_pass_lease: pass the lease into the user function
        also_pass_zk_client: pass our zk client into the user function

    >>> @obtain_lease(
    ...         lease_id='zookeeper_doctest',
    ...         duration=datetime.timedelta(seconds=5),
    ... )
    ... def f(name: str) -> int:
    ...     print(f'Hello, {name}')
    ...     return 123

    >>> f('Scott')
    Hello, Scott
    123

    """
    if not lease_id.startswith('/leases/'):
        lease_id = f'/leases/{lease_id}'
        lease_id = file_utils.fix_multiple_slashes(lease_id)

    def wrapper(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper2(*args, **kwargs) -> Optional[Any]:
            zk = get_started_zk_client()
            logger.debug(
                'Trying to obtain %s for contender %s now...',
                lease_id,
                contender_id,
            )
            lease = RenewableReleasableLease(
                zk,
                lease_id,
                duration,
                contender_id,
            )
            if lease:
                logger.debug(
                    'Successfully obtained %s for contender %s; invoking user function.',
                    lease_id,
                    contender_id,
                )
                if also_pass_zk_client:
                    args = (*args, zk)
                if also_pass_lease:
                    args = (*args, lease)
                ret = func(*args, *kwargs)

                # We don't care if this release operation succeeds;
                # there are legitimate cases where it will fail such
                # as when the user code has already voluntarily
                # released the lease.
                lease.release()
            else:
                logger.debug(
                    'Failed to obtain %s for contender %s, shutting down.',
                    lease_id,
                    contender_id,
                )
                ret = None
            logger.debug('Shutting down zookeeper client.')
            zk.stop()
            return ret

        return wrapper2

    if f is None:
        return wrapper
    else:
        return wrapper(f)


def run_for_election(
    f: Optional[Callable] = None,
    *,
    election_id: str = PROGRAM_NAME,
    contender_id: str = platform.node(),
    also_pass_zk_client: bool = False,
):
    """Run as a contender for a leader election.  If/when we become
    the leader, invoke the user's function.

    The user's function will be executed on a new thread and must
    accept a "stop processing" event that it must check regularly.
    This event will be set automatically by the wrapper in the event
    that we lose connection to zookeeper (and hence are no longer
    confident that we are still the leader).

    The user's function may return at any time which will cause
    the wrapper to also return and effectively cede leadership.

    Because the user's code is run in a separate thread, it may
    not return anything / whatever it returns will be dropped.

    Args:
        election_id: global string identifier for the election
        contender_id: string identifying who is running for leader
        also_pass_zk_client: pass the zk client into the user code

    >>> @run_for_election(
    ...         election_id='zookeeper_doctest',
    ...         also_pass_zk_client=True
    ... )
    ... def g(name: str, zk: KazooClient, stop_now: threading.Event):
    ...     import time
    ...     count = 0
    ...     while True:
    ...         print(f"Hello, {name}, I'm the leader.")
    ...         if stop_now.is_set():
    ...             print("Oops, not anymore?!")
    ...             return
    ...         time.sleep(0.1)
    ...         count += 1
    ...         if count >= 3:
    ...             print("I'm sick of being leader.")
    ...             return

    >>> g("Scott")
    Hello, Scott, I'm the leader.
    Hello, Scott, I'm the leader.
    Hello, Scott, I'm the leader.
    I'm sick of being leader.

    """
    if not election_id.startswith('/elections/'):
        election_id = f'/elections/{election_id}'
        election_id = file_utils.fix_multiple_slashes(election_id)

    class wrapper:
        """Helper wrapper class."""

        def __init__(self, func: Callable) -> None:
            functools.update_wrapper(self, func)
            self.func = func
            self.zk = get_started_zk_client()
            self.stop_event = threading.Event()
            self.stop_event.clear()

        def zk_listener(self, state: KazooState) -> None:
            logger.debug('Listener received state %s.', state)
            if state != KazooState.CONNECTED:
                logger.debug(
                    'Bad connection to zookeeper (state=%s); bailing out.',
                    state,
                )
                self.stop_event.set()

        def runit(self, *args, **kwargs) -> None:
            # Possibly augment args if requested; always pass stop_event
            if also_pass_zk_client:
                args = (*args, self.zk)
            args = (*args, self.stop_event)

            thread = threading.Thread(
                target=self.func,
                args=args,
                kwargs=kwargs,
            )
            logger.debug(
                'Invoking user code on separate thread: %s',
                thread.getName(),
            )
            thread.start()

            # Periodically poll the zookeeper state (fail safe for
            # listener) and the state of the child thread.
            while True:
                state = self.zk.client_state
                if state != KazooState.CONNECTED:
                    logger.error(
                        'Bad connection to zookeeper (state=%s); bailing out.',
                        state,
                    )
                    self.stop_event.set()
                    logger.debug('Waiting for user thread to tear down...')
                    thread.join()
                    logger.debug('User thread exited after our notification.')
                    return

                thread.join(timeout=5.0)
                if not thread.is_alive():
                    logger.info('User thread exited on its own.')
                    return

        def __call__(self, *args, **kwargs):
            election = self.zk.Election(election_id, contender_id)
            self.zk.add_listener(self.zk_listener)
            election.run(self.runit, *args, **kwargs)
            self.zk.stop()

    if f is None:
        return wrapper
    else:
        return wrapper(f)


if __name__ == '__main__':
    import doctest

    doctest.testmod()
