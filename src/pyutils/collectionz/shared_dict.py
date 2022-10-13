#!/usr/bin/env python3

"""
The MIT License (MIT)

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

This class is based on https://github.com/luizalabs/shared-memory-dict.
For details about what is preserved from the original and what was changed
by Scott, see NOTICE at the root of this module.
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
    Multiprocessing.SharedMemory region to back the dict such that it
    can be read and written by multiple independent processes at the
    same time.  Because it constantly de/re-serializes the dict, it is
    much slower than a normal dict.

    """

    NULL_BYTE = b'\x00'
    LOCK = RLock()

    def __init__(
        self,
        name: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> None:
        """
        Creates or attaches a shared dictionary back by a SharedMemory buffer.
        For create semantics, a unique name (string) and a max dictionary size
        (expressed in bytes) must be provided.  For attach semantics, these are
        ignored.

        The first process that creates the SharedDict is responsible for
        (optionally) naming it and deciding the max size (in bytes) that
        it may be.  It does this via args to the c'tor.

        Subsequent processes may safely omit name and size args.

        """
        assert size_bytes is None or size_bytes > 0
        self._serializer = PickleSerializer()
        self.shared_memory = self._get_or_create_memory_block(name, size_bytes)
        self._ensure_memory_initialization()
        self.name = self.shared_memory.name

    def get_name(self):
        """Returns the name of the shared memory buffer backing the dict."""
        return self.name

    def _get_or_create_memory_block(
        self,
        name: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> shared_memory.SharedMemory:
        try:
            return shared_memory.SharedMemory(name=name)
        except FileNotFoundError:
            assert size_bytes is not None
            return shared_memory.SharedMemory(name=name, create=True, size=size_bytes)

    def _ensure_memory_initialization(self):
        with SharedDict.LOCK:
            memory_is_empty = (
                bytes(self.shared_memory.buf).split(SharedDict.NULL_BYTE, 1)[0] == b''
            )
            if memory_is_empty:
                self.clear()

    def _write_memory(self, db: Dict[Hashable, Any]) -> None:
        data = self._serializer.dumps(db)
        with SharedDict.LOCK:
            try:
                self.shared_memory.buf[: len(data)] = data
            except ValueError as e:
                raise ValueError("exceeds available storage") from e

    def _read_memory(self) -> Dict[Hashable, Any]:
        with SharedDict.LOCK:
            return self._serializer.loads(self.shared_memory.buf.tobytes())

    @contextmanager
    def _modify_dict(self):
        with SharedDict.LOCK:
            db = self._read_memory()
            yield db
            self._write_memory(db)

    def close(self) -> None:
        """Unmap the shared dict and memory behind it from this
        process.  Called by automatically __del__"""
        if not hasattr(self, 'shared_memory'):
            return
        self.shared_memory.close()

    def cleanup(self) -> None:
        """Unlink the shared dict and memory behind it.  Only the last process should
        invoke this.  Not called automatically."""
        if not hasattr(self, 'shared_memory'):
            return
        with SharedDict.LOCK:
            self.shared_memory.unlink()

    def clear(self) -> None:
        """Clear the dict."""
        self._write_memory({})

    def copy(self) -> Dict[Hashable, Any]:
        """Returns a shallow copy of the dict."""
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
        """Gets the value associated with key or a default."""
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
