# pyutils

## Introduction

When I was writing little tools in Python and found myself
implementing a generally useful pattern I stuffed it into a local
library.  That library grew into pyutils: a set of collections,
helpers and utilities that I find useful and hope you will too.

Code is under [src/pyutils/](https://github.com/scottgasch/pyutils/tree/master/src/pyutils).
Most code includes inline documentation and doctests.  I've tried to
organize it into logical packages based on the code's functionality.
Note that when words would collide with a Python standard library or
reserved word I've used a 'z' at the end, e.g. 'collectionz' instead
of 'collections', 'typez' instead of 'type', etc...

The repo now lives on [GitHub](https://github.com/scottgasch/pyutils) but
a lot of the development happened against a [local git server](
https://wannabe.guru.org/gitweb/?p=pyutils.git;a=summary)

For a long time this was just a local library on my machine that my
tools imported but I've now decided to [release it on PyPi](https://pypi.org/project/pyutils/)
so you can get it via a:

    pip install pyutils

The [LICENSE](https://github.com/scottgasch/pyutils/blob/master/LICENSE)
and [NOTICE](https://github.com/scottgasch/pyutils/blob/master/NOTICE)
files at the root of the project describe reusing this code and where
everything came from.

## Examples

There's some example code that uses various features of this project checked
in under [examples/](https://github.com/scottgasch/pyutils/tree/master/examples).

## Setup

In addition to installing the library (`pip install pyutils` or via
the wheels checked in under [dist/](https://github.com/scottgasch/pyutils/tree/main/dist)),
you should configure your parallelizer remote workers file, if you
want to use `@parallelize(mathod = Method.REMOTE)`.

This involves editing a file called `.remote_worker_records` that,
by default, lives in your home directory.  It has [instructions inline](https://github.com/scottgasch/pyutils/blob/main/examples/parallelize_config/.remote_worker_records).
Also check out the [more complete instructions](https://github.com/scottgasch/pyutils/tree/main/src/pyutils/parallelize) 
for getting remote parallelization configured.

    cp examples/parallelize_config/.remote_worker_records $HOME
    vi $HOME/.remote_worker_records

## Testing

Unit and integration tests live under [tests/](
https://github.com/scottgasch/pyutils/tree/master/tests).
To run all tests, follow the steps in the **Setup** section above
or check out the [GitHub action that does](
https://github.com/scottgasch/pyutils/blob/main/.github/workflows/run-tests.yml).
Once you've done that, to run the tests:

    cd tests/
    ./run_tests.py --all [--coverage] [--keep_going] [--show_failures]

See the [README](https://github.com/scottgasch/pyutils/blob/main/tests/README.md)
under `tests/` and the code of `run_tests.py` for more options / information
about running the tests.

## Documentation

This package generates Sphinx docs which are available at
[https://wannabe.guru.org/pydocs/pyutils/pyutils.html](https://wannabe.guru.org/pydocs/pyutils/pyutils.html).
You can generate them yourself by running `make html` (with [GNU make](https://www.gnu.org/software/make/)
under the [docs/](https://github.com/scottgasch/pyutils/tree/master/docs)
folder.)

## Troubleshooting

### ANTLR4 version incompatibilities

If you have trouble with [ANTLR](https://www.antlr.org/), e.g. you see messages like "Exception:
Could not deserialize ATN with version", make sure that the version of
the `antlr4-python3-runtime` package is correct.  It must match the version of
`antlr4` that was used to create generated files under `src/pyutils/datetimes`.
You can regenerate those files yourself by installing antlr4
on your machine and then running `antlr4 -Dlanguage=Python3 ./dateparse_utils.g4`
from that directory.  Once you've done this, run `antlr4` without arguments
and note the version number of antlr4 you just used.  Then, install the matching
runtime package using pip: `pip install -U antlr4-python3-runtime==<version>`.

### Missing .remote_worker_records file

A `.remote_worker_records` file, by default in your home directory (but overridable
via the `--remote_worker_records_file` commandline argument), is used to
set up remote machines with the same version of python in an identical venv that
can be used to parallelize code across multiple machines.  An example of this file
is checked in under [examples/parallelize_config](https://github.com/scottgasch/pyutils/blob/main/examples/parallelize_config/.remote_worker_records)
and has inline comments describing the format.  The setup process itself is
described in the [src/pyutil/parallelize/README.md](https://github.com/scottgasch/pyutils/tree/main/src/pyutils/parallelize).

If you attempt to use `@parallelize.parallelize(method=Method.REMOTE)` without
setting this up, you will get an error message with a URL that points here.

### Missing .sparse_index file

The [unscrambler.py code](https://github.com/scottgasch/pyutils/blob/main/src/pyutils/unscrambler.py)
attempts to generate an indexfile using an input "dictionary" of all language
words, by default `/usr/share/dict/words` but overridable via the 
`--unscrambler_source_dictfile` commandline argument.  This indexfile lives, by
default, in `.sparse_index` in your home directory but that location can also
be overridden using the `--unscrambler_default_indexfile` commandline argument.

If this indexfile is not present when you attempt to instantiate an `Unscrambler`, 
it will attempt to read the dictfile input and generate its indexfile.  This
process usually just takes a second or two and is a one-time cost (assuming
that it can find the indexfile on subsequent invocations).  If something goes
wrong (e.g. no input dictfile, unreadable input dictfile, unwritable indexfile
location) you can intervene by using the commandline arguments above.

You can force the library to attempt to generate the indexfile using interactive
python:

    >>> from pyutils.unscrambler import Unscrambler
    >>> u = Unscrambler()

If the indexfile does not exist, this will attempt to create it.

## Support

Drop me a line if you are using this, [find a bug](
https://github.com/scottgasch/pyutils/issues), have a question,
or have a suggestion:

  --Scott Gasch ([scott.gasch@gmail.com](mailto://scott.gasch@gmail.com))
