"""Helpers for managing brightness and colors on LED strips."""

from __future__ import annotations

import json
import logging
import threading
import time

from typing import Any
from typing import Dict
from typing import Sequence
from typing import Union

import neopixel
import board

from adafruit_pixelbuf import ColorUnion
from microcontroller import Pin

from huereka.lib import response_utils
from huereka.lib.color_utils import Colors

logger = logging.getLogger(__name__)

DEFAULT_LED_UPDATE_DELAY = 0.01
KEY_LED_COUNT = 'led_count'
KEY_BRIGHTNESS = 'brightness'
KEY_PIXEL_ORDER = 'pixel_order'
KEY_PIN = 'pin'


class LEDManager(neopixel.NeoPixel):
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
            index: Union[int, slice],
            color: Union[Colors, ColorUnion, Sequence[ColorUnion]],
    ) -> None:
        """Overridden setter to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        with self.synchronized_lock:
            super().__setitem__(index, color)

    def fill(self, color: Union[Colors, ColorUnion]) -> None:
        """Overridden fill to handle additional color types."""
        if isinstance(color, Colors):
            color = color.value
        with self.synchronized_lock:
            super().fill(color)

    @staticmethod
    def from_json(data: dict) -> LEDManager:
        """Convert JSON type into manager instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated manager with the given attributes.
        """
        # Required arguments.
        led_count = data.get(KEY_LED_COUNT)
        if not led_count or not isinstance(led_count, int):
            raise LEDManagerValueError('invalid-led-manager-led-count')
        pin = data.get(KEY_PIN)
        if not isinstance(pin, int):
            raise LEDManagerValueError('invalid-led-manager-pin')

        # Optional arguments.
        brightness = data.get(KEY_BRIGHTNESS, 1.0)
        if not isinstance(brightness, float) or brightness < 0 or brightness > 1:
            raise LEDManagerValueError('invalid-led-manager-brightness')
        pixel_order = data.get(KEY_PIXEL_ORDER, 'RGB')
        if not isinstance(pixel_order, str) or pixel_order not in ('RGB', 'RGBW'):
            raise LEDManagerValueError('invalid-led-manager-pixel-order')

        return LEDManager(
            led_count=led_count,
            brightness=brightness,
            pixel_order=pixel_order,
            pin=Pin(pin),
        )

    def set_color(
            self,
            color: Union[Colors, ColorUnion],
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
            colors: list[Union[Colors, ColorUnion]],
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


class LEDManagerValueError(response_utils.APIError, ValueError):
    """Exception subclass to help identify failures that indicate an LED manager value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = 422) -> None:
        """Setup the user details of the error."""
        super().__init__(error, data, code=code)


class LEDManagerDuplicate(LEDManagerValueError):
    """Exception subclass to help identify failures that indicate a manager already exists."""

    def __init__(self, pin_id: int) -> None:
        """Setup the user details of the error.

        Args:
            pin_id: ID/index of the pin on the board.
        """
        super().__init__('duplicate-led-manager', pin_id)


class LEDManagerNotFound(LEDManagerValueError):
    """Exception subclass to help identify failures that indicate a manager needs to be setup."""

    def __init__(self, pin_id: int) -> None:
        """Setup the user details of the error.

        Args:
            pin_id: ID/index of the pin on the board.
        """
        super().__init__('missing-led-manager', pin_id)


class LEDManagers:
    """Singleton for managing concurrent access to LEDs connected to GPIO pins."""

    __led_managers__: Dict[Pin, LEDManager] = {}
    __led_managers_lock__ = threading.Condition()
    __led_managers_uri__: str = None

    @classmethod
    def create(
            cls,
            pin: Pin = board.D18,
            led_count: int = 100,
            brightness: float = 1.0,
            pixel_order: str = 'RGB',
    ) -> LEDManager:
        """Setup a single LED chain/strip.

        Args:
            pin: GPIO pin to use to send the signal.
            led_count: How many LEDs are on the strip of lights.
            brightness: Default brightness as a percent between 0.0 and 1.0.
            pixel_order: RGB/RGBW/etc ordering of the LEDs on each microcontroller.

        Returns:
            New LED manager for the given pin if not already created.

        Raises:
            LEDManagerDuplicate if the manager is already setup, indicating it should updated instead.
        """
        with cls.__led_managers_lock__:
            if pin.id in cls.__led_managers__:
                raise LEDManagerDuplicate(pin.id)
            cls.__led_managers__[pin.id] = LEDManager(
                led_count=led_count,
                brightness=brightness,
                pixel_order=pixel_order,
                pin=pin
            )
            return cls.__led_managers__[pin.id]

    @classmethod
    def get(cls, pin: Pin = board.D18) -> LEDManager:
        """Find the manager associated with a given pin, or raise a specific error message for handling downstream.

        Args:
            pin: GPIO pin to use to send the signal.

        Returns:
            Instance of the LED manager connected to the requested pin.

        Raises:
            LEDManagerNotFound if the manager has not been setup.
        """
        manager = cls.__led_managers__.get(pin.id)
        if not manager:
            raise LEDManagerNotFound(pin.id)
        return manager

    @classmethod
    def load(cls, manager_data: Union[str, list[dict]]) -> None:
        """Initialize the manager cache by loading saved configurations.

        Args:
            manager_data: Manager data to load as JSON string, JSON file path, or pre-structured python objects.
        """
        loaded_data = []
        if isinstance(manager_data, str):
            if manager_data.startswith('['):
                try:
                    loaded_data = json.loads(manager_data)
                except Exception:  # pylint: disable=broad-except
                    logger.exception('Failed to load LED managers from text')
            elif manager_data.startswith(('/', 'file://')):
                manager_data = manager_data.removeprefix('file://')
                cls.__led_managers_uri__ = manager_data
                try:
                    with open(manager_data, 'rt', encoding='utf-8') as file_in:
                        try:
                            loaded_data = json.load(file_in)
                            logger.info(f'Loaded color profiles from {cls.__led_managers_uri__}')
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(f'Failed to load LED managers from local file {manager_data}')
                except FileNotFoundError:
                    logger.warning(f'Skipping LED managers load, file not found {manager_data}')
        elif isinstance(manager_data, list):
            loaded_data = manager_data
        for index, manager_config in enumerate(loaded_data):
            pin_id = manager_config.get(KEY_PIN)
            if pin_id in cls.__led_managers__:
                logger.warning(f'Skipping duplicate LED manager setup at index {index}')
                continue
            try:
                manager = LEDManager.from_json(manager_config)
                cls.register(manager)
            except Exception:  # pylint: disable=broad-except
                logger.exception(f'Skipping invalid manager setup at index {index}')

    @classmethod
    def register(cls, manager: LEDManager) -> None:
        """Store a manager for concurrent access.

        Args:
            manager: Previously setup LED manager to be stored in the cache and used during concurrent calls.
        """
        with cls.__led_managers_lock__:
            pin_id = manager.led_pin.id
            if pin_id in cls.__led_managers__:
                raise LEDManagerDuplicate(pin_id)
            cls.__led_managers__[pin_id] = manager

    @classmethod
    def remove(cls, pin: Pin = board.D18) -> None:
        """Remove a single LED chain/strip and release its resources.

        Args:
            pin: GPIO pin to use to send the signal.

        Raises:
            LEDManagerNotFound if the manager does not exist and cannot be removed.
        """
        with cls.__led_managers_lock__:
            if pin.id not in cls.__led_managers__:
                raise LEDManagerNotFound(pin.id)
            manager = cls.__led_managers__.pop(pin.id)
            manager.teardown()

    @classmethod
    def set_color(
            cls,
            color: Union[Colors, ColorUnion],
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
        with cls.__led_managers_lock__:
            cls.get(pin).set_color(color, index=index, show=show)

    @classmethod
    def set_colors(
            cls,
            colors: list[Union[Colors, ColorUnion]],
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
        with cls.__led_managers_lock__:
            manager = cls.get(pin)
            manager.set_colors(colors, delay=delay, show=show)

    @classmethod
    def shutoff(cls, pin: Pin = board.D18) -> None:
        """Clear LED states and shut off pin.

        Args:
            pin: GPIO pin/index of the manager to use to send the signal.
        """
        with cls.__led_managers_lock__:
            cls.get(pin).turn_off()

    @classmethod
    def show(cls, pin: Pin = board.D18) -> None:
        """Call the associated write function to display the pixels on a manager.

        Args:
            pin: GPIO pin/index of the manager to use to send the signal.
        """
        with cls.__led_managers_lock__:
            cls.get(pin).show()

    @classmethod
    def teardown(cls) -> None:
        """Clear all LED manager states, and release resources.

        Managers should not be reused after teardown.
        """
        with cls.__led_managers_lock__:
            for pin_id in list(cls.__led_managers__.keys()):
                cls.remove(Pin(pin_id))

    @classmethod
    def to_json(cls) -> list[dict]:
        """Convert all the managers into JSON compatible types.

        Returns:
            List of manager configurations.
        """
        with cls.__led_managers_lock__:
            return [manager.to_json() for manager in cls.__led_managers__.values()]
