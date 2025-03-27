"""Utilities for performing operations consistently across CPython and MicroPython environments.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

from __future__ import annotations

import platform
from typing import Any
from typing import Callable


def is_micro_python() -> bool:
    """Determine if current runtime environment is MicroPython based.

    Returns:
        True if MicroPython, False otherwise.
    """
    return "micropython" in platform.platform().lower()


def uclass(*args: Any, **kwargs: Any) -> Callable:
    """Mark a class as requiring extra compatibility calls against a class for parity between CPython and MicroPython.

    Args:
        args: Positional arguments to pass along to `__init_subclass__` instead of placing in class declaration.
        kwargs: Keyword arguments to pass along to `__init_subclass__` instead of placing in class declaration.

    Returns:
        A function that can be used as a decorator on a class to trigger extra compatibility calls.
    """

    def _micropython_class(cls: type) -> type:
        """Call extra compatibility logic in a way compatible between CPython and MicroPython."""
        if init := getattr(cls, "__init_subclass__", None):
            init(*args, **kwargs)
        return cls

    return _micropython_class


class uproperty:  # Match CPython property style. pylint: disable=invalid-name
    """A lightweight micro-"property" decorator, providing feature parity across CPython and MicroPython.

    Compared to MicroPython's `@property` decorator, fget/etc are maintained to allow access from the class/instance,
    similar to CPython access.
    """

    def __init__(self, fget: Callable | None = None) -> None:
        """Initialize the property to allow attaching additional value management.

        Args:
            fget: The method used to get the property's value.
        """
        self.fget = fget
        self.fset = None
        self.fdel = None

    def __delete__(self, instance: Any) -> None:
        """Delete the value represented by the property."""
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(instance)

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        """Get the value represented by the property."""
        if instance is None:
            return self
        if self.fget is None:
            raise AttributeError(f"no attribute '{instance}'")
        return self.fget(instance)

    def __set__(self, instance: Any, value: Any) -> None:
        """Set the value represented by the property."""
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(instance, value)

    def getter(self, fget: Callable) -> uproperty:
        """Attach a method to get the property value.

        Args:
            fget: The method used to get the property's value.

        Returns:
            The property to allow for chaining calls.
        """
        self.fget = fget
        return self

    def setter(self, fset: Callable) -> uproperty:
        """Attach a method to set the property value.

        Args:
            fset: The method used to set the property's value.

        Returns:
            The property to allow for chaining calls.
        """
        self.fset = fset
        return self

    def deleter(self, fdel: Callable) -> uproperty:
        """Attach a method to delete the property value.

        Args:
            fdel: The method used to delete the property's value.

        Returns:
            The property to allow for chaining calls.
        """
        self.fdel = fdel
        return self
