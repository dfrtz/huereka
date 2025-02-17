"""Managers for storing and accessing API collections.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

from __future__ import annotations

import abc
import binascii
import json
import logging
import os
import pathlib
from types import TracebackType
from typing import Any
from typing import Callable

from huereka.shared import environments
from huereka.shared import responses

logger = logging.getLogger(__name__)

KEY_ID = "id"
KEY_NAME = "name"


class Collection(abc.ABC):
    """Base singleton class for managing reusable collection entries."""

    # Base values are not implemented here to enforce each class declare concrete instances and not share.

    # Base collection mapping. Should be replaced with: {}
    _collection: dict[str, CollectionEntry] = abc.abstractproperty(dict)
    # Shared lock across threads. Should be replaced with: threading.Condition() or threading.Lock() on systems where
    # multithreading is used, or DisabledCollectionLock() on systems where multithreading is not supported or used.
    _collection_lock: Any = abc.abstractproperty()
    # Location where the collection is stored. Should be replaced with: None
    # First load will set the URI for all future actions.
    _collection_uri: str = abc.abstractproperty(str)

    # Text used when displaying helper/logging messages. e.g. 'user documents'
    collection_help: str = abc.abstractproperty(str)
    # Class used to instantiate entries on load.
    entry_cls: type[CollectionEntry] = abc.abstractproperty(type)

    @classmethod
    def collection_help_api_name(cls) -> str:
        """Provide a consistent, machine/API style, version of the collection help."""
        return cls.collection_help.lower().replace(" ", "_")

    @classmethod
    def get(cls, key: str) -> CollectionEntry:
        """Find the entry associated with a given key.

        Args:
            key: Key used to map saved entry as a unique value in the collection.
                Must match attribute used in register().

        Returns:
            Instance of the entry matching the key.

        Raises:
            APIError if the entry is not found in persistent storage.
        """
        entry = cls._collection.get(key)
        if not entry:
            raise responses.APIError(f"missing-{cls.collection_help_api_name()}", key, code=404)
        return entry

    @classmethod
    def load(cls, data: str | list[dict]) -> tuple[list[CollectionEntry], list[tuple[int, Exception]]]:
        """Initialize the entry cache by loading saved configurations.

        Args:
            data: Collection entry data to load as JSON string, JSON file path, or pre-structured python objects.

        Returns:
            Any entries that auto generated values (such as ID), and any errors that occurred while loading.
        """
        loaded_data = []
        if isinstance(data, str):
            string_result = cls._load_str(data)
            if string_result is not None:
                loaded_data = string_result
        elif isinstance(data, list):
            loaded_data = data
        generated = []
        errors = []
        for index, entry_config in enumerate(loaded_data):
            if not cls.validate_entry(entry_config, index):
                continue
            try:
                entry = cls.entry_cls.from_json(entry_config)
                cls.register(entry)
                if not entry_config.get(KEY_ID):
                    generated.append(entry)
            except Exception as error:  # pylint: disable=broad-except
                errors.append((index, error))
                logger.exception(f"Skipping invalid {cls.collection_help} setup at index {index}", exc_info=error)
        cls.post_load()
        return generated, errors

    @classmethod
    def _load_str(cls, data: str | list[dict]) -> list | None:
        """Load collection configuration from a string."""
        loaded_data = None
        if data.startswith("["):
            try:
                loaded_data = json.loads(data)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(f"Failed to load {cls.collection_help} from text", exc_info=error)
        elif data.startswith("/") or data.startswith("file://"):
            cls._collection_uri = data
            data = data.replace("file://", "")
            try:
                with open(data, "rt", encoding="utf-8") as file_in:
                    try:
                        loaded_data = json.load(file_in)
                        logger.info(f"Loaded {len(loaded_data)} {cls.collection_help} from {cls._collection_uri}")
                    except Exception as error:  # pylint: disable=broad-except
                        logger.exception(f"Failed to load {cls.collection_help} from local file {data}", exc_info=error)
            except OSError as error:
                if error.errno == 2:
                    logger.warning(f"Skipping {cls.collection_help} load, file not found {data}")
                else:
                    raise error
        return loaded_data

    @classmethod
    def post_load(cls) -> None:
        """Actions to perform after load completes."""
        # No actions by default.

    @classmethod
    def register(cls, entry: CollectionEntry) -> None:
        """Store an entry for concurrent access.

        Args:
            entry: Previously setup entry to be stored in the cache and used during concurrent calls.
        """
        with cls._collection_lock:
            uuid = entry.uuid
            if uuid in cls._collection:
                raise responses.APIError(f"duplicate-{cls.collection_help_api_name()}", uuid, code=422)
            cls._collection[uuid] = entry
            logger.debug(f"Registered {cls.collection_help} {entry.uuid} {entry.name}")

    @classmethod
    def remove(cls, key: str) -> CollectionEntry:
        """Remove an entry from persistent storage.

        Args:
            key: ID of the saved entry.

        Raises:
            APIError if the entry does not exist and cannot be removed.
        """
        with cls._collection_lock:
            if key not in cls._collection:
                raise responses.APIError(f"missing-{cls.collection_help_api_name()}", key, code=404)
            return cls._collection.pop(key)

    @classmethod
    def save(cls) -> None:
        """Persist the current entries to storage."""
        if cls._collection_uri is not None:
            uri = cls._collection_uri
            if uri.startswith("/") or uri.startswith("file://"):
                uri = uri.replace("file://", "")

                path = pathlib.Path(uri)
                path.parent.mkdir(parents=True, exist_ok=True)

                with cls._collection_lock:
                    # Write to a temporary file, and then move to expected file, so that if for any reason
                    # it is interrupted, the original remains intact and the user can decide which to load.
                    tmp_path = f"{uri}.tmp"
                    with open(tmp_path, "w+", encoding="utf-8") as file_out:
                        # Use pretty-print in standard environments to simplify manual reviews of collections,
                        # since their collections are typically large. MicroPython does not support pretty-printing.
                        if environments.is_micro_python():
                            json.dump(cls.to_json(save_only=True), file_out)
                        else:
                            json.dump(cls.to_json(save_only=True), file_out, indent=2)
                    os.rename(tmp_path, uri)
                    logger.info(f"Saved {cls.collection_help} to {uri}")

    @classmethod
    def teardown(cls) -> None:
        """Clear all states, and release resources."""

    @classmethod
    def to_json(cls, save_only: bool = False) -> list[dict]:
        """Convert all the entries into JSON compatible types.

        Args:
            save_only: Whether to only include values that are meant to be saved.

        Returns:
            List of entries as basic objects.
        """
        with cls._collection_lock:
            return [entry.to_json(save_only=save_only) for entry in cls._collection.values()]

    @classmethod
    def update(
        cls,
        uuid: str,
        new_values: dict,
    ) -> dict:
        """Update the values of an entry.

        Args:
            uuid: ID of the original entry to update.
            new_values: New attributes to set on the entry.

        Returns:
            Final configuration with the updated values.
        """
        with cls._collection_lock:
            result = cls.get(uuid).update(new_values)
        return result

    @classmethod
    def validate_entry(
        cls,
        data: dict,
        index: int,
    ) -> bool:
        """Additional confirmation of entry values before load.

        Args:
            data: Original data to check for valid values.
            index: Position of the entry in the source where it is being loaded from.

        Returns:
            True if the load should continue, False if it should be skipped.
        """
        uuid = data.get(KEY_ID)
        if uuid in cls._collection:
            logger.warning(f"Skipping duplicate {cls.collection_help} setup at index {index} using uuid {uuid}")
            return False
        return True


class CollectionEntry(abc.ABC):
    """Base for loading and storing collection entries."""

    def __init__(self, uuid: str | None = None, name: str | None = None) -> None:
        """Set up the base collection entry values.

        Args:
            uuid: Universally unique identifier.
            name: Human readable name used to store/reference in collections.
        """
        self.uuid = uuid if uuid else str(uuid4())
        self.name = name or f"{self.__class__.__name__}_{self.uuid}"

    def __hash__(self) -> int:
        """Make the collection hashable."""
        return hash(self.uuid)

    def __gt__(self, other: Any) -> bool:
        """Make the collection comparable for greater than operations by name."""
        return isinstance(other, self.__class__) and self.name > other.name

    def __lt__(self, other: Any) -> bool:
        """Make the collection comparable for less than operations by name."""
        return isinstance(other, self.__class__) and self.name < other.name

    @classmethod
    @abc.abstractmethod
    def from_json(cls, data: dict) -> CollectionEntry:
        """Convert JSON type into collection entry instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated entry with the given attributes.
        """

    def to_json(
        self,
        save_only: bool = False,  # Used by subclasses. pylint: disable=unused-argument
    ) -> dict:
        """Convert the entry into a JSON compatible type.

        Args:
            save_only: Whether to only include values that are meant to be saved.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_ID: self.uuid,
            KEY_NAME: self.name,
        }

    def update(
        self,
        new_values: dict,
    ) -> dict:
        """Update the values of an entry.

        Args:
            new_values: New attributes to set on the entry.

        Returns:
            Final configuration with the updated values.

        Raises:
            CollectionValueError if the class does not allow updates.
        """
        raise CollectionValueError("no-updates-allowed", code=responses.STATUS_INVALID_DATA)


class CollectionValueError(responses.APIError):
    """Exception subclass to help identify failures that indicate a collection entry value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = responses.STATUS_INVALID_DATA) -> None:
        """Set up the user details of the error."""
        super().__init__(error, data, code=code)


class DisabledCollectionLock:
    """Simulated lock object without locking capabilities to allow collection usage in various environments.

    Prefer to use threading.Lock where possible. Using this will remove all multithreading safety from the object,
    and require access to be manually protected by callers.
    """

    def __enter__(self) -> DisabledCollectionLock:
        """Placeholder to return this instance when lock context is entered."""
        return self

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType) -> None:
        """Placeholder for exit actions when lock context is exited."""


def get_and_validate(  # Allow complex combinations to validate values consistently. pylint: disable=too-many-arguments
    data: dict,
    key: str,
    *,
    expected_type: type | None = None,
    expected_choices: list | tuple | None = None,
    nullable: bool = True,
    default: Any = None,
    validator: Callable | None = None,
    validation_error: str = "invalid-value",
    validation_message: str = "Invalid value",
) -> Any:
    """Retrieve and validate data.

    Args:
        data: Mapping of key value pairs available to a collection.
        key: Name of the value to pull from the data.
        expected_type: Instance type that the value should be, such as int or bool.
        expected_choices: Possible valid choices.
        nullable: Whether the value is allowed to be null.
        default: Value to use if the key is not found in the data.
        validator: Custom function that returns true if the value is valid, false otherwise.
        validation_error: Custom error type that will display if the custom validator fails validation.
        validation_message: Custom error message that will display if the custom validator fails validation.

    Returns:
        Final value pulled from the data if valid.

    Raises:
        CollectionValueError if the data fails to meet all the required criteria.
    """
    value = data.get(key, default)
    if value is None and nullable:
        return value
    if value is None:
        raise CollectionValueError(
            "not-nullable",
            data={
                "key": key,
            },
        )
    if expected_type is not None and not isinstance(value, expected_type):
        raise CollectionValueError(
            "invalid-type",
            data={
                "key": key,
                "value": value,
                "options": str(expected_type),
            },
        )
    if expected_choices is not None and value not in expected_choices:
        raise CollectionValueError(
            "invalid-choice",
            data={
                "key": key,
                "value": value,
                "options": list(expected_choices),
            },
        )
    if validator is not None and not validator(value):
        raise CollectionValueError(
            validation_error,
            data={
                "key": key,
                "value": value,
                "msg": validation_message,
            },
        )
    return value


def uuid4() -> str:
    """Generate a random RFC 4122 compliant UUID.

    Returns:
        128 bit (16 byte) Universally Unique IDentifier.
    """
    random = bytearray(os.urandom(16))
    random[6] = (random[6] & 0x0F) | 0x40
    random[8] = (random[8] & 0x3F) | 0x80
    hex_values = binascii.hexlify(random).decode()
    uuid = "-".join(
        (
            hex_values[0:8],
            hex_values[8:12],
            hex_values[12:16],
            hex_values[16:20],
            hex_values[20:32],
        )
    )
    return uuid
