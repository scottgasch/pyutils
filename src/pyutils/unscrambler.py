#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""A fast (English) word unscrambler."""

import logging
from typing import Dict, Mapping, Optional

from pyutils import config, decorator_utils, list_utils
from pyutils.files import file_utils

cfg = config.add_commandline_args(
    f"Unscrambler base library ({__file__})", "A fast word unscrambler."
)
cfg.add_argument(
    "--unscrambler_default_indexfile",
    help="Path to a file of signature -> word index.",
    metavar="FILENAME",
    default="/usr/share/dict/sparse_index",
)

logger = logging.getLogger(__name__)

letters_bits = 32
letters_mask = 2**letters_bits - 1

fprint_bits = 52
fprint_mask = (2**fprint_bits - 1) << letters_bits

fprint_feature_bit = {
    "e": 0,
    "i": 2,
    "a": 4,
    "o": 6,
    "r": 8,
    "n": 10,
    "t": 12,
    "s": 14,
    "l": 16,
    "c": 18,
    "u": 20,
    "p": 22,
    "m": 24,
    "d": 26,
    "h": 28,
    "y": 30,
    "g": 32,
    "b": 34,
    "f": 36,
    "v": 38,
    "k": 40,
    "w": 42,
    "z": 44,
    "x": 46,
    "q": 48,
    "j": 50,
}

letter_sigs = {
    "a": 1789368711,
    "b": 3146859322,
    "c": 43676229,
    "d": 3522623596,
    "e": 3544234957,
    "f": 3448207591,
    "g": 1282648386,
    "h": 3672791226,
    "i": 1582316135,
    "j": 4001984784,
    "k": 831769172,
    "l": 1160692746,
    "m": 2430986565,
    "n": 1873586768,
    "o": 694443915,
    "p": 1602297017,
    "q": 533722196,
    "r": 3754550193,
    "s": 1859447115,
    "t": 1121373020,
    "u": 2414108708,
    "v": 2693866766,
    "w": 748799881,
    "x": 2627529228,
    "y": 2376066489,
    "z": 802338724,
}


class Unscrambler(object):
    """A class that unscrambles words quickly by computing a signature
    (sig) for the word based on its position independent letter
    population and then using a pregenerated index to look up known
    words the same set of letters.

    Sigs are designed to cluster similar words near each other so both
    lookup methods support a "fuzzy match" argument that can be set to
    request similar words that do not match exactly in addition to any
    exact matches.

    .. note::

        Each instance of Unscrambler caches its index to speed up
        lookups number 2..N; careless deletion / reinstantiation will
        suffer slower performance.
    """

    def __init__(self, indexfile: Optional[str] = None):
        """
        Constructs an unscrambler.

        Args:
            indexfile: overrides the default indexfile location if provided.
                To [re]generate the indexfile, see :meth:`repopulate`.
        """

        # Cached index per instance.
        self.sigs = []
        self.words = []

        filename = Unscrambler.get_indexfile(indexfile)
        with open(filename, "r") as rf:
            lines = rf.readlines()
        for line in lines:
            line = line[:-1]
            (fsig, word) = line.split("+")
            isig = int(fsig, 16)
            self.sigs.append(isig)
            self.words.append(word)

    @staticmethod
    def get_indexfile(indexfile: Optional[str]) -> str:
        """
        Returns:
            The current indexfile location
        """
        if indexfile is None:
            if "unscrambler_default_indexfile" in config.config:
                indexfile = config.config["unscrambler_default_indexfile"]
                assert isinstance(indexfile, str)
            else:
                indexfile = "/usr/share/dict/sparse_index"
        else:
            assert file_utils.is_readable(indexfile), f"Can't read {indexfile}"
        return indexfile

    # 52 bits
    @staticmethod
    def _compute_word_fingerprint(population: Mapping[str, int]) -> int:
        fp = 0
        for pair in sorted(population.items(), key=lambda x: x[1], reverse=True):
            letter = pair[0]
            if letter in fprint_feature_bit:
                count = min(pair[1], 3)
                shift = fprint_feature_bit[letter]
                s = count << shift
                fp |= s
        return fp << letters_bits

    # 32 bits
    @staticmethod
    def _compute_word_letter_sig(
        lsigs: Mapping[str, int],
        word: str,
        population: Mapping[str, int],
    ) -> int:
        sig = 0
        for pair in sorted(population.items(), key=lambda x: x[1], reverse=True):
            letter = pair[0]
            if letter not in lsigs:
                continue
            s = lsigs[letter]
            count = pair[1]
            if count > 1:
                s <<= count
                s |= count
            s &= letters_mask
            sig ^= s
        length = min(len(word), 31)
        sig ^= length << 8
        sig &= letters_mask
        return sig

    # 52 + 32 bits
    @staticmethod
    @decorator_utils.memoized
    def compute_word_sig(word: str) -> int:
        """Given a word, compute its signature for subsequent lookup
        operations.  Signatures are computed based on the letters in
        the word and their frequencies.  We try to cluster "similar"
        words close to each other in the signature space.

        Args:
            word: the word to compute a signature for

        Returns:
            The word's signature.

        >>> test = Unscrambler.compute_word_sig('test')
        >>> test
        105560478284788

        >>> teste = Unscrambler.compute_word_sig('teste')
        >>> teste
        105562386542095

        >>> teste - test
        1908257307

        """
        population = list_utils.population_counts(word)
        fprint = Unscrambler._compute_word_fingerprint(population)
        letter_sig = Unscrambler._compute_word_letter_sig(letter_sigs, word, population)
        assert fprint & letter_sig == 0
        sig = fprint | letter_sig
        return sig

    @staticmethod
    def repopulate(
        dictfile: str = "/usr/share/dict/words",
        indexfile: str = "/usr/share/dict/sparse_index",
    ) -> None:
        """
        Repopulates the indexfile.

        Args:
            dictfile: a file that contains one word per line
            indexfile: the file to populate with sig, word pairs for future use
                by this class.

        .. warning::

            Before calling this method, change `letter_sigs` from the
            default above unless you want to populate the same exact
            files.
        """
        words_by_sigs: Dict[int, str] = {}
        seen = set()
        with open(dictfile, "r") as f:
            for word in f:
                word = word.replace("\n", "")
                word = word.lower()
                sig = Unscrambler.compute_word_sig(word)
                logger.debug("%s => 0x%x", word, sig)
                if word in seen:
                    continue
                seen.add(word)
                if sig in words_by_sigs:
                    words_by_sigs[sig] += f",{word}"
                else:
                    words_by_sigs[sig] = word
        with open(indexfile, "w") as f:
            for sig in sorted(words_by_sigs.keys()):
                word = words_by_sigs[sig]
                print(f"0x{sig:x}+{word}", file=f)

    def lookup(self, word: str, *, window_size: int = 5) -> Dict[str, bool]:
        """Looks up a potentially scrambled word optionally including near
        "fuzzy" matches.

        Args:
            word: the word to lookup
            window_size: the number of nearby fuzzy matches to return

        Returns:
            A dict of word -> bool containing unscrambled words with (close
            to or precisely) the same letters as the input word.  The bool
            values in this dict indicate whether the key word is an exact
            or near match.  The count of entries in this dict is controlled
            by the window_size param.

        >>> u = Unscrambler()
        >>> u.lookup('eanycleocipd', window_size=0)
        {'encyclopedia': True}
        """
        sig = Unscrambler.compute_word_sig(word)
        return self.lookup_by_sig(sig, window_size=window_size)

    def lookup_by_sig(self, sig: int, *, window_size: int = 5) -> Dict[str, bool]:
        """Looks up a word that has already been translated into a signature by
        a previous call to Unscrambler.compute_word_sig.  Optionally returns
        near "fuzzy" matches.

        Args:
            sig: the signature of the word to lookup (see :meth:`compute_word_sig`
                to generate these signatures).
            window_size: the number of nearby fuzzy matches to return

        Returns:
            A dict of word -> bool containing unscrambled words with (close
            to or precisely) the same letters as the input word.  The bool
            values in this dict indicate whether the key word is an exact
            or near match.  The count of entries in this dict is controlled
            by the window_size param.

        >>> sig = Unscrambler.compute_word_sig('sunepsapetuargiarin')
        >>> sig
        18491949645300288339

        >>> u = Unscrambler()
        >>> u.lookup_by_sig(sig)
        {'pupigerous': False, 'pupigenous': False, 'unpurposing': False, 'superpurgation': False, 'unsupporting': False, 'superseptuaginarian': True, 'purpurogallin': False, 'scuppaug': False, 'purpurigenous': False, 'purpurogenous': False, 'proppage': False}
        """
        ret = {}
        (_, location) = list_utils.binary_search(self.sigs, sig)
        start = location - window_size
        start = max(start, 0)
        end = location + 1 + window_size
        end = min(end, len(self.words))

        for x in range(start, end):
            word = self.words[x]
            fsig = self.sigs[x]
            if window_size > 0 or (fsig == sig):
                ret[word] = fsig == sig
        return ret


if __name__ == "__main__":
    import doctest

    doctest.testmod()
