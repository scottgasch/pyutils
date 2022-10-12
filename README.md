# pyutils

This is a collection of Python utilities that I wrote and find useful.
From collections that try to emulate Pythonic patterns
(pyutils.collectionz) to a "smart" natural language date parser
(pyutils.datetimez.dateparse_utils), to filesystem helpers
(pyutils.files.file_utils) to a "simple" parallelization framework
(pyutils.parallelize.parallelize).  I hope you find them useful.

Code is under src/*.  Most code includes doctests.

Tests are under tests/*.  To run all tests:

    cd tests/
    ./run_tests.py --all [--coverage]

See the README under tests/ for more options / information.

This package generates Sphinx docs which are available at:

    https://wannabe.guru.org/pydocs/pyutils/pyutils.html

For a long time this was just a local library on my machine that
my tools imported but I've decided to release it on PyPi.  I hope
you find it useful.  LICENSE and NOTICE describe reusing it and
where everything came from.  Drop me a line if you are using this,
find a bug, or have a question.

  --Scott Gasch (scott.gasch@gmail.com)

