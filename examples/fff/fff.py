#!/usr/bin/env python3

"""
This isn't really an example of pyutils but rather a development
tool I used as part of a git pre-commit hook...

f)ind f)ucked f)-strings

Searches python files for suspicious looking strings that seem to
use f-string {interpolations} without acutally being f-strings.

Usage: fff.py *.py
"""

import re
import sys
import tokenize
from pathlib import Path
from token import STRING
from typing import List, Tuple

from pyutils import ansi

curly = re.compile(r'\{[^\}]+\}')


def looks_suspicious(q: str, previous_tokens: List[Tuple[int, str]]) -> bool:
    for pair in previous_tokens:
        if ':' in pair[1]:
            return False
    return q[0] != 'f' and curly.search(q) is not None


for filename in sys.argv[1:]:
    path = Path(filename)
    if path.suffix != ".py":
        print(f"{filename} doesn't look like python; skipping.", file=sys.stderr)
        continue
    with tokenize.open(filename) as f:
        previous_tokens = []
        for token in tokenize.generate_tokens(f.readline):
            (ttype, text, (start_row, _), (end_row, _), _) = token
            if ttype == STRING:
                if (
                    'r"' not in text
                    and "r'" not in text
                    and looks_suspicious(text, previous_tokens)
                ):
                    print(
                        f"{ansi.fg('green')}{filename}:{start_row}-{end_row}>{ansi.reset()}"
                    )
                    for (n, line) in enumerate(text.split('\n')):
                        print(
                            f'{ansi.fg("dark gray")}{start_row+n}:{ansi.reset()} {line}'
                        )
            #                        print('Previous context:')
            #                        for pair in previous_tokens:
            #                            print(f'{pair[0]} ({pair[1]})', end=' + ')
            #                        print()
            previous_tokens.append((ttype, text))
            previous_tokens = previous_tokens[-3:]
