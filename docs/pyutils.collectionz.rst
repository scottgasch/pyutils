pyutils.collectionz package
===========================

Submodules
----------

pyutils.collectionz.bidict module
---------------------------------

The bidict.BiDict class is a bidirectional dictionary.  It maps each
key to a value in constant time and each value back to the one or more
keys it is associated with in constant time.  It does this by simply
storing the data twice.

.. automodule:: pyutils.collectionz.bidict
   :members:
   :undoc-members:
   :show-inheritance:

pyutils.collectionz.bst module
------------------------------

The bst.BinarySearchTree class is a binary search tree container.

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

The trie.Trie class is a Trie or prefix tree.  It can be used with
arbitrary sequences as keys and stores its values in a tree with paths
determined by the sequence determined by each key.  Thus, it can
determine whether a value is contained in the tree via a simple
traversal in linear time and can also check whether a key-prefix is
present in the tree in linear time.

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
