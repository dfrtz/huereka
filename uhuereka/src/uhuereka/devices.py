"""Primary uHuereka configuration for the device running the software."""

from __future__ import annotations

import logging
import pathlib
import re

import machine

from huereka.shared import file_utils
from huereka.shared.collections import KEY_ID
from huereka.shared.collections import KEY_NAME
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import gen_uuid
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property

DEFAULT_MFG_PATH = "/mfg.json"
DEFAULT_CONFIG_PATH = "/device.json"

NO_CONFIG_FOUND = "--NO_CONFIG_FOUND--"

logger = logging.getLogger(__name__)


@uclass()
class MCUDevice(CollectionEntry):
    """Primary configuration for the device running the software."""

    def __init__(
        self,
        uuid: str | None = None,
        name: str | None = None,
        hostname: str | None = None,
        port: int | None = None,
        wlan_enabled: bool = True,
        control_pin: int | None = None,
    ) -> None:
        """Set up the base device values.

        Args:
            uuid: Universally unique identifier used to store/reference in collections.
            name: Human readable name.
            hostname: Hostname the device will request on networks.
            port: TCP Port the device should listen to incoming API requests on to control the hardware/software.
            wlan_enabled: Whether the WLAN hardware is allowed to be used for control requests.
            control_pin: Pin that should listen to button presses to control the hardware/software.
        """
        uuid = uuid or gen_uuid()
        super().__init__(uuid=uuid, name=name or f"uhuereka-mcu-{uuid[:8]}")
        self._hostname = hostname or re.sub(r"[^A-Za-z0-9-.]", "", re.sub(r"\s+", "-", self.name))
        self._port: int | None = None
        self._wlan_enabled: bool = True
        self._control_pin: int | None = None

        # Safely set user values.
        self.port = port
        self.wlan_enabled = wlan_enabled
        self.control_pin = control_pin

    @property
    def control_pin(self) -> int:
        """Pin that should listen to button presses to control the hardware/software."""
        return self._control_pin

    @data_property(int)
    @control_pin.setter
    def control_pin(self, control_pin: int) -> None:
        """Safely set the Pin that should listen to button presses to control the hardware/software."""
        self._control_pin = control_pin

    @property
    def hostname(self) -> str:
        """The current hostname the device will request on networks."""
        return self._hostname

    @data_property(
        str,
        # N.B. MicroPython has limited regex support. Perform as much hostname validation as possible.
        validator=lambda value: len(value) < 64 and re.match(r"^[A-Za-z0-9][A-Za-z0-9-.]+[A-Za-z0-9]$", value),
        message="Valid hostnames only contain letters/numbers/dashes, and are < 64 characters",
    )
    @hostname.setter
    def hostname(self, hostname: str) -> None:
        """Safely set the hostname the device will request on networks."""
        self._hostname = hostname

    @property
    def port(self) -> int | None:
        """The current port the device is listening to API requests on."""
        return self._port

    @data_property(int)
    @port.setter
    def port(self, port: int | None) -> None:
        """Safely set the port the device is listening to API requests on."""
        self._port = port

    @property
    def wlan_enabled(self) -> int:
        """Whether the WLAN hardware is allowed to be used for control requests."""
        return self._wlan_enabled

    @data_property(bool)
    @wlan_enabled.setter
    def wlan_enabled(self, wlan_enabled: bool) -> None:
        """Safely set whether the WLAN hardware is allowed to be used for control requests."""
        self._wlan_enabled = wlan_enabled


def hard_reset_config(path: str = DEFAULT_CONFIG_PATH, reset_machine: bool = True) -> None:
    """Hard reset the device to the default configuration.

    Args:
        path: Path to saved device configuration file containing manufacturing overrides.
        reset_machine: Reset the device in a manner similar to pushing the external RESET button after config reset.
    """
    device_config = pathlib.Path(path)
    if device_config.exists():
        try:
            device_config.unlink()
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(f"Failed to remove device configuration during hard reset: {error}", exc_info=error)
    if reset_machine:
        machine.reset()


def load_config(
    mfg_path: str = DEFAULT_MFG_PATH,
    overrides_path: str = DEFAULT_CONFIG_PATH,
    defaults: dict | None = None,
) -> MCUDevice:
    """Load the device configuration from all available sources.

    Args:
        mfg_path: Path to the manufacturing defaults used as the configuration baseline.
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
        save_config(loaded, path=overrides_path)
        logger.info(f"Saved updated device configuration: {loaded.to_json()}")
    return loaded


def save_config(config: dict | MCUDevice, path: str = DEFAULT_CONFIG_PATH) -> None:
    """Save device configuration to a file.

    Args:
        config: Device configuration to save to the file.
        path: Path to file where device configuration should be saved.

    Raises:
        Exception on failure to save.
    """
    if isinstance(config, MCUDevice):
        config = config.to_json(save_only=True)
    file_utils.save_json(config, path)
