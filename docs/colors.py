#!/usr/bin/env python3

"""
The start of something cool.
"""

import logging
import math
from typing import Optional, Tuple

from pyutils import ansi, bootstrap, config

logger = logging.getLogger(__name__)
args = config.add_commandline_args(f'({__file__})', f'Args related to {__file__}')


def rgb_to_hsv(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    r = rgb[0] / 255.0
    g = rgb[1] / 255.0
    b = rgb[2] / 255.0

    cmax = max(r, g, b)
    cmin = min(r, g, b)
    diff = cmax - cmin
    h = -1
    s = -1

    if cmax == cmin:
        h = 0
    elif cmax == r:
        h = math.fmod(60 * ((g - b) / diff) + 360, 360)
    elif cmax == g:
        h = math.fmod(60 * ((b - r) / diff) + 120, 360)
    elif cmax == b:
        h = math.fmod(60 * ((r - g) / diff) + 240, 360)

    if cmax == 0:
        s = 0
    else:
        s = (diff / cmax) * 100.0

    v = cmax * 100.0
    return (h, s, v)


def step(code, repetitions=1):
    r = code[0]
    g = code[1]
    b = code[2]
    lum = math.sqrt(0.241 * r + 0.691 * g + 0.068 * b)
    h, s, v = rgb_to_hsv(code)
    h2 = int(h * repetitions)
    lum2 = int(lum * repetitions)
    v2 = int(v * repetitions)
    if h2 % 2 == 1:
        v2 = repetitions - v2
        lum = repetitions - lum
    return (-h2, lum, v2)


def sort_value(code: Tuple[int, int, int]) -> int:
    lum = math.sqrt(0.241 * code[0] + 0.691 * code[1] + 0.068 * code[2])
    hsv = rgb_to_hsv(code)
    return lum * hsv[0] * hsv[1]


@bootstrap.initialize
def main() -> Optional[int]:
    colors = {}
    colors_to_code = {}
    for name, code in ansi.COLOR_NAMES_TO_RGB.items():
        colors_to_code[name] = code
        colors[name] = step(code, 8)

    print('    <TABLE><TR><TD></TD><TD></TD><TD></TD><TD></TD>')
    for n, name in enumerate(
        {k: v for k, v in sorted(colors.items(), key=lambda i: i[1])}
    ):
        if n % 4 == 0:
            print('    </TR><TR>')
        code = colors_to_code[name]
        contrast = ansi.pick_contrasting_color(None, code[0], code[1], code[2])
        code = code[0] << 16 | code[1] << 8 | code[2]
        code = f'{code:06X}'
        contrast = contrast[0] << 16 | contrast[1] << 8 | contrast[2]
        contrast = f'{contrast:06X}'

        print(
            f"    <TD BGCOLOR='{code}'><FONT COLOR='{contrast}'><CENTER>{name} (0x{code})</CENTER></FONT></TD>"
        )
    return None


if __name__ == '__main__':
    main()
