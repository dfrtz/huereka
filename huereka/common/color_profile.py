"""Helpers for managing colors and patterns on LED strips."""

from __future__ import annotations

import logging
from typing import Any
from typing import override

from huereka.common import color_utils
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import CollectionValueError
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property

logger = logging.getLogger(__name__)

KEY_COLORS = "colors"
KEY_GAMMA = "gamma"
KEY_MODE = "mode"
KEY_NAME = "name"

MODE_NONE = 0
MODE_REPEAT = 1
MODE_MIRROR = 2
MODE_RANDOM = 4

DEFAULT_PROFILE_OFF = "off"
DEFAULT_GAMMA_CORRECTION = 1.0


@uclass()
class ColorProfile(CollectionEntry):
    """Color profile used to control LED strip."""

    def __init__(
        self,
        name: str,
        uuid: str | None = None,
        colors: list | None = None,
        gamma_correction: float = DEFAULT_GAMMA_CORRECTION,
        mode: int = MODE_REPEAT,
    ) -> None:
        """Set up a color profile for managing LED patterns.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
            colors: Numerical values, or string numerical value, representing raw colors.
            gamma_correction: Gamma correction values to balance LED power to more human comparable levels.
                Quantization will result in less possible values, but balanced. e.g. 2.5 == 172 colors
            mode: Value representing enabled color pattern modes.
                Can be combined via bitwise operations. e.g. MODE_REPEAT | MODE_MIRROR == MODE_REPEAT AND MODE_MIRROR
        """
        super().__init__(uuid=uuid, name=name)
        self._corrected_colors = tuple()
        self._mode = mode
        self._colors: list | None = None

        # Set the current colors, and set a blank corrected colors value so first gamma application updates.
        self.colors = colors
        self._last_corrected_colors = []

        # Update gamma values last so that correct colors are calculated on first application.
        self._gamma_values = tuple()
        self._gamma_correction = 0.0
        self.gamma_correction = gamma_correction

    def __eq__(self, other: Any) -> bool:
        """Make the profile comparable for equality using unique attributes."""
        return (
            isinstance(other, ColorProfile)
            and self.name == other.name
            and self.gamma_correction == other.gamma_correction
            and self.colors == other.colors
            and self._mode == other._mode
        )

    def _set_mode(self, mode: int) -> None:
        """Toggle combination flag for a mode on."""
        self._mode |= mode

    def _unset_mode(self, mode: int) -> None:
        """Toggle combination flag for a mode off."""
        self._mode &= ~mode

    @property
    def colors(self) -> list[color_utils.Color]:
        """Raw colors before color correction is applied."""
        return self._colors

    @data_property(list, validator=lambda items: all(isinstance(item, int) for item in items))
    @colors.setter
    def colors(self, colors: list[int]) -> None:
        """Safely set the raw colors."""
        self._colors = [color_utils.parse_color(color) for color in colors or []]

    def copy(self) -> ColorProfile:
        """Duplicate the Color profile to prevent modifications to the original.

        Returns:
            Deep copy of the profile.
        """
        return ColorProfile(
            name=self.name,
            uuid=self.uuid,
            colors=self.colors.copy(),
            gamma_correction=self.gamma_correction,
            mode=self._mode,
        )

    @property
    def corrected_colors(self) -> tuple:
        """The current gamma corrected colors."""
        if self._last_corrected_colors is not self.colors:
            self._corrected_colors = tuple(
                color_utils.Color.from_rgb(
                    self.gamma_values[color.red], self.gamma_values[color.green], self.gamma_values[color.blue]
                )
                for color in self.colors
            )
            self._last_corrected_colors = self.colors
        return self._corrected_colors

    @property
    def gamma_correction(self) -> float:
        """The current gamma correction value."""
        return self._gamma_correction

    @data_property(float, key=KEY_GAMMA, default=DEFAULT_GAMMA_CORRECTION)
    @gamma_correction.setter
    def gamma_correction(self, value: float) -> None:
        """Update the gamma correction base value and individual corrected values."""
        new_value = round(value, 2)
        if new_value != self._gamma_correction:
            self._gamma_correction = round(value, 2)
            max_input = 255
            max_output = 255
            self._gamma_values = tuple(
                int(pow(i / max_input, self._gamma_correction) * max_output + 0.5) for i in range(max_input + 1)
            )

    @property
    def gamma_values(self) -> tuple:
        """The current gamma corrected values."""
        return self._gamma_values

    @property
    def mirror(self) -> bool:
        """Whether this profile should use mirroring in color patterns."""
        return self._mode & MODE_MIRROR != 0

    @mirror.setter
    def mirror(self, enabled: bool) -> None:
        """Toggle mirror pattern attribute."""
        if enabled:
            self._set_mode(MODE_MIRROR)
        else:
            self._unset_mode(MODE_MIRROR)

    @data_property(int, default=MODE_REPEAT)
    @property
    def mode(self) -> int:
        """Enabled color pattern modes."""
        return self._mode

    @property
    def random(self) -> bool:
        """Whether this profile should use randomization in color patterns."""
        return self._mode & MODE_RANDOM != 0

    @random.setter
    def random(self, enabled: bool) -> None:
        """Toggle randomization pattern attribute."""
        if enabled:
            self._set_mode(MODE_RANDOM)
        else:
            self._unset_mode(MODE_RANDOM)

    @property
    def repeat(self) -> bool:
        """Whether this profile should use repetition in color patterns."""
        return self._mode & MODE_REPEAT != 0

    @repeat.setter
    def repeat(self, enabled: bool) -> None:
        """Toggle repetition pattern attribute."""
        if enabled:
            self._set_mode(MODE_REPEAT)
        else:
            self._unset_mode(MODE_REPEAT)


class ColorProfiles(Collection):
    """Singleton for managing reusable color profiles."""

    collection_help: str = "color profiles"
    entry_cls: str = ColorProfile

    @classmethod
    def post_load(cls) -> None:
        """Actions to perform after load completes."""
        # Always register the default "off" profile.
        cls.register(ColorProfile(DEFAULT_PROFILE_OFF, uuid=DEFAULT_PROFILE_OFF, colors=[]))

    @classmethod
    def update(
        cls,
        entry: str | ColorProfile,
        **values: Any,
    ) -> dict:
        """Update the values of a color profile.

        Args:
            entry: Name of the original profile, or original profile, to update.
            values: New JSON like attributes to set on the profile.

        Returns:
            Final profile configuration with the updated values.
        """
        with cls._collection_lock:
            profile = cls.get(entry)
            name = values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise CollectionValueError("invalid-color_profile-name")
                original_name = profile.name
                profile.name = name
                cls._collection[name] = cls._collection.pop(original_name)
            colors = values.get(KEY_COLORS)
            if colors is not None:
                if not isinstance(colors, list):
                    raise CollectionValueError("invalid-color_profile-colors")
                try:
                    profile.colors = [color_utils.parse_color(color) for color in colors]
                except Exception as error:  # pylint: disable=broad-except
                    raise CollectionValueError("invalid-color_profile-colors") from error
            gamma_correction = values.get(KEY_GAMMA)
            if gamma_correction is not None:
                if not isinstance(gamma_correction, float):
                    raise CollectionValueError("invalid-color_profile-gamma")
                profile.gamma_correction = gamma_correction
            mode = values.get(KEY_MODE)
            if mode is not None:
                if not isinstance(mode, int):
                    raise CollectionValueError("invalid-color_profile-mode")
                if mode == MODE_NONE:
                    profile.mode = MODE_NONE
                else:
                    profile.repeat = mode & MODE_REPEAT != 0
                    profile.mirror = mode & MODE_MIRROR != 0
                    profile.random = mode & MODE_RANDOM != 0
            result = profile.to_json()
        return result

    @classmethod
    @override
    def validate_entry(cls, data: dict, index: int) -> bool:
        if not super().validate_entry(data, index):
            return False
        name = data.get(KEY_NAME)
        if name == DEFAULT_PROFILE_OFF:
            logger.warning(
                f'Skipping stored {cls.collection_help} for "{DEFAULT_PROFILE_OFF}", not allowed to be overridden'
            )
            return False
        return True
