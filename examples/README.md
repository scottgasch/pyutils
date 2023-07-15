# examples

Stuff under here is example code that uses pyutils library routines and
is meant to just be illustrative and fun.  Each should be runnable as-is
if you have pyutils installed.  Use the `--help` flag for more info.

## cron

Wrapper for running cronjobs with optional locks to ensure that no
more than one instance executes at the same time, optional max
frequencies, optionally touch a file on successful execution to
drive monitoring, etc...

## dedup_files
Util that traverses a directory structure and identifies files that
are duplicates of each other then optionally deletes duplicates or
symlinks duplicates back to an original.

## fff
Find f'ed fstrings... not so much an example but rather a
development tool.  Identifies places where I meant to use an
f-string (used braces in a string) but didn't make the string an
f-string.  I run this as a pre-commit hook and thought it would be
good to include.

## parallelize_config
This is a sample config file (place in `~/.remote_worker_records` or
override with `--remote_worker_records_file`) for the `@parallelize`
framework to understand how to dispatch work to remote machines.

## pyskel
This is a "skeleton" I keep around for when I want to start
working on a new script.

## reminder
Reminds you of important dates which are stored in the .reminder
file.

## scrabble
Helps you play Scrabble word game.

## wordle
Plays and helps you cheat at the Wordle word game.  Demo of using
the `@parallelize` framework and `shared_dict` which it uses to
precompute the solution space on several processes at once.

## ../tests/run_tests.py
Though not under `examples/` this is still a stand alone program that
uses pyutils concepts like `@parallelize` and `smart_futures` that might
be helpful to look at.

