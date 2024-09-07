#!/usr/bin/env python3

"""
A (unix terminal)  stopwatch utility.
"""

import logging
import sys
import time

from pyutils import bootstrap, config, input_utils

logger = logging.getLogger(__name__)
args = config.add_commandline_args(f'({__file__})', f'Args related to {__file__}')
args.add_argument("--start", action="store_true", help="Start as soon as possible.")


class Stopwatch:
    def __init__(self):
        self.running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0

    def start(self):
        if not self.running:
            self.start_time = time.time()
            self.running = True

    def pause(self):
        if self.running:
            self.elapsed_time += time.time() - self.start_time
            self.running = False

    def reset(self):
        self.running = False
        self.start_time = 0
        self.elapsed_time = 0

    def get_elapsed_time(self) -> float:
        if self.running:
            return self.elapsed_time + time.time() - self.start_time
        else:
            return self.elapsed_time


@bootstrap.initialize
def main():
    print("Stopwatch...  [space]=stop/start, [l]ap, [r]eset, [q]uit (or ^C)")
    stopwatch = Stopwatch()
    if config.config["start"]:
        stopwatch.start()

    with input_utils.KeystrokeReader() as get_keystroke:
        while True:
            # Check / parse any keys.
            key = get_keystroke(timeout_seconds=0.01)
            if key:
                if key == ' ':
                    if not stopwatch.running:
                        stopwatch.start()
                    else:
                        stopwatch.pause()
                elif key == 'r':
                    print(" " * 50, end='\r')
                    stopwatch.reset()
                elif key == 'l':
                    print(f"Lap: {stopwatch.get_elapsed_time():.5f}", end="\r\n")
                elif key == 'q' or key == chr(3):
                    print()
                    return

            # Update display.
            print(f"Elapsed time: {stopwatch.get_elapsed_time():0.4f}", end="\r")
            sys.stdout.flush()
    return None


if __name__ == "__main__":
    main()
