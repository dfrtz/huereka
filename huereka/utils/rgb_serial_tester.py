#!/usr/bin/env python3

"""Huereka Serial RGB LED tester."""

import argparse
import logging
import time

from huereka.common import color_utils
from huereka.common import micro_managers


def console(
    port: str = "/dev/ttyACM0",
    baudrate: int = 115200,
    pin: int = 5,
    led_count: int = 100,
) -> None:
    """Send manually encoded messages to a serial manager.

    Args:
        port: Location of the serial port to connect to.
        baudrate: Speed of the serial connection. Must match the configuration of the serial device.
        pin: GPIO pin on the serial device to use to send the signal.
        led_count: How many LEDs are on the strip of lights.
    """
    manager = micro_managers.SerialManager(port=port, baudrate=baudrate, pin=pin, led_count=led_count)
    serial = manager._serial  # Allow direct access for simple testing. pylint: disable=protected-access
    serial.reset_input_buffer()
    serial.reset_output_buffer()
    while True:
        message = input("Enter message to be transmitted as bytes:")
        data = b""
        for character in message.split():
            data += int(character).to_bytes(length=1, byteorder="little", signed=False)
        serial.write(data)
        logging.info(f"Sending {data}")


def rotate_colors(  # Allow full control over setup and run time loop. pylint: disable=too-many-arguments
    *,
    port: str = "/dev/ttyACM0",
    baudrate: int = 115200,
    pin: int = 5,
    led_count: int = 100,
    colors: list[int] = None,
    brightness: float = 0.25,
    delay: float = 0.01,
    max_cycles: int = 0,
) -> None:
    """Test LEDs by sending a rapid rotation of colors repeatedly.

    Args:
        port: Location of the serial port to connect to.
        baudrate: Speed of the serial connection. Must match the configuration of the serial device.
        pin: GPIO pin on the serial device to use to send the signal.
        led_count: How many LEDs are on the strip of lights.
        colors: Colors to display in rotation across LEDs.
        brightness: Initial brightness level to set.
        delay: Delay between sending LED updates to serial device in seconds.
        max_cycles: Maximum number of full color test cycles to perform before exit.
    """
    logging.info(f"Starting tests for {led_count} LEDs on pin {pin} with a {delay}s delay")
    manager = micro_managers.SerialManager(port=port, baudrate=baudrate, pin=pin, led_count=led_count)
    # Allow some time to set up before sending.
    time.sleep(2)

    colors = colors or [0xFF0000, 0x00FF00, 0x0000FF]
    cycle_count = 0
    msg_count = 0
    start = time.time()
    color_index = 0
    try:
        index = 0
        manager.set_brightness(brightness)
        while True:
            if max_cycles and cycle_count > max_cycles:
                break
            if index == 0:
                logging.info(
                    f"Starting new cycle for color {color_index} #{hex(colors[color_index]).removeprefix('0x').zfill(6)}"
                )

            manager.set_color(colors[color_index], index=index, show=True)
            index += 1
            if index == led_count:
                index = 0
                color_index += 1
                if color_index == len(colors):
                    color_index = 0
                    cycle_count += 1

            msg_count += 1
            time.sleep(delay)
    except KeyboardInterrupt:
        logging.info(f"Sent {msg_count} messages to serial device in {time.time() - start} seconds")
    finally:
        manager.teardown()


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description="Perform basic RGB LED color test on serial device.")
    parser.add_argument(
        "-l",
        "--length",
        dest="led_count",
        type=int,
        default=100,
        help="LED count of the strip connected to the serial device.",
    )
    parser.add_argument(
        "-p",
        "--pin",
        type=int,
        default=5,
        help="Data pin the strip is connected to on the serial device.",
    )
    parser.add_argument(
        "-c",
        "--colors",
        type=color_utils.parse_color,
        nargs="+",
        default=(0xFF0000, 0x00FF00, 0x0000FF),
        help="Colors to display. One color per LED in strand.",
    )
    parser.add_argument(
        "-b",
        "--brightness",
        type=float,
        default=0.25,
        help="Initial brightness level to set.",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0.01,
        help="Delay between sending LED updates to serial device in seconds.",
    )
    parser.add_argument(
        "-m",
        "--max-cycles",
        type=int,
        default=0,
        help="Maximum number of full color test cycles to perform before exit.",
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyACM0",
        help="Location of the serial port to connect to.",
    )
    parser.add_argument(
        "--baud",
        default=115200,
        help="Speed of the serial connection. Must match the configuration of the serial device.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Enter a console to send manual messages, instead of automated color loop animation.",
    )
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic serial LED test."""
    args = parse_args()
    if args.cli:
        console(
            port=args.port,
            baudrate=args.baud,
            pin=args.pin,
            led_count=args.led_count,
        )
    else:
        rotate_colors(
            port=args.port,
            baudrate=args.baud,
            pin=args.pin,
            led_count=args.led_count,
            colors=args.colors,
            brightness=args.brightness,
            delay=args.delay,
        )


if __name__ == "__main__":
    main()
