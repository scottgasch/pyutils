pyutils.collectionz package
===========================

This subpackage contains some homegrown collections that try to
emulate :mod:`collections` included in the Python standard library
(see:
https://docs.python.org/3/library/collections.html#module-collections).
It ends with a 'z' so as not to collide with the standard library
package.

Submodules
----------

pyutils.collectionz.bidict module
---------------------------------

.. automodule:: pyutils.collectionz.bidict
   :imported-members:
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.collectionz.bst module
------------------------------

.. automodule:: pyutils.collectionz.bst
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.collectionz.shared\_dict module
---------------------------------------

The shared\_dict.SharedDict class is a normal python dictionary that
can be accessed safely in parallel from multiple threads or processes
without (external) locking by using Multiprocessing.SharedMemory.  It
uses internal locking and rewrites the shared memory region as it is
changed so it is slower than a normal dict.  It also does not grow
dynamically; the creator of the shared\_dict must declare a maximum
size.

.. automodule:: pyutils.collectionz.shared_dict
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.collectionz.trie module
-------------------------------

.. automodule:: pyutils.collectionz.trie
   :members:
   :undoc-members:
   :show-inheritance:

Module contents
---------------

.. automodule:: pyutils.collectionz
   :members:
   :undoc-members:
   :show-inheritance:
