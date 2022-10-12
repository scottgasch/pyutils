#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Several helpers to keep track of internal state via periodic
polling.  :class:`StateTracker` expects to be invoked periodically to
maintain state whereas the others (:class:`AutomaticStateTracker` and
:class:`WaitableAutomaticStateTracker`) automatically update themselves
and, optionally, expose an event for client code to wait on state
changes.
"""

import datetime
import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

import pytz

from pyutils.parallelize.thread_utils import background_thread

logger = logging.getLogger(__name__)


class StateTracker(ABC):
    """A base class that maintains and updates a global state via an
    update routine.  Instances of this class should be periodically
    invoked via the heartbeat() method.  This method, in turn, invokes
    update() with update_ids according to a schedule / periodicity
    provided to the c'tor.
    """

    def __init__(self, update_ids_to_update_secs: Dict[str, float]) -> None:
        """The update_ids_to_update_secs dict parameter describes one or more
        update types (unique update_ids) and the periodicity(ies), in
        seconds, at which it/they should be invoked.

        .. note::
            When more than one update is overdue, they will be
            invoked in order by their update_ids so care in choosing these
            identifiers may be in order.

        Args:
            update_ids_to_update_secs: a dict mapping a user-defined
                update_id into a period (number of seconds) with which
                we would like this update performed.  e.g.::

                    update_ids_to_update_secs = {
                        'refresh_local_state': 10.0,
                        'refresh_remote_state': 60.0,
                    }

                This would indicate that every 10s we would like to
                refresh local state whereas every 60s we'd like to
                refresh remote state.
        """
        self.update_ids_to_update_secs = update_ids_to_update_secs
        self.last_reminder_ts: Dict[str, Optional[datetime.datetime]] = {}
        self.now: Optional[datetime.datetime] = None
        for x in update_ids_to_update_secs.keys():
            self.last_reminder_ts[x] = None

    @abstractmethod
    def update(
        self,
        update_id: str,
        now: datetime.datetime,
        last_invocation: Optional[datetime.datetime],
    ) -> None:
        """Put whatever you want here to perform your state updates.

        Args:
            update_id: the string you passed to the c'tor as a key in
                the update_ids_to_update_secs dict.  :meth:`update` will
                only be invoked on the shoulder, at most, every update_secs
                seconds.

            now: the approximate current timestamp at invocation time.

            last_invocation: the last time this operation was invoked
                (or None on the first invocation).
        """
        pass

    def heartbeat(self, *, force_all_updates_to_run: bool = False) -> None:
        """Invoke this method to cause the StateTracker instance to identify
        and invoke any overdue updates based on the schedule passed to
        the c'tor.  In the base :class:`StateTracker` class, this method must
        be invoked manually by a thread from external code.  Other subclasses
        are available that create their own updater threads (see below).

        If more than one type of update (update_id) are overdue,
        they will be invoked in order based on their update_ids.

        Setting force_all_updates_to_run will invoke all updates
        (ordered by update_id) immediately ignoring whether or not
        they are due.
        """

        self.now = datetime.datetime.now(tz=pytz.timezone("US/Pacific"))
        for update_id in sorted(self.last_reminder_ts.keys()):
            if force_all_updates_to_run:
                logger.debug('Forcing all updates to run')
                self.update(update_id, self.now, self.last_reminder_ts[update_id])
                self.last_reminder_ts[update_id] = self.now
                return

            refresh_secs = self.update_ids_to_update_secs[update_id]
            last_run = self.last_reminder_ts[update_id]
            if last_run is None:  # Never run before
                logger.debug('id %s has never been run; running it now', update_id)
                self.update(update_id, self.now, self.last_reminder_ts[update_id])
                self.last_reminder_ts[update_id] = self.now
            else:
                delta = self.now - last_run
                if delta.total_seconds() >= refresh_secs:  # Is overdue?
                    logger.debug('id %s is overdue; running it now', update_id)
                    self.update(
                        update_id,
                        self.now,
                        self.last_reminder_ts[update_id],
                    )
                    self.last_reminder_ts[update_id] = self.now


class AutomaticStateTracker(StateTracker):
    """Just like :class:`StateTracker` but you don't need to pump the
    :meth:`heartbeat` method periodically because we create a background
    thread that manages periodic calling.  You must call :meth:`shutdown`,
    though, in order to terminate the update thread.
    """

    @background_thread
    def pace_maker(self, should_terminate: threading.Event) -> None:
        """Entry point for a background thread to own calling :meth:`heartbeat`
        at regular intervals so that the main thread doesn't need to
        do so.
        """
        while True:
            if should_terminate.is_set():
                logger.debug('pace_maker noticed event; shutting down')
                return
            self.heartbeat()
            logger.debug('pace_maker is sleeping for %.1fs', self.sleep_delay)
            time.sleep(self.sleep_delay)

    def __init__(
        self,
        update_ids_to_update_secs: Dict[str, float],
        *,
        override_sleep_delay: Optional[float] = None,
    ) -> None:
        """Construct an AutomaticStateTracker.

        Args:
            update_ids_to_update_secs: a dict mapping a user-defined
                update_id into a period (number of seconds) with which
                we would like this update performed.  e.g.::

                    update_ids_to_update_secs = {
                        'refresh_local_state': 10.0,
                        'refresh_remote_state': 60.0,
                    }

                This would indicate that every 10s we would like to
                refresh local state whereas every 60s we'd like to
                refresh remote state.

            override_sleep_delay: By default, this class determines
                how long the background thread should sleep between
                automatic invocations to :meth:`heartbeat` based on the
                period of each update type in update_ids_to_update_secs.
                If this argument is non-None, it overrides this computation
                and uses this period as the sleep in the background thread.
        """
        from pyutils import math_utils

        super().__init__(update_ids_to_update_secs)
        if override_sleep_delay is not None:
            logger.debug('Overriding sleep delay to %.1f', override_sleep_delay)
            self.sleep_delay = override_sleep_delay
        else:
            periods_list = list(update_ids_to_update_secs.values())
            self.sleep_delay = math_utils.gcd_float_sequence(periods_list)
            logger.info('Computed sleep_delay=%.1f', self.sleep_delay)
        (thread, stop_event) = self.pace_maker()
        self.should_terminate = stop_event
        self.updater_thread = thread

    def shutdown(self):
        """Terminates the background thread and waits for it to tear down.
        This may block for as long as self.sleep_delay.
        """
        logger.debug('Setting shutdown event and waiting for background thread.')
        self.should_terminate.set()
        self.updater_thread.join()
        logger.debug('Background thread terminated.')


class WaitableAutomaticStateTracker(AutomaticStateTracker):
    """This is an AutomaticStateTracker that exposes a wait method which
    will block the calling thread until the state changes with an
    optional timeout.  The caller should check the return value of
    wait; it will be true if something changed and false if the wait
    simply timed out.  If the return value is true, the instance
    should be reset() before wait is called again.

    Example usage::

        detector = waitable_presence.WaitableAutomaticStateSubclass()
        while True:
            changed = detector.wait(timeout=60 * 5)
            if changed:
                detector.reset()
                # Figure out what changed and react
            else:
                # Just a timeout; no need to reset.  Maybe do something
                # else before looping up into wait again.
    """

    def __init__(
        self,
        update_ids_to_update_secs: Dict[str, float],
        *,
        override_sleep_delay: Optional[float] = None,
    ) -> None:
        """Construct an WaitableAutomaticStateTracker.

        Args:
            update_ids_to_update_secs: a dict mapping a user-defined
                update_id into a period (number of seconds) with which
                we would like this update performed.  e.g.::

                    update_ids_to_update_secs = {
                        'refresh_local_state': 10.0,
                        'refresh_remote_state': 60.0,
                    }

                This would indicate that every 10s we would like to
                refresh local state whereas every 60s we'd like to
                refresh remote state.

            override_sleep_delay: By default, this class determines
                how long the background thread should sleep between
                automatic invocations to :meth:`heartbeat` based on the
                period of each update type in update_ids_to_update_secs.
                If this argument is non-None, it overrides this computation
                and uses this period as the sleep in the background thread.
        """
        self._something_changed = threading.Event()
        super().__init__(
            update_ids_to_update_secs, override_sleep_delay=override_sleep_delay
        )

    def something_changed(self):
        """Indicate that something has changed."""
        self._something_changed.set()

    def did_something_change(self) -> bool:
        """Indicate whether some state has changed in the background."""
        return self._something_changed.is_set()

    def reset(self):
        """Call to clear the 'something changed' bit.  See usage above."""
        self._something_changed.clear()

    def wait(self, *, timeout=None):
        """Wait for something to change or a timeout to lapse.

        Args:
            timeout: maximum amount of time to wait.  If None, wait
                forever (until something changes).
        """
        return self._something_changed.wait(timeout=timeout)
