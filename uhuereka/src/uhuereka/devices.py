"""Primary uHuereka configuration for the device running the software."""

from __future__ import annotations

import logging
import re
from typing import override

from huereka.shared import file_utils
from huereka.shared.collections import KEY_ID
from huereka.shared.collections import KEY_NAME
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import get_and_validate
from huereka.shared.collections import uuid4

NO_CONFIG_FOUND = "NO_CONFIG_FOUND"
KEY_PORT = "port"
KEY_CTRL_PIN = "control_pin"

logger = logging.getLogger(__name__)


class MCUDevice(CollectionEntry):
    """Primary configuration for the device running the software."""

    def __init__(
        self,
        uuid: str | None = None,
        name: str | None = None,
        port: int | None = None,
        control_pin: int | None = None,
    ) -> None:
        """Set up the base collection entry values.

        Args:
            uuid: Universally unique identifier.
            name: Human readable name, also the hostname, used to store/reference in collections.
            port: TCP Port the device should listen to incoming API requests on to control the hardware/software.
            control_pin: Pin that should listen to button presses to control the hardware/software.
        """
        uuid = uuid or uuid4()
        super().__init__(uuid=uuid, name=name or f"uhuereka-{uuid.split('-', 1)[0]}")
        self.port = port
        self.control_pin = control_pin

    @classmethod
    @override
    def from_json(cls, data: dict) -> MCUDevice:
        cls._validate_config(data)
        return MCUDevice(
            uuid=data.get(KEY_ID),
            name=data.get(KEY_NAME),
            port=data.get(KEY_PORT),
            control_pin=data.get(KEY_CTRL_PIN),
        )

    @override
    def to_json(self, save_only: bool = False) -> dict:
        data = super().to_json() | {
            KEY_PORT: self.port,
            KEY_CTRL_PIN: self.control_pin,
        }
        return data

    @classmethod
    def _validate_config(cls, config: dict) -> None:
        """Ensure a configuration is valid for use as a MCUDevice."""
        get_and_validate(config, KEY_ID, expected_type=str)
        get_and_validate(
            config,
            KEY_NAME,
            expected_type=str,
            # N.B. MicroPython has limited regex support. Perform as much hostname validation as possible.
            validator=lambda value: len(value) < 64 and re.match(r"^[A-Za-z0-9][A-Za-z0-9-.]+[A-Za-z0-9]$", value),
            validation_message=f"Valid names only contain letters/numbers/dashes, and are < 64 characters",
        )
        get_and_validate(config, KEY_PORT, expected_type=int)
        get_and_validate(config, KEY_CTRL_PIN, expected_type=int)


def load_device(
    mfg_path: str = "/mfg.json",
    overrides_path: str = "/device.json",
    defaults: dict | None = None,
) -> MCUDevice:
    """Load a device configuration from all available sources.

    Args:
        mfg_path: Path to the manufacturing default file as the baseline.
        overrides_path: Path to saved device configuration file containing manufacturing overrides.
            Will be updated if primary values are not populated.
        defaults: Inline defaults to apply where no values are found from other configs.

    Returns:
        Initialized device based on configurations.
    """
    config = {}
    if mfg_config := file_utils.load_json(mfg_path):
        config |= mfg_config
    if user_config := file_utils.load_json(overrides_path):
        config |= user_config
    if defaults:
        for key, value in defaults.items():
            if config.get(key, NO_CONFIG_FOUND) == NO_CONFIG_FOUND:
                config[key] = value
    pending_save = not bool(config.get(KEY_ID)) or not bool(config.get(KEY_NAME))
    loaded = MCUDevice.from_json(config)
    if pending_save:
        file_utils.save_json(loaded.to_json(), overrides_path)
        logger.info(f"Saved updated device configuration: {loaded.to_json()}")
    return loaded
