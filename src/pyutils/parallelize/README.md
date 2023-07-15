This is a set of code that uses a decorator to implement simple
parallelization in Python.  When decorated functions are invoked they
execute on a background thread, process or remote machine depending on
the style of decoration.  Here's an example:

    from pyutils.parallelize import parallelize as p

    @p.parallelize    # defaults to thread-mode
    def my_function(a, b, c) -> int:
        ...do some slow / expensive work, e.g., an http request

    # Run with background subprocess
    @p.parallelize(method=Method.PROCESS)
    def my_other_function(d, e, f) -> str:
        ...do more really expensive work, e.g., a network read

    # Run in a helper process on another machine.
    @p.parallelize(method=Method.REMOTE)
    def my_other_other_function(g, h) -> int:
        ...this work will be distributed to a remote machine pool

This will "just work" out of the box with `Method.THREAD` (the default)
and `Method.PROCESS` but in order to use `Method.REMOTE` you need to
do some setup work:

    1. To use `@parallelize(method=Method.REMOTE)` with your code you
       need to hook your code into
       [`pyutils.config`](https://github.com/scottgasch/pyutils/blob/master/src/pyutils/config.py)
       to enable commandline flags from `pyutil` files.  You can do
       this by either wrapping your main entry point with the
       [`pyutils.bootstrap.initialize`](https://github.com/scottgasch/pyutils/blob/master/src/pyutils/bootstrap.py) decorator or just calling
       `config.parse()` early in your program.  See instructions in
       [`pyutils.bootstrap`](https://github.com/scottgasch/pyutils/blob/master/src/pyutils/bootstrap.py) and :mod:`pyutils.config` for more
       information.

    2. You need to create and configure a pool of worker machines.
       All of these machines should run the same version of Python,
       ideally in a virtual environment (venv) with the same
       versions of the same Python package dependencies installed.
       See: [https://docs.python.org/3/library/venv.html](https://github.com/scottgasch/pyutils/blob/master/src/pyutils/bootstrap.py)

       .. warning::

           Different versions of code, libraries, or of the interpreter
           itself can cause issues with running cloudpicked code.

    3. You need an account that can ssh into any / all of these pool
       machines non-interactively to perform tasks such as copying
       code to the worker machine and running Python in the
       aforementioned virtual environment.  This likely means setting
       up `ssh` / `scp` with key-based authentication.
       See: [https://www.digitalocean.com/community/tutorials/how-to-set-up-ssh-keys-2](https://github.com/scottgasch/pyutils/blob/master/src/pyutils/bootstrap.py)

    4. You need to tell this parallelization framework about the pool
       of machines you created by editing a JSON-based configuration
       file.  The location of this file defaults to
       `.remote_worker_records` in your home directory but can
       be overridden via the `--remote_worker_records_file`
       commandline argument.  An example JSON configuration [can be
       found under examples](https://github.com/scottgasch/pyutils/blob/master/examples/parallelize_config/.remote_worker_records).

    5. Finally, you will also need tell the
       `pyutils.parallelize.executors.RemoteExecutor` class how to
       invoke the (remote_worker.py)[https://github.com/scottgasch/pyutils/blob/master/src/pyutils/remote_worker.py] on remote machines by
       passing its path on remote worker machines in your setup via
       the `--remote_worker_helper_path` commandline flag (or,
       honestly, if you made it this far, just update the default in
       this code -- find `executors.py` under `site-packages` in your
       virtual environment and update the default value of the
       `--remote_worker_helper_path` flag)

    If you're trying to set this up and struggling, email me at
    (scott.gasch@gmail.com)[mailto://scott.gasch@gmail.com].  I'm happy to help.

    What you get back when you call a decorated function (using
    threads, processes or a remote worker) is a
    `pyutils.parallelize.smart_future.SmartFuture`.  This class
    attempts to transparently wrap a normal Python (`Future`)[
    https://docs.python.org/3/library/concurrent.futures.html#future-objects].
    If your code just uses the result of a `parallelized` method it
    will block waiting on the result of the wrapped function as soon
    as it uses that result in a manner that requires its value to be
    known (e.g. using it in an expression, calling a method on it,
    passing it into a method, hashing it / using it as a dict key,
    etc...)  But you can do operations that do not require the value
    to be known (e.g. storing it in a list, storing it as a value in a
    dict, etc...) safely without blocking.

    There are two helper methods in
    `pyutils.parallelize.smart_future` to help deal with these
    `SmartFuture` objects called
    `pyutils.parallelize.smart_future.wait_all` and
    `pyutils.parallelize.smart_future.wait_any`.  These, when
    given a collection of `SmartFuture` objects,
    will block until one (any) or all (all) are finished and yield the
    finished objects to the caller.  Callers can be confident that any
    objects returned from these methods will not block when accessed.
    See documentation in (pyutils.parallelize.smart_future)[https://github.com/scottgasch/pyutils/blob/master/src/pyutils/parallelize/smart_future.py] for
    more details.

    The files
    (run_all_tests.py)[https://github.com/scottgasch/pyutils/blob/master/tests/run_tests.py]
    and
    (wordle.py)[https://github.com/scottgasch/pyutils/blob/master/examples/wordle/wordle.py]
    use this parallelization framework... as does the (parallelize
    integration
    test)[https://github.com/scottgasch/pyutils/blob/master/tests/parallelize/parallelize_itest.py].

"""
