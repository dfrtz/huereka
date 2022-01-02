"""Helpers for managing user colors."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading

from typing import Any
from typing import Dict

from huereka.lib import response_utils
from huereka.lib import color_utils

logger = logging.getLogger(__name__)

KEY_NAME = 'name'
KEY_VALUE = 'value'

DEFAULT_COLOR_BLACK = 'black'
DEFAULT_COLOR_WHITE = 'white'


class Color:
    """User color preference."""

    def __init__(
            self,
            name: str,
            value: str | int | float,
    ) -> None:
        """Setup a color for saving user selections.

        Args:
            name: Human readable name used to store/reference in collections.
            value: Numerical value, or string numerical value, representing raw color.
        """
        self.name = name
        self._color = color_utils.parse_color(value)

    def __eq__(self, other: Any) -> bool:
        """Make the color comparable for equality using unique attributes."""
        return isinstance(other, Color) \
            and self.name == other.name \
            and self.value == other.value

    @staticmethod
    def from_json(data: dict) -> Color:
        """Convert JSON type into color instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated color with the given attributes.
        """
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise ColorValueError('invalid-color-name')
        value = data.get(KEY_VALUE)
        if value is None or not isinstance(value, (str, int, float)):
            raise ColorValueError('invalid-color-value')
        return Color(name, value)

    def to_json(self) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_NAME: self.name,
            KEY_VALUE: self.value.to_rgb(),
        }

    @property
    def value(self) -> color_utils.Color:
        """Raw color value."""
        return self._color

    @value.setter
    def value(self, value: str | int | float) -> None:
        """Update the raw color value."""
        self._color = color_utils.parse_color(value)


class ColorValueError(response_utils.APIError, ValueError):
    """Exception subclass to help identify failures that indicate a color value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = 422) -> None:
        """Setup the user details of the error."""
        super().__init__(error, data, code=code)


class ColorDuplicate(ColorValueError):
    """Exception subclass to help identify failures that indicate a color already exists."""

    def __init__(self, color_name: str) -> None:
        """Setup the user details of the error.

        Args:
            color_name: Name of the color that already exists.
        """
        super().__init__('duplicate-color', color_name, code=422)


class ColorNotFound(ColorValueError):
    """Exception subclass to help identify failures that indicate a color needs to be created first."""

    def __init__(self, color_name: str) -> None:
        """Setup the user details of the error.

        Args:
            color_name: Name of the color that was not found.
        """
        super().__init__('missing-color', color_name, code=404)


class Colors:
    """Singleton for managing reusable colors."""

    __colors__: Dict[str, Color] = {}
    __colors_lock__ = threading.Condition()
    __colors_uri__: str = None

    @classmethod
    def create(
            cls,
            name: str,
            value: str | int | float,
    ) -> Color:
        """Setup a color for reuse and concurrent access.

        Args:
            name: Human readable name used to store/reference in collections.
            value: Numerical value, or string numerical value, representing raw color.

        Returns:
            New color if not already created.

        Raises:
            ColorDuplicate if the color is already found, indicating it should updated instead.
        """
        with cls.__colors_lock__:
            if name in cls.__colors__:
                raise ColorDuplicate(name)
            cls.__colors__[name] = Color(name, value=value)
            return cls.__colors__[name]

    @classmethod
    def get(cls, name: str) -> Color:
        """Find the color associated with a given name, or raise an error message for handling downstream.

        Args:
            name: Name of the saved color.

        Returns:
            Instance of the color matching the name.

        Raises:
            ColorNotFound if the color is not found in persistent storage.
        """
        color = cls.__colors__.get(name)
        if not color:
            raise ColorNotFound(name)
        return color

    @classmethod
    def load(cls, color_data: str | list[dict]) -> None:
        """Initialize the color cache by loading saved configurations.

        Args:
            color_data: Color data to load as JSON string, JSON file path, or pre-structured python objects.
        """
        loaded_data = []
        if isinstance(color_data, str):
            if color_data.startswith('['):
                try:
                    loaded_data = json.loads(color_data)
                except Exception:  # pylint: disable=broad-except
                    logger.exception('Failed to load colors from text')
            elif color_data.startswith(('/', 'file://')):
                color_data = color_data.removeprefix('file://')
                cls.__colors_uri__ = color_data
                try:
                    with open(color_data, 'rt', encoding='utf-8') as file_in:
                        try:
                            loaded_data = json.load(file_in)
                            logger.info(f'Loaded colors from {cls.__colors_uri__}')
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(f'Failed to load colors from local file {color_data}')
                except FileNotFoundError:
                    logger.warning(f'Skipping colors load, file not found {color_data}')
        elif isinstance(color_data, list):
            loaded_data = color_data
        for index, color_config in enumerate(loaded_data):
            name = color_config.get(KEY_NAME)
            if name == DEFAULT_COLOR_BLACK:
                logger.warning(f'Skipping stored color for "{DEFAULT_COLOR_BLACK}", not allowed to be overridden')
            if name == DEFAULT_COLOR_WHITE:
                logger.warning(f'Skipping stored color for "{DEFAULT_COLOR_WHITE}", not allowed to be overridden')
            if name in cls.__colors__:
                logger.warning(f'Skipping duplicate color setup at index {index}')
                continue
            try:
                manager = Color.from_json(color_config)
                cls.register(manager)
            except Exception:  # pylint: disable=broad-except
                logger.exception(f'Skipping invalid color setup at index {index}')
        # Always register the default colors.
        cls.register(Color(DEFAULT_COLOR_BLACK, value=color_utils.Colors.BLACK.value))
        cls.register(Color(DEFAULT_COLOR_WHITE, value=color_utils.Colors.WHITE.value))

    @classmethod
    def register(cls, color: Color) -> None:
        """Store a color for concurrent access.

        Args:
            color: Previously setup color to be stored in the cache and used during concurrent calls.
        """
        with cls.__colors_lock__:
            name = color.name
            if name in cls.__colors__:
                raise ColorDuplicate(name)
            cls.__colors__[name] = color

    @classmethod
    def remove(cls, name: str) -> Color:
        """Remove a color from persistent storage.

        Args:
            name: Name of the saved color.

        Raises:
            ColorNotFound if the color does not exist and cannot be removed.
        """
        with cls.__colors_lock__:
            if name not in cls.__colors__:
                raise ColorNotFound(name)
            return cls.__colors__.pop(name)

    @classmethod
    def save(cls) -> None:
        """Persist the current colors to storage."""
        if cls.__colors_uri__ is not None:
            os.makedirs(os.path.dirname(cls.__colors_uri__), exist_ok=True)
            with cls.__colors_lock__:
                # Write to a temporary file, and then move to expected file, so that if for any reason
                # it is interrupted, the original remains intact and the user can decide which to load.
                tmp_path = f'{cls.__colors_uri__}.tmp'
                with open(tmp_path, 'w+', encoding='utf-8') as file_out:
                    json.dump(cls.to_json(), file_out, indent=2)
                shutil.move(tmp_path, cls.__colors_uri__)
                logger.info(f'Saved color to {cls.__colors_uri__}')

    @classmethod
    def to_json(cls) -> list[dict]:
        """Convert all the colors into JSON compatible types.

        Returns:
            List of color configurations.
        """
        with cls.__colors_lock__:
            return [color.to_json() for color in cls.__colors__.values()]

    @classmethod
    def update(
            cls,
            old_color: str,
            new_values: dict,
    ) -> Color:
        """Update the values of a color.

        Args:
            old_color: Name of the original color to update.
            new_values: New JSON like attributes to set on the color.

        Returns:
            Final color with the updated values.
        """
        with cls.__colors_lock__:
            color = cls.get(old_color)
            name = new_values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise ColorValueError('invalid-color-name')
                original_name = color.name
                color.name = name
                cls.__colors__[name] = cls.__colors__.pop(original_name)
            value = new_values.get(KEY_VALUE)
            if value is None or not isinstance(value, (str, int, float)):
                raise ColorValueError('invalid-color-value')
            color.value = value
        return color
