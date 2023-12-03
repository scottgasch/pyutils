#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""An object that adheres to the threading.Event interface
(https://docs.python.org/3/library/threading.html#event-objects) that,
unlike threading.Event, can be used with select() allowing for
efficient waiting on many events.  Idea stolen from
https://lat.sk/2015/02/multiple-event-waiting-python-3/.

    >>> events = []
    >>> for n in range(10):
    ...     events.append(SelectableEvent())

    >>> t = wait_for_multiple(events, timeout=0.5)
    >>> t is None
    True

    >>> import random
    >>> e = random.choice(events)
    >>> e.set()

    >>> t = wait_for_multiple(events, timeout=0.5)
    >>> t == e
    True

"""

import os
import select
import selectors
import threading
from typing import Iterable, Optional


class SelectableEvent:
    def __init__(self):
        """Create and store two file descriptors connected by a pipe.
        We'll use data written to the pipe (and available on the read
        file descriptor) to indicate that the event is signaled.  The
        event is created is a "not signaled" state initially.

        >>> e = SelectableEvent()
        >>> e.is_set()
        False
        """
        self._read_fd, self._write_fd = os.pipe()
        self.lock = threading.Lock()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Use select to check if a byte is ready to read from the
        read side of the pipe thus indicating the event is signaled.

        Args:
            timeout: number of seconds to wait, at max; defaults to no
                time limit (wait forever).

        Returns:
            True if the event is signaled on exit and False otherwise.

        >>> e = SelectableEvent()
        >>> e.wait(1.0)
        False

        >>> e.set()
        >>> e.wait()
        True
        """
        rfds, _, _ = select.select([self._read_fd], [], [], timeout)
        return self._read_fd in rfds

    def is_set(self):
        """
        Returns:
            True if the event is signaled and False otherwise.

        >>> e = SelectableEvent()
        >>> e.is_set()
        False
        >>> e.set()
        >>> e.is_set()
        True
        """
        return self.wait(0)

    def clear(self):
        """
        Make the event not set.  Note: like threading.Event, this
        method must be called to reset the event state; simply calling
        :meth:`wait` doesn't change the state of the event.

        The lock is to ensure that we do not have a race condition
        between the is_set check and the subsequent read.
        """
        with self.lock:
            if self.is_set():
                os.read(self._read_fd, 1)
            assert not self.is_set()

    def set(self):
        """
        Signal the event.  Wake any waiters.  The lock is to
        ensure that we do not accidentally write more than one byte to
        the pipe because of a race condition between the call to
        is_set() and the call to write.

        >>> e = SelectableEvent()
        >>> e.is_set()
        False
        >>> e.set()
        >>> e.is_set()
        True

        >>> e.set()
        >>> e.set()
        >>> e.set()
        >>> rfds, _, _ = select.select([e._read_fd], [], [], 0)
        >>> e._read_fd in rfds
        True

        >>> e.wait(0)
        True
        >>> e.clear()
        >>> rfds, _, _ = select.select([e._read_fd], [], [], 0)
        >>> e._read_fd in rfds
        False

        """
        with self.lock:
            if not self.is_set():
                os.write(self._write_fd, b'!')
            assert self.is_set()

    def fileno(self):
        """
        Returns:
            The file descriptor number of the read side of the pipe,
            allows this event object to be used with select.select().
        """
        return self._read_fd

    def __del__(self):
        """Cleanup the pipe."""

        os.close(self._read_fd)
        os.close(self._write_fd)


def wait_for_multiple(
    events: Iterable[SelectableEvent], *, timeout: Optional[float] = None
) -> Optional[SelectableEvent]:
    """
    A helper function that, given a list of SelectableEvent, will wait
    until one becomes triggered with an optional timeout.

    Args:
        events: the list of events to wait for
        timeout: an optional max number of seconds to wait; the default
            is to wait forever.

    Returns:
        A reference to the event that has become signaled.
    """
    sel = selectors.DefaultSelector()
    for e in events:
        sel.register(e.fileno(), selectors.EVENT_READ, e)

    triggered = sel.select(timeout=timeout)
    if not triggered:
        return None
    else:
        return triggered[0][0].data


if __name__ == "__main__":
    import doctest

    doctest.testmod()
