# docs

This is a directory containing the instructions to Sphinx (`pip install sphinx`)
for generating HTML-based source code documentation for the pyutils library.

You can generate the current docs via `make html`.  This expects a GNU make
utility.

The generated docs are hosted at [https://wannabe.guru.org/pydocs/pyutils/pyutils.html](https://wannabe.guru.org/pydocs/pyutils/pyutils.html).

I regenerate (and publish) the docs as a `.git/hook/post-push` step.
