#! /usr/bin/env python

"""Huereka GPIO tester."""

import argparse
import time

from RPi import GPIO


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description='Perform basic GPIO power on and off tests.')
    parser.add_argument('-p', '--pin', type=int, default=18,
                        help='Test a specific GPIO pin. Defaults to GPIO18.')
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic GPIO test."""
    args = parse_args()
    pin = args.pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([pin], GPIO.OUT)
    print(f'Testing GPIO pin {pin}')
    try:
        while True:
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(1)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        GPIO.output(pin, GPIO.LOW)


if __name__ == '__main__':
    main()
