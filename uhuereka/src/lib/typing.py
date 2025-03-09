"""Placeholders for typing to allow cross compatibility between CPython and MicroPython."""

Any = "Any"
Callable = "Callable"


def override(func: Callable) -> Callable:
    """Indicate that a method is intended to override a method in a base class.

    Based on CPython 3.12.
    """
    try:
        func.__override__ = True
    except (AttributeError, TypeError):
        pass
    return func
