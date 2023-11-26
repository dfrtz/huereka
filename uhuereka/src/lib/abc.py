"""Placeholders for abc to allow cross compatibility between CPython and MicroPython."""

from typing import Callable


class ABC:
    """Simulated class indicating abstract metaclass.

    Compared to CPython, this does not provide a metaclass; they are not supported in MicroPython.

    Does not provide any runtime abstraction checking in MicroPython.
    Refer to CPython abc.ABC()/abc.ABCMeta() for full details.
    """


class abstractproperty(property):
    """Simulated class indicating abstract properties.

    Prefer @property + @abstractmethod where possible. Although this is deprecated in CPython,
    it can be used to indicate to CPython and linters that an attribute must be overriden.

    Does not provide any runtime abstraction checking in MicroPython.
    Refer to CPython abc.abstractproperty() for full details.
    """


def abstractmethod(funcobj: Callable) -> Callable:
    """Simulated decorator indicating abstract methods.

    Does not provide any runtime abstraction checking in MicroPython.
    Refer to CPython abc.abstractmethod() for full details.
    """
    return funcobj
