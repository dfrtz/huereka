#! /usr/bin/env python

"""Huereka LED tester."""

import argparse
import time

import board
import microcontroller

from huereka.lib import color_utils
from huereka.lib.led_manager import LEDManager
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
    parser.add_argument('-p', '--pin', type=int, default=board.D18.id,
                        help='Colors to display. One color per LED in strand.')
    parser.add_argument('-f', '--fade', action='store_true',
                        help='Fade of brightness down to 0, and then back to 1, repeatedly.')
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic LED test."""
    args = parse_args()

    colors = color_utils.generate_pattern(args.colors, args.length)
    if len(colors) < 1:
        return

    pin = microcontroller.Pin(args.pin)
    LEDManagers.register(LEDManager(led_count=len(colors), pin=pin))
    print(f'Testing {len(colors)} LEDs. Press CTRL+C to stop...')
    try:
        for index, color in enumerate(colors):
            LEDManagers.set_color(color, index=index, show=False, pin=pin)
        LEDManagers.show(pin=pin)
        brightness = 1.0
        decreasing = True
        while True:
            if args.fade:
                time.sleep(.033)
                LEDManagers.set_brightness(brightness, pin=pin)
                LEDManagers.show(pin=pin)
                brightness = brightness - (0.05 if decreasing else -0.05)
                if brightness < 0:
                    brightness = 0
                    decreasing = False
                elif brightness > 1:
                    brightness = 1
                    decreasing = True
            else:
                time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        LEDManagers.teardown()


if __name__ == '__main__':
    main()
