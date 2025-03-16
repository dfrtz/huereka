"""Helpers for managing user colors."""

from __future__ import annotations

import logging
from typing import Any

from huereka.common import color_utils
from huereka.shared.collections import KEY_ID
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import CollectionValueError

logger = logging.getLogger(__name__)

KEY_NAME = "name"
KEY_VALUE = "value"


class Color(CollectionEntry):
    """User color preference."""

    def __init__(
        self,
        name: str,
        value: str | int | float,
        uuid: str = None,
    ) -> None:
        """Set up a color for saving user selections.

        Args:
            name: Human readable name used to store/reference in collections.
            value: Numerical value, or string numerical value, representing raw color.
            uuid: Unique identifier.
        """
        super().__init__(uuid=uuid, name=name)
        self._color = color_utils.parse_color(value)

    def __eq__(self, other: Any) -> bool:
        """Make the color comparable for equality using unique attributes."""
        return isinstance(other, Color) and self.name == other.name and self.value == other.value

    @classmethod
    def from_json(cls, data: dict) -> Color:
        """Convert JSON type into color instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated color with the given attributes.
        """
        uuid = data.get(KEY_ID)
        if not isinstance(uuid, str) and uuid is not None:
            raise CollectionValueError("invalid-color-id")
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise CollectionValueError("invalid-color-name")
        value = data.get(KEY_VALUE)
        if value is None or not isinstance(value, (str, int, float)):
            raise CollectionValueError("invalid-color-value")
        return Color(name, value)

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_ID: self.uuid,
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

    collection_help: str = "colors"
    entry_cls: str = Color

    @classmethod
    def get(cls, key: str) -> Color:
        """Find the color associated with a given key.

        Override to update typehint and simplify caller typechecks.
        """
        return super().get(key)

    @classmethod
    def update(
        cls,
        uuid: str,
        new_values: dict,
    ) -> dict:
        """Update the values of a color.

        Args:
            uuid: Name of the original color to update.
            new_values: New JSON like attributes to set on the color.

        Returns:
            Final color configuration with the updated values.
        """
        with cls._collection_lock:
            color = cls.get(uuid)
            name = new_values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise CollectionValueError("invalid-color-name")
                original_name = color.name
                color.name = name
                cls._collection[name] = cls._collection.pop(original_name)
            value = new_values.get(KEY_VALUE)
            if value is None or not isinstance(value, (str, int, float)):
                raise CollectionValueError("invalid-color-value")
            color.value = value
            result = color.to_json()
        return result
