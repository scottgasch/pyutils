#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# © Copyright 2021-2023, Scott Gasch

"""
Utilities for dealing with and creating text chunks.  For example:

    - Make a bar graph / progress graph,
    - make a spark line,
    - left, right, center, justify text,
    - word wrap text,
    - indent / dedent text,
    - create a header line,
    - draw a box around some text.

"""

import contextlib
import enum
import logging
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Generator, List, Literal, Optional, Tuple, Union

from pyutils import string_utils
from pyutils.ansi import fg, reset

logger = logging.getLogger(__file__)


@dataclass
class RowsColumns:
    """Row + Column"""

    rows: int = 0
    """Numer of rows"""

    columns: int = 0
    """Number of columns"""


def get_console_rows_columns() -> RowsColumns:
    """
    Returns:
        The number of rows/columns on the current console or None
        if we can't tell or an error occurred.
    """
    from pyutils.exec_utils import cmd

    rows: Union[Optional[str], int] = os.environ.get("LINES", None)
    cols: Union[Optional[str], int] = os.environ.get("COLUMNS", None)
    if not rows or not cols:
        try:
            size = os.get_terminal_size()
            rows = size.lines
            cols = size.columns
        except Exception:
            rows = None
            cols = None

    if not rows or not cols:
        logger.debug("Rows: %s, cols: %s, trying stty.", rows, cols)
        try:
            rows, cols = cmd(
                "stty size",
                timeout_seconds=1.0,
            ).split()
        except Exception:
            rows = None
            cols = None

    if not rows or not cols:
        raise Exception("Can't determine console size?!")
    return RowsColumns(int(rows), int(cols))


class BarGraphText(enum.Enum):
    """What kind of text to include at the end of the bar graph?"""

    NONE = (0,)
    """None, leave it blank."""

    PERCENTAGE = (1,)
    """XX.X%"""

    FRACTION = (2,)
    """N / K"""


def bar_graph(
    current: int,
    total: int,
    *,
    width: int = 70,
    text: BarGraphText = BarGraphText.PERCENTAGE,
    fgcolor: str = fg("school bus yellow"),
    left_end: str = "[",
    right_end: str = "]",
    redraw: bool = True,
) -> None:
    """Draws a progress graph at the current cursor position.

    Args:
        current: how many have we done so far?
        total: how many are there to do total?
        text: how should we render the text at the end?
        width: how many columns wide should be progress graph be?
        fgcolor: what color should "done" part of the graph be?
        left_end: the character at the left side of the graph
        right_end: the character at the right side of the graph
        redraw: if True, omit a line feed after the carriage return
            so that subsequent calls to this method redraw the graph
            iteratively.

    See also :meth:`bar_graph_string`, :meth:`sparkline`.

    Example::

        '[███████████████████████████████████                                   ] 0.5'

    """
    ret = "\r" if redraw else "\n"
    bar = bar_graph_string(
        current,
        total,
        text=text,
        width=width,
        fgcolor=fgcolor,
        left_end=left_end,
        right_end=right_end,
    )
    print(bar, end=ret, flush=True, file=sys.stderr)


def _make_bar_graph_text(
    text: BarGraphText, current: int, total: int, percentage: float
):
    if text == BarGraphText.NONE:
        return ""
    elif text == BarGraphText.PERCENTAGE:
        return f"{percentage:.1f}"
    elif text == BarGraphText.FRACTION:
        return f"{current} / {total}"
    raise ValueError(text)


def bar_graph_string(
    current: int,
    total: int,
    *,
    text: BarGraphText = BarGraphText.PERCENTAGE,
    width: int = 70,
    fgcolor: str = fg("school bus yellow"),
    reset_seq: str = reset(),
    left_end: str = "[",
    right_end: str = "]",
) -> str:
    """Returns a string containing a bar graph.

    Args:
        current: how many have we done so far?
        total: how many are there to do total?
        text: how should we render the text at the end?
        width: how many columns wide should be progress graph be?
        fgcolor: what color should "done" part of the graph be?
        reset_seq: sequence to use to turn off color
        left_end: the character at the left side of the graph
        right_end: the character at the right side of the graph

    See also :meth:`bar_graph`, :meth:`sparkline`.

    >>> bar_graph_string(5, 10, fgcolor='', reset_seq='')
    '[███████████████████████████████████                                   ] 0.5'

    """

    if total != 0:
        percentage = float(current) / float(total)
    else:
        percentage = 0.0
    if percentage < 0.0 or percentage > 1.0:
        raise ValueError(percentage)
    txt = _make_bar_graph_text(text, current, total, percentage)
    whole_width = math.floor(percentage * width)
    if whole_width == width:
        whole_width -= 1
        part_char = "▉"
    elif whole_width == 0 and percentage > 0.0:
        part_char = "▏"
    else:
        remainder_width = (percentage * width) % 1
        part_width = math.floor(remainder_width * 8)
        part_char = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"][part_width]
    return (
        left_end
        + fgcolor
        + "█" * whole_width
        + part_char
        + " " * (width - whole_width - 1)
        + reset_seq
        + right_end
        + " "
        + txt
    )


def sparkline(numbers: List[float]) -> Tuple[float, float, str]:
    """
    Makes a "sparkline" little inline histogram graph.  Auto scales.

    Args:
        numbers: the population over which to create the sparkline

    Returns:
        a three tuple containing:

        * the minimum number in the population
        * the maximum number in the population
        * a string representation of the population in a concise format

    See also :meth:`bar_graph`, :meth:`bar_graph_string`.

    >>> sparkline([1, 2, 3, 5, 10, 3, 5, 7])
    (1, 10, '▁▁▂▄█▂▄▆')

    >>> sparkline([104, 99, 93, 96, 82, 77, 85, 73])
    (73, 104, '█▇▆▆▃▂▄▁')

    """
    _bar = "▁▂▃▄▅▆▇█"  # Unicode: 9601, 9602, 9603, 9604, 9605, 9606, 9607, 9608

    barcount = len(_bar)
    min_num, max_num = min(numbers), max(numbers)
    span = max_num - min_num
    sline = "".join(
        _bar[min([barcount - 1, int((n - min_num) / span * barcount)])] for n in numbers
    )
    return min_num, max_num, sline


def distribute_strings(
    strings: List[str],
    *,
    width: int = 80,
    padding: str = " ",
) -> str:
    """
    Distributes strings into a line for justified text.

    Args:
        strings: a list of string tokens to distribute
        width: the width of the line to create
        padding: the padding character to place between string chunks

    Returns:
        The distributed, justified string.

    See also :meth:`justify_string`, :meth:`justify_text`.

    >>> distribute_strings(['this', 'is', 'a', 'test'], width=40)
    '      this      is      a      test     '
    """
    ret = " " + " ".join(strings) + " "
    assert len(string_utils.strip_ansi_sequences(ret)) < width
    x = 0
    while len(string_utils.strip_ansi_sequences(ret)) < width:
        spaces = [m.start() for m in re.finditer(r" ([^ ]|$)", ret)]
        where = spaces[x]
        before = ret[:where]
        after = ret[where:]
        ret = before + padding + after
        x += 1
        if x >= len(spaces):
            x = 0
    return ret


def _justify_string_by_chunk(string: str, width: int = 80, padding: str = " ") -> str:
    """
    Justifies a string chunk by chunk.

    Args:
        string: the string to be justified
        width: how wide to make the output
        padding: what padding character to use between chunks

    Returns:
        the justified string

    >>> _justify_string_by_chunk("This is a test", 40)
    'This          is          a         test'
    >>> _justify_string_by_chunk("This is a test", 20)
    'This   is   a   test'

    """
    assert len(string_utils.strip_ansi_sequences(string)) <= width
    padding = padding[0]
    first, *rest, last = string.split()
    w = width - (
        len(string_utils.strip_ansi_sequences(first))
        + len(string_utils.strip_ansi_sequences(last))
    )
    ret = first + distribute_strings(rest, width=w, padding=padding) + last
    return ret


def justify_string(
    string: str, *, width: int = 80, alignment: str = "c", padding: str = " "
) -> str:
    """Justify a string to width with left, right, center of justified
    alignment.

    Args:
        string: the string to justify
        width: the width to justify the string to
        alignment: a single character indicating the desired alignment:
            * 'c' = centered within the width
            * 'j' = justified at width
            * 'l' = left alignment
            * 'r' = right alignment
        padding: the padding character to use while justifying

    >>> justify_string('This is another test', width=40, alignment='c')
    '          This is another test          '
    >>> justify_string('This is another test', width=40, alignment='l')
    'This is another test                    '
    >>> justify_string('This is another test', width=40, alignment='r')
    '                    This is another test'
    >>> justify_string('This is another test', width=40, alignment='j')
    'This        is        another       test'
    """
    alignment = alignment[0]
    padding = padding[0]
    while len(string_utils.strip_ansi_sequences(string)) < width:
        if alignment == "l":
            string += padding
        elif alignment == "r":
            string = padding + string
        elif alignment == "j":
            return _justify_string_by_chunk(string, width=width, padding=padding)
        elif alignment == "c":
            if len(string) % 2 == 0:
                string += padding
            else:
                string = padding + string
        else:
            raise ValueError
    return string


def justify_text(
    text: str, *, width: int = 80, alignment: str = "c", indent_by: int = 0
) -> str:
    """Justifies text with left, right, centered or justified alignment
    and optionally with initial indentation.

    Args:
        text: the text to be justified
        width: the width at which to justify text
        alignment: a single character indicating the desired alignment:
            * 'c' = centered within the width
            * 'j' = justified at width
            * 'l' = left alignment
            * 'r' = right alignment
        indent_by: if non-zero, adds n prefix spaces to indent the text.

    Returns:
        The justified text.

    See also :meth:`justify_text`.

    >>> justify_text('This is a test of the emergency broadcast system.  This is only a test.',
    ...              width=40, alignment='j')  #doctest: +NORMALIZE_WHITESPACE
    'This  is    a  test  of   the  emergency\\nbroadcast system. This is only a test.'

    """
    retval = ""
    indent = ""
    if indent_by > 0:
        indent += " " * indent_by
    line = indent

    for word in text.split():
        if (
            len(string_utils.strip_ansi_sequences(line))
            + len(string_utils.strip_ansi_sequences(word))
        ) > width:
            line = line[1:]
            line = justify_string(line, width=width, alignment=alignment)
            retval = retval + "\n" + line
            line = indent
        line = line + " " + word
    if len(string_utils.strip_ansi_sequences(line)) > 0:
        if alignment != "j":
            retval += "\n" + justify_string(line[1:], width=width, alignment=alignment)
        else:
            retval += "\n" + line[1:]
    return retval[1:]


def generate_padded_columns(text: List[str]) -> Generator:
    """Given a list of strings, break them into columns using :meth:`split`
    and then compute the maximum width of each column.  Finally,
    distribute the columular chunks into the output padding each to
    the proper width.

    Args:
        text: a list of strings to chunk into padded columns

    Returns:
        padded columns based on text.split()

    >>> for x in generate_padded_columns(
    ...     [ 'reading writing arithmetic',
    ...       'mathematics psychology physics',
    ...       'communications sociology anthropology' ]):
    ...     print(x.strip())
    reading        writing    arithmetic
    mathematics    psychology physics
    communications sociology  anthropology
    """
    max_width: Dict[int, int] = defaultdict(int)
    for line in text:
        for pos, word in enumerate(line.split()):
            max_width[pos] = max(
                max_width[pos], len(string_utils.strip_ansi_sequences(word))
            )

    for line in text:
        out = ""
        for pos, word in enumerate(line.split()):
            width = max_width[pos]
            word = justify_string(word, width=width, alignment="l")
            out += f"{word} "
        yield out


def wrap_string(text: str, n: int) -> str:
    """
    Args:
        text: the string to be wrapped
        n: the width after which to wrap text

    Returns:
        The wrapped form of text
    """
    chunks = text.split()
    out = ""
    width = 0
    for chunk in chunks:
        if width + len(string_utils.strip_ansi_sequences(chunk)) > n:
            out += "\n"
            width = 0
        out += chunk + " "
        width += len(string_utils.strip_ansi_sequences(chunk)) + 1
    return out


class Indenter(contextlib.AbstractContextManager):
    """
    Context manager that indents stuff (even recursively).  e.g.::

        with Indenter(pad_count = 8) as i:
            i.print('test')
            with i:
                i.print('-ing')
                with i:
                    i.print('1, 2, 3')

    Yields::

        test
                -ing
                        1, 2, 3
    """

    def __init__(
        self,
        *,
        pad_prefix: Optional[str] = None,
        pad_char: str = " ",
        pad_count: int = 4,
    ):
        """Construct an Indenter.

        Args:
            pad_prefix: an optional prefix to prepend to each line
            pad_char: the character used to indent
            pad_count: the number of pad_chars to use to indent
        """
        self.level = -1
        if pad_prefix is not None:
            self.pad_prefix = pad_prefix
        else:
            self.pad_prefix = ""
        self.padding = pad_char * pad_count

    def __enter__(self):
        self.level += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> Literal[False]:
        self.level -= 1
        if self.level < -1:
            self.level = -1
        return False

    def print(self, *arg, **kwargs):
        text = string_utils._sprintf(*arg, **kwargs)
        print(self.pad_prefix + self.padding * self.level + text, end="")


def header(
    title: str,
    *,
    width: Optional[int] = None,
    align: Optional[str] = None,
    style: Optional[str] = "solid",
    color: Optional[str] = None,
):
    """
    Creates a nice header line with a title.

    Args:
        title: the title
        width: how wide to make the header
        align: "left" or "right"
        style: "ascii", "solid" or "dashed"
        color: what color to use, if any

    Returns:
        The header as a string.

    >>> header('title', width=60, style='ascii')
    '----[ title ]-----------------------------------------------'
    """
    if not width:
        try:
            width = get_console_rows_columns().columns
        except Exception:
            width = 80
    if not align:
        align = "left"
    if not style:
        style = "ascii"

    text_len = len(string_utils.strip_ansi_sequences(title))
    if align == "left":
        left = 4
        right = width - (left + text_len + 4)
    elif align == "right":
        right = 4
        left = width - (right + text_len + 4)
    else:
        left = int((width - (text_len + 4)) / 2)
        right = left
        while left + text_len + 4 + right < width:
            right += 1

    if style == "solid":
        line_char = "━"
        begin = ""
        end = ""
    elif style == "dashed":
        line_char = "┅"
        begin = ""
        end = ""
    else:
        line_char = "-"
        begin = "["
        end = "]"
    if color:
        col = color
        reset_seq = reset()
    else:
        col = ""
        reset_seq = ""
    return (
        line_char * left
        + begin
        + col
        + " "
        + title
        + " "
        + reset_seq
        + end
        + line_char * right
    )


def box(
    title: Optional[str] = None,
    text: Optional[str] = None,
    *,
    width: int = 80,
    color: str = "",
) -> str:
    """
    Make a nice unicode box (optionally with color) around some text.

    Args:
        title: the title of the box
        text: the text in the box
        width: the box's width
        color: the box's color

    Returns:
        the box as a string

    See also :meth:`print_box`, :meth:`preformatted_box`.

    >>> print(box('title', 'this is some text', width=20).strip())
    ╭──────────────────╮
    │       title      │
    │                  │
    │ this is some     │
    │ text             │
    ╰──────────────────╯
    """
    assert width > 4
    if text is not None:
        text = justify_text(text, width=width - 4, alignment="l")
    return preformatted_box(title, text, width=width, color=color)


def preformatted_box(
    title: Optional[str] = None,
    text: Optional[str] = None,
    *,
    width: int = 80,
    color: str = "",
) -> str:
    """Creates a nice box with rounded corners and returns it as a string.

    Args:
        title: the title of the box
        text: the text inside the box
        width: the width of the box
        color: the box's color

    Returns:
        the box as a string

    See also :meth:`print_box`, :meth:`box`.

    >>> print(preformatted_box('title', 'this\\nis\\nsome\\ntext', width=20).strip())
    ╭──────────────────╮
    │       title      │
    │                  │
    │ this             │
    │ is               │
    │ some             │
    │ text             │
    ╰──────────────────╯
    """
    assert width > 4
    ret = ""
    if color == "":
        rset = ""
    else:
        rset = reset()
    w = width - 2
    ret += color + "╭" + "─" * w + "╮" + rset + "\n"
    if title is not None:
        ret += (
            color
            + "│"
            + rset
            + justify_string(title, width=w, alignment="c")
            + color
            + "│"
            + rset
            + "\n"
        )
        ret += color + "│" + " " * w + "│" + rset + "\n"
    if text is not None:
        for line in text.split("\n"):
            tw = len(string_utils.strip_ansi_sequences(line))
            assert tw <= w
            ret += (
                color
                + "│ "
                + rset
                + line
                + " " * (w - tw - 2)
                + color
                + " │"
                + rset
                + "\n"
            )
    ret += color + "╰" + "─" * w + "╯" + rset + "\n"
    return ret


def print_box(
    title: Optional[str] = None,
    text: Optional[str] = None,
    *,
    width: int = 80,
    color: str = "",
) -> None:
    """Draws a box with nice rounded corners.

    Args:
        title: the title of the box
        text: the text inside the box
        width: the width of the box
        color: the box's color

    Returns:
        None

    Side-effects:
        Prints a box with your text on the console to sys.stdout.

    See also :meth:`preformatted_box`, :meth:`box`.

    >>> print_box('Title', 'This is text', width=30)
    ╭────────────────────────────╮
    │            Title           │
    │                            │
    │ This is text               │
    ╰────────────────────────────╯

    >>> print_box(None, 'OK', width=6)
    ╭────╮
    │ OK │
    ╰────╯
    """
    print(preformatted_box(title, text, width=width, color=color), end="")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
