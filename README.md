# pyutils

When I was writing little tools in Python and found myself implementing
a generally useful pattern I stuffed it into a local library.  That
library grew into pyutils: a set of collections, helpers and utilities
that I find useful and hope you will too.

Code is under [src/pyutils/](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=tree;f=src/pyutils;h=e716e14b7a895e5c6206af90f4628bf756f040fe;hb=HEAD).
Most code includes inline documentation and doctests.  I've tried to
organize it into logical packages based on the code's functionality.
Note that when words would collide with a Python library or reserved
word I've used a 'z' at the end, e.g. 'collectionz' instead of
'collections', 'typez' instead of 'type', etc...

There's some example code that uses various features of this project checked
in under [examples/](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=tree;f=examples;h=d9744bf2b171ba7a9ff21ae1d3862b673647fff4;hb=HEAD) that you can check out.

Unit and integration tests are under [tests/](
https://wannabe.guru.org/gitweb/?p=pyutils.git;a=tree;f=tests;h=8c303f23cd89b6d2e4fbf214a5c7dcc0941151b4;hb=HEAD).  To run all tests:

    cd tests/
    ./run_tests.py --all [--coverage]

See the [README](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=tests/README;hb=HEAD)) under `tests/` and the code of `run_tests.py` for more options / information about running tests.

This package generates Sphinx docs which are available at [https://wannabe.guru.org/pydocs/pyutils/pyutils.html](https://wannabe.guru.org/pydocs/pyutils/pyutils.html)

Package code is checked into a local git server and available to clone
from git at https://wannabe.guru.org/git/pyutils.git or to view in a
web browser at [https://wannabe.guru.org/gitweb/?p=pyutils.git;a=summary](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=summary)

For a long time this was just a local library on my machine that my
tools imported but I've now decided to release it on PyPi.  Earlier
development happened in a different git repo [https://wannabe.guru.org/gitweb/?p=python_utils.git;a=summary](https://wannabe.guru.org/gitweb/?p=python_utils.git;a=summary)

The [LICENSE](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=LICENSE;hb=HEAD)
and [NOTICE](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=blob_plain;f=NOTICE;hb=HEAD)
files at the root of the project describe reusing this code and where
everything came from.  Drop me a line if you are using this, find a
bug, have a question, or have a suggestion:

  --Scott Gasch (scott.gasch@gmail.com)
