"""Utilities to manage files on the local filesystem.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

import json
import logging
import pathlib
from typing import Any

from huereka.shared import micro_utils

logger = logging.getLogger(__name__)


def copy_file(source: str, destination: str) -> None:
    """Copy a file in a manner compatible across Python platforms.

    Args:
        source: Path to original file.
        destination: Path to new file.

    Raises:
        Exceptions on any failures to copy the file.
    """
    path = pathlib.Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(source, "rb", encoding=None) as src_file:
        with open(destination, "wb", encoding=None) as dest_file:
            dest_file.write(src_file.read())


def load_json(path: str, backup_ext: str = ".bkp") -> Any:
    """Load a JSON file with multiple safeguards against failures in case recovery is needed.

    Args:
        path: Path to file with JSON data to read. Reads from backup if available.
        backup_ext: Extension to use to read backup file.

    Return:
        Value(s) loaded from file, or None if no file found.

    Raises:
        Exceptions on any failures to read both original and backup file.
    """
    file = pathlib.Path(path)
    bkp_file = pathlib.Path(f"{path}{backup_ext}")
    content = None
    read_error = None
    if file.exists():
        try:
            content = file.read_text(encoding="utf-8")
        except Exception as error:  # pylint: disable=broad-exception-caught
            read_error = error
    if not content:
        if bkp_file.exists():
            if read_error:
                logger.exception(
                    f"Failed to load, attempting to read backup for {path}: {read_error}",
                    exc_info=read_error,
                )
            try:
                content = bkp_file.read_text(encoding="utf-8")
                logger.warning(f"Loaded backup for {path}")
            except Exception as error:
                logger.exception(f"Failed to load backup for {path}: {error}", exc_info=error)
                raise read_error  # pylint: disable=raise-missing-from
        elif read_error:
            raise read_error
    result = json.loads(content or "null")
    return result


def save_json(data: Any, destination: str, indent: int | None = None, backup_ext: str = ".bkp") -> None:
    """Save a JSON file with multiple safeguards against failures in case recovery is needed.

    Args:
        data: New JSON compatible data to save to the file.
        destination: Path to save the data to. Overwrites existing file.
            Performs a backup and restore of original file in case of failures.
        indent: Pretty-printed with the requested indent level.
            None for no pretty-print, and 0 for newlines, but no indentation.
        backup_ext: Extension to use to save backup file.

    Raises:
        Exceptions on any failures to save or verify.
    """
    # Move old file, write to new file, and verify readability at each step of the way, so that if for any reason
    # it is interrupted/fails, the original remains intact and the user can decide which to load.
    if micro_utils.is_micro_python():
        data_out = json.dumps(data)
    else:
        data_out = json.dumps(data, indent=indent)
    new_path = pathlib.Path(f"{destination}")
    backup_path = pathlib.Path(f"{new_path}{backup_ext}")

    # Move and verify the backup file is readable before attempting new save.
    if new_path.exists():
        new_path.rename(str(backup_path))
        json.loads(backup_path.read_text(encoding="utf-8") or "null")

    # Save new file and verify before cleaning up backup files.
    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(data_out, encoding="utf-8")
        json.loads(new_path.read_text(encoding="utf-8") or "null")
        if backup_path.exists():
            backup_path.unlink()
    except Exception as error:
        if new_path.exists():
            new_path.unlink()
        backup_path.rename(str(new_path))
        raise error
