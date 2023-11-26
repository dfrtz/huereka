"""Managers for detecting and controlling the local environment.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

import platform


def is_micro_python() -> bool:
    """Determine if current runtime environment is MicroPython based."""
    return "micropython" in platform.platform().lower()
