#! /usr/bin/env python

"""Huereka UART serial communication loopback tester."""

import argparse

import serial


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser(description="Perform basic UART loopback test.")
    parser.add_argument(
        "message",
        default="Hello World, nice to meet you!",
        help="Message to be sent on TX, and expected to be received on RX.",
    )
    parser.add_argument(
        "-p",
        "--ports",
        nargs="*",
        default=["/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0"],
        help="Ports to test. Defaults to /dev/serial0, /dev/ttyS0, and /dev/ttyAMA0.",
    )
    parser.add_argument(
        "--baud",
        default=9600,
        help="Speed of the serial connection. Must match the configuration of the serial device.",
    )
    args = parser.parse_args()
    return args


def main() -> None:
    """Perform basic UART test."""
    args = parse_args()
    for port in args.ports:
        print(f"Testing port: {port}")
        try:
            serial_port = serial.Serial(port, args.baud, timeout=2)
            bytes_sent = serial_port.write(args.message.encode())
            print(f"Sent {bytes_sent} bytes.")
            response = serial_port.read(bytes_sent).decode("utf-8")
            if response == args.message:
                print(f"PASS: Received {len(response)} bytes.\n")
            else:
                print(f"FAIL: Received {len(response)} bytes, expected {bytes_sent}. Response: {response}\n")
            serial_port.close()
        except Exception as error:  # pylint: disable=broad-except
            print(f"FAIL: Test error: {error}\n")


if __name__ == "__main__":
    main()
