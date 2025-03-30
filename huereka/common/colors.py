"""Helpers for managing user colors."""

from __future__ import annotations

import logging
from typing import Any
from typing import override

from huereka.common import color_utils
from huereka.shared.collections import KEY_NAME
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import CollectionValueError
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property

logger = logging.getLogger(__name__)

KEY_VALUE = "value"


@uclass()
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

    @override
    def to_json(self, save_only: bool = False) -> dict:
        data = super().to_json(save_only=save_only)
        data[KEY_VALUE] = data[KEY_VALUE].to_rgb()
        return data

    @property
    def value(self) -> color_utils.Color:
        """Raw color value."""
        return self._color

    @data_property((str, int, float))
    @value.setter
    def value(self, value: str | int | float) -> None:
        """Update the raw color value."""
        self._color = color_utils.parse_color(value)


class Colors(Collection):
    """Singleton for managing reusable colors."""

    collection_help: str = "colors"
    entry_cls: str = Color

    @classmethod
    @override
    def get(cls, key: str, *, raise_on_missing: bool = False) -> Color | list[Color] | None:
        # Override to update typehint and simplify caller typechecks.
        return super().get(key, raise_on_missing=raise_on_missing)

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
