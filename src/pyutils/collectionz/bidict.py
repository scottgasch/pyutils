#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""A bidirectional dictionary."""


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
