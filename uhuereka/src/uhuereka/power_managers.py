"""Power manager configurations for uHuereka devices."""

from __future__ import annotations

import logging
import time
from typing import Any
from typing import override

import machine

from huereka.shared.automation import automate
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property

DEFAULT_CONFIG_PATH = "/power_managers.json"

KEY_TEARDOWN = "teardown"
KEY_TYPE = "type"

MODE_OFF = 0
MODE_ON = 1
ALL_MODES = (MODE_OFF, MODE_ON)

STATUS_OFF = 0
STATUS_ON = 1
All_STATES = (STATUS_OFF, STATUS_ON)

DEVICE_TOGGLE = "pwr_toggle"
DEVICE_PWM = "pwr_pwm"
ALL_DEVICES = (DEVICE_TOGGLE, DEVICE_PWM)

logger = logging.getLogger(__name__)


@uclass()
class PowerManager(CollectionEntry):  # pylint: disable=too-many-instance-attributes
    """Manage the power of a device.

    Example:
    {
        "uuid": "1-2-3-4-5",
        "name": "Slot 1",
        "device_type": "pwr_toggle",
        "pin": 2,
        "mode": 1,
        "power": 1.0,
        "teardown": true,
    }
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        uuid: str | None = None,
        name: str | None = None,
        device_type: str = DEVICE_TOGGLE,
        pin: int | None = None,
        mode: int = MODE_OFF,
        mode_at: int = 0,
        on_limit: int = 0,
        power: float = 1.0,
        should_teardown: bool = True,
    ) -> None:
        """Set up the base Power Manager values.

        Args:
            uuid: Universally unique identifier.
            name: Human readable name used to store/reference in collections.
            device_type: Type of the power signal to determine on/off behavior and advanced features.
            pin: GPIO pin ID on the device to use to send the signal.
            mode: Activity mode for the schedule as 0, 1 (off, on).
            mode_at: When the current mode was set.
            on_limit: Max time the mode is allowed to be on in seconds.
            power: Default power level as a percent between 0.0 and 1.0.
            should_teardown: Whether the device should teardown on service teardowns, or stay in pre-existing state.
        """
        super().__init__(uuid=uuid, name=name)
        self._device_type = DEVICE_TOGGLE
        self._pin: int | None = None
        self._gpio_pin: machine.Pin | None = None
        self._gpio_pwm: machine.PWM | None = None
        self._mode = MODE_OFF
        self._mode_at = 0
        self._on_limit = 0
        self._power = 0.0
        self._should_teardown = True
        self._status = STATUS_OFF

        # Safely set user values. Set in specific order to ensure initial values are correct for pin setup.
        self.mode = mode
        self.on_limit = on_limit
        self.power = power
        self.device_type = device_type
        self.should_teardown = should_teardown
        # Set pin last since it will configure the underlying GPIO pin.
        self.pin = pin
        # Set mode_at after mode is set to ensure original time from load is preserved.
        self._mode_at = mode_at

    def __init_pin_type__(self) -> None:
        """Update the initial type of the GPIO pin after device type is set."""
        if self._gpio_pin is not None:
            if self._gpio_pwm is not None:
                self._gpio_pwm.deinit()
                self._gpio_pwm = None
            self._gpio_pin.off()
        self._gpio_pin = None
        self._gpio_pwm = None
        try:
            if self.device_type == DEVICE_TOGGLE:
                self._gpio_pin = machine.Pin(self._pin, machine.Pin.OUT)
            elif self.device_type == DEVICE_PWM:
                self._gpio_pin = machine.Pin(self._pin, machine.Pin.OUT)
                self._gpio_pwm = machine.PWM(self._gpio_pin)
        except ValueError as error:
            self._gpio_pin = None
            self._gpio_pwm = None
            raise ValueError(f"Invalid pin configuration: {error}") from error
        self.__init_pin_value__()

    def __init_pin_value__(self) -> None:
        """Update the initial value of the GPIO pin based on the status after pin type is set."""
        if self.device_type == DEVICE_TOGGLE and self._gpio_pin:
            if self.status == STATUS_ON:
                self._gpio_pin.on()
            else:
                self._gpio_pin.off()
        elif self._device_type == DEVICE_PWM and self._gpio_pwm:
            # N.B. Power level currently does not work with 5V + PWM + transistor, do not attempt to use.
            if self.status == STATUS_ON:
                self._gpio_pwm.duty_u16(int(65535 * self.power))
            else:
                self._gpio_pwm.duty_u16(0)

    @property
    def device_type(self) -> str:
        """The current device type set on the manager."""
        return self._device_type

    @data_property(str, key=KEY_TYPE, default=DEVICE_TOGGLE, choices=ALL_DEVICES)
    @device_type.setter
    def device_type(self, device_type: str) -> None:
        """Safely set the current device type of the manager."""
        original_type = self._device_type
        self._device_type = device_type
        if original_type != device_type:
            self.__init_pin_type__()

    @property
    def mode(self) -> int:
        """The current mode set on the manager."""
        return self._mode

    @automate()
    @data_property(int, default=MODE_OFF, choices=ALL_MODES)
    @mode.setter
    def mode(self, mode: int) -> None:
        """Safely set the current mode of the manager."""
        if mode != self._mode:
            self._mode_at = time.time()
        self._mode = mode
        # N.B. Status is currently a passthrough of mode, ensure all branches keep values in sync on change.
        self.status = mode

    @data_property(int, default=0, update=False)
    @property
    def mode_at(self) -> int:
        """The time the current mode was set."""
        return self._mode_at

    @property
    def on_limit(self) -> int:
        """The maximum amount of time the mode is allowed to be on."""
        return self._on_limit

    @data_property(
        int,
        default=0,
        validator=lambda value: 0 <= value <= 86400,
        message="Valid on_limit values are: >= 0, <= 86400",
    )
    @on_limit.setter
    def on_limit(self, on_limit: float) -> None:
        """Safely set the maximum on time for the manager."""
        self._on_limit = on_limit

    @property
    def pin(self) -> int:
        """The current GPIO pin ID in use by the manager."""
        return self._pin

    @data_property(int, update=False)
    @pin.setter
    def pin(self, pin: int) -> None:
        """Safely set the current GPIO pin in use by the manager."""
        self._pin = pin
        self.__init_pin_type__()

    @property
    def power(self) -> float:
        """The current power level set on the manager."""
        return self._power

    @automate()
    @data_property(
        float,
        default=1.0,
        validator=lambda value: 0.0 <= value <= 1.0,
        message="Valid power levels are: >= 0.0, <= 1.0",
    )
    @power.setter
    def power(self, power: float) -> None:
        """Safely set the current power level of the manager."""
        if self.device_type == DEVICE_PWM and (power != 0.0 or power != 1.0):
            raise ValueError("Valid power levels are: 0.0, 1.0")
        self._power = power

    @property
    def should_teardown(self) -> bool:
        """Whether the device should teardown on service teardowns, or stay in pre-existing state."""
        return self._should_teardown

    @data_property(bool, key=KEY_TEARDOWN, default=True, update=False)
    @should_teardown.setter
    def should_teardown(self, should_teardown: bool) -> None:
        """Safely set whether the device should teardown on service teardowns, or stay in pre-existing state."""
        self._should_teardown = should_teardown

    @property
    def status(self) -> int:
        """The current status of the manager."""
        return self._status

    @automate()
    @data_property(int, choices=All_STATES, save=False, update=False)
    @status.setter
    def status(self, status: int) -> None:
        """Safely set the current status of the manager."""
        if status == STATUS_ON and self.mode == MODE_OFF:
            raise ValueError("Status may not be set to on while mode is set to off")
        self._status = status
        self.__init_pin_value__()

    def teardown(self) -> None:
        """Clear the manager state and release resources."""
        if self.should_teardown:
            self.mode = MODE_OFF

    @override
    def update(
        self,
        **values: Any,
    ) -> dict:
        result = super().update(**values)
        self.__init_pin_value__()
        return result

    @property
    def uptime(self) -> int:
        """The amount of time the device mode has been set to "on" in seconds."""
        if self.mode == MODE_ON:
            return time.time() - self.mode_at
        return 0


@uclass()
class PowerManagers(Collection):
    """Singleton for managing power managers connected to pins on an MCU."""

    collection_help: str = "power managers"
    entry_cls: str = PowerManager

    @classmethod
    def teardown(cls) -> None:
        """Clear all power manager states, and release resources.

        Managers should not be reused after teardown.
        """
        with cls._collection_lock:
            for uuid in list(cls._collection.keys()):
                manager: PowerManager = cls.remove(uuid)
                manager.teardown()


def load_config(path: str = DEFAULT_CONFIG_PATH) -> None:
    """Load the power manager singleton for the device.

    Args:
        path: Path to the  file containing power manager configurations.
    """
    generated, errors = PowerManagers.load(path)
    if generated:
        if not errors:
            logger.info(f"Auto generated values for {len(generated)} power manager(s), saving final configuration")
            PowerManagers.save()
        else:
            logger.error(
                f"Skipping save of generated values for {len(generated)} power manager(s) due to {len(errors)} error(s), they will be regenerated on each load until errors are resolved"
            )
