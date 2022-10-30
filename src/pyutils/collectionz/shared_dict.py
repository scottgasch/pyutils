#!/usr/bin/env python3

"""The MIT License (MIT)

Copyright (c) 2020 LuizaLabs

Additions/Modifications Copyright (c) 2022 Scott Gasch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This class is based on
https://github.com/luizalabs/shared-memory-dict.  For details about
what is preserved from the original and what was changed by Scott, see
`NOTICE
<https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=NOTICE;hb=HEAD>`_
at the root of this module.

"""

import pickle
from contextlib import contextmanager
from multiprocessing import RLock, shared_memory
from typing import (
    Any,
    Dict,
    Hashable,
    ItemsView,
    Iterator,
    KeysView,
    Optional,
    Tuple,
    ValuesView,
)


class PickleSerializer:
    """A serializer that uses pickling.  Used to read/write bytes in the shared
    memory region and interpret them as a dict."""

    def dumps(self, obj: Dict[Hashable, Any]) -> bytes:
        try:
            return pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
        except pickle.PicklingError as e:
            raise Exception from e

    def loads(self, data: bytes) -> Dict[Hashable, Any]:
        try:
            return pickle.loads(data)
        except pickle.UnpicklingError as e:
            raise Exception from e


# TODOs: profile the serializers and figure out the fastest one.  Can
# we use a ChainMap to avoid the constant de/re-serialization of the
# whole thing?


class SharedDict(object):
    """This class emulates the dict container but uses a
    `Multiprocessing.SharedMemory` region to back the dict such that it
    can be read and written by multiple independent processes at the
    same time.  Because it constantly de/re-serializes the dict, it is
    much slower than a normal dict.

    Example usage... one process should set up the shared memory::

        from pyutils.collectionz.shared_dict import SharedDict

        shared_memory_id = 'SharedDictIdentifier'
        shared_memory_size_bytes = 4096
        shared_memory = SharedDict(shared_memory_id, shared_memory_size_bytes)

    Other processes can then attach to the shared memory by
    referencing its name.  Don't try to pass the :class:`SharedDict` itself to
    a child process.  Rather, just pass its name string.  You can create
    child processes any way that Python supports.  The
    `wordle example <https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=examples/wordle/wordle.py;h=df9874ee0b309e7a70a5a7c8900629869def3928;hb=HEAD>`__ uses the
    parallelize framework with `SharedDict` but a simple `subprocess.run`,
    `exec_utils`, `ProcessExecutor`, whatever::

        from pyutils import exec_utils

        processes = []
        for i in range(10):
            processes.append(
                exec_utils.cmd_in_background(
                    f'myhelper.py --number {i} --shared_memory={shared_memory_id}'
                )
            )

    In the child process, attach the already created :class:`SharedDict`
    using its name.  A size is not necessary when attaching to an
    already created shared memory region -- it cannot be resized after
    creation.  The name must be the same exact name that was used to
    create it originally::

        from pyutils.collectionz.shared_dict import SharedDict

        shared_memory_id = config.config['shared_memory']
        shared_memory = SharedDict(shared_memory_id)

    The children processes (and parent process, also) can now just use
    the shared memory like a normal `dict`::

        if shared_memory[work_id] is None:
            result = do_expensive_work(work_id)
            shared_memory[work_id] = result

    .. note::

        It's pretty slow to mutate data in the shared memory.  First,
        it needs to acquire an exclusive lock.  Second, it essentially
        pickles an entire dict into the shared memory region.  So this
        is not a data structure that is going to win awards for speed.
        But it is a very convenient way to have a shared cache, for
        example.  See the wordle example for a real life program using
        `SharedDict` this way.  It basically saves the result of large
        computations in a `SharedDict` thereby allowing all threads to
        avoid recomputing that same expensive computation.  In this
        scenario the slowness of the dict writes are more than paid
        for by the avoidence of duplicated, expensive work.

    Finally, someone (likely the main process) should call the :meth:`cleanup`
    method when the shared memory region is no longer needed::

        shared_memory.cleanup()

    See also the `shared_dict_test.py <https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=tests/collectionz/shared_dict_test.py;h=0a684f4835554553018cefbc114034c2dc405794;hb=HEAD>`__ for an
    example of using this class.

    ---
    """

    NULL_BYTE = b"\x00"
    LOCK = RLock()

    def __init__(
        self,
        name: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> None:
        """Creates or attaches a shared dictionary back by a
        :class:`SharedMemory` buffer.  For create semantics, a unique
        name (string) and a max dictionary size (expressed in bytes)
        must be provided.  For attach semantics size is ignored.

        .. warning::

            Size is ignored on attach operations.  The size of the
            shared memory region cannot be changed once it has been
            created.

        The first process that creates the :class:`SharedDict` is
        responsible for (optionally) naming it and deciding the max
        size (in bytes) that it may be.  It does this via args to the
        c'tor.

        Subsequent processes may safely the size arg.

        Args:
            name: the name of the shared dict, only required for initial caller
            size_bytes: the maximum size of data storable in the shared dict,
                only required for the first caller.

        """
        assert size_bytes is None or size_bytes > 0
        self._serializer = PickleSerializer()
        self.shared_memory = self._get_or_create_memory_block(name, size_bytes)
        self._ensure_memory_initialization()
        self.name = self.shared_memory.name

    def get_name(self):
        """
        Returns:
            The name of the shared memory buffer backing the dict.
        """
        return self.name

    def _get_or_create_memory_block(
        self,
        name: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> shared_memory.SharedMemory:
        """Internal helper."""
        try:
            return shared_memory.SharedMemory(name=name)
        except FileNotFoundError:
            assert size_bytes is not None
            return shared_memory.SharedMemory(name=name, create=True, size=size_bytes)

    def _ensure_memory_initialization(self):
        """Internal helper."""
        with SharedDict.LOCK:
            memory_is_empty = (
                bytes(self.shared_memory.buf).split(SharedDict.NULL_BYTE, 1)[0] == b""
            )
            if memory_is_empty:
                self.clear()

    def _write_memory(self, db: Dict[Hashable, Any]) -> None:
        """Internal helper."""
        data = self._serializer.dumps(db)
        with SharedDict.LOCK:
            try:
                self.shared_memory.buf[: len(data)] = data
            except ValueError as e:
                raise ValueError("exceeds available storage") from e

    def _read_memory(self) -> Dict[Hashable, Any]:
        """Internal helper."""
        with SharedDict.LOCK:
            return self._serializer.loads(self.shared_memory.buf.tobytes())

    @contextmanager
    def _modify_dict(self):
        """Internal helper."""
        with SharedDict.LOCK:
            db = self._read_memory()
            yield db
            self._write_memory(db)

    def close(self) -> None:
        """Unmap the shared dict and memory behind it from this
        process.  Called by automatically :meth:`__del__`.
        """
        if not hasattr(self, "shared_memory"):
            return
        self.shared_memory.close()

    def cleanup(self) -> None:
        """Unlink the shared dict and memory behind it.  Only the last process
        should invoke this.  Not called automatically."""
        if not hasattr(self, "shared_memory"):
            return
        with SharedDict.LOCK:
            self.shared_memory.unlink()

    def clear(self) -> None:
        """Clears the shared dict."""
        self._write_memory({})

    def copy(self) -> Dict[Hashable, Any]:
        """
        Returns:
            A shallow copy of the shared dict.
        """
        return self._read_memory()

    def __getitem__(self, key: Hashable) -> Any:
        return self._read_memory()[key]

    def __setitem__(self, key: Hashable, value: Any) -> None:
        with self._modify_dict() as db:
            db[key] = value

    def __len__(self) -> int:
        return len(self._read_memory())

    def __delitem__(self, key: Hashable) -> None:
        with self._modify_dict() as db:
            del db[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._read_memory())

    def __reversed__(self) -> Iterator[Hashable]:
        return reversed(self._read_memory())

    def __del__(self) -> None:
        self.close()

    def __contains__(self, key: Hashable) -> bool:
        return key in self._read_memory()

    def __eq__(self, other: Any) -> bool:
        return self._read_memory() == other

    def __ne__(self, other: Any) -> bool:
        return self._read_memory() != other

    def __str__(self) -> str:
        return str(self._read_memory())

    def __repr__(self) -> str:
        return repr(self._read_memory())

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Args:
            key: the key to lookup
            default: the value returned if key is not present

        Returns:
            The value associated with key or a default.
        """
        return self._read_memory().get(key, default)

    def keys(self) -> KeysView[Hashable]:
        return self._read_memory().keys()

    def values(self) -> ValuesView[Any]:
        return self._read_memory().values()

    def items(self) -> ItemsView[Hashable, Any]:
        return self._read_memory().items()

    def popitem(self) -> Tuple[Hashable, Any]:
        """Remove and return the last added item."""
        with self._modify_dict() as db:
            return db.popitem()

    def pop(self, key: Hashable, default: Optional[Any] = None) -> Any:
        """Remove and return the value associated with key or a default"""
        with self._modify_dict() as db:
            if default is None:
                return db.pop(key)
            return db.pop(key, default)

    def update(self, other=(), /, **kwds):
        with self._modify_dict() as db:
            db.update(other, **kwds)

    def setdefault(self, key: Hashable, default: Optional[Any] = None):
        with self._modify_dict() as db:
            return db.setdefault(key, default)
