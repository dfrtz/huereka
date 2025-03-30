"""Helpers for managing brightness and colors on LED strips."""

from __future__ import annotations

import logging
from typing import Sequence
from typing import override

from adafruit_pixelbuf import ColorUnion

from huereka.common import micro_managers
from huereka.common.color_utils import Colors
from huereka.common.micro_managers import KEY_PIN
from huereka.common.micro_managers import KEY_PORT
from huereka.common.micro_managers import KEY_TYPE
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import CollectionValueError
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property

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


@uclass()
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
        micromanager: micro_managers.LEDMicroManager | None = None,
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
        self._led_delay = 0.0
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
    @override
    def from_json(cls, data: dict) -> LEDManager:
        manager_type = data.get(KEY_TYPE)
        if not isinstance(manager_type, str) or manager_type.lower() not in ("neopixel", "serial"):
            raise CollectionValueError("invalid-led_manager-type")
        micromanager = None
        if manager_type.lower() == "neopixel":
            micromanager = micro_managers.NeoPixelManager.from_json(data)
        elif manager_type.lower() == "serial":
            micromanager = micro_managers.SerialManager.from_json(data)
        manager = super().from_json(data)
        manager._led_manager = micromanager  # pylint: disable=protected-access
        return manager

    def off(self, show: bool = True) -> None:
        """Helper to disable (reduce brightness to 0) and immediately show change.

        Args:
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        self._led_manager.off(show=show)

    @property
    def led_delay(self) -> float:
        """Minimum time delay allowed in seconds between individual LED updates during animations."""
        return self._led_delay

    @data_property(float, default=DEFAULT_LED_UPDATE_DELAY)
    @led_delay.setter
    def led_delay(self, led_delay: int) -> None:
        """Safely set the minimum time delay allowed in seconds between individual LED updates during animations."""
        self._led_delay = led_delay

    @property
    def mode(self) -> int:
        """Return the current mode set on the manager."""
        return self._mode

    @data_property(int, default=MODE_OFF, choices=(MODE_OFF, MODE_ON))
    @mode.setter
    def mode(self, mode: int) -> None:
        """Safely set the current mode of the manager."""
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

    @data_property(int, choices=(STATUS_OFF, STATUS_ON), save=False, update=False)
    @status.setter
    def status(self, status: int) -> None:
        """Safely set the current status of the manager."""
        if status == STATUS_ON and self.mode == MODE_OFF:
            raise ValueError("Status may not be set to on while mode is set to off")
        self._status = status

    def teardown(self) -> None:
        """Clear LED states, and release resources.

        Manager should not be reused after teardown.
        """
        self._led_manager.teardown()

    @override
    def to_json(self, save_only: bool = False) -> dict:
        return self._led_manager.to_json(save_only=save_only) | super().to_json(save_only=save_only)

    @override
    def update(
        self,
        new_values: dict,
    ) -> dict:
        self._led_manager.update(new_values)
        return self.to_json()


class LEDManagers(Collection):
    """Singleton for managing concurrent access to LEDs connected to GPIO pins."""

    collection_help: str = "LED managers"
    entry_cls: str = LEDManager

    @classmethod
    @override
    def get(cls, key: str, *, raise_on_missing: bool = False) -> LEDManager | list[LEDManager] | None:
        # Override to update typehint and simplify caller typechecks.
        return super().get(key, raise_on_missing=raise_on_missing)

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
    @override
    def validate_entry(cls, data: dict, index: int) -> bool:
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
