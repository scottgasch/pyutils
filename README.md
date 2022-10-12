# pyutils

---

This is a collection of Python utilities that I wrote and find useful.
From collections that try to emulate Pythonic patterns
(pyutils.collectionz) to a "smart" natural language date parser
(pyutils.datetimez.dateparse_utils), to filesystem helpers
(pyutils.files.file_utils) to a "simple" parallelization framework
(pyutils.parallelize.parallelize).  I hope you find them useful, too.

Code is under `src/pyutils/*`.  Most code includes doctests inline.

Tests are under tests/*.  To run all tests:

    cd tests/
    ./run_tests.py --all [--coverage]

See the README under tests/ and the code of run_tests.py for more
options / information.

This package generates Sphinx docs which are available at:

    [https://wannabe.guru.org/pydocs/pyutils/pyutils.html](https://wannabe.guru.org/pydocs/pyutils/pyutils.html)

Package code is checked into a local git server and available to clone
from https://wannabe.guru.org/git/pyutils.git or under:

    [https://wannabe.guru.org/gitweb/?p=pyutils.git;a=summary](https://wannabe.guru.org/gitweb/?p=pyutils.git;a=summary)

For a long time this was just a local library on my machine that my
tools imported but I've now decided to release it on PyPi.  Early
development happened in a different git repo:

    [https://wannabe.guru.org/gitweb/?p=python_utils.git;a=summary](https://wannabe.guru.org/gitweb/?p=python_utils.git;a=summary)

I hope you find this useful.  LICENSE and NOTICE describe reusing it
and where everything came from.  Drop me a line if you are using this,
find a bug, or have a question.

  --Scott Gasch [scott.gasch@gmail.com](mailto://scott.gasch@gmail.com)

