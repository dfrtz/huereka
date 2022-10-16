"""Helpers for managing colors and patterns on LED strips."""

from __future__ import annotations

import logging
import threading

from typing import Any

from huereka.lib import color_utils
from huereka.lib.collections import Collection
from huereka.lib.collections import CollectionEntry
from huereka.lib.collections import CollectionValueError
from huereka.lib.collections import KEY_ID

logger = logging.getLogger(__name__)

KEY_COLORS = 'colors'
KEY_GAMMA = 'gamma'
KEY_MODE = 'mode'
KEY_NAME = 'name'

MODE_NONE = 0
MODE_REPEAT = 1
MODE_MIRROR = 2
MODE_RANDOM = 4

DEFAULT_PROFILE_OFF = 'off'
DEFAULT_GAMMA_CORRECTION = 1.0


class ColorProfile(CollectionEntry):  # Approved override of the default variable limit. pylint: disable=too-many-instance-attributes
    """Color profile used to control LED strip."""

    def __init__(
            self,
            name: str,
            uuid: str = None,
            colors: list = None,
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
        super().__init__(name, uuid)
        self._corrected_colors = tuple()
        self._mode = mode

        # Set the current colors, and set a blank corrected colors value so first gamma application updates.
        self.colors = [color_utils.parse_color(color) for color in colors or []]
        self._last_corrected_colors = []

        # Update gamma values last so that correct colors are calculated on first application.
        self._gamma_values = tuple()
        self._gamma_correction = 0.0
        self.gamma_correction = gamma_correction

    def __eq__(self, other: Any) -> bool:
        """Make the profile comparable for equality using unique attributes."""
        return isinstance(other, ColorProfile) \
            and self.name == other.name \
            and self.gamma_correction == other.gamma_correction \
            and self.colors == other.colors \
            and self._mode == other._mode

    def _set_mode(self, mode: int) -> None:
        """Toggle combination flag for a mode on."""
        self._mode |= mode

    def _unset_mode(self, mode: int) -> None:
        """Toggle combination flag for a mode off."""
        self._mode &= ~mode

    def copy(self) -> ColorProfile:
        """Duplicate the Color profile to prevent modifications to the original.

        Returns:
            Deep copy of the profile.
        """
        return ColorProfile(
            name=self.name,
            uuid=self.uuid,
            colors=self.colors.copy(),
            mode=self._mode,
        )

    @classmethod
    def from_json(cls, data: dict) -> ColorProfile:
        """Convert JSON type into profile instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated profile with the given attributes.
        """
        # Required arguments.
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise CollectionValueError('invalid-color-profile-name')

        # Optional arguments.
        uuid = data.get(KEY_ID)
        if not isinstance(uuid, str) and uuid is not None:
            raise CollectionValueError('invalid-color-profile-id')
        colors = data.get(KEY_COLORS, [])
        if not isinstance(colors, list):
            raise CollectionValueError('invalid-color-profile-colors')
        try:
            colors = [color_utils.parse_color(color) for color in colors]
        except Exception as error:  # pylint: disable=broad-except
            raise CollectionValueError('invalid-color-profile-colors') from error
        gamma_correction = data.get(KEY_GAMMA, DEFAULT_GAMMA_CORRECTION)
        if not isinstance(gamma_correction, float):
            raise CollectionValueError('invalid-color-profile-gamma')
        mode = data.get(KEY_MODE, MODE_REPEAT)
        if not isinstance(mode, int):
            raise CollectionValueError('invalid-color-profile-mode')

        return ColorProfile(
            name,
            uuid=uuid,
            colors=colors,
            gamma_correction=gamma_correction,
            mode=mode,
        )

    @property
    def corrected_colors(self) -> tuple:
        """The current gamma corrected colors."""
        if self._last_corrected_colors != self.colors:
            self._corrected_colors = tuple(color_utils.Color.from_rgb(
                self.gamma_values[color.red],
                self.gamma_values[color.green],
                self.gamma_values[color.blue]
            ) for color in self.colors)
            self._last_corrected_colors = self.colors.copy()
        return self._corrected_colors

    @property
    def gamma_correction(self) -> float:
        """The current gamma correction value."""
        return self._gamma_correction

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

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_ID: self.uuid,
            KEY_NAME: self.name,
            KEY_COLORS: [color.to_rgb() for color in self.colors],
            KEY_GAMMA: self._gamma_correction,
            KEY_MODE: self._mode,
        }


class ColorProfiles(Collection):
    """Singleton for managing reusable color profiles."""

    _collection: dict[str, ColorProfile] = {}
    _collection_lock: threading.Condition = threading.Condition()
    _collection_uri: str = None

    collection_help: str = 'color profile'
    entry_cls: str = ColorProfile

    @classmethod
    def get(cls, key: str) -> ColorProfile:
        """Find the color profile associated with a given key.

        Override to update typehint and simplify caller typechecks.
        """
        return super().get(key)

    @classmethod
    def post_load(cls) -> None:
        """Actions to perform after load completes."""
        # Always register the default "off" profile.
        cls.register(ColorProfile(DEFAULT_PROFILE_OFF, uuid=DEFAULT_PROFILE_OFF, colors=[]))

    @classmethod
    def update(
            cls,
            old_profile: str,
            new_values: dict,
    ) -> ColorProfile:
        """Update the values of a color profile.

        Args:
            old_profile: Name of the original profile to update.
            new_values: New JSON like attributes to set on the profile.

        Returns:
            Final profile with the updated values.
        """
        with cls._collection_lock:
            profile = cls.get(old_profile)
            name = new_values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise CollectionValueError('invalid-color-profile-name')
                original_name = profile.name
                profile.name = name
                cls._collection[name] = cls._collection.pop(original_name)
            colors = new_values.get(KEY_COLORS)
            if colors is not None:
                if not isinstance(colors, list):
                    raise CollectionValueError('invalid-color-profile-colors')
                try:
                    profile.colors = [color_utils.parse_color(color) for color in colors]
                except Exception as error:  # pylint: disable=broad-except
                    raise CollectionValueError('invalid-color-profile-colors') from error
            gamma_correction = new_values.get(KEY_GAMMA)
            if gamma_correction is not None:
                if not isinstance(gamma_correction, float):
                    raise CollectionValueError('invalid-color-profile-gamma')
                profile.gamma_correction = gamma_correction
            mode = new_values.get(KEY_MODE)
            if mode is not None:
                if not isinstance(mode, int):
                    raise CollectionValueError('invalid-color-profile-mode')
                if mode == MODE_NONE:
                    profile.mode = MODE_NONE
                else:
                    profile.repeat = mode & MODE_REPEAT != 0
                    profile.mirror = mode & MODE_MIRROR != 0
                    profile.random = mode & MODE_RANDOM != 0
        return profile

    @classmethod
    def validate_entry(cls, data: dict, index: int) -> bool:
        """Additional confirmation of entry values before load."""
        name = data.get(KEY_NAME)
        if name == DEFAULT_PROFILE_OFF:
            logger.warning(f'Skipping stored {cls.collection_help} for "{DEFAULT_PROFILE_OFF}", not allowed to be overridden')
            return False
        if name in cls._collection:
            logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using name {name}')
            return False
        return True
