"""Helpers for managing brightness and colors on LED strips."""

from __future__ import annotations

import logging
import threading

from typing import Sequence

from adafruit_pixelbuf import ColorUnion

from huereka.lib import micro_managers
from huereka.lib.micro_managers import KEY_PIN
from huereka.lib.micro_managers import KEY_PORT
from huereka.lib.micro_managers import KEY_TYPE
from huereka.lib.collections import KEY_ID
from huereka.lib.collections import KEY_NAME
from huereka.lib.collections import Collection
from huereka.lib.collections import CollectionEntry
from huereka.lib.collections import CollectionValueError
from huereka.lib.collections import get_and_validate
from huereka.lib.color_utils import Colors

logger = logging.getLogger(__name__)

DEFAULT_LED_UPDATE_DELAY = 0.01


class LEDManager(CollectionEntry):
    """Manage the colors and brightness of LEDs connected to a GPIO pin.

    When updating lights it is recommended to use one of the "synchronized" functions in this class,
    instead of function from the base class, to prevent race conditions from concurrent access.
    """

    def __init__(
            self,
            name: str = None,
            uuid: str = None,
            micromanager: micro_managers.LEDMicroManager = None,
    ) -> None:
        """Set up a single LED chain/strip.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
        """
        super().__init__(name, uuid)
        self._led_manager = micromanager

    def __getitem__(self, index: int | slice) -> int:
        """Find LED color at a specific LED position."""
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
        self._led_manager[index] = color

    @property
    def brightness(self) -> float:
        """Current brightness as a percent between 0.0 and 1.0."""
        return self._led_manager.brightness

    def fill(self, color: Colors | ColorUnion) -> None:
        """Overridden fill to handle additional color types."""
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
        manager_type = data.get(KEY_TYPE)
        if not isinstance(manager_type, str) or manager_type.lower() not in ('neopixel', 'serial'):
            raise CollectionValueError('invalid-led-manager-type')
        uuid = data.get(KEY_ID)
        if not uuid or not isinstance(uuid, str):
            raise CollectionValueError('invalid-led-manager-id')

        # Optional arguments.
        name = data.get(KEY_NAME)
        if not isinstance(uuid, str) and name is not None:
            raise CollectionValueError('invalid-led-manager-name')
        micromanager = None
        if manager_type.lower() == 'neopixel':
            micromanager = micro_managers.NeoPixelManager.from_json(data)
        elif manager_type.lower() == 'serial':
            micromanager = micro_managers.SerialManager.from_json(data)

        return LEDManager(name=name, uuid=uuid, micromanager=micromanager)

    def off(self, show: bool = True) -> None:
        """Helper to turn off (reduce brightness to 0) and immediately show change.

        Args:
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        self._led_manager.off(show=show)

    def set_brightness(
            self,
            brightness: float = 1.0,
            show: bool = True,
            save: bool = False,
    ) -> None:
        """Set LED brightness for entire strip.

        Args:
            brightness: New brightness as a percent between 0.0 and 1.0.
            show: Whether to show the change immediately, or delay until the next show() is called.
                Ignored if delay > 0.
            save: Whether to save the value permanently, or only apply to the underlying manager.
        """
        self._led_manager.set_brightness(brightness, show=show, save=save)

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
        self._led_manager.set_color(color, index, delay=delay, show=show)

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
        self._led_manager.set_colors(colors, delay=delay, show=show)

    def show(self) -> None:
        """Display all pending pixel changes since last show."""
        self._led_manager.show()

    def teardown(self) -> None:
        """Clear LED states, and release resources.

        Manager should not be reused after teardown.
        """
        self._led_manager.teardown()

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        data = self._led_manager.to_json()
        data[KEY_ID] = self.uuid
        data[KEY_NAME] = self.name
        return data

    def update(
            self,
            new_values: dict,
    ) -> dict:
        """Update the values of an LED manager.

        Args:
            new_values: New attributes to set on the manager.

        Returns:
            Final manager configuration with the updated values.
        """
        invalid_prefix = 'invalid-lighting-manager'
        name = get_and_validate(new_values, KEY_NAME, str, nullable=True, error_prefix=invalid_prefix)
        if name is not None and name != self.name:
            self.name = name
        self._led_manager.update(new_values)
        return self.to_json()


class LEDManagers(Collection):
    """Singleton for managing concurrent access to LEDs connected to GPIO pins."""

    _collection: dict[str, LEDManager] = {}
    _collection_lock: threading.Condition = threading.Condition()
    _collection_uri: str = None

    collection_help: str = 'LED manager'
    entry_cls: str = LEDManager

    @classmethod
    def get(cls, key: str) -> LEDManager:
        """Find the manager associated with a given key.

        Override to update typehint and simplify caller typechecks.
        """
        return super().get(key)

    @classmethod
    def set_brightness(
            cls,
            uuid: str,
            brightness: float,
            show: bool = True,
            save: bool = False,
    ) -> None:
        """Set brightness on a single pin and immediately show change.

        Args:
            uuid: ID of the manager to use to send the signal.
            brightness: New brightness as a percent between 0.0 and 1.0.
            show: Whether to show the change immediately, or delay until the next show() is called.
            save: Whether to save the value permanently, or only set temporarily.
        """
        with cls._collection_lock:
            cls.get(uuid).set_brightness(brightness, show=show, save=save)

    @classmethod
    def set_color(
            cls,
            uuid: str,
            color: Colors | ColorUnion,
            index: int = -1,
            show: bool = True,
    ) -> None:
        """Set color on a single pin and immediately show change.

        Args:
            uuid: ID of the manager to use to send the signal.
            color: New color to set.
            index: Position of the LED in the chain. Defaults to -1 to fill all.
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        with cls._collection_lock:
            cls.get(uuid).set_color(color, index=index, show=show)

    @classmethod
    def set_colors(
            cls,
            uuid: str,
            colors: list[Colors | ColorUnion],
            delay: float = DEFAULT_LED_UPDATE_DELAY,
            show: bool = True,
    ) -> None:
        """Set colors and immediately show change.

        Args:
            uuid: ID of the manager to use to send the signal.
            colors: New colors to set, one per pin.
            delay: Time to wait between each LED update in seconds.
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        with cls._collection_lock:
            manager = cls.get(uuid)
            manager.set_colors(colors, delay=delay, show=show)

    @classmethod
    def shutoff(cls, uuid: str) -> None:
        """Clear LED states and shut off pin.

        Args:
            uuid: ID of the manager to use to send the signal.
        """
        with cls._collection_lock:
            cls.get(uuid).off()

    @classmethod
    def show(cls, uuid: str) -> None:
        """Call the associated write function to display the pixels on a manager.

        Args:
            uuid: ID of the manager to use to send the signal.
        """
        with cls._collection_lock:
            cls.get(uuid).show()

    @classmethod
    def teardown(cls) -> None:
        """Clear all LED manager states, and release resources.

        Managers should not be reused after teardown.
        """
        with cls._collection_lock:
            for uuid in list(cls._collection.keys()):
                manager: LEDManager = cls.remove(uuid)
                manager.teardown()

    @classmethod
    def update(
            cls,
            uuid: str,
            new_values: dict,
    ) -> dict:
        """Update the values of an LED manager.

        Args:
            uuid: ID of the original manager to update.
            new_values: New attributes to set on the manager.

        Returns:
            Final manager configuration with the updated values.
        """
        with cls._collection_lock:
            result = cls.get(uuid).update(new_values)
        return result

    @classmethod
    def validate_entry(cls, data: dict, index: int) -> bool:
        """Additional confirmation of entry values before load."""
        if not super().validate_entry(data, index):
            return False
        manager_type = data.get(KEY_TYPE)
        if manager_type.lower() == 'neopixel':
            pin = data.get(KEY_PIN)
            for manager in cls._collection.keys():
                if isinstance(manager, micro_managers.NeoPixelManager) and manager.led_pin == pin:
                    logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using pin {pin}')
                    return False
        elif manager_type.lower() == 'serial':
            port = data.get(KEY_PORT)
            for manager in cls._collection.keys():
                if isinstance(manager, micro_managers.SerialManager) and manager.port == port:
                    logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using port {port}')
                    return False
        return True
