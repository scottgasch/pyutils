# tests

This directory contains the (non-doctest) testcode for pyutils (i.e. unit tests
and integration tests).  It also contains a couple of helpers to run the tests.

The easiest way to run the tests is, from within this tests/ directory, to run:

    ./run_tests_serially.sh -a

If you only want to run a subset of the tests (e.g. all doctests only) run:

    ./run_tests_serially.sh -d

As you can tell from the name, this shell script runs the tests in serial.
If you want to go faster (and put more load on your machine), try:

    ./run_tests.py --all

Or:

    ./run_tests.py -d

Both of these runners store test output under tests/test_output.

Both of them can optionally use coverage (pip install coverage) to generate a
code coverage report at the end of testing:

    ./run_tests.py --all --coverage

I use `./run_tests.py --all --coverage` as a `.git/hooks/pre-commit-hook` during
development.