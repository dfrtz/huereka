"""Automation orchestration using observer and pub/sub patterns."""

from typing import Any
from typing import Callable

__prop_orchestrator__: Callable[[Any, str, Any, Any], None] | None = None


class AutomationDependency:  # pylint: disable=too-few-public-methods
    """Configuration for automating property change events."""

    def __init__(
        self,
        key: str,
    ) -> None:
        """Configure a property for automation.

        Args:
            key: Name of the property to associate with the data in automation events.
        """
        self.key = key


def automate() -> Callable:
    """Wrap a property with additional metadata for triggering automation events."""

    def _wrapper(prop: property) -> property:
        """Update the property automation configuration."""
        prop_key = prop.fget.__name__
        prop.__automation_dependency__ = AutomationDependency(
            prop_key,
        )
        if prop.fset:
            original_fset = prop.fset

            def _setter(self: Any, value: Any) -> Any:
                """Call the property setter and trigger automation orchestration on changes."""
                if __prop_orchestrator__:
                    old_value = prop.fget(self)
                    original_fset(self, value)
                    new_value = prop.fget(self)
                    if old_value != new_value:
                        __prop_orchestrator__(  # pylint: disable=not-callable
                            self.uuid, prop.__automation_dependency__.key, old_value, new_value
                        )
                else:
                    original_fset(self, value)

            prop = prop.setter(_setter)
        return prop

    return _wrapper


def debug_print_orchestrator(uuid: str | dict, prop: str, old_value: Any, new_value: Any) -> None:
    """Print automation events for debugging purposes.

    Do not use in production.
    """
    print(uuid, prop, old_value, new_value)


def set_property_event_orchestrator(receiver: Callable) -> None:
    """Set the receiver to handle all property automation events.

    Args:
        receiver: Where to send property changes.
    """
    global __prop_orchestrator__  # pylint: disable=global-statement
    __prop_orchestrator__ = receiver
