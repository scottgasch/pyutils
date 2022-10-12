#!/bin/bash

/bin/rm -f ./python_modules.* modules.rst
sphinx-apidoc -o . ../src/pyutils
