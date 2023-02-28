#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
The :class:`pyutils.collectionz.bidict.BiDict` class is a subclass
of :py:class:`dict` that implements a bidirectional dictionary.  That
is, it maps each key to a value in constant time and each value back
to the one or more keys it is associated with in constant time.  It
does this by simply storing the data twice.

Sample usage::

    # Initialize with a normal dict...
    third_party_wierdos = BiDict({
        'prometheus-fastapi-instrumentator': 'prometheus_fastapi_instrumentator',
        'scikit-learn': 'sklearn',
        'antlr4-python3-runtime' : 'antlr4',
        'python-dateutil': 'dateutil',
        'speechrecognition': 'speech_recognition',
        'beautifulsoup4': 'bs4',
        'python-dateutil': 'dateutil',
        'homeassistant-api': 'homeassistant_api',
    })

    # Use in one direction:
    x = third_party_wierdos['scikit-learn']

    # Use in opposite direction:
    y = third_party_wierdos.inverse['python_dateutil']

    # Note: type(y) is List since one value may map back to multiple keys.

"""


class BiDict(dict):
    def __init__(self, *args, **kwargs):
        """
        A class that stores both a Mapping between keys and values and
        also the inverse mapping between values and their keys to
        allow for efficient lookups in either direction.  Because it
        is possible to have several keys with the same value, using
        the inverse map returns a sequence of keys.

        >>> d = BiDict()
        >>> d['a'] = 1
        >>> d['b'] = 2
        >>> d['c'] = 2
        >>> d['a']
        1
        >>> d.inverse[1]
        ['a']
        >>> d.inverse[2]
        ['b', 'c']
        >>> len(d)
        3
        >>> del d['c']
        >>> len(d)
        2
        >>> d.inverse[2]
        ['b']

        """
        super().__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            self.inverse.setdefault(value, []).append(key)

    def __setitem__(self, key, value):
        if key in self:
            old_value = self[key]
            self.inverse[old_value].remove(key)
        super().__setitem__(key, value)
        self.inverse.setdefault(value, []).append(key)

    def __delitem__(self, key):
        value = self[key]
        self.inverse.setdefault(value, []).remove(key)
        if value in self.inverse and not self.inverse[value]:
            del self.inverse[value]
        super().__delitem__(key)


if __name__ == '__main__':
    import doctest

    doctest.testmod()
