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

from huereka.lib import response_utils

logger = logging.getLogger(__name__)


class Collection(metaclass=abc.ABCMeta):
    """Base singleton class for managing reusable collection entries in a thread safe manner."""

    # Abstract here to enforce each class declare and not share. Should be replaced with: {}
    _collection: dict[Any, CollectionEntry] = abc.abstractproperty()
    # Abstract here to enforce each class declare and not share. Should be replaced with: threading.Condition()
    _collection_lock: threading.Condition = abc.abstractproperty()
    # Abstract here to enforce each class declare and not share. Should be replaced with: None
    _collection_uri: str = abc.abstractproperty(str)

    # Text used when display helper/logging messages. e.g. 'user documents'
    collection_help: str = abc.abstractproperty(str)
    # Class used to instantiate entries on load.
    entry_cls: Type[CollectionEntry] = abc.abstractproperty()

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
            raise response_utils.APIError(f'missing-{cls.collection_help.replace(" ", "-")}', key, code=404)
        return entry

    @classmethod
    def load(cls, data: str | list[dict]) -> None:
        """Initialize the entry cache by loading saved configurations.

        Args:
            data: Collection entry data to load as JSON string, JSON file path, or pre-structured python objects.
        """
        loaded_data = []
        if isinstance(data, str):
            if data.startswith('['):
                try:
                    loaded_data = json.loads(data)
                except Exception:  # pylint: disable=broad-except
                    logger.exception(f'Failed to load {cls.collection_help}s from text')
            elif data.startswith(('/', 'file://')):
                data = data.removeprefix('file://')
                cls._collection_uri = data
                try:
                    with open(data, 'rt', encoding='utf-8') as file_in:
                        try:
                            loaded_data = json.load(file_in)
                            logger.info(f'Loaded {cls.collection_help}s from {cls._collection_uri}')
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(f'Failed to load {cls.collection_help}s from local file {data}')
                except FileNotFoundError:
                    logger.warning(f'Skipping {cls.collection_help}s load, file not found {data}')
        elif isinstance(data, list):
            loaded_data = data
        for index, entry_config in enumerate(loaded_data):
            if not cls.validate_entry(entry_config, index):
                continue
            try:
                entry = cls.entry_cls.from_json(entry_config)
                cls.register(entry)
            except Exception:  # pylint: disable=broad-except
                logger.exception(f'Skipping invalid {cls.collection_help} setup at index {index}')
        cls.post_load()

    @classmethod
    def post_load(cls) -> None:
        """Actions to perform after load completes."""
        # No actions by default.

    @classmethod
    def register(cls, entry: Any) -> None:
        """Store an entry for concurrent access.

        Args:
            entry: Previously setup entry to be stored in the cache and used during concurrent calls.
        """
        with cls._collection_lock:
            name = entry.name
            if name in cls._collection:
                raise response_utils.APIError(f'duplicate-{cls.collection_help.replace(" ", "-")}', name, code=422)
            cls._collection[name] = entry

    @classmethod
    def remove(cls, key: str) -> CollectionEntry:
        """Remove an entry from persistent storage.

        Args:
            key: Name of the saved entry.

        Raises:
            APIError if the entry does not exist and cannot be removed.
        """
        with cls._collection_lock:
            if key not in cls._collection:
                raise response_utils.APIError(f'missing-{cls.collection_help.replace(" ", "-")}', key, code=404)
            return cls._collection.pop(key)

    @classmethod
    def save(cls) -> None:
        """Persist the current entries to storage."""
        if cls._collection_uri is not None:
            os.makedirs(os.path.dirname(cls._collection_uri), exist_ok=True)
            with cls._collection_lock:
                # Write to a temporary file, and then move to expected file, so that if for any reason
                # it is interrupted, the original remains intact and the user can decide which to load.
                tmp_path = f'{cls._collection_uri}.tmp'
                with open(tmp_path, 'w+', encoding='utf-8') as file_out:
                    json.dump(cls.to_json(), file_out, indent=2)
                shutil.move(tmp_path, cls._collection_uri)
                logger.info(f'Saved {cls.collection_help}s to {cls._collection_uri}')

    @classmethod
    def to_json(cls) -> list[dict]:
        """Convert all the entries into JSON compatible types.

        Returns:
            List of entries as basic objects.
        """
        with cls._collection_lock:
            return [entry.to_json() for entry in cls._collection.values()]

    @classmethod
    def validate_entry(
            cls,
            data: dict,  # Argument used by subclass. pylint: disable=unused-argument
            index: int,  # Argument used by subclass. pylint: disable=unused-argument
    ) -> bool:
        """Additional confirmation of entry values before load.

        Args:
            data: Original data to check for valid values.
            index: Position of the entry in the source where it is being loaded from.

        Returns:
            True if the load should continue, False if it should be skipped.
        """
        # No extra validation performed by default.
        return True


class CollectionEntry:
    """Base class for loading and storing collection entries."""

    @classmethod
    @abc.abstractmethod
    def from_json(cls, data: dict) -> CollectionEntry:
        """Convert JSON type into collection entry instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated entry with the given attributes.
        """

    def to_json(self) -> dict:
        """Convert the entry into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """


class CollectionValueError(response_utils.APIError, ValueError):
    """Exception subclass to help identify failures that indicate a collection entry value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = 422) -> None:
        """Setup the user details of the error."""
        super().__init__(error, data, code=code)
