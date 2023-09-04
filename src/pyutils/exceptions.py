#!/usr/bin/env python3

# © Copyright 2023, Scott Gasch

"""An exception hierarchy for pyutils code.  We will raise a
PyUtilsException, one of its subclasses, or a built-in python
exception (like ValueError, TypeError, etc...) instead of Exception to
make writing catch blocks easier.
"""


class PyUtilsException(Exception):
    pass


class PyUtilsDependencyUnreachableException(PyUtilsException):
    pass


class PyUtilsUnrecognizedArgumentsException(PyUtilsException):
    pass


class PyUtilsUnreadableConsoleException(PyUtilsException):
    pass


class PyUtilsUnreachableConditionException(PyUtilsException):
    pass


class PyUtilsDateParseException(PyUtilsException):
    pass


class PyUtilsLockfileException(PyUtilsException):
    pass


class PyUtilsParseError(PyUtilsException):
    pass
