"""Low level manager for brightness and colors on NeoPixel LED strips."""

from __future__ import annotations

import logging

from typing import Sequence

import neopixel
import board

from adafruit_pixelbuf import ColorUnion
from microcontroller import Pin

from huereka.lib.collections import KEY_ID
from huereka.lib.collections import CollectionValueError
from huereka.lib import color_utils
from huereka.lib.color_utils import Colors
from huereka.lib.micro_managers._manager_base import LEDMicroManager
from huereka.lib.micro_managers._manager_base import KEY_BRIGHTNESS
from huereka.lib.micro_managers._manager_base import KEY_LED_COUNT
from huereka.lib.micro_managers._manager_base import KEY_PIN
from huereka.lib.micro_managers._manager_base import KEY_TYPE

logger = logging.getLogger(__name__)

KEY_PIXEL_ORDER = 'pixel_order'


class NeoPixelManager(LEDMicroManager):
    """Manage the colors and brightness of LEDs connected to a GPIO pin."""

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
            self,
            led_count: int = 100,
            brightness: float = 1.0,
            pixel_order: str = 'RGB',
            pin: Pin = board.D18,
    ) -> None:
        """Set up a single NeoPixel LED strip.

        Args:
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            pixel_order: RGB/RGBW/etc ordering of the LEDs on each microcontroller.
            pin: GPIO pin to use to send the signal.
        """
        super().__init__(brightness=brightness)
        self._neo_pixel = neopixel.NeoPixel(
            pin,
            led_count,
            brightness=brightness,
            auto_write=False,
            pixel_order=pixel_order,
            bpp=len(pixel_order)
        )
        self.led_pin = pin
        logger.info(f'Initialized LED manager for pin {self.led_pin.id}')

    def __getitem__(self, index: int | slice) -> int:
        """Find LED color at a specific LED position."""
        with self._lock:
            return self._neo_pixel[index]

    def __len__(self) -> int:
        """Number of controlled pixels."""
        return len(self._neo_pixel)

    def __setitem__(
            self,
            index: int | slice,
            color: Colors | ColorUnion | Sequence[ColorUnion],
    ) -> None:
        """Set color at a specific LED position and immediately show change."""
        color = color_utils.parse_color(color)
        with self._lock:
            self._neo_pixel[index] = color

    @classmethod
    def from_json(cls, data: dict) -> NeoPixelManager:
        """Convert JSON type into manager instance."""
        # Required arguments.
        led_count = data.get(KEY_LED_COUNT)
        if not led_count or not isinstance(led_count, int):
            raise CollectionValueError('invalid-led-manager-led-count')
        pin = data.get(KEY_PIN)
        if not isinstance(pin, int):
            raise CollectionValueError('invalid-led-manager-pin')

        # Optional arguments.
        uuid = data.get(KEY_ID)
        if not isinstance(uuid, str) and uuid is not None:
            raise CollectionValueError('invalid-led-manager-id')
        brightness = data.get(KEY_BRIGHTNESS, 1.0)
        if not isinstance(brightness, float) or brightness < 0 or brightness > 1:
            raise CollectionValueError('invalid-led-manager-brightness')
        pixel_order = data.get(KEY_PIXEL_ORDER, 'RGB')
        if not isinstance(pixel_order, str) or pixel_order not in ('RGB', 'RGBW'):
            raise CollectionValueError('invalid-led-manager-pixel-order')

        return NeoPixelManager(
            led_count=led_count,
            brightness=brightness,
            pixel_order=pixel_order,
            pin=Pin(pin),
        )

    def fill(
            self,
            color: Colors | ColorUnion,
            show: bool = True,
    ) -> None:
        """Fill entire strip with a single color."""
        color = color_utils.parse_color(color)
        with self._lock:
            self._neo_pixel.fill(color)

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
            self._neo_pixel.brightness = brightness
            if show:
                self.show()

    def show(self) -> None:
        """Display all pending pixel changes since last show."""
        with self._lock:
            self._neo_pixel.show()

    def teardown(self) -> None:
        """Clear LED states, and release resources."""
        logger.info(f'Tearing down LED manager for pin {self.led_pin}')
        self._neo_pixel.deinit()

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type."""
        return {
            KEY_LED_COUNT: len(self._neo_pixel),
            KEY_BRIGHTNESS: self.brightness,
            KEY_PIXEL_ORDER: self._neo_pixel.byteorder,
            KEY_PIN: self.led_pin.id,
            KEY_TYPE: 'NeoPixel',
        }
