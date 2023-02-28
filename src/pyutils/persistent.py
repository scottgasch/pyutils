#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
This module defines a class hierarchy (base class :class:`Persistent`) and
a decorator (`@persistent_autoloaded_singleton`) that can be used to create
objects that load and save their state from some external storage location
automatically, optionally and conditionally.

A :class:`Persistent` is just a class with a :meth:`Persistent.load` and
:meth:`Persistent.save` method.   Various subclasses such as
:class:`JsonFileBasedPersistent` and :class:`PicklingFileBasedPersistent`
define these methods to, save data in a particular format.  The details
of where and whether to save are left to your code to decide by implementing
interface methods like :meth:`FileBasedPersistent.get_filename` and
:meth:`FileBasedPersistent.should_we_load_data`.

This module inculdes some helpers to make deciding whether to load persisted
state easier such as :meth:`was_file_written_today` and
:meth:`was_file_written_within_n_seconds`.

:class:`Persistent` classes are good for things backed by persisted
state that is loaded all or most of the time.  For example, the high
score list of a game, the configuration settings of a tool,
etc... Really anything that wants to save/load state from storage and
not bother with the plumbing to do so.
"""

import atexit
import datetime
import enum
import functools
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from overrides import overrides

from pyutils.files import file_utils

logger = logging.getLogger(__name__)


class Persistent(ABC):
    """
    A base class of an object with a load/save method.  Classes that are
    decorated with :code:`@persistent_autoloaded_singleton` should subclass
    this and implement their :meth:`save` and :meth:`load` methods.
    """

    @abstractmethod
    def save(self) -> bool:
        """
        Save this thing somewhere that you'll remember when someone calls
        :meth:`load` later on in a way that makes sense to your code.
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls) -> Any:
        """Load this thing from somewhere and give back an instance which
        will become the global singleton and which may (see
        below) be saved (via :meth:`save`) at program exit time.

        Oh, in case this is handy, here's a reminder how to write a
        factory method that doesn't call the c'tor in python::

            @classmethod
            def load_from_somewhere(cls, somewhere):
                # Note: __new__ does not call __init__.
                obj = cls.__new__(cls)

                # Don't forget to call any polymorphic base class initializers
                super(MyClass, obj).__init__()

                # Load the piece(s) of obj that you want to from somewhere.
                obj._state = load_from_somewhere(somewhere)
                return obj
        """
        pass


class FileBasedPersistent(Persistent):
    """A :class:`Persistent` subclass that uses a file to save/load
    data and knows the conditions under which the state should be
    saved/loaded.
    """

    @staticmethod
    @abstractmethod
    def get_filename() -> str:
        """
        Returns:
            The full path of the file in which we are saving/loading data.
        """
        pass

    @staticmethod
    @abstractmethod
    def should_we_save_data(filename: str) -> bool:
        """
        Returns:
            True if we should save our state now or False otherwise.
        """
        pass

    @staticmethod
    @abstractmethod
    def should_we_load_data(filename: str) -> bool:
        """
        Returns:
            True if we should load persisted state now or False otherwise.
        """
        pass

    @abstractmethod
    def get_persistent_data(self) -> Any:
        """
        Returns:
            The raw state data read from the filesystem.  Can be any format.
        """
        pass


class PicklingFileBasedPersistent(FileBasedPersistent):
    """
    A class that stores its state in a file as pickled Python objects.

    Example usage::

        import persistent

        @persistent.persistent_autoloaded_singleton()
        class MyClass(persistent.PicklingFileBasedPersistent):
            def __init__(self, data: Optional[Whatever]):
                if data:
                    # initialize state from data
                else:
                    # if desired, initialize an "empty" object with new state.

            @staticmethod
            @overrides
            def get_filename() -> str:
                return "/path/to/where/you/want/to/save/data.bin"

            @staticmethod
            @overrides
            def should_we_save_data(filename: str) -> bool:
                return true_if_we_should_save_the_data_this_time()

            @staticmethod
            @overrides
            def should_we_load_data(filename: str) -> bool:
                return persistent.was_file_written_within_n_seconds(whatever)

        # Persistent will handle the plumbing to instantiate your class from its
        # persisted state iff the :meth:`should_we_load_data` says it's ok to.  It
        # will also persist the current in-memory state to disk at program exit iff
        # the :meth:`should_we_save_data` methods says to.
        c = MyClass()

    """

    @classmethod
    @overrides
    def load(cls) -> Optional[Any]:
        filename = cls.get_filename()
        if cls.should_we_load_data(filename):
            logger.debug("Attempting to load state from %s", filename)
            assert file_utils.is_readable(filename)

            import pickle

            try:
                with open(filename, "rb") as rf:
                    data = pickle.load(rf)
                    return cls(data)

            except Exception as e:
                raise Exception(f"Failed to load {filename}.") from e
        return None

    @overrides
    def save(self) -> bool:
        filename = self.get_filename()
        if self.should_we_save_data(filename):
            logger.debug("Trying to save state in %s", filename)
            try:
                import pickle

                with open(filename, "wb") as wf:
                    pickle.dump(self.get_persistent_data(), wf, pickle.HIGHEST_PROTOCOL)
                return True
            except Exception as e:
                raise Exception(f"Failed to save to {filename}.") from e
        return False


class JsonFileBasedPersistent(FileBasedPersistent):
    """A class that stores its state in a JSON format file.

    Example usage::

        import persistent

        @persistent.persistent_autoloaded_singleton()
        class MyClass(persistent.JsonFileBasedPersistent):
            def __init__(self, data: Optional[dict[str, Any]]):
                # load already deserialized the JSON data for you; it's
                # a "cooked" JSON dict of string -> values, lists, dicts,
                # etc...
                if data:
                    #initialize youself from data...
                else:
                    # if desired, initialize an empty state object
                    # when json_data isn't provided.

            @staticmethod
            @overrides
            def get_filename() -> str:
                return "/path/to/where/you/want/to/save/data.json"

            @staticmethod
            @overrides
            def should_we_save_data(filename: str) -> bool:
                return true_if_we_should_save_the_data_this_time()

            @staticmethod
            @overrides
            def should_we_load_data(filename: str) -> bool:
                return persistent.was_file_written_within_n_seconds(whatever)

        # Persistent will handle the plumbing to instantiate your
        # class from its persisted state iff the
        # :meth:`should_we_load_data` says it's ok to.  It will also
        # persist the current in memory state to disk at program exit
        # iff the :meth:`should_we_save_data methods` says to.
        c = MyClass()
    """

    @classmethod
    @overrides
    def load(cls) -> Any:
        filename = cls.get_filename()
        if cls.should_we_load_data(filename):
            logger.debug("Trying to load state from %s", filename)
            import json

            try:
                with open(filename, "r") as rf:
                    lines = rf.readlines()

                # This is probably bad... but I like comments
                # in config files and JSON doesn't support them.  So
                # pre-process the buffer to remove comments thus
                # allowing people to add them.
                buf = ""
                for line in lines:
                    line = re.sub(r"#.*$", "", line)
                    buf += line
                json_dict = json.loads(buf)
                return cls(json_dict)

            except Exception as e:
                logger.exception(
                    "Failed to load path %s; raising an exception", filename
                )
                raise Exception(f"Failed to load {filename}.") from e
        return None

    @overrides
    def save(self) -> bool:
        filename = self.get_filename()
        if self.should_we_save_data(filename):
            logger.debug("Trying to save state in %s", filename)
            try:
                import json

                json_blob = json.dumps(self.get_persistent_data())
                with open(filename, "w") as wf:
                    wf.writelines(json_blob)
                return True
            except Exception as e:
                raise Exception(f"Failed to save to {filename}.") from e
        return False


def was_file_written_today(filename: str) -> bool:
    """Convenience wrapper around :meth:`was_file_written_within_n_seconds`.

    Args:
        filename: path / filename to check

    Returns:
        True if filename was written today.

    >>> import os
    >>> filename = f'/tmp/testing_persistent_py_{os.getpid()}'
    >>> os.system(f'touch {filename}')
    0
    >>> was_file_written_today(filename)
    True
    >>> os.system(f'touch -d 1974-04-15T01:02:03.99 {filename}')
    0
    >>> was_file_written_today(filename)
    False
    >>> os.system(f'/bin/rm -f {filename}')
    0
    >>> was_file_written_today(filename)
    False
    """
    if not file_utils.does_file_exist(filename):
        return False

    mtime = file_utils.get_file_mtime_as_datetime(filename)
    assert mtime is not None
    now = datetime.datetime.now()
    return mtime.month == now.month and mtime.day == now.day and mtime.year == now.year


def was_file_written_within_n_seconds(
    filename: str,
    limit_seconds: int,
) -> bool:
    """Helper for determining persisted state staleness.

    Args:
        filename: the filename to check
        limit_seconds: how fresh, in seconds, it must be

    Returns:
        True if filename was written within the past limit_seconds
        or False otherwise (or on error).

    >>> import os
    >>> filename = f'/tmp/testing_persistent_py_{os.getpid()}'
    >>> os.system(f'touch {filename}')
    0
    >>> was_file_written_within_n_seconds(filename, 60)
    True
    >>> import time
    >>> time.sleep(2.0)
    >>> was_file_written_within_n_seconds(filename, 2)
    False
    >>> os.system(f'/bin/rm -f {filename}')
    0
    >>> was_file_written_within_n_seconds(filename, 60)
    False
    """

    if not file_utils.does_file_exist(filename):
        return False

    mtime = file_utils.get_file_mtime_as_datetime(filename)
    assert mtime is not None
    now = datetime.datetime.now()
    return (now - mtime).total_seconds() <= limit_seconds


class PersistAtShutdown(enum.Enum):
    """
    An enum to describe the conditions under which state is persisted
    to disk.  This is passed as an argument to the decorator below and
    is used to indicate when to call :meth:`save` on a :class:`Persistent`
    subclass.

    * NEVER: never call :meth:`save`
    * IF_NOT_LOADED: call :meth:`save` as long as we did not successfully
      :meth:`load` its state.
    * ALWAYS: always call :meth:`save`
    """

    NEVER = (0,)
    IF_NOT_LOADED = (1,)
    ALWAYS = (2,)


class persistent_autoloaded_singleton(object):
    """A decorator that can be applied to a :class:`Persistent` subclass
    (i.e.  a class with :meth:`save` and :meth:`load` methods.  The
    decorator will intercept attempts to instantiate the class via
    it's c'tor and, instead, invoke the class' :meth:`load` to give it a
    chance to read state from somewhere persistent (disk, db,
    whatever).  Subsequent calls to construt instances of the wrapped
    class will return a single, global instance (i.e. the wrapped
    class is must be a singleton).

    If :meth:`load` fails (returns None), the c'tor is invoked with the
    original args as a fallback.

    Based upon the value of the optional argument
    :code:`persist_at_shutdown` argument, (NEVER, IF_NOT_LOADED,
    ALWAYS), the :meth:`save` method of the class will be invoked just
    before program shutdown to give the class a chance to save its
    state somewhere.

    .. note::
        The implementations of :meth:`save` and :meth:`load` and where the
        class persists its state are details left to the :class:`Persistent`
        implementation.  Essentially this decorator just handles the
        plumbing of calling your save/load and appropriate times and
        creates a transparent global singleton whose state can be
        persisted between runs.

    """

    def __init__(
        self,
        *,
        persist_at_shutdown: PersistAtShutdown = PersistAtShutdown.IF_NOT_LOADED,
    ):
        self.persist_at_shutdown = persist_at_shutdown
        self.instance = None

    def __call__(self, cls: Persistent):
        @functools.wraps(cls)  # type: ignore
        def _load(*args, **kwargs):

            # If class has already been loaded, act like a singleton
            # and return a reference to the one and only instance in
            # memory.
            if self.instance is not None:
                logger.debug(
                    "Returning already instantiated singleton instance of %s.",
                    cls.__name__,
                )
                return self.instance

            # Otherwise, try to load it from persisted state.
            was_loaded = False
            logger.debug("Attempting to load %s from persisted state.", cls.__name__)
            self.instance = cls.load()
            if not self.instance:
                msg = "Loading from cache failed."
                logger.warning(msg)
                logger.debug("Attempting to instantiate %s directly.", cls.__name__)
                self.instance = cls(*args, **kwargs)
            else:
                logger.debug(
                    "Class %s was loaded from persisted state successfully.",
                    cls.__name__,
                )
                was_loaded = True

            assert self.instance is not None

            if self.persist_at_shutdown is PersistAtShutdown.ALWAYS or (
                not was_loaded
                and self.persist_at_shutdown is PersistAtShutdown.IF_NOT_LOADED
            ):
                logger.debug(
                    "Scheduling a deferred called to save at process shutdown time."
                )
                atexit.register(self.instance.save)
            return self.instance

        return _load


if __name__ == "__main__":
    import doctest

    doctest.testmod()
