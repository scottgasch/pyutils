pyutils.files package
=====================

Submodules
----------

pyutils.files.directory\_filter module
--------------------------------------

This module contains two classes meant to help reduce unnecessary disk
I/O operations:

The first determines when the contents of a file held in memory are
identical to the file copy already on disk.  The second is basically
the same except for the caller need not indicate the name of the disk
file because it will check the memory file's signature against a set
of signatures of all files in a particular directory on disk.

.. automodule:: pyutils.files.directory_filter
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.files.file\_utils module
--------------------------------

This is a grab bag of file-related utilities.  It has code to, for example,
read files transforming the text as its read, normalize pathnames, strip
extensions, read and manipulate atimes/mtimes/ctimes, compute a signature
based on a file's contents, traverse the file system recursively, etc...

.. automodule:: pyutils.files.file_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.files.lockfile module
-----------------------------

This is a lockfile implementation I created for use with cronjobs on
my machine to prevent multiple copies of a job from running in
parallel.  When one job is running this code keeps a file on disk to
indicate a lock is held.  Other copies will fail to start if they
detect this lock until the lock is released.  There are provisions in
the code for timing out locks, cleaning up a lock when a signal is
received, gracefully retrying lock acquisition on failure, etc...

.. automodule:: pyutils.files.lockfile
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

This module contains utilities for dealing with files on disk.

.. automodule:: pyutils.files
   :members:
   :undoc-members:
   :show-inheritance:
