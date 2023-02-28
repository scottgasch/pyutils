#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
This is a grab bag of file-related utilities.  It has code to, for example,
read files transforming the text as its read, normalize pathnames, strip
extensions, read and manipulate atimes/mtimes/ctimes, compute a signature
based on a file's contents, traverse the file system recursively, etc...
"""

import contextlib
import datetime
import errno
import fnmatch
import glob
import hashlib
import logging
import os
import pathlib
import re
import time
from os.path import exists, isfile, join
from typing import Callable, List, Literal, Optional, TextIO
from uuid import uuid4

logger = logging.getLogger(__name__)


def remove_newlines(x: str) -> str:
    """Trivial function to be used as a line_transformer in
    :meth:`slurp_file` for no newlines in file contents"""
    return x.replace("\n", "")


def strip_whitespace(x: str) -> str:
    """Trivial function to be used as a line_transformer in
    :meth:`slurp_file` for no leading / trailing whitespace in
    file contents"""
    return x.strip()


def remove_hash_comments(x: str) -> str:
    """Trivial function to be used as a line_transformer in
    :meth:`slurp_file` for no # comments in file contents"""
    return re.sub(r"#.*$", "", x)


def slurp_file(
    filename: str,
    *,
    skip_blank_lines: bool = False,
    line_transformers: Optional[List[Callable[[str], str]]] = None,
):
    """Reads in a file's contents line-by-line to a memory buffer applying
    each line transformation in turn.

    Args:
        filename: file to be read
        skip_blank_lines: should reading skip blank lines?
        line_transformers: little string->string transformations

    Returns:
        A list of lines from the read and transformed file contents.
    """

    ret = []
    xforms = []
    if line_transformers is not None:
        for x in line_transformers:
            xforms.append(x)
    if not is_readable(filename):
        raise Exception(f"{filename} can't be read.")
    with open(filename) as rf:
        for line in rf:
            for transformation in xforms:
                line = transformation(line)
            if skip_blank_lines and line == "":
                continue
            ret.append(line)
    return ret


def remove(path: str) -> None:
    """Deletes a file.  Raises if path refers to a directory or a file
    that doesn't exist.

    Args:
        path: the path of the file to delete

    >>> import os
    >>> filename = '/tmp/file_utils_test_file'
    >>> os.system(f'touch {filename}')
    0
    >>> does_file_exist(filename)
    True
    >>> remove(filename)
    >>> does_file_exist(filename)
    False
    """
    os.remove(path)


def fix_multiple_slashes(path: str) -> str:
    """Fixes multi-slashes in paths or path-like strings

    Args:
        path: the path in which to remove multiple slashes

    >>> p = '/usr/local//etc/rc.d///file.txt'
    >>> fix_multiple_slashes(p)
    '/usr/local/etc/rc.d/file.txt'

    >>> p = 'this is a test'
    >>> fix_multiple_slashes(p) == p
    True
    """
    return re.sub(r"/+", "/", path)


def delete(path: str) -> None:
    """This is a convenience for my dumb ass who can't remember os.remove
    sometimes.
    """
    os.remove(path)


def without_extension(path: str) -> str:
    """Remove one (the last) extension from a file or path.

    Args:
        path: the path from which to remove an extension

    Returns:
        the path with one extension removed.

    See also :meth:`without_all_extensions`.

    >>> without_extension('foobar.txt')
    'foobar'

    >>> without_extension('/home/scott/frapp.py')
    '/home/scott/frapp'

    >>> f = 'a.b.c.tar.gz'
    >>> while('.' in f):
    ...     f = without_extension(f)
    ...     print(f)
    a.b.c.tar
    a.b.c
    a.b
    a

    >>> without_extension('foobar')
    'foobar'

    """
    return os.path.splitext(path)[0]


def without_all_extensions(path: str) -> str:
    """Removes all extensions from a path; handles multiple extensions
    like foobar.tar.gz -> foobar.

    Args:
        path: the path from which to remove all extensions

    Returns:
        the path with all extensions removed.

    See also :meth:`without_extension`

    >>> without_all_extensions('/home/scott/foobar.1.tar.gz')
    '/home/scott/foobar'

    """
    while "." in path:
        path = without_extension(path)
    return path


def get_extension(path: str) -> str:
    """Extract and return one (the last) extension from a file or path.

    Args:
        path: the path from which to extract an extension

    Returns:
        The last extension from the file path.

    See also :meth:`without_extension`, :meth:`without_all_extensions`,
    :meth:`get_all_extensions`.

    >>> get_extension('this_is_a_test.txt')
    '.txt'

    >>> get_extension('/home/scott/test.py')
    '.py'

    >>> get_extension('foobar')
    ''

    """
    return os.path.splitext(path)[1]


def get_all_extensions(path: str) -> List[str]:
    """Return the extensions of a file or path in order.

    Args:
        path: the path from which to extract all extensions.

    Returns:
        a list containing each extension which may be empty.

    See also :meth:`without_extension`, :meth:`without_all_extensions`,
    :meth:`get_extension`.

    >>> get_all_extensions('/home/scott/foo.tar.gz.1')
    ['.tar', '.gz', '.1']

    >>> get_all_extensions('/home/scott/foobar')
    []

    """
    ret = []
    while True:
        ext = get_extension(path)
        path = without_extension(path)
        if ext:
            ret.append(ext)
        else:
            ret.reverse()
            return ret


def without_path(filespec: str) -> str:
    """Returns the base filename without any leading path.

    Args:
        filespec: path to remove leading directories from

    Returns:
        filespec without leading dir components.

    See also :meth:`get_path`, :meth:`get_canonical_path`.

    >>> without_path('/home/scott/foo.py')
    'foo.py'

    >>> without_path('foo.py')
    'foo.py'

    """
    return os.path.split(filespec)[1]


def get_path(filespec: str) -> str:
    """Returns just the path of the filespec by removing the filename and
    extension.

    Args:
        filespec: path to remove filename / extension(s) from

    Returns:
        filespec with just the leading directory components and no
            filename or extension(s)

    See also :meth:`without_path`, :meth:`get_canonical_path`.

    >>> get_path('/home/scott/foobar.py')
    '/home/scott'

    >>> get_path('/home/scott/test.1.2.3.gz')
    '/home/scott'

    >>> get_path('~scott/frapp.txt')
    '~scott'

    """
    return os.path.split(filespec)[0]


def get_canonical_path(filespec: str) -> str:
    """Returns a canonicalized absolute path.

    Args:
        filespec: the path to canonicalize

    Returns:
        the canonicalized path

    See also :meth:`get_path`, :meth:`without_path`.

    >>> get_canonical_path('/home/scott/../../home/lynn/../scott/foo.txt')
    '/usr/home/scott/foo.txt'

    """
    return os.path.realpath(filespec)


def create_path_if_not_exist(
    path: str, on_error: Callable[[str, OSError], None] = None
) -> None:
    """
    Attempts to create path if it does not exist already.

    Args:
        path: the path to attempt to create
        on_error: If set, it's invoked on error conditions and passed then
            path and OSError that it caused.

    See also :meth:`does_file_exist`.

    .. warning::

        Files are created with mode 0o0777 (i.e. world read/writeable).

    >>> import uuid
    >>> import os
    >>> path = os.path.join("/tmp", str(uuid.uuid4()), str(uuid.uuid4()))
    >>> os.path.exists(path)
    False
    >>> create_path_if_not_exist(path)
    >>> os.path.exists(path)
    True
    """
    logger.debug("Creating path %s", path)
    previous_umask = os.umask(0)
    try:
        os.makedirs(path)
        os.chmod(path, 0o777)
    except OSError as ex:
        if ex.errno != errno.EEXIST and not os.path.isdir(path):
            if on_error is not None:
                on_error(path, ex)
            else:
                raise
    finally:
        os.umask(previous_umask)


def does_file_exist(filename: str) -> bool:
    """Returns True if a file exists and is a normal file.

    Args:
        filename: filename to check

    Returns:
        True if filename exists and is a normal file.

    See also :meth:`create_path_if_not_exist`, :meth:`is_readable`.

    >>> does_file_exist(__file__)
    True
    >>> does_file_exist('/tmp/2492043r9203r9230r9230r49230r42390r4230')
    False
    """
    return os.path.exists(filename) and os.path.isfile(filename)


def is_readable(filename: str) -> bool:
    """Is the file readable?

    Args:
        filename: the filename to check for read access

    Returns:
        True if the file exists, is a normal file, and is readable
        by the current process.  False otherwise.

    See also :meth:`does_file_exist`, :meth:`is_writable`,
    :meth:`is_executable`.
    """
    return os.access(filename, os.R_OK)


def is_writable(filename: str) -> bool:
    """Is the file writable?

    Args:
        filename: the file to check for write access.

    Returns:
        True if file exists, is a normal file and is writable by the
        current process.  False otherwise.

    See also :meth:`is_readable`, :meth:`does_file_exist`.
    """
    return os.access(filename, os.W_OK)


def is_executable(filename: str) -> bool:
    """Is the file executable?

    Args:
        filename: the file to check for execute access.

    Returns:
        True if file exists, is a normal file and is executable by the
        current process.  False otherwise.

    See also :meth:`does_file_exist`, :meth:`is_readable`,
    :meth:`is_writable`.
    """
    return os.access(filename, os.X_OK)


def does_directory_exist(dirname: str) -> bool:
    """Does the given directory exist?

    Args:
        dirname: the name of the directory to check

    Returns:
        True if a path exists and is a directory, not a regular file.

    See also :meth:`does_file_exist`.

    >>> does_directory_exist('/tmp')
    True
    >>> does_directory_exist('/xyzq/21341')
    False
    """
    return os.path.exists(dirname) and os.path.isdir(dirname)


def does_path_exist(pathname: str) -> bool:
    """Just a more verbose wrapper around os.path.exists."""
    return os.path.exists(pathname)


def get_file_size(filename: str) -> int:
    """Returns the size of a file in bytes.

    Args:
        filename: the filename to size

    Returns:
        size of filename in bytes
    """
    return os.path.getsize(filename)


def is_normal_file(filename: str) -> bool:
    """Is that file normal (not a directory or some special file?)

    Args:
        filename: the path of the file to check

    Returns:
        True if filename is a normal file.

    See also :meth:`is_directory`, :meth:`does_file_exist`, :meth:`is_symlink`.

    >>> is_normal_file(__file__)
    True
    """
    return os.path.isfile(filename)


def is_directory(filename: str) -> bool:
    """Is that path a directory (not a normal file?)

    Args:
        filename: the path of the file to check

    Returns:
        True if filename is a directory

    See also :meth:`does_directory_exist`, :meth:`is_normal_file`,
    :meth:`is_symlink`.

    >>> is_directory('/tmp')
    True
    """
    return os.path.isdir(filename)


def is_symlink(filename: str) -> bool:
    """Is that path a symlink?

    Args:
        filename: the path of the file to check

    Returns:
        True if filename is a symlink, False otherwise.

    See also :meth:`is_directory`, :meth:`is_normal_file`.

    >>> is_symlink('/tmp')
    False

    >>> is_symlink('/home')
    True
    """
    return os.path.islink(filename)


def is_same_file(file1: str, file2: str) -> bool:
    """Determine if two paths reference the same inode.

    Args:
        file1: the first file
        file2: the second file

    Returns:
        True if the two files are the same file.

    See also :meth:`is_symlink`, :meth:`is_normal_file`.

    >>> is_same_file('/tmp', '/tmp/../tmp')
    True

    >>> is_same_file('/tmp', '/home')
    False
    """
    return os.path.samefile(file1, file2)


def get_file_raw_timestamps(filename: str) -> Optional[os.stat_result]:
    """Stats the file and returns an `os.stat_result` or None on error.

    Args:
        filename: the file whose timestamps to fetch

    Returns:
        the os.stat_result or None to indicate an error occurred

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamp`
    """
    try:
        return os.stat(filename)
    except Exception:
        logger.exception("Failed to stat path %s; returning None", filename)
        return None


def get_file_raw_timestamp(
    filename: str, extractor: Callable[[os.stat_result], Optional[float]]
) -> Optional[float]:
    """Stat a file and, if successful, use extractor to fetch some
    subset of the information in the `os.stat_result`.

    Args:
        filename: the filename to stat
        extractor: Callable that takes a os.stat_result and produces
            something useful(?) with it.

    Returns:
        whatever the extractor produced or None on error.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    """
    tss = get_file_raw_timestamps(filename)
    if tss is not None:
        return extractor(tss)
    return None


def get_file_raw_atime(filename: str) -> Optional[float]:
    """Get a file's raw access time.

    Args:
        filename: the path to the file to stat

    Returns:
        The file's raw atime (seconds since the Epoch) or
        None on error.

    See also
    :meth:`get_file_atime_age_seconds`,
    :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    """
    return get_file_raw_timestamp(filename, lambda x: x.st_atime)


def get_file_raw_mtime(filename: str) -> Optional[float]:
    """Get a file's raw modification time.

    Args:
        filename: the path to the file to stat

    Returns:
        The file's raw mtime (seconds since the Epoch) or
        None on error.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_mtime_age_seconds`,
    :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_raw_timestamps`
    """
    return get_file_raw_timestamp(filename, lambda x: x.st_mtime)


def get_file_raw_ctime(filename: str) -> Optional[float]:
    """Get a file's raw creation time.

    Args:
        filename: the path to the file to stat

    Returns:
        The file's raw ctime (seconds since the Epoch) or
        None on error.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_ctime_age_seconds`,
    :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    """
    return get_file_raw_timestamp(filename, lambda x: x.st_ctime)


def get_file_md5(filename: str) -> str:
    """Hashes filename's disk contents and returns the MD5 digest.

    Args:
        filename: the file whose contents to hash

    Returns:
        the MD5 digest of the file's contents.  Raises on error.
    """
    file_hash = hashlib.md5()
    with open(filename, "rb") as f:
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
    return file_hash.hexdigest()


def set_file_raw_atime(filename: str, atime: float) -> None:
    """Sets a file's raw access time.

    Args:
        filename: the file whose atime should be set
        atime: raw atime as number of seconds since the Epoch to set

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_mtime`,
    :meth:`set_file_raw_atime_and_mtime`,
    :meth:`touch_file`
    """
    mtime = get_file_raw_mtime(filename)
    assert mtime is not None
    os.utime(filename, (atime, mtime))


def set_file_raw_mtime(filename: str, mtime: float):
    """Sets a file's raw modification time.

    Args:
        filename: the file whose mtime should be set
        mtime: the raw mtime as number of seconds since the Epoch to set

    See also
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_mtime_age_seconds`,
    :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`,
    :meth:`touch_file`
    """
    atime = get_file_raw_atime(filename)
    assert atime is not None
    os.utime(filename, (atime, mtime))


def set_file_raw_atime_and_mtime(filename: str, ts: float = None):
    """Sets both a file's raw modification and access times.

    Args:
        filename: the file whose times to set
        ts: the raw time to set or None to indicate time should be
            set to the current time.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_mtime`
    """
    if ts is not None:
        os.utime(filename, (ts, ts))
    else:
        os.utime(filename, None)


def _convert_file_timestamp_to_datetime(
    filename: str,
    producer: Callable[[str], Optional[float]],
) -> Optional[datetime.datetime]:
    """
    Converts a raw file timestamp into a Python datetime.

    Args:
        filename: file whose timestamps should be converted.
        producer: source of the timestamp.
    Returns:
        The datetime.
    """
    ts = producer(filename)
    if ts is not None:
        return datetime.datetime.fromtimestamp(ts)
    return None


def get_file_atime_as_datetime(filename: str) -> Optional[datetime.datetime]:
    """Fetch a file's access time as a Python datetime.

    Args:
        filename: the file whose atime should be fetched.

    Returns:
        The file's atime as a Python :class:`datetime.datetime`.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return _convert_file_timestamp_to_datetime(filename, get_file_raw_atime)


def get_file_mtime_as_datetime(filename: str) -> Optional[datetime.datetime]:
    """Fetch a file's modification time as a Python datetime.

    Args:
        filename: the file whose mtime should be fetched.

    Returns:
        The file's mtime as a Python :class:`datetime.datetime`.

    See also
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_mtime_age_seconds`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return _convert_file_timestamp_to_datetime(filename, get_file_raw_mtime)


def get_file_ctime_as_datetime(filename: str) -> Optional[datetime.datetime]:
    """Fetches a file's creation time as a Python datetime.

    Args:
        filename: the file whose ctime should be fetched.

    Returns:
        The file's ctime as a Python :class:`datetime.datetime`.

    See also
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_ctime_age_seconds`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    """
    return _convert_file_timestamp_to_datetime(filename, get_file_raw_ctime)


def _get_file_timestamp_age_seconds(filename: str, extractor) -> Optional[int]:
    """~Internal helper"""
    now = time.time()
    ts = get_file_raw_timestamps(filename)
    if ts is None:
        return None
    result = extractor(ts)
    return now - result


def get_file_atime_age_seconds(filename: str) -> Optional[int]:
    """Gets a file's access time as an age in seconds (ago).

    Args:
        filename: file whose atime should be checked.

    Returns:
        The number of seconds ago that filename was last accessed.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return _get_file_timestamp_age_seconds(filename, lambda x: x.st_atime)


def get_file_ctime_age_seconds(filename: str) -> Optional[int]:
    """Gets a file's creation time as an age in seconds (ago).

    Args:
        filename: file whose ctime should be checked.

    Returns:
        The number of seconds ago that filename was created.

    See also
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_ctime_age_seconds`,
    :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_timestamps`
    """
    return _get_file_timestamp_age_seconds(filename, lambda x: x.st_ctime)


def get_file_mtime_age_seconds(filename: str) -> Optional[int]:
    """Gets a file's modification time as seconds (ago).

    Args:
        filename: file whose mtime should be checked.

    Returns:
        The number of seconds ago that filename was last modified.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return _get_file_timestamp_age_seconds(filename, lambda x: x.st_mtime)


def _get_file_timestamp_timedelta(
    filename: str, extractor
) -> Optional[datetime.timedelta]:
    """~Internal helper"""
    age = _get_file_timestamp_age_seconds(filename, extractor)
    if age is not None:
        return datetime.timedelta(seconds=float(age))
    return None


def get_file_atime_timedelta(filename: str) -> Optional[datetime.timedelta]:
    """How long ago was a file accessed as a timedelta?

    Args:
        filename: the file whose atime should be checked.

    Returns:
        A Python :class:`datetime.timedelta` representing how long
        ago filename was last accessed.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return _get_file_timestamp_timedelta(filename, lambda x: x.st_atime)


def get_file_ctime_timedelta(filename: str) -> Optional[datetime.timedelta]:
    """How long ago was a file created as a timedelta?

    Args:
        filename: the file whose ctime should be checked.

    Returns:
        A Python :class:`datetime.timedelta` representing how long
        ago filename was created.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_ctime_age_seconds`,
    :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    """
    return _get_file_timestamp_timedelta(filename, lambda x: x.st_ctime)


def get_file_mtime_timedelta(filename: str) -> Optional[datetime.timedelta]:
    """
    Gets a file's modification time as a Python timedelta.

    Args:
        filename: the file whose mtime should be checked.

    Returns:
        A Python :class:`datetime.timedelta` representing how long
        ago filename was last modified.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_mtime_age_seconds`,
    :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return _get_file_timestamp_timedelta(filename, lambda x: x.st_mtime)


def describe_file_timestamp(filename: str, extractor, *, brief=False) -> Optional[str]:
    """~Internal helper"""
    from pyutils.datetimes.datetime_utils import (
        describe_duration,
        describe_duration_briefly,
    )

    age = _get_file_timestamp_age_seconds(filename, extractor)
    if age is None:
        return None
    if brief:
        return describe_duration_briefly(age)
    else:
        return describe_duration(age)


def describe_file_atime(filename: str, *, brief: bool = False) -> Optional[str]:
    """
    Describe how long ago a file was accessed.

    Args:
        filename: the file whose atime should be described.
        brief: if True, describe atime briefly.

    Returns:
        A string that represents how long ago filename was last
        accessed.  The description will be verbose or brief depending
        on the brief argument.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return describe_file_timestamp(filename, lambda x: x.st_atime, brief=brief)


def describe_file_ctime(filename: str, *, brief: bool = False) -> Optional[str]:
    """Describes a file's creation time.

    Args:
        filename: the file whose ctime should be described.
        brief: if True, describe ctime briefly.

    Returns:
        A string that represents how long ago filename was created.
        The description will be verbose or brief depending
        on the brief argument.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_ctime_age_seconds`,
    :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_raw_timestamps`
    """
    return describe_file_timestamp(filename, lambda x: x.st_ctime, brief=brief)


def describe_file_mtime(filename: str, *, brief: bool = False) -> Optional[str]:
    """Describes how long ago a file was modified.

    Args:
        filename: the file whose mtime should be described.
        brief: if True, describe mtime briefly.

    Returns:
        A string that represents how long ago filename was last
        modified.  The description will be verbose or brief depending
        on the brief argument.

    See also
    :meth:`get_file_raw_atime`,
    :meth:`get_file_raw_ctime`,
    :meth:`get_file_raw_mtime`,
    :meth:`get_file_mtime_age_seconds`,
    :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_raw_timestamps`,
    :meth:`set_file_raw_atime`,
    :meth:`set_file_raw_atime_and_mtime`
    """
    return describe_file_timestamp(filename, lambda x: x.st_mtime, brief=brief)


def touch_file(filename: str, *, mode: Optional[int] = 0o666):
    """Like unix "touch" command's semantics: update the timestamp
    of a file to the current time if the file exists.  Create the
    file if it doesn't exist.

    Args:
        filename: the filename
        mode: the mode to create the file with

    .. warning::

        The default creation mode is 0o666 which is world readable
        and writable.  Override this by passing in your own mode
        parameter if desired.

    See also :meth:`set_file_raw_atime`, :meth:`set_file_raw_atime_and_mtime`,
    :meth:`set_file_raw_mtime`, :meth:`create_path_if_not_exist`
    """
    pathlib.Path(filename, mode=mode).touch()


def expand_globs(in_filename: str):
    """
    Expands shell globs (* and ? wildcards) to the matching files.

    Args:
        in_filename: the filepath to be expanded.  May contain '*' and '?'
            globbing characters.

    Returns:
        A Generator that yields filenames that match the input pattern.

    See also :meth:`get_files`, :meth:`get_files_recursive`.
    """
    for filename in glob.glob(in_filename):
        yield filename


def get_files(directory: str):
    """Returns the files in a directory as a generator.

    Args:
        directory: the directory to list files under.

    Returns:
        A generator that yields all files in the input directory.

    See also :meth:`expand_globs`, :meth:`get_files_recursive`,
    :meth:`get_matching_files`.
    """
    for filename in os.listdir(directory):
        full_path = join(directory, filename)
        if isfile(full_path) and exists(full_path):
            yield full_path


def get_matching_files(directory: str, glob_string: str):
    """
    Returns the subset of files whose name matches a glob.

    Args:
        directory: the directory to match files within.
        glob_string: the globbing pattern (may include '*' and '?') to
            use when matching files.

    Returns:
        A generator that yields filenames in directory that match
        the given glob pattern.

    See also :meth:`get_files`, :meth:`expand_globs`.
    """
    for filename in get_files(directory):
        if fnmatch.fnmatch(filename, glob_string):
            yield filename


def get_directories(directory: str):
    """
    Returns the subdirectories in a directory as a generator.

    Args:
        directory: the directory to list subdirectories within.

    Returns:
        A generator that yields all subdirectories within the given
        input directory.

    See also :meth:`get_files`, :meth:`get_files_recursive`.
    """
    for d in os.listdir(directory):
        full_path = join(directory, d)
        if not isfile(full_path) and exists(full_path):
            yield full_path


def get_files_recursive(directory: str):
    """
    Find the files and directories under a root recursively.

    Args:
        directory: the root directory under which to list subdirectories
            and file contents.

    Returns:
        A generator that yields all directories and files beneath the input
        root directory.

    See also :meth:`get_files`, :meth:`get_matching_files`,
    :meth:`get_matching_files_recursive`
    """
    for filename in get_files(directory):
        yield filename
    for subdir in get_directories(directory):
        for file_or_directory in get_files_recursive(subdir):
            yield file_or_directory


def get_matching_files_recursive(directory: str, glob_string: str):
    """Returns the subset of files whose name matches a glob under a root recursively.

    Args:
        directory: the root under which to search
        glob_string: a globbing pattern that describes the subset of
            files and directories to return.  May contain '?' and '*'.

    Returns:
        A generator that yields all files and directories under the given root
        directory that match the given globbing pattern.

    See also :meth:`get_files_recursive`.

    """
    for filename in get_files_recursive(directory):
        if fnmatch.fnmatch(filename, glob_string):
            yield filename


class FileWriter(contextlib.AbstractContextManager):
    """A helper that writes a file to a temporary location and then
    moves it atomically to its ultimate destination on close.

    Example usage.  Creates a temporary file that is populated by the
    print statements within the context.  Until the context is exited,
    the true destination file does not exist so no reader of it can
    see partial writes due to buffering or code timing.  Once the
    context is exited, the file is moved from its temporary location
    to its permanent location by a call to `/bin/mv` which should be
    atomic::

        with FileWriter('/home/bob/foobar.txt') as w:
            print("This is a test!", file=w)
            time.sleep(2)
            print("This is only a test...", file=w)
    """

    def __init__(self, filename: str) -> None:
        """
        Args:
            filename: the ultimate destination file we want to populate.
                On exit, the file will be atomically created.
        """
        self.filename = filename
        uuid = uuid4()
        self.tempfile = f"{filename}-{uuid}.tmp"
        self.handle: Optional[TextIO] = None

    def __enter__(self) -> TextIO:
        assert not does_path_exist(self.tempfile)
        self.handle = open(self.tempfile, mode="w")
        return self.handle

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        if self.handle is not None:
            self.handle.close()
            cmd = f"/bin/mv -f {self.tempfile} {self.filename}"
            ret = os.system(cmd)
            if (ret >> 8) != 0:
                raise Exception(f"{cmd} failed, exit value {ret>>8}!")
        return False


class CreateFileWithMode(contextlib.AbstractContextManager):
    """This helper context manager can be used instead of the typical
    pattern for creating a file if you want to ensure that the file
    created is a particular permission mode upon creation.

    Python's open doesn't support this; you need to set the os.umask
    and then create a descriptor to open via os.open, see below.

        >>> import os
        >>> filename = f'/tmp/CreateFileWithModeTest.{os.getpid()}'
        >>> with CreateFileWithMode(filename, mode=0o600) as wf:
        ...     print('This is a test', file=wf)
        >>> result = os.stat(filename)

        Note: there is a high order bit set in this that is S_IFREG indicating
        that the file is a "normal file".  Clear it with the mask.

        >>> print(f'{result.st_mode & 0o7777:o}')
        600
        >>> with open(filename, 'r') as rf:
        ...     contents = rf.read()
        >>> contents
        'This is a test\\n'
        >>> remove(filename)
    """

    def __init__(self, filename: str, mode: Optional[int] = 0o600) -> None:
        """
        Args:
            filename: path of the file to create.
            mode: the UNIX-style octal mode with which to create the
                filename.  Defaults to 0o600.

        .. warning::

            If the file already exists it will be overwritten!

        """
        self.filename = filename
        if mode is not None:
            self.mode = mode & 0o7777
        else:
            self.mode = 0o666
        self.handle: Optional[TextIO] = None
        self.old_umask = os.umask(0)

    def __enter__(self) -> TextIO:
        descriptor = os.open(
            path=self.filename,
            flags=(os.O_WRONLY | os.O_CREAT | os.O_TRUNC),
            mode=self.mode,
        )
        self.handle = open(descriptor, "w")
        return self.handle

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        os.umask(self.old_umask)
        if self.handle is not None:
            self.handle.close()
        return False


if __name__ == "__main__":
    import doctest

    doctest.testmod()
