#!/usr/bin/env python3

"""This is a little script you can use to cheat at Scrabble.  It
serves as an example of the unscrambler library.  Before you use it
you must initialize the unscrambler:

    % python3
    >> from pyutils.unscrambler import Unscrambler
    >> u.repopulate()

This is quick.  It parses the contents of /usr/share/dict/words (by
default) and writes to /usr/share/dict/sparse_index (by default).  You
can override these if required:

    >> u.repopulate('/usr/share/dict/web2a', '/home/scott/.sparse_index')

Here's the usage:

    $ scrabble.py pexeaml --show_scrabble_score --min_length=5
    peale => 6
    ample => 9
    maple => 9
    expel => 13
    example => 67

You can use underscore (_) to represent a blank tile.
"""

import itertools
import logging
import string
import sys
from collections import Counter
from typing import Generator, Set

from pyutils import ansi, bootstrap, config
from pyutils.unscrambler import Unscrambler

cfg = config.add_commandline_args(
    f'Scrabble (aka Wordscapes)! ({__file__})',
    'Find all words in a query letter set (proper and subset based)',
)
cfg.add_argument(
    '--min_length',
    help='Minimum length permissable in results',
    metavar='N',
    type=int,
    default=1,
)
cfg.add_argument(
    '--show_scrabble_score',
    help='Should we compute and display Scrabble game scores?',
    action='store_true',
)
cfg.add_argument(
    '--extra_letters',
    help='Set of letters available on the board (not in hand).  e.g. --extra_letters s t r',
    nargs='*',
)
logger = logging.getLogger(__name__)


scrabble_score_by_letter = {
    'a': 1,
    'e': 1,
    'i': 1,
    'l': 1,
    'n': 1,
    'o': 1,
    'r': 1,
    's': 1,
    't': 1,
    'u': 1,
    'd': 2,
    'g': 2,
    'b': 3,
    'c': 3,
    'm': 3,
    'p': 3,
    'f': 4,
    'h': 4,
    'v': 4,
    'w': 4,
    'y': 4,
    'k': 5,
    'j': 8,
    'x': 8,
    'q': 10,
    'z': 10,
}


def decorate_word(word: str, given_letters: Set[str]) -> str:
    countz = Counter(given_letters)
    logger.debug("Decorating %s; countz=%s", word, countz)
    out = ''
    for letter in word:
        if letter in countz and countz[letter] > 0:
            countz[letter] -= 1
            out += letter
        else:
            out += f'{ansi.bg("white")}{ansi.fg("black")}{letter}{ansi.reset()}'
    return out


def fill_in_blanks(letters: str, skip: Set[str]) -> Generator[str, None, None]:
    if '_' not in letters:
        logger.debug('Filled in blanks: %s', letters)
        yield letters
        return

    for replacement in string.ascii_lowercase:
        filled_in = letters.replace('_', replacement, 1)
        if filled_in not in skip:
            logger.debug(
                'Orig: %s, replacement is %s, new: %s', letters, replacement, filled_in
            )
            skip.add(filled_in)
            yield from fill_in_blanks(filled_in, skip)


def lookup_letter_set(
    letters: str,
    unscrambler: Unscrambler,
    seen_sigs: Set[int],
    seen_words: Set[str],
) -> None:
    sig = unscrambler.compute_word_sig(letters)
    if sig not in seen_sigs:
        logger.debug('%s => %s', letters, sig)
        for words, exact in unscrambler.lookup_by_sig(sig).items():
            if exact:
                for word in words.split(','):
                    if len(word) >= config.config['min_length']:
                        seen_words.add(word)
                    else:
                        logger.debug('Skipping %s because it\'s too short.', word)
        seen_sigs.add(sig)


@bootstrap.initialize
def main() -> None:
    if len(sys.argv) < 2:
        print("Missing required query.", file=sys.stderr)
        sys.exit(-1)

    seen_sigs: Set[int] = set()
    seen_words: Set[str] = set()
    seen_fill_ins: Set[str] = set()
    u: Unscrambler = Unscrambler()

    query = sys.argv[1].lower()
    orig_letters = set([x for x in query if x != '_'])
    logger.debug('Initial query: %s (%s)', query, orig_letters)

    if config.config['extra_letters']:
        for extra in config.config['extra_letters']:
            extra = extra.lower()
            query = query + extra
            logger.debug('Building with extra letter: %s; query is %s', extra, query)
            for q in fill_in_blanks(query, seen_fill_ins):
                logger.debug('...blanks filled in: %s', q)
                for x in range(config.config['min_length'], len(q) + 1):
                    for tup in itertools.combinations(q, x):
                        letters = ''.join(tup)
                        logger.debug('...considering subset: %s', letters)
                        lookup_letter_set(letters, u, seen_sigs, seen_words)
            query = query[:-1]
            logger.debug('Removing extra letter; query is %s', query)
    else:
        for q in fill_in_blanks(query, seen_fill_ins):
            logger.debug('...blanks filled in: %s', q)
            for x in range(config.config['min_length'], len(q) + 1):
                for tup in itertools.combinations(q, x):
                    letters = ''.join(tup)
                    logger.debug('...considering subset: %s', letters)
                    lookup_letter_set(letters, u, seen_sigs, seen_words)

    output = {}
    for word in sorted(seen_words):
        if config.config['show_scrabble_score']:
            score = 0
            copy = orig_letters.copy()
            for letter in word:
                if letter in copy:
                    copy.remove(letter)
                    score += scrabble_score_by_letter.get(letter, 0)
            if len(word) >= 7:
                score += 50
            output[word] = score
        else:
            output[word] = len(word)

    for word, n in sorted(output.items(), key=lambda x: x[1]):
        decorated_word = decorate_word(word, orig_letters)
        if config.config['show_scrabble_score']:
            print(f'{decorated_word} => {n}')
        else:
            print(decorated_word)


if __name__ == "__main__":
    main()
