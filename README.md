# pyutils

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

There's some example code that uses various features of this project checked
in under [examples/](https://github.com/scottgasch/pyutils/tree/master/examples).

Unit and integration tests live under [tests/](
https://github.com/scottgasch/pyutils/tree/master/tests).  To run all tests,
it might help to check out the [GitHub action that does](https://github.com/scottgasch/pyutils/blob/main/.github/workflows/run-tests.yml)
it as there are some setup steps you need to do first:

1. You will need to install ANTLR4 on your machine.  ANTLR is a tool that
reads grammars and creates helper code to parse expressions in that grammar.
I use it for the datetime_utils free form parser.  When you get ANTLR4, make
sure to get the same version as the pip ANTLR4-python-runtime you have
installed (it was a dependency of pyutils):

        pip list | grep antlr

2. Use the [ANTLR4 tool](https://www.antlr.org/) installed in the previous
step to generate some helper files:

        cd src/pyutils/datetimes
        antlr4  -Dlanguage=Python3 ./dateparse_utils.g4
        cd ../../..

4. Pregenerate an unscrambler datafile, which relies on the presence of the
input file `/usr/share/dict/words` (so install that, maybe via
`sudo apt install wamerican` if required):

       sudo touch /usr/share/dict/sparse_index
       sudo chmod 666 /usr/share/dict/sparse_index
       python3
       >>> from pyutils.unscrambler import Unscrambler
       >>> Unscrambler.repopulate()

5. Setup your parallelizer config file.  This involves editing a file called
`.remote_worker_records` that, by default, lives in your home directory.  It
has instructions inline.

       cp examples/parallelize_config/.remote_worker_records $HOME
       vi $HOME/.remote_worker_records
  
6. Actually run the tests!

       cd tests/
       ./run_tests.py --all [--coverage] [--keep_going] [--show_failures]

See the [README](https://github.com/scottgasch/pyutils/blob/main/tests/README.md)
under `tests/` and the code of `run_tests.py` for more options / information
about running the tests.

This package generates Sphinx docs which are available at
[https://wannabe.guru.org/pydocs/pyutils/pyutils.html](https://wannabe.guru.org/pydocs/pyutils/pyutils.html).  
You can generate them yourself by running `make html` (with GNU make) 
under the [docs/](https://github.com/scottgasch/pyutils/tree/master/docs) 
folder.

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

Drop me a line if you are using this, [find a bug](
https://github.com/scottgasch/pyutils/issues), have a question,
or have a suggestion:

  --Scott Gasch ([scott.gasch@gmail.com](mailto://scott.gasch@gmail.com))
