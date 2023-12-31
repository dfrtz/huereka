#! /usr/bin/env python

"""Huereka RGB LED tester."""

import argparse
import time

import board
import microcontroller

from huereka.common import color_utils
from huereka.common import led_manager
from huereka.common.led_manager import micro_managers


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description="Perform basic RGB LED color test.")
    parser.add_argument(
        "length",
        type=int,
        help="Length of the LED strand.",
    )
    parser.add_argument(
        "-b",
        "--brightness",
        type=float,
        default=1.0,
        help="Brightness of the LEDs. Ignored if fade is enabled.",
    )
    parser.add_argument(
        "-c",
        "--colors",
        type=color_utils.parse_color,
        nargs="+",
        default=(0xFFFFFF, 0xFF0000, 0x00FF00, 0x0000FF),
        help="Colors to display. One color per LED in strand.",
    )
    parser.add_argument(
        "-p",
        "--pin",
        type=int,
        default=board.D18.id,
        help="Colors to display. One color per LED in strand.",
    )
    parser.add_argument(
        "-f",
        "--fade",
        action="store_true",
        help="Fade of brightness down to 0, and then back to 1, repeatedly.",
    )
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic LED test."""
    args = parse_args()

    colors = color_utils.generate_pattern(args.colors, args.length)
    if len(colors) < 1:
        return

    pin = microcontroller.Pin(args.pin)
    manager = led_manager.LEDManager(
        mode=led_manager.MODE_ON,
        micromanager=micro_managers.NeoPixelManager(led_count=len(colors), pin=pin),
    )
    uuid = manager.uuid
    led_manager.LEDManagers.register(manager)
    print(f"Testing {len(colors)} LEDs. Press CTRL+C to stop...")
    brightness = 1.0 if args.fade else args.brightness
    brightness = max(0.0, min(1.0, brightness))
    try:
        for index, color in enumerate(colors):
            led_manager.LEDManagers.set_color(uuid, color, index=index, show=False)
        led_manager.LEDManagers.set_brightness(uuid, brightness)
        led_manager.LEDManagers.show(uuid)
        decreasing = True
        while True:
            if args.fade:
                time.sleep(0.033)
                led_manager.LEDManagers.set_brightness(uuid, brightness)
                led_manager.LEDManagers.show(uuid)
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
        led_manager.LEDManagers.teardown()


if __name__ == "__main__":
    main()
