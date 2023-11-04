"""Shared libraries for low level control of brightness and colors on LED strips."""

from __future__ import annotations

import abc
import logging
import threading
import time
from typing import Sequence

from adafruit_pixelbuf import ColorUnion

from huereka.common import color_utils
from huereka.common.color_utils import Colors

logger = logging.getLogger(__name__)

# Based on max speed without flickering on a 12V strand of 100 WS2811 LEDs with 5V signal.
DEFAULT_LED_UPDATE_DELAY = 0.0125
KEY_LED_COUNT = "led_count"
KEY_BRIGHTNESS = "brightness"
KEY_TYPE = "type"
KEY_PIN = "pin"


class LEDMicroManager(metaclass=abc.ABCMeta):
    """Base class for controlling LEDs in a common way across hardware types."""

    def __init__(
        self,
        brightness: float = 1.0,
    ) -> None:
        """Set up a single LED chain/strip.

        Args:
            brightness: Initial brightness as a percent between 0.0 and 1.0.
        """
        super().__init__()
        self._lock = threading.Condition()
        self._brightness = brightness

    @abc.abstractmethod
    def __getitem__(self, index: int | slice) -> int:
        """Find LED color at a specific LED position."""

    @abc.abstractmethod
    def __len__(self) -> int:
        """Number of controlled pixels."""

    @abc.abstractmethod
    def __setitem__(
        self,
        index: int | slice,
        color: Colors | ColorUnion | Sequence[ColorUnion],
    ) -> None:
        """Set color at a specific LED position.

        Should not call show() to allow optimizing batch calls. To show at same time, use _set_color().
        """

    def _set_color(
        self,
        index: int,
        color: Colors | ColorUnion,
        show: bool = True,
    ) -> bool:
        """Set color at a specific LED position, show change, and return true if color was changed.

        Alias for index operator and call to show() if requested. Override if show can be combined with set.
        """
        changed = False
        color = color_utils.parse_color(color)
        with self._lock:
            if self[index] != color:
                changed = True
                self[index] = color
                if show:
                    self.show()
        return changed

    @property
    def brightness(self) -> float:
        """Current brightness as a percent between 0.0 and 1.0."""
        return self._brightness

    @abc.abstractmethod
    def fill(
        self,
        color: Colors | ColorUnion,
        show: bool = True,
    ) -> None:
        """Fill entire strip with a single color.

        Args:
            color: Color to fill every LED in the strip with.
            show: Whether to show the change immediately, or delay until the next show() is called.
        """

    @classmethod
    @abc.abstractmethod
    def from_json(cls, data: dict) -> LEDMicroManager:
        """Convert JSON data into an LED micromanager.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated manager with the given attributes.
        """

    def off(self, show: bool = True) -> None:
        """Helper to disable (reduce brightness to 0) and immediately show change.

        Args:
            show: Whether to show the change immediately, or delay until the next show() is called.
        """
        self.set_brightness(0, show=show)

    @abc.abstractmethod
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
            with self._lock:
                self._set_color(index, color, show=show)
        else:
            if delay:

                def _set_color() -> None:
                    for led, _ in enumerate(self):
                        with self._lock:
                            self._set_color(led, color, show=True)
                        time.sleep(delay)

                threading.Thread(target=_set_color, daemon=True).start()
            else:
                with self._lock:
                    self.fill(color, show=show)

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
                for led, led_color in enumerate(colors):
                    with self._lock:
                        self._set_color(led, led_color, show=True)
                    time.sleep(delay)

            threading.Thread(target=_set_color, daemon=True).start()
        else:
            with self._lock:
                if all(color == colors[0] for color in colors):
                    self.fill(colors[0], show=show)
                else:
                    for index, color in enumerate(colors):
                        self[index] = color
                    if show:
                        self.show()

    @abc.abstractmethod
    def show(self) -> None:
        """Display all pending pixel changes since last show."""

    @abc.abstractmethod
    def teardown(self) -> None:
        """Clear LED states, and release resources.

        Manager should not be reused after teardown.
        """

    @abc.abstractmethod
    def to_json(self, save_only: bool = False) -> dict:
        """Convert the LED micromanager into a JSON compatible metadata structure.

        Args:
            save_only: Whether to only include values that are meant to be saved.

        Returns:
            Mapping of the instance attributes.
        """

    @abc.abstractmethod
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
