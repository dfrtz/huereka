"""Helpers for managing user colors."""

from __future__ import annotations

import logging
import threading

from typing import Any

from huereka.lib import color_utils
from huereka.lib.collections import Collection
from huereka.lib.collections import CollectionEntry
from huereka.lib.collections import CollectionValueError

logger = logging.getLogger(__name__)

KEY_NAME = 'name'
KEY_VALUE = 'value'

DEFAULT_COLOR_BLACK = 'black'
DEFAULT_COLOR_WHITE = 'white'


class Color(CollectionEntry):
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

    @classmethod
    def from_json(cls, data: dict) -> Color:
        """Convert JSON type into color instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated color with the given attributes.
        """
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise CollectionValueError('invalid-color-name')
        value = data.get(KEY_VALUE)
        if value is None or not isinstance(value, (str, int, float)):
            raise CollectionValueError('invalid-color-value')
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


class Colors(Collection):
    """Singleton for managing reusable colors."""

    _collection: dict[str, Color] = {}
    _collection_lock: threading.Condition = threading.Condition()
    _collection_uri: str = None

    collection_help: str = 'color'
    entry_cls: str = Color

    @classmethod
    def get(cls, key: str) -> Color:
        """Find the color associated with a given key.

        Override to update typehint and simplify caller typechecks.
        """
        return super().get(key)

    @classmethod
    def post_load(cls) -> None:
        """Actions to perform after load completes."""
        # Always register the default colors.
        cls.register(Color(DEFAULT_COLOR_BLACK, value=color_utils.Colors.BLACK.value))
        cls.register(Color(DEFAULT_COLOR_WHITE, value=color_utils.Colors.WHITE.value))

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
        with cls._collection_lock:
            color = cls.get(old_color)
            name = new_values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise CollectionValueError('invalid-color-name')
                original_name = color.name
                color.name = name
                cls._collection[name] = cls._collection.pop(original_name)
            value = new_values.get(KEY_VALUE)
            if value is None or not isinstance(value, (str, int, float)):
                raise CollectionValueError('invalid-color-value')
            color.value = value
        return color

    @classmethod
    def validate_entry(cls, data: dict, index: int) -> bool:
        """Additional confirmation of entry values before load."""
        name = data.get(KEY_NAME)
        if name == DEFAULT_COLOR_BLACK:
            logger.warning(f'Skipping stored color for "{DEFAULT_COLOR_BLACK}", not allowed to be overridden')
        if name == DEFAULT_COLOR_WHITE:
            logger.warning(f'Skipping stored color for "{DEFAULT_COLOR_WHITE}", not allowed to be overridden')
        if name in cls._collection:
            logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using name {name}')
            return False
        return True