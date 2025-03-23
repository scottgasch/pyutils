#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wordle!  PLAY, AUTOPLAY, CHEAT, PRECOMPUTE and SELFTEST.
"""

import enum
import hashlib
import logging
import math
import multiprocessing
import random
import re
import string
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from pyutils import ansi, bootstrap, config, list_utils, string_utils
from pyutils.collectionz.shared_dict import SharedDict
from pyutils.files import file_utils
from pyutils.parallelize import executors
from pyutils.parallelize import parallelize as par
from pyutils.parallelize import smart_future
from pyutils.typez import histogram

logger = logging.getLogger(__name__)
args = config.add_commandline_args(
    f'Wordle! ({__file__})',
    'Args related to cheating at Wordle.',
)
args.add_argument(
    '--mode',
    type=str,
    default='PLAY',
    choices=['CHEAT', 'AUTOPLAY', 'SELFTEST', 'PRECOMPUTE', 'PLAY'],
    metavar='MODE',
    help="""RAW|
Our mode of operation:

      PLAY = play wordle with me!  Pick a random solution or
             specify a solution with --template.

     CHEAT = given a --template and, optionally, --letters_in_word
             and/or --letters_to_avoid, return the best guess word;

  AUTOPLAY = given a complete word in --template, guess it step
             by step showing work;

  SELFTEST = autoplay every possible solution keeping track of
             wins/losses and average number of guesses;

PRECOMPUTE = populate hash table with optimal guesses.
    """,
)
args.add_argument(
    '--template',
    type=str,
    help='The current board in PLAY, CHEAT, AUTOPLAY mode. Use _\'s for unknown letters.',
)
args.add_argument(
    '--letters_to_avoid',
    type=str,
    help='In CHEAT mode, the set of letters known to not be in the solution.',
    metavar='LETTERS',
)
args.add_argument(
    '--letters_in_word',
    type=str,
    help="""RAW|
Letters known to be in the solution but whose positions are not yet known.

For example:

  t0i23 => says we tried a 't' as the first letter (0) so we
           know it's in the word and not there.  We also know
           there's an 'i' which is not the middle letter (2)
           and is not the 4th letter (3).  Note the zero-based
           position counting semantics (i.e. the first letter
           is letter 0).
  e34f0 => mean we know there's an 'e' and an 'f'; we've attempted
           former in positions 3-4 (recall, 4 is the last spot in
           a standard 5 letter wordle) and the latter in the
           first spot (0) already.
    """,
    metavar='<LETTER><ZERO-BASED_POSITION(S)_ALREADY_TRIED>...',
)
args.add_argument(
    '--solutions_file',
    type=str,
    default='wordle_solutions.txt',
    help='Where can I find a valid word list for solutions?',
)
args.add_argument(
    '--guesses_file',
    type=str,
    default='wordle_guesses.txt',
    help='Where can I find a valid word list for guesses?',
)
args.add_argument(
    '--hash_file',
    type=str,
    default='wordle_hash.txt',
    help='Where can I find my precomputed hash file?',
)

# Type aliases for code readability
Position = int
Letter = str
Word = str
Fprint = str
Bucket = int


class Hint(enum.IntFlag):
    """Green, yellow or gray?"""

    GRAY_WRONG = 0
    YELLOW_LETTER_RIGHT_POSITION_WRONG = 1
    GREEN_LETTER_IN_RIGHT_POSITION = 2


class WordStateUndoType(enum.IntFlag):
    """Used to record guess undo information by type."""

    LETTER_IN_SOLUTION_MIN_CHANGE = 1
    LETTER_IN_SOLUTION_MAX_CHANGE = 2
    LETTER_IN_SOLUTION_ADDED_WITH_MIN_MAX = 3
    YELLOW_LETTER_ADDED = 4
    GREEN_LETTER_ADDED = 5
    GRAY_LETTER_ADDED = 6


class WordStateUndo(NamedTuple):
    """A record per guess containing all the info needed to undo it."""

    guess: Word
    hints: Dict[Position, Hint]
    mods: List[Dict[str, Any]]


class WordState(object):
    """Keeps track of the current board state, previous guesses and hints,
    and which letters are known/unknown/eliminated, etc...

    """

    def __init__(
        self,
        solution_length: int,
        max_letter_population_per_word: Dict[Letter, int],
        *,
        letters_at_known_positions: Optional[Dict[Position, Letter]] = None,
        letters_at_unknown_positions: Optional[Dict[Letter, Set[Position]]] = None,
        letters_excluded: Optional[Set[Letter]] = None,
    ):
        """Initialize the WordState given the length of the solution word
        (number of letters), maximum number of times a given letter
        may appear in the solution, and, optionally, some letter
        restrictions.  All positions below are zero-based.

        letters_at_known_positions: position => letter map
        letters_at_unknown_positions: letter => set(position(s) tried) map
        letters_excluded: set of letters known to not be in the word

        """
        super().__init__()
        assert solution_length > 0
        self.solution_length: int = solution_length

        # All info necessary to undo a guess later.  We'll add an entry
        # for every guess in a stack.
        self.undo_info: List[WordStateUndo] = []

        # We're going to use internal methods to set up the initial
        # state and they all require an undo record to populate... but
        # there's no initial guess and we'll never undo beyond here.
        # So create a fake undo record for them to scribble on and
        # throw it away later.
        fake_undo: WordStateUndo = WordStateUndo(
            guess="fake, will be thrown away",
            hints={},
            mods=[],
        )

        # Across all solutions, how many times did each letter appear
        # per word, at max.  For each letter we learn is in the word
        # we'll track a min..max valid occurrances; this is the
        # initial max.  It's the max times a given letter appears in
        # any word in the solution set.
        assert max_letter_population_per_word
        self.max_letter_population_per_word = max_letter_population_per_word

        # The min..max population for every letter we know in the solution.
        # The List[int] here has two entries: min and max.
        self.letters_in_solution: Dict[Letter, List[int]] = {}

        # Green letters by where they are.
        self.letters_at_known_positions: Dict[Position, Letter] = {}
        if letters_at_known_positions is not None:
            for n, letter in letters_at_known_positions.items():
                self.record_green(n, letter, fake_undo)

        # Yellow letters to where we've already tried them (i.e. where
        # the cannot be.)
        self.letters_at_unknown_positions: Dict[Letter, Set[Position]] = defaultdict(
            set
        )
        if letters_at_unknown_positions is not None:
            for letter, tried_pos in letters_at_unknown_positions.items():
                for n in tried_pos:
                    self.record_yellow(n, letter, fake_undo)

        # Excluded letters discovered so far.
        self.letters_excluded: Set[Letter] = set()
        if letters_excluded is not None:
            for letter in letters_excluded:
                self.record_gray(letter, fake_undo)

    def get_template(self) -> str:
        """Return a representation of the board, e.g. __a_e"""

        template = '_' * self.solution_length
        for n in self.letters_at_known_positions:
            letter = self.letters_at_known_positions[n]
            template = template[0:n] + letter + template[n + 1 :]
        return template

    def get_alphabet(self) -> str:
        """Return a colorized set of letters eliminated and still viable."""

        letters_remaining = set(string.ascii_lowercase)
        green_letters = set()
        yellow_letters = set()
        for letter in self.letters_excluded:
            letters_remaining.remove(letter)
        for letter in self.letters_at_known_positions.values():
            assert letter in letters_remaining
            green_letters.add(letter)
        for letter in self.letters_at_unknown_positions.keys():
            if len(self.letters_at_unknown_positions[letter]) > 0:
                assert letter in letters_remaining
                yellow_letters.add(letter)
        ret = ''
        for letter in string.ascii_lowercase:
            if letter in letters_remaining:
                if letter in green_letters:
                    ret += ansi.bg('forest green')
                    ret += ansi.fg('black')
                    ret += letter
                    ret += ansi.reset()
                elif letter in yellow_letters:
                    ret += ansi.bg('energy yellow')
                    ret += ansi.fg('black')
                    ret += letter
                    ret += ansi.reset()
                else:
                    ret += letter
            else:
                ret += ansi.fg('black olive')
                ret += letter
                ret += ansi.reset()
                # ret += ' '
        return ret

    def __repr__(self) -> str:
        return self.get_alphabet()

    def adjust_existing_letters_in_solution_maxes(
        self, max_max: int, undo: WordStateUndo
    ) -> None:
        """We've determined, based on info about letters we know to be in the
        solution and their min..max counts, what the maximum max of
        any letter should be.  Check all letters we know to be in the
        solution and maybe tighten their maxes.  If we do, remember it
        for later undo purposes.

        """
        for letter in self.letters_in_solution.keys():
            old_max = self.letters_in_solution[letter][1]
            new_max = min(max_max, old_max)
            if old_max != new_max:
                self.letters_in_solution[letter][1] = new_max
                undo.mods.append(
                    {
                        "type": WordStateUndoType.LETTER_IN_SOLUTION_MAX_CHANGE,
                        "letter": letter,
                        "old_max": old_max,
                    }
                )

    def record_letter_in_solution(
        self,
        letter: Letter,
        undo: WordStateUndo,
        exact_count: Optional[int] = None,
    ) -> None:
        """Letter is a (maybe new, may existing in a special case, see below)
        letter that we know is in the solution.  For each letter we
        know is in the solution, we track a min..max window indicating
        how many times that letter is permitted to occur in the
        solution.  Manage those here.

        """

        # If letter is already here, allow it to change bounds if it
        # came with an exact_count.
        if letter in self.letters_in_solution:
            if exact_count is not None:
                old_min = self.letters_in_solution[letter][0]
                new_min = exact_count
                if old_min != new_min:
                    self.letters_in_solution[letter][0] = new_min
                    undo.mods.append(
                        {
                            "type": WordStateUndoType.LETTER_IN_SOLUTION_MIN_CHANGE,
                            "letter": letter,
                            "old_min": old_min,
                        }
                    )
                old_max = self.letters_in_solution[letter][1]
                new_max = exact_count
                if old_max != new_max:
                    self.letters_in_solution[letter][1] = new_max
                    undo.mods.append(
                        {
                            "type": WordStateUndoType.LETTER_IN_SOLUTION_MAX_CHANGE,
                            "letter": letter,
                            "old_max": old_max,
                        }
                    )

                # Also... since we now know exactly how many of this
                # letter there are, maybe tighten the rest's maxes.
                if exact_count != 1:
                    num_letters_known = len(self.letters_in_solution) - 1 + exact_count
                    max_max = self.solution_length - (num_letters_known - 1)
                    self.adjust_existing_letters_in_solution_maxes(max_max, undo)
            return

        # If we're here, letter is a newly discovered letter in the
        # solution.  Such a letter will likely affect the max count of
        # existing letters since, as new letters are discovered, there
        # is less room for the other ones in the solution.
        if exact_count is None:
            num_letters_known = len(self.letters_in_solution) + 1
        else:
            num_letters_known = len(self.letters_in_solution) + exact_count
        max_max = self.solution_length - (num_letters_known - 1)
        self.adjust_existing_letters_in_solution_maxes(max_max, undo)

        # Finally, add the new letter's record with its initial min/max.
        if exact_count is None:
            initial_max = min(
                max_max,
                self.max_letter_population_per_word[letter],
            )
            initial_min = 1
        else:
            initial_max = exact_count
            initial_min = exact_count
        self.letters_in_solution[letter] = [initial_min, initial_max]
        undo.mods.append(
            {
                "type": WordStateUndoType.LETTER_IN_SOLUTION_ADDED_WITH_MIN_MAX,
                "min": initial_min,
                "max": initial_max,
                "letter": letter,
            }
        )

    def record_yellow(
        self,
        n: Position,
        letter: Letter,
        undo: WordStateUndo,
        num_correct_doppelgangers: Optional[int] = None,
    ) -> None:
        """We've discovered a new yellow letter or a new place where an
        existing yellow letter is still yellow.  If
        num_correct_doppelgangers is non-None, it means this letter is
        wrong (gray) in the current location but right (green or
        yellow) in other locations and we now know the precise count
        of this letter in the solution -- tell the
        record_letter_in_solution method.

        """
        if n not in self.letters_at_unknown_positions[letter]:
            if (
                len(self.letters_at_unknown_positions[letter]) == 0
                or num_correct_doppelgangers is not None
            ):
                self.record_letter_in_solution(letter, undo, num_correct_doppelgangers)
            self.letters_at_unknown_positions[letter].add(n)
            undo.mods.append(
                {
                    "type": WordStateUndoType.YELLOW_LETTER_ADDED,
                    "letter": letter,
                    "position": n,
                }
            )

    def record_green(self, n: Position, letter: Letter, undo: WordStateUndo):
        """We found a new green letter."""

        if n not in self.letters_at_known_positions:
            self.letters_at_known_positions[n] = letter
            undo.mods.append(
                {
                    "type": WordStateUndoType.GREEN_LETTER_ADDED,
                    "letter": letter,
                    "position": n,
                }
            )
            self.record_letter_in_solution(letter, undo)

    def record_gray(self, letter: Letter, undo: WordStateUndo) -> None:
        """We found a new gray letter."""

        if letter not in self.letters_excluded:
            self.letters_excluded.add(letter)
            undo.mods.append(
                {
                    "type": WordStateUndoType.GRAY_LETTER_ADDED,
                    "letter": letter,
                }
            )

    def record_guess_and_hint(self, guess: Word, hints: Dict[Position, Hint]):
        """Make a guess and change state based on the hint.  Remember how to
        undo everything later.

        """
        undo = WordStateUndo(guess=guess, hints=hints, mods=[])
        for n, letter in enumerate(guess):
            hint = hints[n]

            if hint is Hint.GRAY_WRONG:
                # Exclude letters we got WRONG _unless_ we guessed the
                # same letter elsewhere and got a yellow/green there.
                # In this case the WRONG hint is not saying this
                # letter isn't in the word (it is) but rather that
                # there aren't N+1 instances of this letter.  In this
                # edge case we _do_ know that the letter is not valid
                # in this position, though; treat it as yellow.
                num_correct_doppelgangers = 0
                for k, other in enumerate(guess):
                    if other == letter and n != k and hints[k] != Hint.GRAY_WRONG:
                        num_correct_doppelgangers += 1
                if num_correct_doppelgangers == 0:
                    self.record_gray(letter, undo)
                else:
                    # Treat this as a yellow; we know letter can't go
                    # here or it would have been yellow/green.
                    self.record_yellow(n, letter, undo, num_correct_doppelgangers)
            elif hint is Hint.YELLOW_LETTER_RIGHT_POSITION_WRONG:
                self.record_yellow(n, letter, undo)
            elif hint is Hint.GREEN_LETTER_IN_RIGHT_POSITION:
                self.record_green(n, letter, undo)
        self.undo_info.append(undo)

    def undo_guess(self) -> None:
        """Unmake a guess and revert back to a previous state."""

        assert len(self.undo_info) > 0
        undo = self.undo_info[-1]
        self.undo_info = self.undo_info[:-1]

        # We iterate the mods in reverse order so we never have weird
        # apply/undo ordering artifacts.
        for mod in reversed(undo.mods):
            mod_type = mod['type']
            letter = mod['letter']
            if mod_type is WordStateUndoType.GRAY_LETTER_ADDED:
                self.letters_excluded.remove(letter)
            elif mod_type is WordStateUndoType.YELLOW_LETTER_ADDED:
                pos = mod['position']
                self.letters_at_unknown_positions[letter].remove(pos)
            elif mod_type is WordStateUndoType.GREEN_LETTER_ADDED:
                pos = mod['position']
                del self.letters_at_known_positions[pos]
            elif mod_type is WordStateUndoType.LETTER_IN_SOLUTION_MIN_CHANGE:
                old_min = mod['old_min']
                self.letters_in_solution[letter][0] = old_min
            elif mod_type is WordStateUndoType.LETTER_IN_SOLUTION_MAX_CHANGE:
                old_max = mod['old_max']
                self.letters_in_solution[letter][1] = old_max
            elif mod_type is WordStateUndoType.LETTER_IN_SOLUTION_ADDED_WITH_MIN_MAX:
                del self.letters_in_solution[letter]


class AutoplayOracle(object):
    """The class that knows the right solution and can give hints in
    response to guesses.

    """

    def __init__(self, solution: Word):
        super().__init__()
        self.solution = solution.lower()
        self.solution_letter_count = Counter(self.solution)
        self.solution_letter_to_pos = defaultdict(set)
        for n, letter in enumerate(self.solution):
            self.solution_letter_to_pos[letter].add(n)
        self.hint_quota_by_letter = Counter(self.solution)

    def judge_guess(self, guess: Word) -> Dict[Position, Hint]:
        """Returns a mapping from position -> Hint to indicate
        whether each letter in the guess string is green, yellow
        or gray.

        """
        assert len(guess) == len(self.solution)
        hint_by_pos: Dict[Position, Hint] = {}
        letter_to_pos = defaultdict(set)
        hint_quota_by_letter = self.hint_quota_by_letter.copy()

        for position, letter in enumerate(guess):
            letter_to_pos[letter].add(position)

            if letter == self.solution[position]:  # green
                if hint_quota_by_letter[letter] == 0:
                    # We must tell them this letter is green in this
                    # position but we've exhausted our quota of hints
                    # for this letter.  There must exist some yellow
                    # hint we previously gave that we need to turn to
                    # gray (wrong).
                    for other in letter_to_pos[letter]:
                        if other != position:
                            if (
                                hint_by_pos[other]
                                == Hint.YELLOW_LETTER_RIGHT_POSITION_WRONG
                            ):
                                hint_by_pos[other] = Hint.GRAY_WRONG
                                break
                hint_by_pos[position] = Hint.GREEN_LETTER_IN_RIGHT_POSITION

            elif self.solution_letter_count[letter] > 0:  # yellow
                if hint_quota_by_letter[letter] == 0:
                    # We're out of hints for this letter.  All the
                    # other hints must be green or yellow.  Tell them
                    # this one is gray (wrong).
                    hint_by_pos[position] = Hint.GRAY_WRONG
                else:
                    hint_by_pos[position] = Hint.YELLOW_LETTER_RIGHT_POSITION_WRONG

            else:  # gray
                hint_by_pos[position] = Hint.GRAY_WRONG
            if hint_quota_by_letter[letter] > 0:
                hint_quota_by_letter[letter] -= 1
        return hint_by_pos


class AutoPlayer(object):
    """This is the class that knows how to guess given the current game
    state along with several support methods.

    """

    def __init__(self):
        super().__init__()
        self.solution_length = None

        # Guess judge
        self.oracle = None

        # Board state tracker and move undoer
        self.word_state = None

        # The position hash has known best guesses for some subset of
        # remaining words.  See --mode=PRECOMPUTE for how to populate.
        self.position_hash = {}
        filename = config.config['hash_file']
        if filename is not None and file_utils.is_readable(filename):
            logger.debug('Initializing position hash from %s...', filename)
            with open(filename, 'r') as rf:
                for line in rf:
                    line = line[:-1]
                    line = line.strip()
                    line = re.sub(r'#.*$', '', line)
                    if len(line) == 0:
                        continue
                    (key, word) = line.split(':')
                    (count, fprint) = key.split('@')
                    count = count.strip()
                    count = int(count)
                    fprint = fprint.strip()
                    word = word.strip()
                    self.position_hash[(count, fprint)] = word
            logger.debug('...hash contains %s entries.', len(self.position_hash))

        # All legal solutions pre-sorted by length.
        self.all_possible_solutions_by_length = defaultdict(list)
        filename = config.config['solutions_file']
        if filename is not None and file_utils.is_readable(filename):
            logger.debug('Initializing valid solution word list from %s...', filename)
            with open(filename) as rf:
                for word in rf:
                    word = word[:-1]
                    word = word.lower()
                    self.all_possible_solutions_by_length[len(word)].append(word)
        else:
            logger.error('A valid --solutions_file is required.')
            sys.exit(0)

        # All legal guesses pre-sorted by length.
        self.all_possible_guesses_by_length = defaultdict(list)
        filename = config.config['guesses_file']
        if filename is not None and file_utils.is_readable(filename):
            logger.debug('Initializing legal guess word list from %s...', filename)
            with open(filename) as rf:
                for word in rf:
                    word = word[:-1]
                    word = word.lower()
                    self.all_possible_guesses_by_length[len(word)].append(word)
        else:
            logger.error('A valid --guesses_file is required.')
            sys.exit(0)

    def new_word(
        self,
        length: int,
        oracle: Optional[AutoplayOracle],
        word_state: Optional[WordState],
    ) -> None:
        """Here's a new word to guess.  Reset state to play a new game.  On
        principle we don't give this class the solution.  Instead, we
        just give it length to indicate the number of characters in
        the solution.  Guesses will be turned into hints by the
        oracle.  The current game state is tracked by the
        word_state.

        """
        self.solution_length = length
        self.oracle = oracle
        self.word_state = word_state

    def get_all_possible_solutions(self) -> List[Word]:
        """Given the current known word state, compute the subset of all
        possible solutions that are still possible.  Note: this method
        guarantees to return the possible solutions list in sorted
        order.

        """

        def is_possible_solution(solution: Word, word_state: WordState) -> bool:
            """Note: very perf sensitive code; inner loop."""

            letters_seen: Dict[Letter, int] = defaultdict(int)
            for n, letter in enumerate(solution):
                # The word can't contain letters we know aren't in the
                # solution.
                if letter in word_state.letters_excluded:
                    return False

                # If we know a letter is in a position, solution words
                # must have that letter in that position.
                if (
                    n in word_state.letters_at_known_positions
                    and letter != word_state.letters_at_known_positions[n]
                ):
                    return False

                # If we already tried this letter in this position and
                # it wasn't green, this isn't a possible solution.
                if n in word_state.letters_at_unknown_positions[letter]:
                    return False

                letters_seen[letter] += 1

            # Finally, the word must include all letters presently
            # known to be in the solution to be viable.
            for letter, min_max in word_state.letters_in_solution.items():
                num_seen = letters_seen[letter]
                if num_seen < min_max[0]:
                    return False
                elif num_seen > min_max[1]:
                    return False
            return True

        possible_solutions = []
        for word in self.all_possible_solutions_by_length[self.solution_length]:
            assert self.word_state
            if is_possible_solution(word, self.word_state):
                possible_solutions.append(word)

        # Note: because self.all_possible_solutions_by_length is sorted
        # and we iterated it in order, possible_solutions is also sorted
        # already.
        # assert possible_solutions == sorted(possible_solutions)
        return possible_solutions

    def get_frequency_and_frequency_by_position_tables(
        self,
        possible_solutions: List[Word],
    ) -> Tuple[Dict[Letter, float], List[Dict[Letter, float]]]:
        """This method is used by heuristic mode.  It returns two tables:

        1. The frequency count by letter for words in possible_solutions
           to encourage guesses composed of common letters.
        2. A letter-in-position bonus term to encourage guesses with
           letters in positions that occur frequently in the solutions.

        """
        assert self.word_state
        template = self.word_state.get_template()
        pfreq: List[Dict[Letter, float]] = []
        pop_letters: List[Dict[Letter, int]] = []
        for n in range(len(template)):
            pop_letters.append(defaultdict(int))
            pfreq.append({})

        freq: Dict[Letter, float] = {}
        for word in possible_solutions:
            letter_filter = set()
            for n, letter in enumerate(word):

                # Only count frequency of letters still to be filled in.
                if template[n] != '_':
                    continue

                # Do not give a full frequency bonus to repeated letters.
                if letter not in letter_filter:
                    freq[letter] = freq.get(letter, 0) + 1
                    letter_filter.add(letter)
                else:
                    freq[letter] += 0.1
                pop_letters[n][letter] += 1  # type: ignore

        # Reward guesses that place the most popular letter in a position.
        # Save the top 3 letters per position.
        # don't give a bonus if letters spread all over the place?
        # only give a bonus to a given letter in one position?
        total_letters_in_position = len(possible_solutions)
        for n in range(len(template)):
            for letter, count in sorted(pop_letters[n].items(), key=lambda x: -x[1]):
                if count <= 1:
                    break
                normalized = count / total_letters_in_position
                assert 0.0 < normalized <= 1.0
                if normalized > 0.08:
                    pfreq[n][letter] = normalized
                else:
                    break
        return (freq, pfreq)

    def dump_frequency_data(
        self,
        possible_solutions: List[Word],
        letter_frequency: Dict[Letter, float],
        letter_position_frequency: List[Dict[Letter, float]],
    ) -> None:
        """Just logs the frequency tables we computed above."""

        logger.debug('Unknown letter(s) frequency table: ')
        out = ''
        for letter, weight in sorted(letter_frequency.items(), key=lambda x: -x[1]):
            out += f'{letter}:{weight}, '
        if len(out) > 0:
            out = out[:-2]
            logger.debug(out)

        logger.debug('Unknown letter-in-position bonus table: ')
        out = ''
        for n in range(len(possible_solutions[0])):
            pop = letter_position_frequency[n]
            for letter, weight in sorted(pop.items(), key=lambda x: -x[1]):
                out += f'pos{n}:{letter}@{weight:.5f}, '
        if len(out) > 0:
            out = out[:-2]
            logger.debug(out)

    def position_in_hash(self, num_potential_solutions: int, fprint: Fprint):
        """Is a position in our hash table?"""
        return (num_potential_solutions, fprint) in self.position_hash

    def guess_word(self) -> Optional[Word]:
        """Compute a guess word and return it.  Returns None on error."""

        assert self.word_state
        template = self.word_state.get_template()
        possible_solutions = self.get_all_possible_solutions()
        num_possible_solutions = len(possible_solutions)
        fprint = hashlib.md5(repr(possible_solutions).encode('ascii')).hexdigest()

        n = num_possible_solutions
        logger.debug(
            string_utils.make_contractions(
                f'There {string_utils.is_are(n)} {n} word{string_utils.pluralize(n)} '
                + f'({template} @ {fprint}).'
            )
        )
        if num_possible_solutions < 30:
            logger.debug(
                string_utils.make_contractions(
                    f'{string_utils.capitalize_first_letter(string_utils.it_they(n))} '
                    + f'{string_utils.is_are(n)}: {possible_solutions}'
                )
            )
        logger.debug(
            'Letter count restrictions: %s', self.word_state.letters_in_solution
        )
        if num_possible_solutions == 0:
            logger.error('No possible solutions?!')
            print('No possible solutions?!', file=sys.stderr)
            print(self.word_state)
            print(self.word_state.letters_in_solution)
            return None

        elif num_possible_solutions == 1:
            return possible_solutions[0]

        # Check the hash table for a precomputed best guess.
        elif self.position_in_hash(num_possible_solutions, fprint):
            guess = self.position_hash[(num_possible_solutions, fprint)]
            logger.debug('hash hit: %s', guess)
            return guess

        # If there are just a few solutions possible, brute force the
        # guess.  This is expensive: for every possible solution it
        # computes the entropy of every possible guess.  Not fast for
        # large numbers of solutions.
        elif num_possible_solutions < 20:
            logger.debug(
                'Only %d solutions; using brute force strategy.', num_possible_solutions
            )
            return self.brute_force_internal(
                possible_solutions,
                self.all_possible_guesses_by_length[len(possible_solutions[0])],
                'brute_force',
            )

        # A hybrid approach: narrow down the guess list using
        # heuristic scoring and then compute the entropy of the topN
        # guesses via brute force.
        elif num_possible_solutions < 100:
            logger.debug(
                'Only %d solutions; using hybrid strategy.', num_possible_solutions
            )
            return self.hybrid_search(possible_solutions)

        # There are a lot of words left; score the guesses based on
        # fast heuristics (i.e. letter frequency).
        else:
            logger.debug(
                'There are %s solutions; using fast heuristics.', num_possible_solutions
            )
            return self.heuristics_search(possible_solutions)

    def brute_force_internal(
        self,
        possible_solutions: List[Word],
        all_guesses: List[Word],
        label: str,
    ) -> Optional[Word]:
        """Assume every possible solution is the answer, in turn.  For each
        one, try all_guesses and pay attention to the hint we would
        get back.  Compute the entropy of each guess and return the
        guess with the highest entropy -- i.e. the guess that gives us
        the most information on average; or, the guess whose results
        would take the most bits to represent.

        Note, this is expensive.  O(num_possible_solutions * all_guesses)

        """
        num_possible_solutions = len(possible_solutions)
        if num_possible_solutions == 1:
            return possible_solutions[0]
        possible_solutions_set = set(possible_solutions)  # for O(1) lookups

        # Buckets count distinct outcomes of a guess.  e.g. if a guess
        # yields the hint G_Y__ that outcome is assigned a bucket
        # number and we will increment the count of how many times
        # that outcome happened for this guess across all possible
        # solutions.
        bucket_population_by_guess: Dict[Word, Dict[Bucket, int]] = {}
        for guess in all_guesses:
            bucket_population_by_guess[guess] = defaultdict(int)

        # Pretend that each possible solution is the real solution
        # and make every possible guess for each.
        for solution in possible_solutions:
            oracle = AutoplayOracle(solution)
            for guess in all_guesses:
                hints = oracle.judge_guess(guess)

                # Note: this is a really good way to make sure that
                # make/unmake moves works:
                #
                # before = self.word_state.__repr__()
                assert self.word_state
                self.word_state.record_guess_and_hint(guess, hints)
                # during = self.word_state.__repr__()

                # Map the hint returned into a bucket number and
                # keep track of population per bucket.  Below:
                #
                #   n is a position := {0, 1, 2, 3, 4}
                #   hint[n] := {1, 2, 3}
                #
                bucket: Bucket = 0
                for n in range(len(guess)):
                    bucket += hints[n] * (3**n)
                bucket_population_by_guess[guess][bucket] += 1
                self.word_state.undo_guess()

                # after = self.word_state.__repr__()
                # if before != after:
                #    print(f'BEFORE: {before}')
                #    print(f'  WORD: {colorize_guess(guess, hints)}')
                #    print(f'  HINT: {hints}')
                #    print(f'DURING: {during}')
                #    print(f' AFTER: {after}')
                #    assert False

        # Compute the entropy of every guess across all possible
        # solutions:
        #
        # https://markmliu.medium.com/what-in-the-wordle-5dc5ed94fe2
        # https://machinelearningmastery.com/what-is-information-entropy/
        # https://en.wikipedia.org/wiki/Entropy_(information_theory)
        best_entropy = None
        best_guess = None
        entropy: Dict[Word, float] = {}
        for guess in all_guesses:
            entropy[guess] = 0.0
            for bucket in bucket_population_by_guess[guess]:

                # We counted how many times this outcome occurred.
                # The probabilty of this outcome = count / total.
                p = float(bucket_population_by_guess[guess][bucket])
                p /= num_possible_solutions
                entropy[guess] += p * math.log2(p)
            entropy[guess] = -entropy[guess]

            if best_entropy is None:
                best_entropy = entropy[guess]
                best_guess = guess
            else:

                # We always choose the guess with the highest entropy
                # because this guess gives us the most information in
                # the average case, i.e. it takes the most bits to
                # represent the average outcome of this guess.
                #
                # However, in practice, usually several guesses tie
                # for best.  Prefer guesses that are also potential
                # solutions (not just legal guesses)
                if entropy[guess] > best_entropy or (
                    entropy[guess] == best_entropy and guess in possible_solutions_set
                ):
                    best_entropy = entropy[guess]
                    best_guess = guess

        # This is just logging the results.  Display the guesses with
        # the highest entropy but also display the entropy of every
        # possible solution, too, even if they are not best.
        possible_solutions_seen = 0
        best_entropy = None
        best_count = 0
        for n, (guess, guess_entropy) in enumerate(
            sorted(entropy.items(), key=lambda x: -x[1])
        ):
            if best_entropy is None:
                best_entropy = guess_entropy
            if guess in possible_solutions_set:
                possible_solutions_seen += 1
                logger.debug(
                    f'{label}: #{n}: {guess} with {guess_entropy:.5f} bits <--'
                )
            elif guess_entropy == best_entropy and best_count < 15:
                logger.debug(f'{label}: #{n}: {guess} with {guess_entropy:.5f} bits')
                best_count += 1
        logger.debug('%s: best guess is %s.', label, best_guess)
        return best_guess

    def hybrid_search(self, possible_solutions: List[Word]) -> Optional[Word]:
        """Use heuristic scoring to reduce the number of guesses before
        calling brute force search.

        """
        (freq, pfreq) = self.get_frequency_and_frequency_by_position_tables(
            possible_solutions
        )
        self.dump_frequency_data(possible_solutions, freq, pfreq)
        scored_guesses = self.assign_scores(possible_solutions, freq, pfreq)
        best_guess = None

        topn_guesses = []
        count = 1
        for guess, score in sorted(scored_guesses.items(), key=lambda x: -x[1]):
            logger.debug(f'hybrid: heuristic #{count} = {guess} with {score:.5f}')
            topn_guesses.append(guess)
            count += 1
            if count > 10:
                break

        best_guess = self.brute_force_internal(
            possible_solutions, topn_guesses, 'hybrid: brute_force'
        )
        return best_guess

    def assign_scores(
        self,
        possible_solutions: List[Word],
        freq: Dict[Letter, float],
        pfreq: List[Dict[Letter, float]],
    ) -> Dict[Word, float]:
        """Given some letter frequency and letter+position bonus data, assign
        a score to every possible guess.

        """
        num_possible_solutions = len(possible_solutions)
        assert num_possible_solutions > 1
        assert self.word_state
        template = self.word_state.get_template()

        # Give every word a score composed of letter frequencies and letter
        # in position frequencies.  This score attempts to approximate the
        # result of brute_force_search less expensively.
        word_scores: Dict[Word, float] = {}
        for guess in possible_solutions:
            freq_term = 0.0
            pfreq_term = 0.0

            letter_filter = set()
            for n, letter in enumerate(guess):

                # Ignore letters we already know.
                if template[n] != '_':
                    continue

                # Is there a bonus for this letter in this position?  (pfreq)
                pop = pfreq[n]
                if letter in pop:
                    pfreq_term += pop[letter] * num_possible_solutions / 4

                # Don't count freq bonus more than once per letter.  (freq)
                if letter in letter_filter:
                    continue
                freq_term += freq.get(letter, 0.0)
                letter_filter.add(letter)
            score = freq_term + pfreq_term
            word_scores[guess] = score
        return word_scores

    def heuristics_search(self, possible_solutions: List[Word]) -> Word:
        """The dumbest but fastest search.  Use fast heuristics to score each
        possible guess and then guess the one with the highest
        score.

        """
        (freq, pfreq) = self.get_frequency_and_frequency_by_position_tables(
            possible_solutions
        )
        self.dump_frequency_data(possible_solutions, freq, pfreq)
        scored_guesses = self.assign_scores(possible_solutions, freq, pfreq)
        best_guess = None
        for n, (guess, score) in enumerate(
            sorted(scored_guesses.items(), key=lambda x: -x[1])
        ):
            if best_guess is None:
                best_guess = guess
            if n < 20:
                logger.debug(f'heuristic: #{n}: {guess} with {score:.5f}')
        assert best_guess is not None
        return best_guess


def colorize_guess(guess: Word, hints: Dict[Position, Hint]) -> str:
    """Use hints to make the letters green/yellow/gray."""
    ret = ''
    for n, letter in enumerate(guess):
        hint = hints[n]
        if hint is Hint.GRAY_WRONG:
            ret += ansi.bg('mist gray')
        elif hint is Hint.YELLOW_LETTER_RIGHT_POSITION_WRONG:
            ret += ansi.bg('energy yellow')
        elif hint is Hint.GREEN_LETTER_IN_RIGHT_POSITION:
            ret += ansi.bg('forest green')
        ret += ansi.fg('black')
        ret += letter
        ret += ansi.reset()
    return ret


def get_max_letter_population() -> Dict[Letter, int]:
    filename = config.config['solutions_file']
    max_letter_population_per_word: Dict[Letter, int] = defaultdict(int)
    if filename is not None and file_utils.is_readable(filename):
        logger.debug(
            'Figuring out all letters\' max frequency in the solution space...'
        )
        with open(filename) as rf:
            for word in rf:
                word = word[:-1]
                word = word.lower()
                letter_pop = Counter(word)
                for letter, pop in letter_pop.items():
                    if pop > max_letter_population_per_word[letter]:
                        max_letter_population_per_word[letter] = pop
    else:
        logger.error('A valid --solutions_file is required.')
        sys.exit(0)
    return max_letter_population_per_word


def autoplay(
    solution: Word,
    oracle: AutoplayOracle,
    word_state: WordState,
    player: AutoPlayer,
    quiet: bool = False,
):
    """Make guesses one by one until arriving at a known solution."""
    if not quiet:
        logger.debug('Autoplayer mode...')
    player.new_word(len(solution), oracle, word_state)

    guesses = []
    while True:
        guess = player.guess_word()
        if guess is not None:
            hints = oracle.judge_guess(guess)
            word_state.record_guess_and_hint(guess, hints)
            guesses.append(guess)
            if not quiet:
                colorized_guess = colorize_guess(guess, hints)
                print(f'Guess #{len(guesses)}: {colorized_guess} => {word_state}')
        if guess == solution:
            break
        if guess is None:
            logger.error(f'"{solution}" is not in my --solutions_file.')
            break
    return guesses


def cheat():
    """Cheater!  Given a board state, determine the best guess.  Note that
    in this mode the solution is not known.

    """
    logger.debug('Cheater mode...')

    template = config.config['template']
    assert template

    # Extract known letter positions from the template.
    template = template.lower()
    letters_at_known_positions = {}
    for n, letter in enumerate(template):
        if letter != '_':
            letters_at_known_positions[n] = letter

    # Initialize set of letters to be avoided.
    avoid = config.config['letters_to_avoid']
    if not avoid:
        avoid = ''
    avoid = avoid.lower()
    letters_to_avoid = set(list(avoid))

    # Initialize the set of letters we know are in the solution but
    # not where, yet.
    in_word = config.config['letters_in_word']
    if not in_word:
        in_word = ''
    in_word = in_word.lower()

    # This is parsing out the --letters_in_word argument.  The
    # format is:
    #
    #   <letter><1 or more zero-based positions we already tried it>
    #
    # So, if we know an E is in the word (i.e. it's yellow) and
    # we tried it in the first and third letter already:
    #
    #   e02
    #
    # Note: 0 means "the first letter", i.e. position is zero based.
    #
    # You can stack letters this way.  e.g.:
    #
    #   e02a3
    letters_in_word_at_unknown_position = defaultdict(set)
    last_letter = None
    for letter in in_word:
        if letter.isdigit():
            assert last_letter
            letters_in_word_at_unknown_position[last_letter].add(int(letter))
        elif letter.isalpha():
            last_letter = letter

    max_letter_pop_per_word = get_max_letter_population()
    word_state = WordState(
        len(template),
        max_letter_pop_per_word,
        letters_at_known_positions=letters_at_known_positions,
        letters_at_unknown_positions=letters_in_word_at_unknown_position,
        letters_excluded=letters_to_avoid,
    )

    player = AutoPlayer()
    player.new_word(len(template), None, word_state)
    return player.guess_word()


def selftest():
    """Autoplay every possible solution and pay attention to statistics."""

    logger.debug('Selftest mode...')
    total_guesses = 0
    total_words = 0
    max_guesses = None
    max_guesses_words = []
    every_guess = set()
    hist = histogram.SimpleHistogram(
        [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 100)]
    )
    top_guess_number = defaultdict(dict)
    num_losses = 0

    player = AutoPlayer()
    filename = str(config.config['solutions_file'])
    with open(filename, 'r') as rf:
        contents = rf.readlines()

    max_letter_pop_per_word = get_max_letter_population()
    start = time.time()
    for word in contents:
        word = word[:-1]
        word = word.lower()
        if len(word) != 5:
            logger.warning(
                f'Found word "{word}" in solutions file that is not 5 letters in length.  Skipping it.'
            )
            continue
        oracle = AutoplayOracle(word)
        word_state = WordState(len(word), max_letter_pop_per_word)
        player.new_word(len(word), oracle, word_state)

        total_words += 1
        runtime = time.time() - start
        print(
            f'{total_words} / {len(contents)} ("{word}") = {total_words/len(contents)*100.0:.2f}% | {total_guesses/total_words:.3f} guesses/word | {runtime:.1f}s @ {runtime/total_words:.3f}s/word\r',
            end='',
        )
        if total_words % 100 == 0:
            print(f'\nAfter {total_words} words:')
            print(
                f'...I made {total_guesses} guesses; ({total_guesses/total_words:.3f}/word)'
            )
            print(
                f'...Max guesses was {max_guesses} for {max_guesses_words}; I lost {num_losses} times.'
            )
            print(f'...I made {len(every_guess)} total distinct "interior" guesses.')
            print()

        guesses = autoplay(word, oracle, word_state, player, True)
        guess_count = len(guesses)
        if guess_count > 6:
            num_losses += 1
        hist.add_item(guess_count)
        total_guesses += guess_count
        for n, guess in enumerate(guesses):
            tops = top_guess_number[n]
            tops[guess] = tops.get(guess, 0) + 1
            if n != len(guesses) - 1:
                every_guess.add(guess)
        if max_guesses is None or guess_count > max_guesses:
            max_guesses = guess_count
            max_guesses_words = [word]
        elif guess_count == max_guesses:
            max_guesses_words.append(word)
    print("\nFinal Report:")
    print("-------------")
    print(f'On {total_words} words:')
    print(
        f'...I made {total_guesses} guesses; ({total_guesses / total_words:.3f} / word)'
    )
    print(
        f'...Max guesses was {max_guesses} for {max_guesses_words}; I lost {num_losses} times.'
    )
    print(f'...I made {len(every_guess)} total distinct "interior" guesses.')
    print()
    for n in range(0, 8):
        top_guesses = top_guess_number[n]
        num = 0
        out = ''
        print(f'Top guesses #{n+1}: ', end='')
        for guess, count in sorted(top_guesses.items(), key=lambda x: -x[1]):
            out += f'{guess}@{count}, '
            num += 1
            if num > 8:
                break
        out = out[:-2]
        print(out)
    print()
    print(hist)


@par.parallelize(method=par.Method.PROCESS)
def do_words(
    solutions: List[Word],
    shard_num: int,
    shared_cache_name: str,
    lock: multiprocessing.RLock,
    max_letter_pop_per_word: Dict[Letter, int],
):
    """Work on precomputing one shard of the solution space, in parallel."""

    logger.debug(f'Shard {shard_num} owns solutions {solutions[0]}..{solutions[-1]}.')
    player = AutoPlayer()
    length = len(solutions[0])
    shared_cache = SharedDict(shared_cache_name, 0, lock)
    begin = solutions[0]
    end = solutions[-1]

    passes = 0
    while True:
        num_computed = 0
        passes += 1
        assert passes < 10
        local_cache: Dict[Tuple[int, Fprint], Word] = {}

        for n, solution in enumerate(solutions):
            oracle = AutoplayOracle(solution)
            word_state = WordState(length, max_letter_pop_per_word)
            player.new_word(length, oracle, word_state)
            guesses = []

            # Make guesses until the next guess is not in the hash or
            # the shared dict.
            while True:
                remaining_words = player.get_all_possible_solutions()
                num_remaining_words = len(remaining_words)
                if num_remaining_words <= 1:
                    break

                sig_remaining_words = hashlib.md5(
                    remaining_words.__repr__().encode('ascii')
                ).hexdigest()
                key = (num_remaining_words, sig_remaining_words)

                if player.position_in_hash(num_remaining_words, sig_remaining_words):
                    provenance = 'game_hash'
                    guess = player.guess_word()
                elif key in local_cache:
                    provenance = 'local_cache'
                    guess = local_cache[key]
                elif key in shared_cache:
                    provenance = 'shared_cache'
                    guess = shared_cache[key]
                else:
                    provenance = 'computed'
                    guess = player.brute_force_internal(
                        remaining_words,
                        player.all_possible_guesses_by_length[length],
                        'precompute',
                    )
                    local_cache[key] = guess
                    shared_cache[key] = guess
                    num_computed += 1
                assert guess
                guesses.append(guess)
                hints = oracle.judge_guess(guess)
                word_state.record_guess_and_hint(guess, hints)
                print(
                    f'shard{shard_num}: '
                    + f'{passes}/{n}/{len(solutions)}/{solution}> '
                    + f'{num_remaining_words} @ {sig_remaining_words}: {guesses} # {provenance}'
                )

        # When we can make it through a pass over all solutions and
        # never miss the hash or shared dict, we're done.
        if num_computed == 0:
            print(
                f'{ansi.bg("green")}{ansi.fg("black")}'
                + f'shard{shard_num}: "{begin}".."{end}" is finished!'
                + f'{ansi.reset()}'
            )
            break
    shared_cache.close()
    return f'(shard {shard_num} done)'


def precompute():
    """Precompute the best guess in every situation via the expensive
    brute force / entropy method.  Break the solutions list into
    shards and execute each one in parallel.  Persist the concatenated
    results in a file.

    """
    filename = str(config.config['solutions_file'])
    with open(filename, 'r') as rf:
        contents = rf.readlines()
    all_words = []
    length = None
    for word in contents:
        word = word[:-1]
        word = word.lower()
        if length is None:
            length = len(word)
        else:
            assert len(word) == length
        all_words.append(word)

    max_letter_pop_per_word = get_max_letter_population()
    shards = []
    logger.debug('Sharding words into groups of 10.')
    for subset in list_utils.shard(all_words, 10):
        shards.append([x for x in subset])

    logger.debug('Kicking off helper pool.')

    # Shared cache is a dict that is slow to read/write but is visible
    # to all shards so that they can benefit from results already
    # computed in one of the other workers.  10 pages (~40kb) of
    # memory.
    shared_cache = SharedDict("wordle_shared_dict", 4096 * 10)
    results = []
    try:
        for n, shard in enumerate(shards):
            results.append(
                do_words(
                    shard,
                    n,
                    shared_cache.get_name(),
                    SharedDict.LOCK,
                    max_letter_pop_per_word,
                )
            )
        smart_future.wait_all(results)

        filename = str(config.config['hash_file'])
        with open(filename, 'a') as wf:
            for key, value in shared_cache.items():
                print(f'{key[0]} @ {key[1]}: {value}', file=wf)
    finally:
        shared_cache.close()
        shared_cache.cleanup()
        executors.DefaultExecutors().process_pool().shutdown()


def get_legal_guesses() -> Set[Word]:
    legal_guesses = set()
    filename = str(config.config['guesses_file'])
    with open(filename, 'r') as rf:
        contents = rf.readlines()
    for line in contents:
        line = line[:-1]
        line = line.lower()
        legal_guesses.add(line)
    return legal_guesses


def get_solution() -> Word:
    if config.config['template'] is not None:
        solution = config.config['template']
        print(ansi.clear())
    else:
        filename = str(config.config['solutions_file'])
        with open(filename, 'r') as rf:
            contents = rf.readlines()
        solution = random.choice(contents)
        solution = solution[:-1]
        solution = solution.lower()
        solution = solution.strip()
    assert solution
    return solution


def give_hint(num_hints: int, player: AutoPlayer, word_state: WordState):
    """Give a smart(?) hint to the guesser."""

    possible_solutions = player.get_all_possible_solutions()
    n = len(possible_solutions)
    if num_hints == 1:
        print(
            f'There {string_utils.is_are(n)} {n} possible solution{string_utils.pluralize(n)}.'
        )
    elif num_hints == 2:
        (freq, _) = player.get_frequency_and_frequency_by_position_tables(
            possible_solutions
        )
        hint_letters = sorted(freq.items(), key=lambda x: -x[1])
        good_hints = set(string.ascii_lowercase)
        for letter in word_state.letters_at_unknown_positions.keys():
            if len(word_state.letters_at_unknown_positions[letter]) > 0:
                if letter in good_hints:
                    good_hints.remove(letter)
        for letter in word_state.letters_at_known_positions.values():
            if letter in good_hints:
                good_hints.remove(letter)
        limit = 2
        if n < 10:
            limit = 1
        for letter, _ in hint_letters:
            if letter in good_hints:
                print(
                    f'"{letter}" is popular in the possible solution{string_utils.pluralize(n)}.'
                )
                limit -= 1
                if limit == 0:
                    break
    elif num_hints == 3:
        limit = 3
        if n < 10:
            limit = 1
        for possibility in random.sample(possible_solutions, min(limit, n)):
            print(f'Maybe something like "{possibility}"?')
    elif num_hints >= 4:
        best_guess = player.guess_word()
        print(f'Try "{best_guess}"')


def play() -> None:
    """Allow users to play and color in the letter for them."""

    legal_guesses = get_legal_guesses()
    solution = get_solution()
    oracle = AutoplayOracle(solution)
    max_letter_pop_per_word = get_max_letter_population()
    word_state = WordState(len(solution), max_letter_pop_per_word)
    player = AutoPlayer()
    player.new_word(len(solution), oracle, word_state)

    num_guesses = 0
    prompt = 'Guess #_/6 (or "?" for a hint): '
    padding = ' ' * len(prompt)
    colorized_guess = "▢" * len(solution)
    guess = None
    num_hints = 0

    while True:
        # Print current state + template.
        print(padding + colorized_guess + "     " + word_state.__repr__())
        if guess == solution:
            print('Nice!')
            break
        if num_guesses >= 6:
            print('Better luck next time.')
            print(padding + f'{solution}')
            break

        # Get a guess / command.
        guess = input(prompt.replace('_', str(num_guesses + 1))).lower().strip()

        # Parse it.
        if guess == '?':
            num_hints += 1
            give_hint(num_hints, player, word_state)
            continue
        elif guess == '#brute':
            remaining_words = player.get_all_possible_solutions()
            brute = player.brute_force_internal(
                remaining_words,
                player.all_possible_guesses_by_length[len(solution)],
                'precompute',
            )
            print(word_state)
            print(brute)
            continue
        elif len(guess) != len(solution) or guess not in legal_guesses:
            print(f'"{guess}" is not a legal guess, try again.')
            continue

        # If we get here it was a guess.  Process it.
        num_guesses += 1
        hints = oracle.judge_guess(guess)
        colorized_guess = colorize_guess(guess, hints)
        word_state.record_guess_and_hint(guess, hints)
        num_hints = 0


# The bootstrap.initialize decorator takes care of parsing our commandline
# flags and populating config.  It can also do cool things like time and
# profile the code run within it, audit imports, profile memory usage,
# and break into pdb on unhandled exception.
@bootstrap.initialize
def main() -> Optional[int]:
    mode = config.config['mode'].upper().strip()
    if mode == 'AUTOPLAY':
        solution = config.config['template']
        assert solution
        solution = solution.lower()
        oracle = AutoplayOracle(solution)
        max_letter_pop_per_word = get_max_letter_population()
        word_state = WordState(len(solution), max_letter_pop_per_word)
        player = AutoPlayer()
        autoplay(solution, oracle, word_state, player)
        return None
    elif mode == 'CHEAT':
        cheat()
        return None
    elif mode == 'PLAY':
        play()
        return None
    elif mode == 'SELFTEST':
        selftest()
        return None
    elif mode == 'PRECOMPUTE':
        precompute()
        return None
    raise Exception('wtf?')


if __name__ == '__main__':
    main()
