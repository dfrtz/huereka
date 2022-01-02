"""Helpers for managing brightness and colors on LED strips."""

from __future__ import annotations

import logging
import threading
import time

from typing import Dict
from typing import Sequence

import neopixel
import board

from adafruit_pixelbuf import ColorUnion
from microcontroller import Pin

from huereka.lib import response_utils
from huereka.lib.collections import Collection
from huereka.lib.collections import CollectionEntry
from huereka.lib.collections import CollectionValueError
from huereka.lib.color_utils import Colors

logger = logging.getLogger(__name__)

DEFAULT_LED_UPDATE_DELAY = 0.01
KEY_LED_COUNT = 'led_count'
KEY_BRIGHTNESS = 'brightness'
KEY_PIXEL_ORDER = 'pixel_order'
KEY_PIN = 'pin'


class LEDManager(neopixel.NeoPixel, CollectionEntry):
    """Manage the colors and brightness of LEDs connected to a GPIO pin.

    When updating lights it is recommended to use one of the "synchronized" functions in this class,
    instead of function from the base class, to prevent race conditions from concurrent access.
    """

    def __init__(
            self,
            led_count: int = 100,
            brightness: float = 1.0,
            pixel_order: str = 'RGB',
            pin: Pin = board.D18,
    ) -> None:
        """Setup a single LED chain/strip.

        Args:
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            pixel_order: RGB/RGBW/etc ordering of the LEDs on each microcontroller.
            pin: GPIO pin to use to send the signal.
        """
        super().__init__(
            pin,
            led_count,
            brightness=brightness,
            auto_write=False,
            pixel_order=pixel_order,
            bpp=len(pixel_order)
        )
        self.led_pin = pin  # Track the original pin for reference, it is dropped in parent.
        self.synchronized_lock = threading.Condition()
        logger.info(f'Initialized LED manager for pin {self.led_pin.id}')

    def __setitem__(
            self,
            index: int | slice,
            color: Colors | ColorUnion | Sequence[ColorUnion],
    ) -> None:
        """Overridden setter to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        with self.synchronized_lock:
            super().__setitem__(index, color)

    def fill(self, color: Colors | ColorUnion) -> None:
        """Overridden fill to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        with self.synchronized_lock:
            super().fill(color)

    @classmethod
    def from_json(cls, data: dict) -> LEDManager:
        """Convert JSON type into manager instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated manager with the given attributes.
        """
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
        pixel_order = data.get(KEY_PIXEL_ORDER, 'RGB')
        if not isinstance(pixel_order, str) or pixel_order not in ('RGB', 'RGBW'):
            raise CollectionValueError('invalid-led-manager-pixel-order')

        return LEDManager(
            led_count=led_count,
            brightness=brightness,
            pixel_order=pixel_order,
            pin=Pin(pin),
        )

    def set_color(
            self,
            color: Colors | ColorUnion,
            index: int = -1,
            delay: float = DEFAULT_LED_UPDATE_DELAY,
            show: bool = True,
    ) -> None:
        """Set LED color and immediately show change.

        Args:
            color: New color to set.
            index: Position of the LED in the chain. Defaults to -1 to fill all.
                Disables delay.
            delay: Time to wait between each LED update in seconds.
                Ignored if index >= 0.
            show: Whether to show the change immediately, or delay until the next show() is called.
                Ignored if delay > 0.
        """
        if index >= 0:
            with self.synchronized_lock:
                self[index] = color
                if show:
                    self.show()
        else:
            if delay:
                def _set_color() -> None:
                    delay_until = time.time()
                    for led, _ in enumerate(self):
                        delay_until += delay
                        self.synchronized_lock.acquire()
                        self[led] = color
                        self.show()
                        self.synchronized_lock.release()
                        delta = delay_until - time.time()
                        if delta > 0:
                            time.sleep(delta)
                threading.Thread(target=_set_color, daemon=True).start()
            else:
                with self.synchronized_lock:
                    self.fill(color)
                    if show:
                        self.show()

    def set_colors(
            self,
            colors: list[Colors | ColorUnion],
            delay: float = DEFAULT_LED_UPDATE_DELAY,
            show: bool = True,
    ) -> None:
        """Set multiple LED colors simultaneously and show change.

        Args:
            colors: New colors to set, one per LED
            delay: Time to wait between each LED update in seconds.
                Ignored if index >= 0.
            show: Whether to show the change immediately, or delay until the next show() is called.
                Ignored if delay > 0.
        """
        if delay:
            def _set_color() -> None:
                delay_until = time.time()
                for led, led_color in enumerate(colors):
                    delay_until += delay
                    self.synchronized_lock.acquire()
                    self[led] = led_color
                    self.show()
                    self.synchronized_lock.release()
                    delta = delay_until - time.time()
                    if delta > 0:
                        time.sleep(delta)
            threading.Thread(target=_set_color, daemon=True).start()
        else:
            with self.synchronized_lock:
                for index, color in enumerate(colors):
                    self[index] = color
                if show:
                    self.show()

    def teardown(self) -> None:
        """Clear LED states, and release resources.

        Manager should not be reused after teardown.
        """
        logger.info(f'Tearing down LED manager for pin {self.led_pin.id}')
        self.deinit()

    def to_json(self) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_LED_COUNT: len(self),
            KEY_BRIGHTNESS: self.brightness,
            KEY_PIXEL_ORDER: self.byteorder,
            KEY_PIN: self.led_pin.id,
        }

    def turn_off(self, index: int = -1, show: bool = True) -> None:
        """Helper to turn off (set color to black) and immediately show change.

        Args:
            index: Position of the LED in the chain. Defaults to -1 to turn off all.
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        with self.synchronized_lock:
            if index < 0:
                self.fill(Colors.BLACK)
            else:
                self[index] = Colors.BLACK
            if show:
                self.show()


class LEDManagers(Collection):
    """Singleton for managing concurrent access to LEDs connected to GPIO pins."""

    _collection: Dict[int, LEDManager] = {}
    _collection_lock: threading.Condition = threading.Condition()
    _collection_uri: str = None

    collection_help: str = 'LED manager'
    entry_cls: str = LEDManager

    @classmethod
    def get(cls, key: int | Pin) -> LEDManager:
        """Find the manager associated with a given key.

        Override to update typehint and simplify caller typechecks.
        """
        if isinstance(key, Pin):
            key = key.id
        return super().get(key)

    @classmethod
    def register(cls, entry: LEDManager) -> None:
        """Store a manager for concurrent access.

        Override of base to change type use pin ID instead of name for storage.

        Args:
            entry: Previously setup LED manager to be stored in the cache and used during concurrent calls.
        """
        with cls._collection_lock:
            pin_id = entry.led_pin.id
            if pin_id in cls._collection:
                raise response_utils.APIError(f'duplicate-{cls.collection_help.replace(" ", "-")}', pin_id, code=422)
            cls._collection[pin_id] = entry

    @classmethod
    def remove(cls, key: int | Pin) -> LEDManager:
        """Remove a single LED chain/strip and release its resources.

        Override to update typehint and simplify caller typechecks.
        """
        if isinstance(key, Pin):
            key = key.id
        return super().remove(key)

    @classmethod
    def set_color(
            cls,
            color: Colors | ColorUnion,
            index: int = -1,
            show: bool = True,
            pin: Pin = board.D18,
    ) -> None:
        """Set color on a single ping and immediately show change.

        Args:
            color: New color to set.
            index: Position of the LED in the chain. Defaults to -1 to fill all.
            show: Whether to show the change immediately, or delay until the next show() is called.
            pin: GPIO pin/index of the manager to use to send the signal.
        """
        with cls._collection_lock:
            cls.get(pin).set_color(color, index=index, show=show)

    @classmethod
    def set_colors(
            cls,
            colors: list[Colors | ColorUnion],
            delay: float = DEFAULT_LED_UPDATE_DELAY,
            show: bool = True,
            pin: Pin = board.D18,
    ) -> None:
        """Set colors and immediately show change.

        Args:
            colors: New colors to set, one per pin.
            delay: Time to wait between each LED update in seconds.
            show: Whether to show the change immediately, or delay until the next show() is called.
            pin: GPIO pin/index of the manager to use to send the signal.
        """
        with cls._collection_lock:
            manager = cls.get(pin)
            manager.set_colors(colors, delay=delay, show=show)

    @classmethod
    def shutoff(cls, pin: Pin = board.D18) -> None:
        """Clear LED states and shut off pin.

        Args:
            pin: GPIO pin/index of the manager to use to send the signal.
        """
        with cls._collection_lock:
            cls.get(pin).turn_off()

    @classmethod
    def show(cls, pin: Pin = board.D18) -> None:
        """Call the associated write function to display the pixels on a manager.

        Args:
            pin: GPIO pin/index of the manager to use to send the signal.
        """
        with cls._collection_lock:
            cls.get(pin).show()

    @classmethod
    def teardown(cls) -> None:
        """Clear all LED manager states, and release resources.

        Managers should not be reused after teardown.
        """
        with cls._collection_lock:
            for pin_id in list(cls._collection.keys()):
                cls.remove(pin_id)

    @classmethod
    def to_json(cls) -> list[dict]:
        """Convert all the managers into JSON compatible types.

        Returns:
            List of manager configurations.
        """
        with cls._collection_lock:
            return [manager.to_json() for manager in cls._collection.values()]

    @classmethod
    def validate_entry(cls, data: dict, index: int) -> bool:
        """Additional confirmation of entry values before load."""
        pin_id = data.get(KEY_PIN)
        if pin_id in cls._collection:
            logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using ping {pin_id}')
            return False
        return True
