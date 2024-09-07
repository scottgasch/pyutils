#!/usr/bin/env python3

"""
A (unix terminal) countdown timer utility.
"""

import logging
import sys
import time
from typing import Optional

from pyutils import argparse_utils, bootstrap, config, input_utils

logger = logging.getLogger(__name__)
args = config.add_commandline_args(f'({__file__})', f'Args related to {__file__}')
args.add_argument(
    "time_limit",
    type=argparse_utils.valid_duration,
    help="The time limit of the countdown timer.",
)
args.add_argument(
    "--infinite",
    action="store_true",
    help="After the timer expires, reset and start again forever.",
)
args.add_argument(
    "--pause_between",
    action="store_true",
    help="Should we pause between adjacent timer runs.",
)


class Timer:
    def __init__(self, duration: float):
        self.running = True
        self.start = time.time()
        self.original_duration = duration
        self.duration = duration
        self.run_number = 1
        self.elapsed_before_pause = 0.0

    def get_remaining_time(self) -> float:
        return self.original_duration - self.get_elapsed_time()

    def get_elapsed_time(self) -> float:
        if self.running:
            now = time.time()
            return now - self.start + self.elapsed_before_pause
        else:
            return self.elapsed_before_pause

    def is_expired(self):
        elapsed = self.get_elapsed_time()
        return elapsed >= self.original_duration

    def reset(self):
        self.run_number += 1
        self.start = time.time()
        self.duration = self.original_duration
        self.elapsed_before_pause = 0
        self.running = True

    def reset_and_pause(self):
        self.run_number += 1
        self.start = time.time()
        self.duration = self.original_duration
        self.elapsed_before_pause = 0
        self.running = False

    def pause(self):
        self.elapsed_before_pause = self.get_elapsed_time()
        self.running = False

    def unpause(self):
        self.start = time.time()
        self.duration = self.original_duration - self.elapsed_before_pause
        self.running = True


@bootstrap.initialize
def main() -> Optional[int]:
    duration = config.config["time_limit"]
    timer = Timer(duration.seconds)
    print("Countdown timer... [space]=pause/unpause, [r]eset, [q]uit (or ^C).")

    with input_utils.KeystrokeReader() as get_keystroke:
        while True:

            # Check for input / parse any.
            key = get_keystroke(timeout_seconds=0.01)
            if key:
                if key == ' ':
                    if timer.running:
                        timer.pause()
                    else:
                        timer.unpause()
                elif key == 'r':
                    print(end="\r\n")
                    timer.reset()
                elif key == 'q' or key == chr(3):
                    sys.exit(0)

            # Display remaining countdown.
            remaining = timer.get_remaining_time()
            print(f"{remaining:0.2f}  ", end='\r')

            # Done?
            if timer.is_expired():
                if not config.config["infinite"]:
                    print("Beep, beep, beep!", end="\r\n")
                    sys.exit(0)

                print(
                    f"Run number {timer.run_number} expired... Beep, beep, beep!",
                    end="\r\n",
                )
                if config.config["pause_between"]:
                    timer.reset_and_pause()
                else:
                    timer.reset()
    return None


if __name__ == '__main__':
    main()
