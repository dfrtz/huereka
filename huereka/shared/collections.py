"""Managers for storing and accessing API collections.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

from __future__ import annotations

import abc
import asyncio
import binascii
import json
import logging
import os
from collections import OrderedDict
from types import TracebackType
from typing import Any
from typing import Generator

from huereka.shared import file_utils
from huereka.shared import micro_utils
from huereka.shared import responses
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.properties import DataProperty
from huereka.shared.properties import data_property
from huereka.shared.properties import get_and_validate
from huereka.shared.properties import validate

logger = logging.getLogger(__name__)

KEY_ID = "id"
KEY_NAME = "name"


class Collection(abc.ABC):
    """Base singleton class for managing reusable collection entries."""

    # Base values are not implemented here to enforce each class declare concrete instances and not share.
    # On subclass init/declarations, they will be set to ensure no sharing across subtypes.

    _collection: OrderedDict[str, CollectionEntry]
    """Base collection mapping."""
    # Use OrderedDict for MicroPython compatibility.

    _collection_lock: CollectionLock
    """Shared lock across threads and coroutines (depending on environment)."""

    _collection_uri: str | None
    """Location where the collection is stored."""
    # First load will set the URI for all future actions.

    collection_help: str = abc.abstractproperty()
    """Text used when displaying helper/logging messages. e.g. 'user documents'"""

    entry_cls: type[CollectionEntry] = abc.abstractproperty(type)
    """Class used to instantiate entries on load."""

    @classmethod
    def __init_subclass__(cls) -> None:
        """Initialize the subclass properties on declaration to prevent sharing with other subclass singletons."""
        cls._collection = OrderedDict()
        cls._collection_lock = CollectionLock()
        cls._collection_uri = None

    @classmethod
    def collection_help_api_name(cls) -> str:
        """Provide a consistent, machine/API style, version of the collection help."""
        return cls.collection_help.lower().replace(" ", "_")

    @classmethod
    def get(
        cls,
        key: str | None,
        *,
        raise_on_missing: bool = True,
    ) -> CollectionEntry | dict[str, CollectionEntry] | None:
        """Find the entry associated with a given key.

        Args:
            key: Key used to map saved entry as a unique value in the collection.
                Must match attribute used in register(). Providing no key will return full collection.
            raise_on_missing: Whether to raise an API error if no entry found.

        Returns:
            Instance of the entry matching the key, shallow copy of collection if no key provided, or None.

        Raises:
            APIError if the entry is not found in persistent storage and raising is enabled.
        """
        if key:
            entry = cls._collection.get(key)
            if not entry and raise_on_missing:
                raise responses.APIError(f"missing-{cls.collection_help_api_name()}", key, code=404)
            return entry
        with cls._collection_lock:
            return cls._collection.copy()

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
            except CollectionValueError as error:
                errors.append((index, error))
                logger.error(f"Skipping invalid {cls.collection_help} setup at index {index}: {error}")
            except Exception as error:  # pylint: disable=broad-except
                errors.append((index, error))
                logger.exception(
                    f"Skipping unprocessable {cls.collection_help} setup at index {index}: {error}",
                    exc_info=error,
                )
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
                loaded_data = file_utils.load_json(data)
                logger.info(f"Loaded {len(loaded_data)} {cls.collection_help} from {cls._collection_uri}")
            except OSError as error:
                if error.errno == 2:
                    logger.warning(f"Skipping {cls.collection_help} load, file not found {data}")
                else:
                    raise error
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(f"Failed to load {cls.collection_help} from local file {data}", exc_info=error)
                raise
        return loaded_data

    @classmethod
    def lock(cls) -> CollectionLock:
        """Provide the lock used by the collection singleton to safely perform modifications."""
        return cls._collection_lock

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
    def remove(cls, key: str, *, raise_on_missing: bool = True) -> CollectionEntry | None:
        """Remove an entry from persistent storage.

        Args:
            key: ID of the saved entry.
            raise_on_missing: Whether to raise an API error if no entry found.

        Returns:
            The item removed if found, None otherwise.

        Raises:
            APIError if the entry does not exist and raise and raising is enabled.
        """
        with cls._collection_lock:
            if key not in cls._collection and raise_on_missing:
                raise responses.APIError(f"missing-{cls.collection_help_api_name()}", key, code=404)
            return cls._collection.pop(key, None)

    @classmethod
    def save(cls) -> None:
        """Persist the current entries to storage."""
        if cls._collection_uri is not None:
            uri = cls._collection_uri
            if uri.startswith("/") or uri.startswith("file://"):
                with cls._collection_lock:
                    file_utils.save_json(
                        cls.to_json(save_only=True),
                        uri.replace("file://", ""),
                        # Use pretty-print in standard environments to simplify manual reviews of collections,
                        # since their collections are typically large. MicroPython does not support pretty-printing.
                        indent=None if micro_utils.is_micro_python() else 2,
                    )
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

    __property_configs__: dict[str, DataProperty]

    def __init__(self, uuid: str | None = None, name: str | None = None) -> None:
        """Set up the base collection entry values.

        Args:
            uuid: Universally unique identifier.
            name: Human readable name used to store/reference in collections.
        """
        self._uuid = None
        self._name = None
        # Safely set the values.
        self.uuid = uuid or str(uuid4())
        self.name = name or f"{self.__class__.__name__}_{self.uuid.split('-', 1)[0]}"

    @classmethod
    def __init_subclass__(cls) -> None:
        """Initialize the subclass properties on declaration to prevent sharing with other subclass singletons."""
        cls.__property_configs__ = OrderedDict()
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if config := getattr(attr, "__property_config__", None):
                cls.__property_configs__[attr_name] = config

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
    def from_json(cls, data: dict) -> CollectionEntry | None:
        """Convert JSON data into a collection entry instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated entry with the given attributes.
        """
        kwargs = {
            "uuid": get_and_validate(data, KEY_ID, expected_type=str),
            KEY_NAME: get_and_validate(data, KEY_NAME, expected_type=str),
        }
        for key, config in cls.__property_configs__.items():
            if not config.save:
                continue
            value = get_and_validate(
                data,
                config.key,
                expected_type=config.expected_type,
                expected_choices=config.choices,
                nullable=config.nullable,
                default=config.default,
                validator=config.validator,
                validation_error=config.error,
                validation_message=config.message,
            )
            if config.convert:
                value = [config.convert.from_json(val) for val in value] if value else value
            kwargs[key] = value
        return cls(**kwargs)

    @property
    def name(self) -> str:
        """The current name of the entry."""
        return self._name

    @data_property(str)
    @name.setter
    def name(self, name: str) -> None:
        """Safely set the current name of the entry."""
        validate(KEY_NAME, name, validator=self._name_validator)
        self._name = name

    @staticmethod
    def _name_validator(name: str) -> bool:  # Used by subclasses. pylint: disable=unused-argument
        """Custom validator for the entry's name property.

        If a custom error message is required, then the function should raise a `CollectionValueError` manually.
        """
        # Default to no extra validation by default.
        return True

    def to_json(
        self,
        save_only: bool = False,
    ) -> dict:
        """Convert the entry into a JSON compatible type.

        Args:
            save_only: Whether to only include values that are meant to be saved.

        Returns:
            Mapping of the instance attributes in JSON compatible format.
        """
        data = OrderedDict()
        data[KEY_ID] = self.uuid
        data[KEY_NAME] = self.name
        for attr_name, config in self.__property_configs__.items():
            if attr_name in ("uuid", "name"):
                # Skip, these are always set in the output first.
                continue
            value = getattr(self, attr_name)
            if config.convert and value is not None:
                if isinstance(value, list):
                    value = [val.to_json() for val in value] if value else None
                else:
                    value = value.to_json()
            if value != (config.default if not callable(config.default) else config.default()):
                if config.save or not save_only:
                    data[attr_name] = value
        return data

    @property
    def uuid(self) -> str:
        """The current UUID of the entry."""
        return self._uuid

    @data_property(str, key=KEY_ID, update=False)
    @uuid.setter
    def uuid(self, uuid: str) -> None:
        """Safely set the current UUID of the entry."""
        self._uuid = uuid

    def update(
        self,
        new_values: dict,
    ) -> dict:
        """Update the values of an entry.

        Only completes update operation if all values pass validation.

        Args:
            new_values: New attributes to set on the entry.

        Returns:
            Final configuration with the updated values.

        Raises:
            CollectionValueError if the class does not allow updates.
        """
        pending_update = []
        for config in self.__property_configs__.values():
            key = config.key
            if not config.update or key not in new_values:
                continue
            value = new_values.get(key)
            validate(
                key,
                value,
                expected_type=config.expected_type,
                expected_choices=config.choices,
                nullable=False,
                validator=config.validator,
                validation_error=config.error,
                validation_message=config.message,
            )
            pending_update.append((config, value))
        for config, value in pending_update:
            config.set_without_validation(self, value)
        return self.to_json(save_only=True)


class CollectionLock:
    """Lock that adjusts available functionality to allow safe collection usage in various environments.

    In CPython, the class supports locking both threads and async coroutines.
    In MicroPython, the class only supports locking async coroutines.
    """

    def __init__(self) -> None:
        """Initialize the available locks based on the environment."""
        try:
            import threading  # pylint: disable=import-outside-toplevel

            self._thread_lock = threading.Lock()
        except ImportError:
            self._thread_lock = None
        self.async_lock = asyncio.Lock()

    async def __aenter__(self) -> CollectionLock:
        """Acquire the async lock and threading lock when the context is entered."""
        # pylint: disable=consider-using-with
        await self.async_lock.acquire()
        if self._thread_lock:
            self._thread_lock.acquire()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType
    ) -> None:
        """Release the async lock and threading lock when the context is exited."""
        self.async_lock.release()
        if self._thread_lock:
            self._thread_lock.release()

    def __await__(self) -> Generator:
        """Yield to external asynchronous function to perform work while locks are acquired."""
        yield

    def __enter__(self) -> CollectionLock:
        """Acquire the threading lock when the context is entered."""
        if self._thread_lock:
            self._thread_lock.acquire()
        return self._thread_lock

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType) -> None:
        """Release the threading lock when the context is exited."""
        if self._thread_lock:
            self._thread_lock.release()


class CollectionValueError(responses.APIError):
    """Exception subclass to help identify failures that indicate a collection entry value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = responses.STATUS_INVALID_DATA) -> None:
        """Set up the user details of the error."""
        super().__init__(error, data, code=code)


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
