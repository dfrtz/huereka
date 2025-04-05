"""Dependencies for input/output actions via observation and pub/sub patterns.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

from __future__ import annotations

from typing import Any

from huereka.shared.micro_utils import uclass

KEY_TYPE = "type"
KEY_ID = "id"
KEY_PROP = "prop"

SKIP = "__SKIP__"
"""Indicate that a specific output should be ignored in an observation callback."""


class Dependency:
    """Base for all observation dependencies."""

    __dep_types__ = {}
    _type: str

    def __init__(
        self,
        uuid: str | dict,
        prop: str,
    ) -> None:
        """Initialize base dependency identification.

        Args:
            uuid: Universally Unique ID, or ID pattern, that a component uses to send and receive updates.
            prop: Property name on the component that sends and receives updates.
        """
        self._uuid = uuid
        self._prop = prop

    @classmethod
    def __init_subclass__(cls) -> None:
        """Track all types of dependencies."""
        cls.__dep_types__[cls._type] = cls

    def __eq__(self, other: Any) -> bool:
        """Evaluate if another object is equal to this Dependency."""
        return isinstance(other, Dependency) and self.uuid == other.uuid and self.prop == other.prop

    def __hash__(self) -> int:
        """Convert object into hash usable in maps."""
        return hash(str(self))

    def __repr__(self) -> str:
        """Convert object into human-readable, machine loadable, text."""
        return f"{self.__class__.__name__}('{self.uuid}', '{self.prop}')"

    def __str__(self) -> str:
        """Convert object into human-readable text."""
        return f"{self.prop}@{self.uuid}"

    @classmethod
    def from_json(cls, data: dict) -> Dependency | None:
        """Convert object into JSON format.

        Returns:
            Mapping of properties in JSON compatible format.
        """
        if dep_type := cls.__dep_types__.get(data.get(KEY_TYPE)):
            return dep_type(data.get(KEY_ID), data.get(KEY_PROP))
        return None

    @property
    def prop(self) -> str | dict:
        """Property name on the component that sends and receives updates."""
        return self._prop

    def to_json(self, **_: Any) -> dict:
        """Convert object into JSON format.

        Returns:
            Mapping of properties in JSON compatible format.
        """
        return {KEY_TYPE: self._type, KEY_ID: self.uuid, KEY_PROP: self.prop}

    @property
    def uuid(self) -> str | dict:
        """Universally Unique ID, or ID pattern, that a component uses to send and receive updates."""
        return self._uuid


@uclass()
class Modified(Dependency):
    """Triggering input of an observation callback based on a stateful attribute update.

    Property/attribute to monitor for modifications and trigger observation callbacks.
    """

    _type = "mod"


@uclass()
class Published(Dependency):
    """Triggering input of an observation callback based on a stateless event, rather than a stateful property.

    Event type to monitor for announcements and trigger observation callbacks.
    """

    _type = "pub"

    def __init__(
        self,
        uuid: str | dict,
        event: str | type,
    ) -> None:
        """Initialize published event dependency.

        Args:
            uuid: ID, or object with ID property, that a component uses to send updates.
            event: Event type, or namespace, that is sent from the component to trigger updates.
        """
        super().__init__(
            uuid,
            f"{event.__module__}.{event.__name__}" if not isinstance(event, str) else event,
        )


@uclass()
class Select(Dependency):
    """Non-triggering input of an observation callback.

    Most recent property value to send to a callback without triggering if the property is updated.
    """

    _type = "sel"


@uclass()
class Update(Dependency):
    """Output of an observation callback that will update another component, or trigger another event.

    Property to apply, or event to trigger, after an input dependency triggers an observation callback.
    """

    _type = "upd"


Inputs = (Modified, Published)
States = (Select,)
Outputs = (Update,)
