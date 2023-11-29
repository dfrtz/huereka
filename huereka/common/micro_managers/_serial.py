"""Manager for brightness and colors on an LED strip connected to a serial."""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Sequence

import serial
from adafruit_pixelbuf import ColorUnion

from huereka.common import color_utils
from huereka.common.color_utils import Colors
from huereka.common.micro_managers._manager_base import DEFAULT_LED_UPDATE_DELAY
from huereka.common.micro_managers._manager_base import KEY_BRIGHTNESS
from huereka.common.micro_managers._manager_base import KEY_LED_COUNT
from huereka.common.micro_managers._manager_base import KEY_PIN
from huereka.common.micro_managers._manager_base import KEY_TYPE
from huereka.common.micro_managers._manager_base import LEDMicroManager
from huereka.shared.collections import CollectionValueError
from huereka.shared.collections import get_and_validate

logger = logging.getLogger(__name__)

# Use FastLED default of 400 FPS (2.5 ms)
DEFAULT_REFRESH_RATE = 2500

OP_MAGIC = int(127).to_bytes(length=1, byteorder="big", signed=False)

OP_INIT_STRIP = 1
OP_SET_BRIGHTNESS = 32
OP_FILL_LEDS = 33
OP_SET_LED = 34
OP_SHOW = 35
OP_TEST = 77
OP_RESET = 99

KEY_REFRESH_RATE = "refresh_rate"
KEY_STRIP = "strip"
KEY_PORT = "port"
KEY_BAUD = "baud"


class SerialManager(
    LEDMicroManager
):  # Approved override of the default variable limit. pylint: disable=too-many-instance-attributes
    """Manage the colors and brightness of LEDs connected to a GPIO pin on a device connected to a serial port."""

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
        self,
        led_count: int = 100,
        brightness: float = 1.0,
        strip: int = 0,
        pin: int = 5,
        refresh_rate: int = DEFAULT_REFRESH_RATE,
        port: str = "/dev/ttyACM0",
        baudrate: int = 115200,
        timeout: int = 10,
        dsrdtr: bool = False,
    ) -> None:
        """Set up a single FastLED strip.

        Args:
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            strip: Index of the strip to initialize on the serial device.
            pin: GPIO pin on the serial device to use to send the signal.
            refresh_rate: Refresh rate in microseconds (e.g. 5000 == 200 FPS, 16000 == ~60 FPS, 33000 == ~30 FPS, etc.).
            port: Location of the serial port to connect to.
            baudrate: Speed of the serial connection. Must match the configuration of the serial device.
            timeout: Amount of time in seconds to wait for a message to send before timing out.
            dsrdtr: Enable hardware (DSR/DTR) flow control.
        """
        super().__init__(brightness=brightness)
        self._ready = False
        self._pending = []
        self._colors = [Colors.BLACK.value for _ in range(led_count)]
        self.strip = strip
        self.pin = pin
        self.refresh_rate = refresh_rate
        self.port = port
        self.baudrate = baudrate
        self._serial = serial.Serial(self.port, self.baudrate, timeout=timeout, dsrdtr=dsrdtr)
        # Delay startup by half a second to prevent silent failures when it looks like the data sent.
        # All pending actions will be queued up to run as soon as available.
        threading.Timer(0.5, self._init).start()
        logger.info(f"Initialized LED manager for pin {self.pin} on {self.port}")

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

    def _init(self, led_delay: float = DEFAULT_LED_UPDATE_DELAY) -> None:
        """Send operation to set up LED strip.

        Should be called by new thread due to delay operations to prevent blocking.
        """
        with self._lock:
            self._ready = True
            self._op_init_strip()
            # Slight delay to ensure strip is ready before sending messages.
            time.sleep(led_delay)
            self._op_fill_leds(Colors.BLACK.value, show=True)
            for values, start in self._pending:
                self._write(*values, start=start)
                time.sleep(led_delay)

    def _op_init_strip(self) -> None:
        """Send operation to set up LED strip."""
        self._write(
            OP_INIT_STRIP,
            0,  # Placeholder for LED type.
            self.pin,
            len(self).to_bytes(length=2, byteorder="big", signed=False),
            self.refresh_rate.to_bytes(length=2, byteorder="big", signed=False),
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
            pos.to_bytes(length=2, byteorder="big", signed=False),
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

    def _write(self, *values: int | bytes, start: bool = True) -> None:
        """Write out a set of unsigned, single byte, values to the serial connection."""
        if not self._ready:
            self._pending.append((values, start))
            return
        if start:
            msg = OP_MAGIC
        else:
            msg = b""
        for value in values:
            if isinstance(value, bytes):
                msg += value
            else:
                msg += value.to_bytes(length=1, byteorder="big", signed=False)
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
            raise CollectionValueError("invalid-led_manager-led_count")
        pin = data.get(KEY_PIN)
        if not isinstance(pin, int):
            raise CollectionValueError("invalid-led_manager-pin")

        # Optional arguments.
        refresh_rate = data.get(KEY_REFRESH_RATE, DEFAULT_REFRESH_RATE)
        if not isinstance(refresh_rate, int):
            raise CollectionValueError("invalid-led_manager-refresh_rate")
        brightness = data.get(KEY_BRIGHTNESS, 1.0)
        if not isinstance(brightness, float) or brightness < 0 or brightness > 1:
            raise CollectionValueError("invalid-led_manager-brightness")
        strip = data.get(KEY_STRIP, 0)
        if not isinstance(strip, int) or strip < 0:
            raise CollectionValueError("invalid-led_manager-strip")
        port = data.get(KEY_PORT, "/dev/ttyACM0")
        if not isinstance(port, str):
            raise CollectionValueError("invalid-led_manager-port")
        baudrate = data.get(KEY_BAUD, 115200)
        if not isinstance(baudrate, int):
            raise CollectionValueError("invalid-led_manager-baud")

        return SerialManager(
            led_count=led_count,
            brightness=brightness,
            strip=strip,
            pin=pin,
            refresh_rate=refresh_rate,
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
        logger.info(f"Tearing down LED manager for pin {self.pin} on {self.port}")
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
            KEY_REFRESH_RATE: self.refresh_rate,
            KEY_PORT: self.port,
            KEY_BAUD: self.baudrate,
            KEY_TYPE: "Serial",
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
        brightness = get_and_validate(new_values, KEY_BRIGHTNESS, float)
        if brightness is not None:
            self.set_brightness(brightness, save=True)
        strip = get_and_validate(new_values, KEY_STRIP, int)
        if strip is not None:
            self.strip = strip
        pin = get_and_validate(new_values, KEY_PIN, int)
        if pin is not None:
            self.pin = pin
        refresh_rate = get_and_validate(new_values, KEY_REFRESH_RATE, int)
        if refresh_rate is not None:
            self.refresh_rate = refresh_rate
        port = get_and_validate(new_values, KEY_PORT, str)
        if port is not None:
            self.port = port
        baudrate = get_and_validate(new_values, KEY_BAUD, int)
        if baudrate is not None:
            self.baudrate = baudrate
        led_count = get_and_validate(new_values, KEY_LED_COUNT, int)
        if led_count is not None:
            if led_count > len(self._colors):
                self._colors = self._colors[:led_count]
            else:
                self._colors = self._colors + [Colors.BLACK.value for _ in range(led_count - len(self._colors))]
        return self.to_json()
