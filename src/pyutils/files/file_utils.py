#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Utilities for working with files."""

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
    return x.replace('\n', '')


def strip_whitespace(x: str) -> str:
    """Trivial function to be used as a line_transformer in
    :meth:`slurp_file` for no leading / trailing whitespace in
    file contents"""
    return x.strip()


def remove_hash_comments(x: str) -> str:
    """Trivial function to be used as a line_transformer in
    :meth:`slurp_file` for no # comments in file contents"""
    return re.sub(r'#.*$', '', x)


def slurp_file(
    filename: str,
    *,
    skip_blank_lines=False,
    line_transformers: Optional[List[Callable[[str], str]]] = None,
):
    """Reads in a file's contents line-by-line to a memory buffer applying
    each line transformation in turn.

    Args:
        filename: file to be read
        skip_blank_lines: should reading skip blank lines?
        line_transformers: little string->string transformations
    """

    ret = []
    xforms = []
    if line_transformers is not None:
        for x in line_transformers:
            xforms.append(x)
    if not file_is_readable(filename):
        raise Exception(f'{filename} can\'t be read.')
    with open(filename) as rf:
        for line in rf:
            for transformation in xforms:
                line = transformation(line)
            if skip_blank_lines and line == '':
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
    return re.sub(r'/+', '/', path)


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

    >>> without_all_extensions('/home/scott/foobar.1.tar.gz')
    '/home/scott/foobar'

    """
    while '.' in path:
        path = without_extension(path)
    return path


def get_extension(path: str) -> str:
    """Extract and return one (the last) extension from a file or path.

    Args:
        path: the path from which to extract an extension

    Returns:
        The last extension from the file path.

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

    >>> get_canonical_path('/home/scott/../../home/lynn/../scott/foo.txt')
    '/usr/home/scott/foo.txt'

    """
    return os.path.realpath(filespec)


def create_path_if_not_exist(path, on_error=None) -> None:
    """
    Attempts to create path if it does not exist already.

    .. warning::

        Files are created with mode 0x0777 (i.e. world read/writeable).

    Args:
        path: the path to attempt to create
        on_error: If True, it's invoked on error conditions.  Otherwise
            any exceptions are raised.

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

    >>> does_file_exist(__file__)
    True
    >>> does_file_exist('/tmp/2492043r9203r9230r9230r49230r42390r4230')
    False
    """
    return os.path.exists(filename) and os.path.isfile(filename)


def file_is_readable(filename: str) -> bool:
    """True if file exists, is a normal file and is readable by the
    current process.  False otherwise.

    Args:
        filename: the filename to check for read access
    """
    return does_file_exist(filename) and os.access(filename, os.R_OK)


def file_is_writable(filename: str) -> bool:
    """True if file exists, is a normal file and is writable by the
    current process.  False otherwise.

    Args:
        filename: the file to check for write access.
    """
    return does_file_exist(filename) and os.access(filename, os.W_OK)


def file_is_executable(filename: str) -> bool:
    """True if file exists, is a normal file and is executable by the
    current process.  False otherwise.

    Args:
        filename: the file to check for execute access.
    """
    return does_file_exist(filename) and os.access(filename, os.X_OK)


def does_directory_exist(dirname: str) -> bool:
    """Returns True if a file exists and is a directory.

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
    """Returns True if filename is a normal file.

    >>> is_normal_file(__file__)
    True
    """
    return os.path.isfile(filename)


def is_directory(filename: str) -> bool:
    """Returns True if filename is a directory.

    >>> is_directory('/tmp')
    True
    """
    return os.path.isdir(filename)


def is_symlink(filename: str) -> bool:
    """True if filename is a symlink, False otherwise.

    >>> is_symlink('/tmp')
    False

    >>> is_symlink('/home')
    True

    """
    return os.path.islink(filename)


def is_same_file(file1: str, file2: str) -> bool:
    """Returns True if the two files are the same inode.

    >>> is_same_file('/tmp', '/tmp/../tmp')
    True

    >>> is_same_file('/tmp', '/home')
    False

    """
    return os.path.samefile(file1, file2)


def get_file_raw_timestamps(filename: str) -> Optional[os.stat_result]:
    """Stats the file and returns an os.stat_result or None on error.

    Args:
        filename: the file whose timestamps to fetch

    Returns:
        the os.stat_result or None to indicate an error occurred
    """
    try:
        return os.stat(filename)
    except Exception as e:
        logger.exception(e)
        return None


def get_file_raw_timestamp(
    filename: str, extractor: Callable[[os.stat_result], Optional[float]]
) -> Optional[float]:
    """Stat a file and, if successful, use extractor to fetch some
    subset of the information in the os.stat_result.  See also
    :meth:`get_file_raw_atime`, :meth:`get_file_raw_mtime`, and
    :meth:`get_file_raw_ctime` which just call this with a lambda
    extractor.

    Args:
        filename: the filename to stat
        extractor: Callable that takes a os.stat_result and produces
            something useful(?) with it.

    Returns:
        whatever the extractor produced or None on error.
    """
    tss = get_file_raw_timestamps(filename)
    if tss is not None:
        return extractor(tss)
    return None


def get_file_raw_atime(filename: str) -> Optional[float]:
    """Get a file's raw access time or None on error.

    See also :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    and :meth:`get_file_atime_age_seconds`.
    """
    return get_file_raw_timestamp(filename, lambda x: x.st_atime)


def get_file_raw_mtime(filename: str) -> Optional[float]:
    """Get a file's raw modification time or None on error.

    See also :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    and :meth:`get_file_mtime_age_seconds`.
    """
    return get_file_raw_timestamp(filename, lambda x: x.st_mtime)


def get_file_raw_ctime(filename: str) -> Optional[float]:
    """Get a file's raw creation time or None on error.

    See also :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    and :meth:`get_file_ctime_age_seconds`.
    """
    return get_file_raw_timestamp(filename, lambda x: x.st_ctime)


def get_file_md5(filename: str) -> str:
    """Hashes filename's disk contents and returns the MD5 digest.

    Args:
        filename: the file whose contents to hash

    Returns:
        the MD5 digest of the file's contents.  Raises on errors.
    """
    file_hash = hashlib.md5()
    with open(filename, "rb") as f:
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
    return file_hash.hexdigest()


def set_file_raw_atime(filename: str, atime: float):
    """Sets a file's raw access time.

    See also :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_atime_age_seconds`,
    and :meth:`get_file_raw_atime`.
    """
    mtime = get_file_raw_mtime(filename)
    assert mtime is not None
    os.utime(filename, (atime, mtime))


def set_file_raw_mtime(filename: str, mtime: float):
    """Sets a file's raw modification time.

    See also :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_mtime_age_seconds`,
    and :meth:`get_file_raw_mtime`.
    """
    atime = get_file_raw_atime(filename)
    assert atime is not None
    os.utime(filename, (atime, mtime))


def set_file_raw_atime_and_mtime(filename: str, ts: float = None):
    """Sets both a file's raw modification and access times

    Args:
        filename: the file whose times to set
        ts: the raw time to set or None to indicate time should be
            set to the current time.
    """
    if ts is not None:
        os.utime(filename, (ts, ts))
    else:
        os.utime(filename, None)


def convert_file_timestamp_to_datetime(
    filename: str, producer
) -> Optional[datetime.datetime]:
    """Convert a raw file timestamp into a python datetime."""
    ts = producer(filename)
    if ts is not None:
        return datetime.datetime.fromtimestamp(ts)
    return None


def get_file_atime_as_datetime(filename: str) -> Optional[datetime.datetime]:
    """Fetch a file's access time as a python datetime.

    See also :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`describe_file_atime`,
    and :meth:`get_file_raw_atime`.
    """
    return convert_file_timestamp_to_datetime(filename, get_file_raw_atime)


def get_file_mtime_as_datetime(filename: str) -> Optional[datetime.datetime]:
    """Fetches a file's modification time as a python datetime.

    See also :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_mtime_age_seconds`,
    and :meth:`get_file_raw_mtime`.
    """
    return convert_file_timestamp_to_datetime(filename, get_file_raw_mtime)


def get_file_ctime_as_datetime(filename: str) -> Optional[datetime.datetime]:
    """Fetches a file's creation time as a python datetime.

    See also :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_ctime_age_seconds`,
    and :meth:`get_file_raw_ctime`.
    """
    return convert_file_timestamp_to_datetime(filename, get_file_raw_ctime)


def get_file_timestamp_age_seconds(filename: str, extractor) -> Optional[int]:
    """~Internal helper"""
    now = time.time()
    ts = get_file_raw_timestamps(filename)
    if ts is None:
        return None
    result = extractor(ts)
    return now - result


def get_file_atime_age_seconds(filename: str) -> Optional[int]:
    """Gets a file's access time as an age in seconds (ago).

    See also :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`describe_file_atime`,
    and :meth:`get_file_raw_atime`.
    """
    return get_file_timestamp_age_seconds(filename, lambda x: x.st_atime)


def get_file_ctime_age_seconds(filename: str) -> Optional[int]:
    """Gets a file's creation time as an age in seconds (ago).

    See also :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_ctime_age_seconds`,
    and :meth:`get_file_raw_ctime`.
    """
    return get_file_timestamp_age_seconds(filename, lambda x: x.st_ctime)


def get_file_mtime_age_seconds(filename: str) -> Optional[int]:
    """Gets a file's modification time as seconds (ago).

    See also :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_mtime_age_seconds`,
    and :meth:`get_file_raw_mtime`.
    """
    return get_file_timestamp_age_seconds(filename, lambda x: x.st_mtime)


def get_file_timestamp_timedelta(
    filename: str, extractor
) -> Optional[datetime.timedelta]:
    """~Internal helper"""
    age = get_file_timestamp_age_seconds(filename, extractor)
    if age is not None:
        return datetime.timedelta(seconds=float(age))
    return None


def get_file_atime_timedelta(filename: str) -> Optional[datetime.timedelta]:
    """How long ago was a file accessed as a timedelta?

    See also :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`describe_file_atime`,
    and :meth:`get_file_raw_atime`.
    """
    return get_file_timestamp_timedelta(filename, lambda x: x.st_atime)


def get_file_ctime_timedelta(filename: str) -> Optional[datetime.timedelta]:
    """How long ago was a file created as a timedelta?

    See also :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_ctime_age_seconds`,
    and :meth:`get_file_raw_ctime`.
    """
    return get_file_timestamp_timedelta(filename, lambda x: x.st_ctime)


def get_file_mtime_timedelta(filename: str) -> Optional[datetime.timedelta]:
    """
    Gets a file's modification time as a python timedelta.

    See also :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_mtime_age_seconds`,
    and :meth:`get_file_raw_mtime`.
    """
    return get_file_timestamp_timedelta(filename, lambda x: x.st_mtime)


def describe_file_timestamp(filename: str, extractor, *, brief=False) -> Optional[str]:
    """~Internal helper"""
    from pyutils.datetimez.datetime_utils import (
        describe_duration,
        describe_duration_briefly,
    )

    age = get_file_timestamp_age_seconds(filename, extractor)
    if age is None:
        return None
    if brief:
        return describe_duration_briefly(age)
    else:
        return describe_duration(age)


def describe_file_atime(filename: str, *, brief=False) -> Optional[str]:
    """
    Describe how long ago a file was accessed.

    See also :meth:`get_file_atime_as_datetime`,
    :meth:`get_file_atime_timedelta`,
    :meth:`get_file_atime_age_seconds`,
    :meth:`describe_file_atime`,
    and :meth:`get_file_raw_atime`.
    """
    return describe_file_timestamp(filename, lambda x: x.st_atime, brief=brief)


def describe_file_ctime(filename: str, *, brief=False) -> Optional[str]:
    """Describes a file's creation time.

    See also :meth:`get_file_ctime_as_datetime`,
    :meth:`get_file_ctime_timedelta`,
    :meth:`get_file_ctime_age_seconds`,
    and :meth:`get_file_raw_ctime`.
    """
    return describe_file_timestamp(filename, lambda x: x.st_ctime, brief=brief)


def describe_file_mtime(filename: str, *, brief=False) -> Optional[str]:
    """
    Describes how long ago a file was modified.

    See also :meth:`get_file_mtime_as_datetime`,
    :meth:`get_file_mtime_timedelta`,
    :meth:`get_file_mtime_age_seconds`,
    and :meth:`get_file_raw_mtime`.
    """
    return describe_file_timestamp(filename, lambda x: x.st_mtime, brief=brief)


def touch_file(filename: str, *, mode: Optional[int] = 0o666):
    """Like unix "touch" command's semantics: update the timestamp
    of a file to the current time if the file exists.  Create the
    file if it doesn't exist.

    Args:
        filename: the filename
        mode: the mode to create the file with
    """
    pathlib.Path(filename, mode=mode).touch()


def expand_globs(in_filename: str):
    """Expands shell globs (* and ? wildcards) to the matching files."""
    for filename in glob.glob(in_filename):
        yield filename


def get_files(directory: str):
    """Returns the files in a directory as a generator."""
    for filename in os.listdir(directory):
        full_path = join(directory, filename)
        if isfile(full_path) and exists(full_path):
            yield full_path


def get_matching_files(directory: str, glob: str):
    """Returns the subset of files whose name matches a glob."""
    for filename in get_files(directory):
        if fnmatch.fnmatch(filename, glob):
            yield filename


def get_directories(directory: str):
    """Returns the subdirectories in a directory as a generator."""
    for d in os.listdir(directory):
        full_path = join(directory, d)
        if not isfile(full_path) and exists(full_path):
            yield full_path


def get_files_recursive(directory: str):
    """Find the files and directories under a root recursively."""
    for filename in get_files(directory):
        yield filename
    for subdir in get_directories(directory):
        for file_or_directory in get_files_recursive(subdir):
            yield file_or_directory


def get_matching_files_recursive(directory: str, glob: str):
    """Returns the subset of files whose name matches a glob under a root recursively."""
    for filename in get_files_recursive(directory):
        if fnmatch.fnmatch(filename, glob):
            yield filename


class FileWriter(contextlib.AbstractContextManager):
    """A helper that writes a file to a temporary location and then moves
    it atomically to its ultimate destination on close.
    """

    def __init__(self, filename: str) -> None:
        self.filename = filename
        uuid = uuid4()
        self.tempfile = f'{filename}-{uuid}.tmp'
        self.handle: Optional[TextIO] = None

    def __enter__(self) -> TextIO:
        assert not does_path_exist(self.tempfile)
        self.handle = open(self.tempfile, mode="w")
        return self.handle

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        if self.handle is not None:
            self.handle.close()
            cmd = f'/bin/mv -f {self.tempfile} {self.filename}'
            ret = os.system(cmd)
            if (ret >> 8) != 0:
                raise Exception(f'{cmd} failed, exit value {ret>>8}!')
        return False


if __name__ == '__main__':
    import doctest

    doctest.testmod()
