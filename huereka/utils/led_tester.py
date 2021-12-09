#! /usr/bin/env python

"""Huereka LED tester."""

import argparse
import time

from huereka.lib.led_manager import LEDManagers


def _int_helper(value: str) -> int:
    """Convert an int string as base 10 or base 16 into int."""
    if 'x' in value.lower():
        return int(value, base=16)
    return int(value)


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description='Perform basic LED color test.')
    parser.add_argument('length', type=int,
                        help='Length of the LED strand.')
    parser.add_argument('-c', '--colors', type=_int_helper, nargs='+', default=(0xffffff, 0xff0000, 0x00ff00, 0x0000ff),
                        help='Colors to display. One color per LED in strand.')
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic LED test."""
    args = parse_args()

    user_colors = args.colors
    colors = []
    current = 0
    for index in range(args.length):
        colors.append(user_colors[current])
        current += 1
        if current >= len(user_colors):
            current = 0
    if len(colors) < 1:
        return

    LEDManagers.create_manager(led_count=len(colors))
    print(f'Testing {len(colors)} LEDs. Press CTRL+C to stop...')
    try:
        for index, color in enumerate(colors):
            LEDManagers.set_color(index, color, show=False)
        LEDManagers.show()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        LEDManagers.teardown()


if __name__ == '__main__':
    main()
