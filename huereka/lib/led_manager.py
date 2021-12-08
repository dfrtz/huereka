"""Helpers for managing brightness and colors on LED strips."""

from typing import Sequence
from typing import Union

import neopixel
import board

from adafruit_blinka.microcontroller.generic_linux.libgpiod_pin import Pin
from adafruit_pixelbuf import ColorUnion

from huereka.lib.color_utils import Colors


class LEDManager(neopixel.NeoPixel):
    """Manage the colors and brightness of LEDs connected to a single GPIO pin."""

    def __init__(
            self,
            led_count: int = 100,
            brightness: float = 1.0,
            pixel_order: str = 'RGB',
            data_pin: Pin = board.D18,
    ) -> None:
        """Setup a single LED chain/strip.

        Args:
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            pixel_order: RGB/RGBW/etc ordering of the LEDs on each microcontroller.
            data_pin: GPIO pin to use to send the signal.
        """
        super().__init__(
            data_pin,
            led_count,
            brightness=brightness,
            auto_write=False,
            pixel_order=pixel_order,
            bpp=len(pixel_order)
        )

    def __setitem__(
            self,
            index: Union[int, slice],
            color: Union[Colors, ColorUnion, Sequence[ColorUnion]],
    ) -> None:
        """Overridden setter to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        super().__setitem__(index, color)

    def clear_all_leds(self) -> None:
        """Clear (turn off) all LEDs."""
        self.fill(Colors.OFF)
        self.show()

    def clear_led(self, index: int, show: bool = True) -> None:
        """Helper to clear (turn off) color and immediately show change on a single LED.

        Args:
            index: Position of the LED in the chain.
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        self[index] = Colors.OFF
        if show:
            self.show()

    def fill(self, color: Union[Colors, ColorUnion]) -> None:
        """Overridden fill to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        super().fill(color)

    def update_led(self, index: int, color: Union[Colors, ColorUnion], show: bool = True) -> None:
        """Helper to set color and immediately show change.

        Args:
            index: Position of the LED in the chain.
            color: New color to set.
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        self[index] = color
        if show:
            self.show()
