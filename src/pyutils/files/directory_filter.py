#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""This module contains two classes meant to help reduce unnecessary disk
I/O operations:

The first, :class:`DirectoryFileFilter`, determines when the contents
of a file held in memory are identical to the file copy already on
disk.

The second, :class:`DirectoryAllFilesFilter`, is basically the same
except for the caller need not indicate the name of the disk file
because it will check the memory file's signature against *all file
signatures* in a particular directory on disk.

See examples below.
"""

import hashlib
import logging
import os
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class DirectoryFileFilter(object):
    """A predicate that will return False if / when a proposed file's
    content to-be-written is identical to the contents of the file on
    disk allowing calling code to safely skip the write.

    >>> testfile = '/tmp/directory_filter_text_f39e5b58-c260-40da-9448-ad1c3b2a69c2.txt'
    >>> contents = b'This is a test'
    >>> with open(testfile, 'wb') as wf:
    ...     wf.write(contents)
    14

    >>> d = DirectoryFileFilter('/tmp')

    >>> d.apply(contents, testfile)     # False if testfile already contains contents
    False

    >>> d.apply(b'That was a test', testfile)    # True otherwise
    True

    >>> os.remove(testfile)
    """

    def __init__(self, directory: str):
        """
        Args:
            directory: the directory we're filtering accesses to
        """
        super().__init__()
        from pyutils.files import file_utils

        if not file_utils.does_directory_exist(directory):
            raise ValueError(directory)
        self.directory = directory
        self.md5_by_filename: Dict[str, str] = {}
        self.mtime_by_filename: Dict[str, float] = {}
        self._update()

    def _update(self):
        """
        Internal method.  Foreach file in the directory, compute its
        MD5 checksum via :meth:`_update_file`.
        """
        for direntry in os.scandir(self.directory):
            if direntry.is_file(follow_symlinks=True):
                mtime = direntry.stat(follow_symlinks=True).st_mtime
                path = f"{self.directory}/{direntry.name}"
                self._update_file(path, mtime)

    def _update_file(self, filename: str, mtime: Optional[float] = None):
        """
        Internal method.  Given a file and mtime, compute its MD5 checksum
        and persist it in an internal map.
        """
        from pyutils.files import file_utils

        assert file_utils.does_file_exist(filename)
        if mtime is None:
            mtime = file_utils.get_file_raw_mtime(filename)
        assert mtime is not None
        if self.mtime_by_filename.get(filename, 0) != mtime:
            md5 = file_utils.get_file_md5(filename)
            logger.debug(
                "Computed/stored %s's MD5 at ts=%.2f (%s)", filename, mtime, md5
            )
            self.mtime_by_filename[filename] = mtime
            self.md5_by_filename[filename] = md5

    def apply(self, proposed_contents: Any, filename: str) -> bool:
        """Call this with the proposed new contents of filename in
        memory and we'll compute the checksum of those contents and
        return a value that indicates whether they are identical to
        the disk contents already (so you can skip the write safely).

        Args:
            proposed_contents: the contents about to be written to
                filename
            filename: the file about to be populated with
                proposed_contents

        Returns:
            True if the disk contents of the file are identical to
            proposed_contents already and False otherwise.
        """
        self._update_file(filename)
        file_md5 = self.md5_by_filename.get(filename, 0)
        logger.debug("%s's checksum is %s", filename, file_md5)
        mem_hash = hashlib.md5()
        mem_hash.update(proposed_contents)
        md5 = mem_hash.hexdigest()
        logger.debug("Item's checksum is %s", md5)
        return md5 != file_md5


class DirectoryAllFilesFilter(DirectoryFileFilter):
    """A predicate that will return False if a file to-be-written to a
    particular directory is identical to any other file in that same
    directory (regardless of its name).

    i.e. this is the same as :class:`DirectoryFileFilter` except that
    our :meth:`apply` method will return true not only if the contents
    to be written are identical to the contents of filename on the
    disk but also it returns true if there exists some other file
    sitting in the same directory which already contains those
    identical contents.

    >>> testfile = '/tmp/directory_filter_text_f39e5b58-c260-40da-9448-ad1c3b2a69c3.txt'

    >>> contents = b'This is a test'
    >>> with open(testfile, 'wb') as wf:
    ...     wf.write(contents)
    14

    >>> d = DirectoryAllFilesFilter('/tmp')

    >>> d.apply(contents)    # False is _any_ file in /tmp contains contents
    False

    >>> d.apply(b'That was a test')    # True otherwise
    True

    >>> os.remove(testfile)

    """

    def __init__(self, directory: str):
        """
        Args:
            directory: the directory we're watching
        """
        self.all_md5s: Set[str] = set()
        super().__init__(directory)

    def _update_file(self, filename: str, mtime: Optional[float] = None):
        """Internal method.  Given a file and its mtime, update internal
        state.
        """
        from pyutils.files import file_utils

        assert file_utils.does_file_exist(filename)
        if mtime is None:
            mtime = file_utils.get_file_raw_mtime(filename)
        assert mtime is not None
        if self.mtime_by_filename.get(filename, 0) != mtime:
            md5 = file_utils.get_file_md5(filename)
            self.mtime_by_filename[filename] = mtime
            self.md5_by_filename[filename] = md5
            self.all_md5s.add(md5)

    def apply(
        self, proposed_contents: Any, ignored_filename: Optional[str] = None
    ) -> bool:
        """Call this before writing a new file to directory with the
        proposed_contents to be written and it will return a value that
        indicates whether the identical contents is already sitting in
        *any* file in that directory.  Useful, e.g., for caching.

        Args:
            proposed_contents: the contents about to be persisted to
                directory
            ignored_filename: unused for now, must be None

        Returns:
            True if proposed contents does not yet exist in any file in
            directory or False if it does exist in some file already.
        """
        assert ignored_filename is None
        self._update()
        mem_hash = hashlib.md5()
        mem_hash.update(proposed_contents)
        md5 = mem_hash.hexdigest()
        return md5 not in self.all_md5s


if __name__ == "__main__":
    import doctest

    doctest.testmod()
