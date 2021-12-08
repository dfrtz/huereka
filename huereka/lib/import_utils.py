"""Utilities to help perform runtime imports."""

import importlib
import os

from glob import glob


def import_modules(module_folder: str, package: str, recursive: bool = True, imported: list = None) -> list[str]:
    """Import all modules in a directory.

    Args:
        module_folder: A directory containing one or more python modules.
        package: The package root of all the modules.
        recursive: Whether to search all sub directories for modules as well.
        imported: List modified inplace to store imported module names for recursive calls and reporting.

    Returns:
        imported: The name of all modules imported.
    """
    # Must check explicitly for None, otherwise an empty module directory will reset the shared list.
    if imported is None:
        imported = []
    for abs_path in glob(os.path.join(module_folder, '*.py')):
        filename = os.path.basename(abs_path)
        if not filename.startswith('__'):
            module_name = f'{package}.{os.path.splitext(filename)[0]}'
            importlib.import_module(module_name)
            imported.append(module_name)
    if recursive and os.path.exists(module_folder):
        # Index 1 of os.walk tuples is a list of all sub directories.
        for directory in next(os.walk(module_folder))[1]:
            if directory.startswith(('_', 'test')) or '.' in directory:
                # Do not walk directories for tests, private libs, or unsupported python lib characters (period).
                continue
            sub_dir = os.path.join(module_folder, directory)
            sub_module = f'{package}.{directory}'
            import_modules(sub_dir, sub_module, recursive=True, imported=imported)
    return imported
