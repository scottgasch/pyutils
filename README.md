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
the wheel checked in under `dist/`), there are a couple of steps you
should do so that everything works:

1. Pregenerate an unscrambler datafile, which relies on the presence
of the input file `/usr/share/dict/words` (so install that, maybe via
`sudo apt install wamerican` if required):

       sudo touch /usr/share/dict/sparse_index
       sudo chmod 666 /usr/share/dict/sparse_index
       python3
       >>> from pyutils.unscrambler import Unscrambler
       >>> Unscrambler.repopulate()

2. Setup your parallelizer config file.  This involves editing a file
called `.remote_worker_records` that, by default, lives in your home
directory.  It has instructions inline.

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
You can generate them yourself by running `make html` (with GNU make)
under the [docs/](https://github.com/scottgasch/pyutils/tree/master/docs)
folder.

## Troubleshooting

If you have trouble with ANTLR, e.g. you see messages like "Exception:
Could not deserialize ATN with version", make sure that the version of
the `antlr4-python3-runtime` is correct.  It must match the version of
`antlr4` that was used to create generated files under `src/pyutils/datetimes`.
If all else fails, regenerate those files yourself by installing antlr4
on your machine and then running `antlr4 -Dlanguage=Python3 ./dateparse_utils.g4`.
Once you've done this, run `antlr4` without arguments and note the version
of antlr4 you just used.  Then, install the matching runtime using pip:
`pip install -U antlr4-python3-runtime==<version>`.

## Support

Drop me a line if you are using this, [find a bug](
https://github.com/scottgasch/pyutils/issues), have a question,
or have a suggestion:

  --Scott Gasch ([scott.gasch@gmail.com](mailto://scott.gasch@gmail.com))
