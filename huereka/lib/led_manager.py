"""Helpers for managing brightness and colors on LED strips."""

from __future__ import annotations

import logging
import threading
import time

from typing import Sequence

import neopixel
import board

from adafruit_pixelbuf import ColorUnion
from microcontroller import Pin

from huereka.lib import response_utils
from huereka.lib.collections import Collection
from huereka.lib.collections import CollectionEntry
from huereka.lib.collections import CollectionValueError
from huereka.lib.collections import KEY_ID
from huereka.lib.color_utils import Colors

logger = logging.getLogger(__name__)

DEFAULT_LED_UPDATE_DELAY = 0.01
KEY_LED_COUNT = 'led_count'
KEY_BRIGHTNESS = 'brightness'
KEY_PIXEL_ORDER = 'pixel_order'
KEY_TYPE = 'type'
KEY_PIN = 'pin'


class LEDManager(CollectionEntry):
    """Manage the colors and brightness of LEDs connected to a GPIO pin.

    When updating lights it is recommended to use one of the "synchronized" functions in this class,
    instead of function from the base class, to prevent race conditions from concurrent access.
    """

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
            self,
            name: str = None,
            uuid: str = None,
            led_count: int = 100,
            brightness: float = 1.0,
            pixel_order: str = 'RGB',
            pin: Pin = board.D18,
            manager_type: str = 'NeoPixel',
    ) -> None:
        """Set up a single LED chain/strip.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            pixel_order: RGB/RGBW/etc ordering of the LEDs on each microcontroller.
            pin: GPIO pin to use to send the signal.
            manager_type: Type of LED manager to use on the backend. e.g. "NeoPixel"
        """
        super().__init__(name, uuid)
        if manager_type.lower() == 'neopixel':
            self._led_manager = neopixel.NeoPixel(
                pin,
                led_count,
                brightness=brightness,
                auto_write=False,
                pixel_order=pixel_order,
                bpp=len(pixel_order)
            )
        self.brightness = brightness
        self.led_pin = pin
        self.manager_type = manager_type
        self.synchronized_lock = threading.Condition()
        logger.info(f'Initialized LED manager for pin {self.led_pin.id}')

    def __getitem__(self, index: int | slice) -> int:
        """Find LED color at a specific LED position."""
        with self.synchronized_lock:
            return self._led_manager[index]

    def __len__(self) -> int:
        """Number of controlled pixels."""
        return len(self._led_manager)

    def __setitem__(
            self,
            index: int | slice,
            color: Colors | ColorUnion | Sequence[ColorUnion],
    ) -> None:
        """Set color at a specific LED position and immediately show change."""
        if isinstance(color, Colors):
            color = color.value
        with self.synchronized_lock:
            self._led_manager[index] = color

    def fill(self, color: Colors | ColorUnion) -> None:
        """Overridden fill to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        with self.synchronized_lock:
            self._led_manager.fill(color)

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
        uuid = data.get(KEY_ID)
        if not isinstance(uuid, str) and uuid is not None:
            raise CollectionValueError('invalid-led-manager-id')
        brightness = data.get(KEY_BRIGHTNESS, 1.0)
        if not isinstance(brightness, float) or brightness < 0 or brightness > 1:
            raise CollectionValueError('invalid-led-manager-brightness')
        pixel_order = data.get(KEY_PIXEL_ORDER, 'RGB')
        if not isinstance(pixel_order, str) or pixel_order not in ('RGB', 'RGBW'):
            raise CollectionValueError('invalid-led-manager-pixel-order')
        manager_type = data.get(KEY_TYPE, 'NeoPixel')
        if not isinstance(manager_type, str) or manager_type.lower() not in ('neopixel',):
            raise CollectionValueError('invalid-led-manager-type')

        return LEDManager(
            led_count=led_count,
            brightness=brightness,
            pixel_order=pixel_order,
            pin=Pin(pin),
            manager_type=manager_type
        )

    def set_brightness(
            self,
            brightness: float = 1.0,
            show: bool = True,
            save: bool = False,
    ) -> None:
        """Set LED brightness and immediately show change.

        Args:
            brightness: New brightness as a percent between 0.0 and 1.0.
            show: Whether to show the change immediately, or delay until the next show() is called.
                Ignored if delay > 0.
            save: Whether to save the value permanently, or only apply to the underlying manager.
        """
        brightness = min(max(0.0, brightness), 1.0)
        with self.synchronized_lock:
            if save:
                self.brightness = brightness
            self._led_manager.brightness = brightness
            if show:
                self.show()

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

    def show(self) -> None:
        """Display all pending pixel changes since last show."""
        with self.synchronized_lock:
            self._led_manager.show()

    def teardown(self) -> None:
        """Clear LED states, and release resources.

        Manager should not be reused after teardown.
        """
        logger.info(f'Tearing down LED manager for pin {self.led_pin.id}')
        self._led_manager.deinit()

    def to_json(self) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_LED_COUNT: len(self._led_manager),
            KEY_BRIGHTNESS: self.brightness,
            KEY_PIXEL_ORDER: self._led_manager.byteorder,
            KEY_PIN: self.led_pin.id,
            KEY_TYPE: self.manager_type,
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

    _collection: dict[int, LEDManager] = {}
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
    def set_brightness(
            cls,
            brightness: float = 1.0,
            show: bool = True,
            pin: Pin = board.D18,
            save: bool = False,
    ) -> None:
        """Set brightness on a single pin and immediately show change.

        Args:
            brightness: New brightness as a percent between 0.0 and 1.0.
            show: Whether to show the change immediately, or delay until the next show() is called.
            pin: GPIO pin/index of the manager to use to send the signal.
            save: Whether to save the value permanently, or only set temporarily.
        """
        with cls._collection_lock:
            cls.get(pin).set_brightness(brightness, show=show, save=save)

    @classmethod
    def set_color(
            cls,
            color: Colors | ColorUnion,
            index: int = -1,
            show: bool = True,
            pin: Pin = board.D18,
    ) -> None:
        """Set color on a single pin and immediately show change.

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
                manager = cls.remove(pin_id)
                manager.teardown()

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
            logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using pin {pin_id}')
            return False
        return True
