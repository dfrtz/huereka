#! /usr/bin/env python

"""Huereka GPIO tester."""

import argparse
import time

from RPi import GPIO  # pylint: disable=import-error


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description="Perform basic GPIO power on and off tests.")
    parser.add_argument(
        "-p",
        "--pin",
        type=int,
        default=18,
        help="Test a specific GPIO pin. Defaults to GPIO18.",
    )
    parser.add_argument(
        "--off",
        type=float,
        default=1.0,
        help="Delay between on to off state changes. Default: 1 second",
    )
    parser.add_argument(
        "--on",
        type=float,
        default=1.0,
        help="Delay between off to on state changes. Default: 1 second",
    )
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic GPIO test."""
    args = parse_args()
    pin = args.pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([pin], GPIO.OUT)
    print(f"Testing GPIO pin {pin}. Press CTRL+C to stop...")
    try:
        while True:
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(args.off)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(args.on)
    except KeyboardInterrupt:
        print()
    finally:
        GPIO.output(pin, GPIO.LOW)


if __name__ == "__main__":
    main()
