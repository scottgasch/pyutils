pyutils package
===============

When I was writing little tools in Python and found myself implementing
a generally useful pattern I stuffed it into a local library.  That
library grew into pyutils: a set of collections, helpers and utilities
that I find useful and hope you will too.

Code is under `src/pyutils/`.  Most code includes documentation and inline
doctests.

Unit and integration tests are under `tests/*`.  To run all tests::

    cd tests/
    ./run_tests.py --all [--coverage]

See the README under `tests/` and the code of `run_tests.py` for more
options / information.

This package generates Sphinx docs which are available at:

    https://wannabe.guru.org/pydocs/pyutils/pyutils.html

Package code is checked into a local git server and available to clone
from git at https://wannabe.guru.org/git/pyutils.git or from a web browser
at:

    https://wannabe.guru.org/gitweb/?p=pyutils.git;a=summary

For a long time this was just a local library on my machine that my
tools imported but I've now decided to release it on PyPi.  Early
development happened in a different git repo:

    https://wannabe.guru.org/gitweb/?p=python_utils.git;a=summary

I hope you find this useful.  LICENSE and NOTICE describe reusing it
and where everything came from.  Drop me a line if you are using this,
find a bug, or have a question:

  --Scott Gasch (scott.gasch@gmail.com)


Subpackages
-----------

.. toctree::
   :maxdepth: 4

   pyutils.collectionz
   pyutils.compress
   pyutils.datetimez
   pyutils.files
   pyutils.parallelize
   pyutils.search
   pyutils.security
   pyutils.typez

Submodules
----------

pyutils.ansi module
-------------------

This file mainly contains code for changing the nature of text printed
to the console via ANSI escape sequences.  e.g. it can be used to emit
text that is bolded, underlined, italicised, colorized, etc...

It also contains a colorizing context that will apply color patterns
based on regular expressions to any data emitted to stdout that may be
useful in adding color to other programs' outputs, for instance.

.. automodule:: pyutils.ansi
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.argparse\_utils module
------------------------------

I use the Python internal `argparse` module for commandline argument
parsing but found it lacking in some ways.  This module contains code to
fill those gaps.  It include stuff like:

    - An `argparse.Action` to create pairs of flags such as
      `--feature` and `--no_feature`.
    - A helper to parse and validate bools, IP addresses, MAC
      addresses, filenames, percentages, dates, datetimes, and
      durations passed as flags.

.. automodule:: pyutils.argparse_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.bootstrap module
------------------------

Bootstrap module defines a decorator meant to wrap your main function.
This decorator will do several things for you:

    - If your code uses the :file:`config.py` module (see below), it invokes
      `parse` automatically to initialize `config.config` from commandline
      flags, environment variables, or other sources.
    - It will optionally break into pdb in response to an unhandled
      Exception at the top level of your code.
    - It initializes logging for your program (see :file:`logging.py`).
    - It can optionally run a code and/or memory profiler on your code.

.. automodule:: pyutils.bootstrap
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.config module
---------------------

This module reads the program's configuration parameters from: the
commandline (using argparse), environment variables and/or a shared
zookeeper-based configuration.  It stores this configuration state in
a dict-like structure that can be queried by your code at runtime.

It handles creating a nice `--help` message for your code.

It can optionally react to dynamic config changes and change state at
runtime (iff you name your flag with the *dynamic_* prefix and are
using zookeeper-based configs).

It can optionally save and retrieve sets of arguments from files on
the local disk or on zookeeper.

All of my examples use this as does the pyutils library itself.

.. automodule:: pyutils.config
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.decorator\_utils module
-------------------------------

This is a grab bag of decorators.

.. automodule:: pyutils.decorator_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.dict\_utils module
--------------------------

A bunch of helpers for dealing with Python dicts.

.. automodule:: pyutils.dict_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.exec\_utils module
--------------------------

Helper code for dealing with subprocesses.

.. automodule:: pyutils.exec_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.function\_utils module
------------------------------

Helper util for dealing with functions.

.. automodule:: pyutils.function_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.id\_generator module
----------------------------

Generate unique identifiers.

.. automodule:: pyutils.id_generator
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.iter\_utils module
--------------------------

Iterator utilities including a :class:PeekingIterator, :class:PushbackIterator,
and :class:SamplingIterator.

.. automodule:: pyutils.iter_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.list\_utils module
--------------------------

Utilities for dealing with Python lists.

.. automodule:: pyutils.list_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.logging\_utils module
-----------------------------

This is a module that offers an opinionated take on how whole program logging
should be initialized and controlled.  It uses standard Python logging but gives
you control, via commandline config, to:

    - Set the logging level of the program including overriding the
      logging level for individual modules,
    - Define the logging message format including easily adding a
      PID/TID marker on all messages to help with multithreaded debugging,
    - Control the destination (file, sys.stderr, syslog) of messages,
    - Control the facility and logging level used with syslog,
    - Squelch repeated messages,
    - Log probalistically,
    - Clear rogue logging handlers added by other imports.

.. automodule:: pyutils.logging_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.math\_utils module
--------------------------

Helper utilities that are "mathy" such as a :class:NumericPopulation that
makes population summary statistics available to your code quickly, GCD
computation, literate float truncation, percentage <-> multiplier, prime
number determination, etc...

.. automodule:: pyutils.math_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.misc\_utils module
--------------------------

Miscellaneous utilities: are we running as root, and is a debugger attached?

.. automodule:: pyutils.misc_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.persistent module
-------------------------

Persistent defines a class hierarchy and decorator for creating
singleton classes that (optionally/conditionally) load their state
from some external location and (optionally/conditionally) stave their
state to an external location at shutdown.

.. automodule:: pyutils.persistent
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.remote\_worker module
-----------------------------

This module defines a helper that is invoked by the remote executor to
run pickled code on a remote machine.  It is used by code marked with
@parallelize(method=Method.REMOTE) in the parallelize framework.

.. automodule:: pyutils.remote_worker
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.state\_tracker module
-----------------------------

This module defines several classes (:class:StateTracker,
:class:AutomaticStateTracker, and
:class:WaitableAutomaticStateTracker) that can be used as base
classes.  These class patterns are meant to encapsulate and represent
state that dynamically changes.  These classes update their state
(either automatically or when invoked to poll) and allow their callers
to wait on state changes.

.. automodule:: pyutils.state_tracker
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.stopwatch module
------------------------

This is a stopwatch context that just times how long something took to
execute.

.. automodule:: pyutils.stopwatch
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.string\_utils module
----------------------------

A bunch of utilities for dealing with strings.  Based on a really great
starting library from Davide Zanotti, I've added a pile of other string
functions so hopefully it will handle all of your string-needs.

.. automodule:: pyutils.string_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.text\_utils module
--------------------------

Utilities for dealing with and creating text chunks.  For example:

    - Make a bar graph,
    - make a spark line,
    - left, right, center, justify text,
    - word wrap text,
    - indent text,
    - create a header line,
    - draw a box around some text.

.. automodule:: pyutils.text_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.unittest\_utils module
------------------------------

Utilities to support smarter unit tests.

.. automodule:: pyutils.unittest_utils
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.unscrambler module
--------------------------

Unscramble scrambled English words quickly.

.. automodule:: pyutils.unscrambler
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.zookeeper module
------------------------

A helper module for dealing with Zookeeper that adds some functionality.

.. automodule:: pyutils.zookeeper
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

.. automodule:: pyutils
   :members:
   :undoc-members:
   :show-inheritance:
