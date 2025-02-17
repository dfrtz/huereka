"""Helpers for managing brightness and colors on LED strips."""

from __future__ import annotations

import logging
import threading
from typing import Sequence

from adafruit_pixelbuf import ColorUnion

from huereka.common import micro_managers
from huereka.common.color_utils import Colors
from huereka.common.micro_managers import KEY_PIN
from huereka.common.micro_managers import KEY_PORT
from huereka.common.micro_managers import KEY_TYPE
from huereka.shared.collections import KEY_ID
from huereka.shared.collections import KEY_NAME
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import CollectionValueError
from huereka.shared.collections import get_and_validate

logger = logging.getLogger(__name__)

KEY_MODE = "mode"
KEY_STATUS = "status"
KEY_LED_DELAY = "led_delay"

# Based on max speed without flickering/mis-coloring on a 12V strand of 250-300 WS2811 LEDs with 5V signal.
DEFAULT_LED_UPDATE_DELAY = 0.0125

MODE_OFF = 0
MODE_ON = 1

STATUS_OFF = 0
STATUS_ON = 1


class LEDManager(CollectionEntry):
    """Manage the colors and brightness of LEDs.

    Low level lighting controls are delegated to micromanagers based on the hardware. No direct access to hardware
    should be performed in this class, and only passthroughs to micromanagers are allowed.
    """

    def __init__(
        self,
        name: str = None,
        uuid: str = None,
        mode: int = MODE_OFF,
        led_delay: float = DEFAULT_LED_UPDATE_DELAY,
        micromanager: micro_managers.LEDMicroManager = None,
    ) -> None:
        """Set up a single LED chain/strip.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
            mode: Activity mode for the schedule as 0, 1 (off, on).
            led_delay: Minimum time delay allowed in seconds between individual LED updates during animations.
            micromanager: Low level manager that controls connectivity and messaging to LED hardware.
        """
        super().__init__(uuid=uuid, name=name)
        self._mode = MODE_OFF
        self._status = STATUS_OFF
        self._led_manager = micromanager
        self.mode = mode
        self.led_delay = led_delay

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
        if not isinstance(manager_type, str) or manager_type.lower() not in ("neopixel", "serial"):
            raise CollectionValueError("invalid-led_manager-type")
        uuid = data.get(KEY_ID)
        if not uuid or not isinstance(uuid, str):
            raise CollectionValueError("invalid-led_manager-id")

        # Optional arguments.
        name = data.get(KEY_NAME)
        if not isinstance(uuid, str) and name is not None:
            raise CollectionValueError("invalid-led_manager-name")
        mode = data.get(KEY_MODE, MODE_OFF)
        if not isinstance(mode, int):
            raise CollectionValueError("invalid-led_manager-mode")
        led_delay = data.get(KEY_LED_DELAY, DEFAULT_LED_UPDATE_DELAY)
        if not isinstance(led_delay, float):
            raise CollectionValueError("invalid-led_manager-led_delay")
        micromanager = None
        if manager_type.lower() == "neopixel":
            micromanager = micro_managers.NeoPixelManager.from_json(data)
        elif manager_type.lower() == "serial":
            micromanager = micro_managers.SerialManager.from_json(data)

        return LEDManager(name=name, uuid=uuid, mode=mode, micromanager=micromanager, led_delay=led_delay)

    def off(self, show: bool = True) -> None:
        """Helper to disable (reduce brightness to 0) and immediately show change.

        Args:
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        self._led_manager.off(show=show)

    @property
    def mode(self) -> int:
        """Return the current mode set on the manager."""
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        """Safely set the current mode of the manager."""
        valid_modes = (MODE_OFF, MODE_ON)
        if mode not in valid_modes:
            raise ValueError(f"Valid modes are: {valid_modes}")
        self._mode = mode

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
        delay: float | None = None,
        show: bool = True,
    ) -> None:
        """Set LED color and immediately show change.

        Args:
            color: New color to set.
            index: Position of the LED in the chain. Defaults to -1 to fill all.
                Disables delay.
            delay: Time to wait between each LED update in seconds.
                Ignored if index >= 0. Defaults to manager delay. Overridden by manager delay if too low.
            show: Whether to show the change immediately, or delay until the next show() is called.
                Ignored if delay > 0.
        """
        self._led_manager.set_color(color, index, delay=delay if delay is not None else self.led_delay, show=show)

    def set_colors(
        self,
        colors: list[Colors | ColorUnion],
        delay: float | None = None,
        show: bool = True,
    ) -> None:
        """Set multiple LED colors simultaneously and show change.

        Args:
            colors: New colors to set, one per LED
            delay: Time to wait between each LED update in seconds.
                Ignored if index >= 0. Defaults to manager delay. Overridden by manager delay if too low.
            show: Whether to show the change immediately, or delay until the next show() is called.
                Ignored if delay > 0.
        """
        self._led_manager.set_colors(colors, delay=delay if delay is not None else self.led_delay, show=show)

    def show(self) -> None:
        """Display all pending pixel changes since last show."""
        self._led_manager.show()

    @property
    def status(self) -> int:
        """Return the current status of the manager."""
        return self._status

    @status.setter
    def status(self, status: int) -> None:
        """Safely set the current status of the manager."""
        valid_states = (STATUS_OFF, STATUS_ON)
        if status not in valid_states:
            raise ValueError(f"Valid states are: {valid_states}")
        if status == STATUS_ON and self.mode == MODE_OFF:
            raise ValueError("Status may not be set to on while mode is set to off")
        self._status = status

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
        data[KEY_MODE] = self.mode
        data[KEY_LED_DELAY] = self.led_delay
        if not save_only:
            data[KEY_STATUS] = self.status
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
        name = get_and_validate(new_values, KEY_NAME, expected_type=str)
        if name is not None and name != self.name:
            self.name = name
        mode = get_and_validate(new_values, KEY_MODE, expected_type=int)
        if mode is not None and mode != self.mode:
            self.mode = mode
        led_delay = get_and_validate(new_values, KEY_LED_DELAY, expected_type=float)
        if led_delay is not None:
            self.led_delay = led_delay
        self._led_manager.update(new_values)
        return self.to_json()


class LEDManagers(Collection):
    """Singleton for managing concurrent access to LEDs connected to GPIO pins."""

    _collection: dict[str, LEDManager] = {}
    _collection_lock: threading.Condition = threading.Condition()
    _collection_uri: str = None

    collection_help: str = "LED managers"
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
        delay: float | None = None,
        show: bool = True,
    ) -> None:
        """Set colors and immediately show change.

        Args:
            uuid: ID of the manager to use to send the signal.
            colors: New colors to set, one per pin.
            delay: Time to wait between each LED update in seconds.
                Defaults to manager delay. Overridden by manager delay if too low.
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
    def validate_entry(cls, data: dict, index: int) -> bool:
        """Additional confirmation of entry values before load."""
        if not super().validate_entry(data, index):
            return False
        manager_type = data.get(KEY_TYPE)
        if manager_type.lower() == "neopixel":
            pin = data.get(KEY_PIN)
            for manager in cls._collection:
                if isinstance(manager, micro_managers.NeoPixelManager) and manager.led_pin == pin:
                    logger.warning(f"Skipping duplicate {cls.collection_help} setup at index {index} using pin {pin}")
                    return False
        elif manager_type.lower() == "serial":
            port = data.get(KEY_PORT)
            for manager in cls._collection:
                if isinstance(manager, micro_managers.SerialManager) and manager.port == port:
                    logger.warning(f"Skipping duplicate {cls.collection_help} setup at index {index} using port {port}")
                    return False
        return True
