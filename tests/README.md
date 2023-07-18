# tests

This directory contains the (non-doctest) testcode for pyutils (i.e. unit tests
and integration tests).  It also contains a couple of helpers to run the tests.

The simplest way to run all the tests is, from this directory, to run:

    ./run_tests.py --all

This `run_tests.py` [helper script](https://github.com/scottgasch/pyutils/main/tests/run_tests.py)
knows about three kinds of tests: unit tests, doctests, and integration tests.
You can run each class individually:

    ./run_tests.py --unittests
    ./run_tests.py --doctests
    ./run_tests.py --integration

Or in combination:

    ./run_tests.py --unittests --doctests

Normally, when a test fails, its output can be found under `tests/test_output`
to figure out what went wrong.  With the optional `--show_failures` flag, though,
the failures will be dumped onto the console as tests break.

The `run_tests.py` script runs tests in parallel.  When one test fails, it
interrupts other tests that are currently running and tears down tests that
are scheduled to start.  With the `--keep_going` flag, other tests are not
interrupted when one test fails.

Finally, running with the `--coverage` flag will include code coverage data
in the output after tests have finished.  To use this, you must have the
coverage python package installed, use `pip install coverage`.

I use `./run_tests.py --all --show_failures --coverage` as a
`.git/hooks/pre-commit-hook` during the development process.

I wrote the `run_tests.py` tool to speed up test passes (and, somewhat, as an
example of using the pyutil parallelize framework).  Before that, I used a
[simple shell script](https://github.com/scottgasch/pyutils/main/tests/run_tests_serially.sh)
to run tests passes and that historical test runner is checked in 
as `run_tests_serially.sh`.  The only reason that might be interesting
to you is if the parallel test running (`run_tests.py`) puts too much load
on your machine.
