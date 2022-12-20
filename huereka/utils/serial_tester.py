#!/usr/bin/env python3

"""Huereka Serial Micro Manager tester."""

import argparse
import time

from huereka.lib import color_utils
from huereka.lib import micro_managers


def console(
        port: str = '/dev/ttyACM0',
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
        message = input('Enter message to be transmitted as bytes:')
        data = b''
        for character in message.split():
            data += int(character).to_bytes(length=1, byteorder='little', signed=False)
        serial.write(data)
        print('Sending', data)


def rotate_colors(
        port: str = '/dev/ttyACM0',
        baudrate: int = 115200,
        pin: int = 5,
        led_count: int = 100,
        colors: list[int] = None,
) -> None:
    """Test LEDs by sending a rapid rotation of colors repeatedly.

    Args:
        port: Location of the serial port to connect to.
        baudrate: Speed of the serial connection. Must match the configuration of the serial device.
        pin: GPIO pin on the serial device to use to send the signal.
        led_count: How many LEDs are on the strip of lights.
        colors: Colors to display in rotation across LEDs.
    """
    manager = micro_managers.SerialManager(port=port, baudrate=baudrate, pin=pin, led_count=led_count)
    # Allow some time to set up before sending.
    time.sleep(2)

    colors = colors or [0xff0000, 0x00ff00, 0x0000ff]
    color_count = len(colors)
    count = 0
    start = time.time()
    try:
        brightness = 1.0
        decreasing = False
        index = 0
        manager.set_brightness(.3)
        while True:
            if index == 0:
                count += 1
                manager.fill(0)
                time.sleep(.01)

            # Delay the updates to just under 100 FPS to reduce likelihood of serial communications
            # nuances impacting overall test (such as signal scrambling colors).
            time.sleep(.0105)
            manager.set_color(colors[index % color_count], index=index, show=True)
            index = 0 if index == led_count - 1 else index + 1

            brightness = brightness - (0.05 if decreasing else -0.05)
            if brightness < 0:
                brightness = 0
                decreasing = False
            elif brightness > 1:
                brightness = 1
                decreasing = True
            count += 1
    except KeyboardInterrupt:
        print('Sent', count, 'messages to serial device in', time.time() - start, 'seconds')


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description='Perform basic LED color test on serial device.')
    parser.add_argument('-l', '--length', dest='led_count', type=int, default=100,
                        help='LED count of the strip connected to the serial device.')
    parser.add_argument('-p', '--pin', type=int, default=5,
                        help='Data pin the strip is connected to on the serial device.')
    parser.add_argument('-c', '--colors', type=color_utils.parse_color, nargs='+',
                        default=(0xff0000, 0x00ff00, 0x0000ff),
                        help='Colors to display. One color per LED in strand.')
    parser.add_argument('--cli', action='store_true', default=100,
                        help='Enter a console to send manual messages, instead of automated color loop animation.')
    parser.add_argument('--port', default='/dev/ttyACM0',
                        help='Location of the serial port to connect to.')
    parser.add_argument('--baud', default=115200,
                        help='Speed of the serial connection. Must match the configuration of the serial device.')
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
        )


if __name__ == '__main__':
    rotate_colors()
