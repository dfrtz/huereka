"""Manager for brightness and colors on an LED strip connected to a serial."""

from __future__ import annotations

import logging
import time

import math
import serial
import threading

from typing import Sequence

from adafruit_pixelbuf import ColorUnion

from huereka.lib import color_utils
from huereka.lib.collections import CollectionValueError
from huereka.lib.collections import get_and_validate
from huereka.lib.color_utils import Colors
from huereka.lib.micro_managers._manager_base import DEFAULT_LED_UPDATE_DELAY
from huereka.lib.micro_managers._manager_base import LEDMicroManager
from huereka.lib.micro_managers._manager_base import KEY_BRIGHTNESS
from huereka.lib.micro_managers._manager_base import KEY_LED_COUNT
from huereka.lib.micro_managers._manager_base import KEY_PIN
from huereka.lib.micro_managers._manager_base import KEY_TYPE

logger = logging.getLogger(__name__)

OP_MAGIC = int(127).to_bytes(length=1, byteorder='little', signed=False)

OP_INIT_STRIP = 1
OP_SET_BRIGHTNESS = 32
OP_FILL_LEDS = 33
OP_SET_LED = 34
OP_SHOW = 35
OP_TEST = 77
OP_RESET = 99

KEY_STRIP = 'strip'
KEY_PORT = 'port'
KEY_BAUD = 'baud'


class SerialManager(LEDMicroManager):
    """Manage the colors and brightness of LEDs connected to a GPIO pin on a device connected to a serial port."""

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
            self,
            led_count: int = 100,
            brightness: float = 1.0,
            strip: int = 0,
            pin: int = 5,
            port: str = '/dev/ttyACM0',
            baudrate: int = 115200,
            timeout: int = 10,
            dsrdtr: bool = False,
    ) -> None:
        """Set up a single FastLED strip.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            pixel_order: RGB/RGBW/etc ordering of the LEDs on each microcontroller.
            pin: GPIO pin to use to send the signal.
            manager_type: Type of LED manager to use on the backend. e.g. "NeoPixel"
            dsrdtr: Enable hardware (DSR/DTR) flow control.
        """
        super().__init__(brightness=brightness)
        self._ready = False
        self._pending = []
        self._colors = [Colors.BLACK.value for _ in range(led_count)]
        self.strip = strip
        self.pin = pin
        self.port = port
        self.baudrate = baudrate
        self._serial = serial.Serial(self.port, self.baudrate, timeout=timeout, dsrdtr=dsrdtr)
        # Delay startup by 1 second to prevent silent failures when it looks like the data sent.
        # All pending actions will be queued up to run as soon as available.
        threading.Timer(1, self._init).start()
        logger.info(f'Initialized LED manager for pin {self.pin} on {self.port}')

    def __getitem__(self, index: int | slice) -> int:
        """Find LED color at a specific LED position."""
        with self._lock:
            return self._colors[index]

    def __len__(self) -> int:
        """Number of controlled pixels."""
        return len(self._colors)

    def __setitem__(
            self,
            index: int | slice,
            color: Colors | ColorUnion | Sequence[ColorUnion],
    ) -> None:
        """Set color at a specific LED position."""
        color = color_utils.parse_color(color)
        with self._lock:
            if self._colors[index] != color:
                self._colors[index] = color
                self._op_set_led(index, color, show=False)

    def _init(self) -> None:
        """Send operation to set up LED strip.

        Should be called by new thread due to delay operations to prevent blocking.
        """
        with self._lock:
            self._ready = True
            self._op_init_strip()
            # Slight delay to ensure strip is ready before sending messages.
            time.sleep(.1)
            self._op_fill_leds(Colors.BLACK.value, show=True)
            for values, start in self._pending:
                self._write(*values, start=start)
                time.sleep(DEFAULT_LED_UPDATE_DELAY)

    def _op_init_strip(self) -> None:
        """Send operation to set up LED strip."""
        self._write(
            OP_INIT_STRIP,
            0,  # Placeholder for LED type.
            self.pin,
            len(self),
            0,  # No init animation.
        )

    def _op_fill_leds(self, color: Colors | ColorUnion | Sequence[ColorUnion], show: bool = True) -> None:
        """Send operation to fill entire LED strip with a single color."""
        color = color_utils.parse_color(color)
        self._write(
            OP_FILL_LEDS,
            self.strip,
            color.red,
            color.green,
            color.blue,
            1 if show else 0,
        )

    def _op_reset(self) -> None:
        """Force the remote device to hard reset."""
        self._write(
            OP_RESET,
        )

    def _op_set_brightness(self, brightness: float, show: bool = True) -> None:
        """Send operation to set brightness of entire LED strip."""
        self._write(
            OP_SET_BRIGHTNESS,
            self.strip,
            math.floor(255 * brightness),
            1 if show else 0,
        )

    def _op_set_led(self, pos: int, color: Colors | ColorUnion | Sequence[ColorUnion], show: bool = True) -> None:
        """Send operation to set color on a single LED."""
        color = color_utils.parse_color(color)
        self._write(
            OP_SET_LED,
            self.strip,
            pos,
            color.red,
            color.green,
            color.blue,
            1 if show else 0,
        )

    def _op_show(self) -> None:
        """Send operation to display all pending pixel changes since last show."""
        self._write(
            OP_SHOW,
            self.strip,
        )

    def _op_test(self, test: int) -> None:
        """Send operation to run a test animation on the strip."""
        self._write(
            OP_TEST,
            self.strip,
            test,
        )

    def _set_color(
            self,
            index: int,
            color: Colors | ColorUnion,
            show: bool = True,
    ) -> bool:
        """Set color at a specific LED position, show change, and return true if color was changed.

        Override of base to combine show with set.
        """
        changed = False
        color = color_utils.parse_color(color)
        with self._lock:
            if self._colors[index] != color:
                changed = True
                self._colors[index] = color
                self._op_set_led(index, color, show=show)
        return changed

    def _write(self, *values: int, start: bool = True) -> None:
        """Write out a set of values to the serial connection."""
        if not self._ready:
            self._pending.append((values, start))
            return
        if start:
            msg = OP_MAGIC
        else:
            msg = b''
        for value in values:
            msg += value.to_bytes(length=1, byteorder='little', signed=False)
        self._serial.write(msg)

    def fill(
            self,
            color: Colors | ColorUnion,
            show: bool = True,
    ) -> None:
        """Fill entire strip with a single color."""
        color = color_utils.parse_color(color)
        with self._lock:
            self._colors = [color for _ in self._colors]
            self._op_fill_leds(color, show=show)

    @classmethod
    def from_json(cls, data: dict) -> SerialManager:
        """Convert JSON type into manager instance."""
        # Required arguments.
        led_count = data.get(KEY_LED_COUNT)
        if not led_count or not isinstance(led_count, int):
            raise CollectionValueError('invalid-led-manager-led-count')
        pin = data.get(KEY_PIN)
        if not isinstance(pin, int):
            raise CollectionValueError('invalid-led-manager-pin')

        # Optional arguments.
        brightness = data.get(KEY_BRIGHTNESS, 1.0)
        if not isinstance(brightness, float) or brightness < 0 or brightness > 1:
            raise CollectionValueError('invalid-led-manager-brightness')
        strip = data.get(KEY_STRIP, 0)
        if not isinstance(strip, int) or strip < 0:
            raise CollectionValueError('invalid-led-manager-strip')
        port = data.get(KEY_PORT, '/dev/ttyACM0')
        if not isinstance(port, str):
            raise CollectionValueError('invalid-led-manager-port')
        baudrate = data.get(KEY_BAUD, 115200)
        if not isinstance(baudrate, int):
            raise CollectionValueError('invalid-led-manager-baud')

        return SerialManager(
            led_count=led_count,
            brightness=brightness,
            strip=strip,
            pin=pin,
            port=port,
            baudrate=baudrate,
        )

    def set_brightness(
            self,
            brightness: float = 1.0,
            show: bool = True,
            save: bool = False,
    ) -> None:
        """Set LED brightness for entire strip."""
        brightness = min(max(0.0, brightness), 1.0)
        with self._lock:
            if save:
                self._brightness = brightness
            self._op_set_brightness(brightness, show=show)

    def show(self) -> None:
        """Display all pending pixel changes since last show."""
        with self._lock:
            self._op_show()

    def teardown(self) -> None:
        """Clear LED states, and release resources."""
        logger.info(f'Tearing down LED manager for pin {self.pin} on {self.port}')
        self._serial.reset_output_buffer()
        self._op_fill_leds(Colors.BLACK.value)
        self._serial.close()

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type."""
        return {
            KEY_LED_COUNT: len(self),
            KEY_BRIGHTNESS: self.brightness,
            KEY_STRIP: self.strip,
            KEY_PIN: self.pin,
            KEY_PORT: self.port,
            KEY_BAUD: self.baudrate,
            KEY_TYPE: 'Serial',
        }

    def update(
            self,
            new_values: dict,
    ) -> dict:
        """Update the configuration of the LED manager.

        Args:
            new_values: New attributes to set on the manager.

        Returns:
            Final manager configuration with the updated values.
        """
        invalid_prefix = 'invalid-lighting-manager'
        brightness = get_and_validate(new_values, KEY_BRIGHTNESS, float, nullable=True, error_prefix=invalid_prefix)
        if brightness is not None:
            self.set_brightness(brightness, save=True)
        strip = get_and_validate(new_values, KEY_STRIP, int, nullable=True, error_prefix=invalid_prefix)
        if strip is not None:
            self.strip = strip
        pin = get_and_validate(new_values, KEY_PIN, int, nullable=True, error_prefix=invalid_prefix)
        if pin is not None:
            self.pin = pin
        port = get_and_validate(new_values, KEY_PORT, str, nullable=True, error_prefix=invalid_prefix)
        if port is not None:
            self.port = port
        baudrate = get_and_validate(new_values, KEY_BAUD, int, nullable=True, error_prefix=invalid_prefix)
        if baudrate is not None:
            self.baudrate = baudrate
        led_count = get_and_validate(new_values, KEY_LED_COUNT, int, nullable=True, error_prefix=invalid_prefix)
        if led_count is not None:
            if led_count > len(self._colors):
                self._colors = self._colors[:led_count]
            else:
                self._colors = self._colors + [Colors.BLACK.value for _ in range(led_count - len(self._colors))]
        return self.to_json()