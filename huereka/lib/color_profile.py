"""Helpers for managing colors and patterns on LED strips."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading

from typing import Any
from typing import Dict
from typing import Union

from huereka.lib import response_utils
from huereka.lib import color_utils

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


class ColorProfile:  # Approved override of the default variable limit. pylint: disable=too-many-instance-attributes
    """Color profile used to control LED strip."""

    def __init__(
            self,
            name: str,
            colors: list = None,
            gamma_correction: float = DEFAULT_GAMMA_CORRECTION,
            mode: int = MODE_REPEAT,
    ) -> None:
        """Setup a color profile for managing LED patterns.

        Args:
            name: Human readable name used to store/reference in collections.
            colors: Numerical values, or string numerical value, representing raw colors.
            gamma_correction: Gamma correction values to balance LED power to more human comparable levels.
                Quantization will result in less possible values, but balanced. e.g. 2.5 == 172 colors
            mode: Value representing enabled color pattern modes.
                Can be combined via bitwise operations. e.g. MODE_REPEAT | MODE_MIRROR == MODE_REPEAT AND MODE_MIRROR
        """
        self._corrected_colors = tuple()
        self._mode = mode
        self.name = name

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
            colors=self.colors.copy(),
            mode=self._mode,
        )

    @staticmethod
    def from_json(data: dict) -> ColorProfile:
        """Convert JSON type into profile instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated profile with the given attributes.
        """
        # Required arguments.
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise ColorProfileValueError('invalid-color-profile-name')

        # Optional arguments.
        colors = data.get(KEY_COLORS, [])
        if not isinstance(colors, list):
            raise ColorProfileValueError('invalid-color-profile-colors')
        try:
            colors = [color_utils.parse_color(color) for color in colors]
        except Exception as error:  # pylint: disable=broad-except
            raise ColorProfileValueError('invalid-color-profile-colors') from error
        gamma_correction = data.get(KEY_GAMMA, DEFAULT_GAMMA_CORRECTION)
        if not isinstance(gamma_correction, float):
            raise ColorProfileValueError('invalid-color-profile-gamma')
        mode = data.get(KEY_MODE, MODE_REPEAT)
        if not isinstance(mode, int):
            raise ColorProfileValueError('invalid-color-profile-mode')

        return ColorProfile(
            name,
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

    def to_json(self) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_NAME: self.name,
            KEY_COLORS: [color.to_rgb() for color in self.colors],
            KEY_GAMMA: self._gamma_correction,
            KEY_MODE: self._mode,
        }


class ColorProfileValueError(response_utils.APIError, ValueError):
    """Exception subclass to help identify failures that indicate a profile value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = 422) -> None:
        """Setup the user details of the error."""
        super().__init__(error, data, code=code)


class ColorProfileDuplicate(ColorProfileValueError):
    """Exception subclass to help identify failures that indicate a profile already exists."""

    def __init__(self, profile_name: str) -> None:
        """Setup the user details of the error.

        Args:
            profile_name: Name of the profile that already exists.
        """
        super().__init__('duplicate-color-profile', profile_name, code=422)


class ColorProfileNotFound(ColorProfileValueError):
    """Exception subclass to help identify failures that indicate a profile needs to be created first."""

    def __init__(self, profile_name: str) -> None:
        """Setup the user details of the error.

        Args:
            profile_name: Name of the profile that was not found.
        """
        super().__init__('missing-color-profile', profile_name, code=404)


class ColorProfiles:
    """Singleton for managing reusable color profiles."""

    __profiles__: Dict[str, ColorProfile] = {}
    __profiles_lock__ = threading.Condition()
    __profiles_uri__: str = None

    @classmethod
    def create(
            cls,
            name: str,
            colors: list = None,
            mode: int = MODE_REPEAT,
    ) -> ColorProfile:
        """Setup a color profile for reuse and concurrent access.

        Args:
            name: Human readable name used to store/reference in collections.
            colors: Numerical values, or string numerical value, representing raw colors.
            mode: Value representing enabled color pattern modes.

        Returns:
            New color profile if not already created.

        Raises:
            ColorProfileDuplicate if the profile is already found, indicating it should updated instead.
        """
        with cls.__profiles_lock__:
            if name in cls.__profiles__:
                raise ColorProfileDuplicate(name)
            cls.__profiles__[name] = ColorProfile(
                name,
                colors=colors,
                mode=mode
            )
            return cls.__profiles__[name]

    @classmethod
    def get(cls, name: str) -> ColorProfile:
        """Find the profile associated with a given name, or raise an error message for handling downstream.

        Args:
            name: Name of the saved profile.

        Returns:
            Instance of the profile matching the name.

        Raises:
            ColorProfileNotFound if the profile is not found in persistent storage.
        """
        profile = cls.__profiles__.get(name)
        if not profile:
            raise ColorProfileNotFound(name)
        return profile

    @classmethod
    def load(cls, profile_data: Union[str, list[dict]]) -> None:
        """Initialize the profile cache by loading saved configurations.

        Args:
            profile_data: Profile data to load as JSON string, JSON file path, or pre-structured python objects.
        """
        loaded_data = []
        if isinstance(profile_data, str):
            if profile_data.startswith('['):
                try:
                    loaded_data = json.loads(profile_data)
                except Exception:  # pylint: disable=broad-except
                    logger.exception('Failed to load color profiles from text')
            elif profile_data.startswith(('/', 'file://')):
                profile_data = profile_data.removeprefix('file://')
                cls.__profiles_uri__ = profile_data
                try:
                    with open(profile_data, 'rt', encoding='utf-8') as file_in:
                        try:
                            loaded_data = json.load(file_in)
                            logger.info(f'Loaded color profiles from {cls.__profiles_uri__}')
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(f'Failed to load color profiles from local file {profile_data}')
                except FileNotFoundError:
                    logger.warning(f'Skipping color profiles load, file not found {profile_data}')
        elif isinstance(profile_data, list):
            loaded_data = profile_data
        for index, profile_config in enumerate(loaded_data):
            name = profile_config.get(KEY_NAME)
            if name == DEFAULT_PROFILE_OFF:
                logger.warning(f'Skipping stored color profile for "{DEFAULT_PROFILE_OFF}", not allowed to be overridden')
            if name in cls.__profiles__:
                logger.warning(f'Skipping duplicate color profile setup at index {index} using name {name}')
                continue
            try:
                manager = ColorProfile.from_json(profile_config)
                cls.register(manager)
            except Exception:  # pylint: disable=broad-except
                logger.exception(f'Skipping invalid color profile setup at index {index}')
        # Always register the default "off" profile.
        cls.register(ColorProfile(DEFAULT_PROFILE_OFF, colors=[]))

    @classmethod
    def register(cls, profile: ColorProfile) -> None:
        """Store a profile for concurrent access.

        Args:
            profile: Previously setup color profile to be stored in the cache and used during concurrent calls.
        """
        with cls.__profiles_lock__:
            name = profile.name
            if name in cls.__profiles__:
                raise ColorProfileDuplicate(name)
            cls.__profiles__[name] = profile

    @classmethod
    def remove(cls, name: str) -> ColorProfile:
        """Remove a color profile from persistent storage.

        Args:
            name: Name of the saved profile.

        Raises:
            ProfileNotFound if the profile does not exist and cannot be removed.
        """
        with cls.__profiles_lock__:
            if name not in cls.__profiles__:
                raise ColorProfileNotFound(name)
            return cls.__profiles__.pop(name)

    @classmethod
    def save(cls) -> None:
        """Persist the current profiles to storage."""
        if cls.__profiles_uri__ is not None:
            os.makedirs(os.path.dirname(cls.__profiles_uri__), exist_ok=True)
            with cls.__profiles_lock__:
                # Write to a temporary file, and then move to expected file, so that if for any reason
                # it is interrupted, the original remains intact and the user can decide which to load.
                tmp_path = f'{cls.__profiles_uri__}.tmp'
                with open(tmp_path, 'w+', encoding='utf-8') as file_out:
                    json.dump(cls.to_json(), file_out, indent=2)
                shutil.move(tmp_path, cls.__profiles_uri__)
                logger.info(f'Saved color profiles to {cls.__profiles_uri__}')

    @classmethod
    def to_json(cls) -> list[dict]:
        """Convert all the profiles into JSON compatible types.

        Returns:
            List of profile configurations.
        """
        with cls.__profiles_lock__:
            return [profile.to_json() for profile in cls.__profiles__.values()]

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
        with cls.__profiles_lock__:
            profile = cls.get(old_profile)
            name = new_values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise ColorProfileValueError('invalid-color-profile-name')
                original_name = profile.name
                profile.name = name
                cls.__profiles__[name] = cls.__profiles__.pop(original_name)
            colors = new_values.get(KEY_COLORS)
            if colors is not None:
                if not isinstance(colors, list):
                    raise ColorProfileValueError('invalid-color-profile-colors')
                try:
                    profile.colors = [color_utils.parse_color(color) for color in colors]
                except Exception as error:  # pylint: disable=broad-except
                    raise ColorProfileValueError('invalid-color-profile-colors') from error
            gamma_correction = new_values.get(KEY_GAMMA)
            if gamma_correction is not None:
                if not isinstance(gamma_correction, float):
                    raise ColorProfileValueError('invalid-color-profile-gamma')
                profile.gamma_correction = gamma_correction
            mode = new_values.get(KEY_MODE)
            if mode is not None:
                if not isinstance(mode, int):
                    raise ColorProfileValueError('invalid-color-profile-mode')
                if mode == MODE_NONE:
                    profile.mode = MODE_NONE
                else:
                    profile.repeat = mode & MODE_REPEAT != 0
                    profile.mirror = mode & MODE_MIRROR != 0
                    profile.random = mode & MODE_RANDOM != 0
        return profile
