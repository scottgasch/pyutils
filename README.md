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
https://github.com/scottgasch/pyutils/tree/master/tests).  To run all tests:

    cd tests/
    ./run_tests.py --all [--coverage]

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
