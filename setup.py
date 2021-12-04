"""Setup configuration and dependencies for the library."""

import os
import setuptools

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))


def _find_requirements(file_name: str) -> list:
    """Locate python requirements from a text file in a compatible format with setuptools."""
    requirements_file = os.path.join(ROOT_DIR, file_name)
    with open(requirements_file, 'rt') as file_in:
        requirements = [requirement.strip() for requirement in file_in.readlines()]
    return requirements


def _find_version() -> str:
    """Locate semantic version from a text file in a compatible format with setuptools."""
    init_file = os.path.join(ROOT_DIR, 'huereka', '__init__.py')
    with open(init_file, 'rt') as file_in:
        for line in file_in.readlines():
            if '__version__' in line:
                # Example:
                # __version__ = '1.0.0' -> 1.0.0
                version = line.split()[2].replace("'", '')
    return version


setuptools.setup(
    name='huereka',
    version=_find_version(),
    description='Decorative lighting management software.',
    url='https://github.com/dfrtz/huereka',
    packages=setuptools.find_packages(
        where=ROOT_DIR,
        include=[
            'huereka*',
        ],
        exclude=[
            '*test',
        ],
    ),
    data_files=[
        ('', [
            'requirements.txt',
        ])
    ],
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            'huereka-server = huereka.huereka_server:main',
        ],
    },
    install_requires=_find_requirements('requirements.txt'),
)
