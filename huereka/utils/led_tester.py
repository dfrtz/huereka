#! /usr/bin/env python

"""Huereka LED tester."""

import argparse
import time

from huereka.lib import color_utils
from huereka.lib.led_manager import LEDManagers


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description='Perform basic LED color test.')
    parser.add_argument('length', type=int,
                        help='Length of the LED strand.')
    parser.add_argument('-c', '--colors', type=color_utils.parse_color, nargs='+',
                        default=(0xffffff, 0xff0000, 0x00ff00, 0x0000ff),
                        help='Colors to display. One color per LED in strand.')
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic LED test."""
    args = parse_args()

    colors = color_utils.generate_pattern(args.colors, args.length)
    if len(colors) < 1:
        return

    LEDManagers.create(led_count=len(colors))
    print(f'Testing {len(colors)} LEDs. Press CTRL+C to stop...')
    try:
        for index, color in enumerate(colors):
            LEDManagers.set_color(color, index=index, show=False)
        LEDManagers.show()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        LEDManagers.teardown()


if __name__ == '__main__':
    main()
