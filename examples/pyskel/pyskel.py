#!/usr/bin/env python3

"""The start of something cool...

This is a skeleton python script that I keep around and use as the
start of any new utility that I'm working on.
"""

import logging
from typing import Optional

from pyutils import bootstrap, config

logger = logging.getLogger(__name__)
args = config.add_commandline_args(f'({__file__})', f'Args related to {__file__}')


@bootstrap.initialize
def main() -> Optional[int]:
    print('Hello world.')
    return None


if __name__ == '__main__':
    main()
