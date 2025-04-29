"""Utilities for automatically validating and converting properties.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

from __future__ import annotations

import logging
from typing import Any
from typing import Callable

from huereka.shared import responses

logger = logging.getLogger(__name__)

KEY_ID = "id"
KEY_NAME = "name"


class DataProperty:  # pylint: disable=too-few-public-methods
    """Configuration for auto-converting a property from input and to output."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        key: str,
        expected_type: type | tuple[type],
        *,
        default: Any = None,
        choices: list | tuple | None = None,
        nullable: bool = True,
        validator: Callable | None = None,
        error: str = "invalid-value",
        message: str = "Invalid value",
        convert: type | None = None,
        save: bool = True,
        update: bool = True,
    ) -> None:
        """Configure a data property.

        Any validation errors during usage of the property will raise a `APIError`.

        Args:
            key: Name of the value to pull when loading from external data.
            expected_type: Instance type that the value should be, such as int or bool.
            default: Value to use if the key is not found in external data.
                May also be a callable to generate values.
            choices: Possible valid choices.
            nullable: Whether the value is allowed to be null when loading from external data.
                Does not allow None during standard set operations after load.
            validator: Custom function that returns true if the value is valid, false otherwise.
            error: Custom error type that will display if the validator determines the value is invalid.
            message: Custom error message that will display if the validator determines the value is invalid.
            convert: Custom type to convert the value to when loading from external data.
                Also triggers conversion during output.
            save: Whether the value should be included in the output for save requests.
            update: Whether the value is allowed to be updated as part of batch update requests.
        """
        self.key = key
        self.expected_type = expected_type
        self.choices = choices
        self.nullable = nullable
        self.default = default
        self.validator = validator
        self.error = error
        self.message = message
        self.convert = convert
        self.save = save
        self.update = update
        # Used to call setter if validation is performed manually.
        # Set after property declaration, do not allow user control.
        self._validator_bypass: Callable | None = None

    def set_without_validation(self, obj: Any, value: Any) -> None:
        """Call setter without validator if validation was performed manually.

        Args:
            obj: Instance that the value should be set on.
            value: Valid value to pass to the property setter.
        """
        if self._validator_bypass:
            self._validator_bypass(obj, value)  # pylint: disable=not-callable


def data_property(  # pylint: disable=too-many-arguments
    expected_type: type | tuple[type],
    *,
    key: str | None = None,
    default: Any = None,
    choices: list | tuple | None = None,
    nullable: bool = True,
    validator: Callable | None = None,
    error: str = "invalid-value",
    message: str = "Invalid value",
    convert: type | None = None,
    save: bool = True,
    update: bool = True,
) -> Callable:
    """Wrap a property with additional metadata for tracking value conversions.

    Refer to `huereka.shared.properties.DataProperty` for argument details.
    """

    def _wrapper(prop: property) -> property:
        """Update the property configuration and validators."""
        prop_key = key or prop.fget.__name__
        prop.__property_config__ = DataProperty(
            prop_key,
            expected_type,
            default=default,
            choices=choices,
            nullable=nullable,
            validator=validator,
            error=error,
            message=message,
            convert=convert,
            save=save,
            update=update,
        )
        if prop.fset:
            prop.__property_config__._validator_bypass = prop.fset  # pylint: disable=protected-access

            def _setter(self: Any, value: Any) -> Any:
                """Call the property with automatic input validation from the metadata."""
                validate(
                    prop_key,
                    value,
                    expected_type=expected_type,
                    expected_choices=choices,
                    nullable=nullable,
                    validator=validator,
                    validation_error=error,
                    validation_message=message,
                )
                prop.__property_config__.set_without_validation(self, value)

            prop = prop.setter(_setter)
        return prop

    return _wrapper


def get_and_validate(  # Allow complex combinations to validate values consistently. pylint: disable=too-many-arguments
    data: dict,
    key: str,
    *,
    expected_type: type | tuple[type] | None = None,
    expected_choices: list | tuple | None = None,
    nullable: bool = True,
    default: Any = None,
    validator: Callable | None = None,
    validation_error: str = "invalid-value",
    validation_message: str = "Invalid value",
) -> Any:
    """Retrieve and validate a value from configuration data.

    Refer to `huereka.shared.properties.DataProperty` for argument details.
    """
    value = data.get(key, default if not callable(default) else default())
    validate(
        key,
        value,
        expected_type=expected_type,
        expected_choices=expected_choices,
        nullable=nullable,
        validator=validator,
        validation_error=validation_error,
        validation_message=validation_message,
    )
    return value


def validate(  # pylint: disable=too-many-arguments
    key: str,
    value: Any,
    *,
    expected_type: type | tuple[type] = None,
    expected_choices: list | tuple | None = None,
    nullable: bool = True,
    validator: Callable | None = None,
    validation_error: str = "invalid-value",
    validation_message: str = "Invalid value",
) -> None:
    """Validate a value from configuration data, or raise APIError if invalid.

    Refer to `huereka.shared.properties.DataProperty` for argument details.
    """
    if value is None and nullable:
        return
    if value is None:
        raise responses.APIError(
            "not-nullable",
            data={"key": key},
            code=responses.STATUS_INVALID_DATA,
        )
    if expected_type and not isinstance(value, expected_type):
        raise responses.APIError(
            "invalid-type",
            data={
                "key": key,
                "value": value,
                "options": expected_type.__name__
                if not isinstance(expected_type, tuple)
                else [sub_type.__name__ for sub_type in expected_type],
            },
            code=responses.STATUS_INVALID_DATA,
        )
    if expected_choices is not None and value not in expected_choices:
        raise responses.APIError(
            "invalid-choice",
            data={"key": key, "value": value, "options": list(expected_choices)},
            code=responses.STATUS_INVALID_DATA,
        )
    if validator is not None and not validator(value):
        raise responses.APIError(
            validation_error,
            data={"key": key, "value": value, "msg": validation_message},
            code=responses.STATUS_INVALID_DATA,
        )
