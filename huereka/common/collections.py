"""Thread safe helpers for managing API collections."""

from __future__ import annotations

import abc
import json
import logging
import os
import shutil
import threading
from typing import Any
from typing import Type
from uuid import uuid4

from huereka.common import response_utils

logger = logging.getLogger(__name__)

KEY_ID = "id"
KEY_NAME = "name"


class Collection(metaclass=abc.ABCMeta):
    """Base singleton class for managing reusable collection entries in a thread safe manner."""

    # Abstract here to enforce each class declare and not share. Should be replaced with: {}
    _collection: dict[str, CollectionEntry] = abc.abstractproperty()
    # Abstract here to enforce each class declare and not share. Should be replaced with: threading.Condition()
    _collection_lock: threading.Condition = abc.abstractproperty()
    # Abstract here to enforce each class declare and not share. Should be replaced with: None
    # First load will set the URI for all future actions.
    _collection_uri: str = abc.abstractproperty(str)

    # Text used when display helper/logging messages. e.g. 'user documents'
    collection_help: str = abc.abstractproperty(str)
    # Class used to instantiate entries on load.
    entry_cls: Type[CollectionEntry] = abc.abstractproperty()

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
            raise response_utils.APIError(f'missing-{cls.collection_help_api_name()}', key, code=404)
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
            if data.startswith("["):
                try:
                    loaded_data = json.loads(data)
                except Exception:  # pylint: disable=broad-except
                    logger.exception(f"Failed to load {cls.collection_help} from text")
            elif data.startswith(("/", "file://")):
                cls._collection_uri = data
                data = data.removeprefix("file://")
                try:
                    with open(data, "rt", encoding="utf-8") as file_in:
                        try:
                            loaded_data = json.load(file_in)
                            logger.info(f"Loaded {cls.collection_help} from {cls._collection_uri}")
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(f"Failed to load {cls.collection_help} from local file {data}")
                except FileNotFoundError:
                    logger.warning(f"Skipping {cls.collection_help} load, file not found {data}")
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
                logger.exception(f"Skipping invalid {cls.collection_help} setup at index {index}")
        cls.post_load()
        return generated, errors

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
                raise response_utils.APIError(f'duplicate-{cls.collection_help_api_name()}', uuid, code=422)
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
                raise response_utils.APIError(f'missing-{cls.collection_help_api_name()}', key, code=404)
            return cls._collection.pop(key)

    @classmethod
    def save(cls) -> None:
        """Persist the current entries to storage."""
        if cls._collection_uri is not None:
            uri = cls._collection_uri
            if uri.startswith(("/", "file://")):
                uri = uri.removeprefix("file://")
                os.makedirs(os.path.dirname(uri), exist_ok=True)
                with cls._collection_lock:
                    # Write to a temporary file, and then move to expected file, so that if for any reason
                    # it is interrupted, the original remains intact and the user can decide which to load.
                    tmp_path = f"{uri}.tmp"
                    with open(tmp_path, "w+", encoding="utf-8") as file_out:
                        json.dump(cls.to_json(save_only=True), file_out, indent=2)
                    shutil.move(tmp_path, uri)
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


class CollectionEntry:
    """Base class for loading and storing collection entries."""

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

    def to_json(self, save_only: bool = False) -> dict:
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
        """
        raise NotImplemented(f"{self.__class__} does not allow updates")


class CollectionValueError(response_utils.APIError, ValueError):
    """Exception subclass to help identify failures that indicate a collection entry value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = 422) -> None:
        """Set up the user details of the error."""
        super().__init__(error, data, code=code)


def get_and_validate(
    data: dict,
    key: str,
    expected_type: Any,
    nullable: bool = False,
    error_prefix: str = "invalid",
) -> Any:
    """Retrieve data and validate type.

    Args:
        data: Mapping of key value pairs available to a collection.
        key: Name of the value to pull from the data.
        expected_type: Instance type that the value should be, such as int or bool.
        nullable: Whether the value is allowed to be null.
        error_prefix: Prefix to add to the exception message if the value is invalid.

    Returns:
        Final value pulled from the data if valid.

    Raises:
        CollectionValueError if the data type is invalid.
    """
    value = data.get(key)
    if (value is None and not nullable) or (value is not None and not isinstance(value, expected_type)):
        raise CollectionValueError(f"{error_prefix}-{key}")
    return value
