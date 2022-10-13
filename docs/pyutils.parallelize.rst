pyutils.parallelize package
===========================

Submodules
----------

pyutils.parallelize.deferred\_operand module
--------------------------------------------

DeferredOperand is the base class for SmartFuture.

.. automodule:: pyutils.parallelize.deferred_operand
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.parallelize.executors module
------------------------------------

This module defines three executors: one for threads in the same
process, one for separate processes on the same machine and the third
for separate processes on remote machines.  Each can be used via the
@parallelize decorator.  These executor pools are automatically
cleaned up at program exit.


.. automodule:: pyutils.parallelize.executors
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.parallelize.parallelize module
--------------------------------------

This module defines a decorator that can be used for simple parallelization.

.. automodule:: pyutils.parallelize.parallelize
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.parallelize.smart\_future module
----------------------------------------

Defines a SmartFuture class that is part of the parallelization
framework.  A SmartFuture is a kind of Future (i.e. a representation
of the result of asynchronous processing that may know its value or
not depending on whether the asynchronous operation has completed).
Whereas normal Python Futures must be waited on or resolved manually,
a SmartFuture automatically waits for its result to be known as soon
as it is utilized in an expression that demands its value.

Also contains some utilility code for waiting for one/many futures.

.. automodule:: pyutils.parallelize.smart_future
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.parallelize.thread\_utils module
----------------------------------------

Simple utils that deal with threads.

.. automodule:: pyutils.parallelize.thread_utils
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

This module contains a framework for easy Python parallelization.  To
see an example of how it is used, look at examples/wordle/...

This module also contains some utilities that deal with parallelization.

.. automodule:: pyutils.parallelize
   :members:
   :undoc-members:
   :show-inheritance:
