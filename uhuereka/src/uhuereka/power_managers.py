"""Power manager configurations for uHuereka devices."""

from __future__ import annotations

import logging
from typing import override

import machine

from huereka.shared.collections import KEY_ID
from huereka.shared.collections import KEY_NAME
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import DisabledCollectionLock
from huereka.shared.collections import get_and_validate

logger = logging.getLogger(__name__)

KEY_MODE = "mode"
KEY_PIN = "pin"
KEY_POWER = "power"
KEY_STATUS = "status"
KEY_TYPE = "type"
KEY_TEARDOWN = "teardown"

MODE_OFF = 0
MODE_ON = 1
ALL_MODES = (MODE_OFF, MODE_ON)

STATUS_OFF = 0
STATUS_ON = 1
All_STATES = (STATUS_OFF, STATUS_ON)

DEVICE_TOGGLE = "pwr_toggle"
DEVICE_PWM = "pwr_pwm"
ALL_DEVICES = (DEVICE_TOGGLE, DEVICE_PWM)


class PowerManager(CollectionEntry):
    """Manage the power of a device.

    Example (ESP32-C3):
    {
        "uuid": "1-2-3-4-5",
        "name": "Slot 1",
        "mode": 1,
        "pin": 2,
        "power": 1.0,
        "device_type": "pwr",
        "teardown": true,
    }
    """

    def __init__(
        self,
        uuid: str = None,
        name: str = None,
        mode: int = MODE_OFF,
        pin: int | None = None,
        power: float = 1.0,
        device_type: str = DEVICE_TOGGLE,
        should_teardown: bool = True,
    ) -> None:
        """Set up the base Power Manager values.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
            mode: Activity mode for the schedule as 0, 1 (off, on).
            power: Default power level as a percent between 0.0 and 1.0.
            pin: GPIO pin ID on the device to use to send the signal.
            device_type: Type of the power signal to determine on/off behavior and advanced features.
            should_teardown: Whether the device should teardown on service teardowns, or stay in pre-existing state.
        """
        super().__init__(uuid=uuid, name=name)
        self._mode = MODE_OFF
        self._status = STATUS_OFF
        self._power = 0.0
        self._pin: int | None = None
        self._gpio_pin: machine.Pin | None = None
        self._gpio_pwm: machine.PWM | None = None
        self._device_type = DEVICE_TOGGLE

        # Safely set user values.
        self.mode = mode
        self.power = power
        self.device_type = device_type
        self.should_teardown = should_teardown

        # Set pin last since it will configure the underlying GPIO pin.
        self.pin = pin

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
            ValueError(f"Invalid pin configuration: {error}")
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

    @device_type.setter
    def device_type(self, device_type: int) -> None:
        """Safely set the current device type of the manager."""
        if device_type not in ALL_DEVICES:
            raise ValueError(f"Valid device types are: {', '.join(ALL_DEVICES)}")
        original_type = self._device_type
        self._device_type = device_type
        if original_type != device_type:
            self.__init_pin_type__()

    @classmethod
    @override
    def from_json(cls, data: dict) -> PowerManager:
        cls._validate_config(data)
        return PowerManager(
            uuid=data.get(KEY_ID),
            name=data.get(KEY_NAME),
            mode=data.get(KEY_MODE, MODE_OFF),
            pin=data.get(KEY_PIN),
            power=data.get(KEY_POWER, 1.0),
            device_type=data.get(KEY_TYPE, DEVICE_TOGGLE),
            should_teardown=data.get(KEY_TEARDOWN, True),
        )

    @property
    def mode(self) -> int:
        """The current mode set on the manager."""
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        """Safely set the current mode of the manager."""
        if mode not in ALL_MODES:
            raise ValueError(f"Valid modes are: {', '.join(str(mode) for more in ALL_MODES)}")
        self._mode = mode
        # N.B. Status is currently a passthrough of mode, ensure all branches keep values in sync on change.
        self.status = mode

    @property
    def pin(self) -> int:
        """The current GPIO pin ID in use by the manager."""
        return self._pin

    @pin.setter
    def pin(self, pin: int) -> None:
        """Safely set the current GPIO pin in use by the manager."""
        self._pin = pin
        self.__init_pin_type__()

    @property
    def power(self) -> float:
        """The current power level set on the manager."""
        return self._power

    @power.setter
    def power(self, power: float) -> None:
        """Safely set the current power level of the manager."""
        if power < 0.0 or power > 1.0:
            raise ValueError(f"Valid power levels are: >= 0.0, <= 1.0")
        if self.device_type == DEVICE_PWM and (power != 0.0 or power != 1.0):
            raise ValueError(f"Valid power levels are: 0.0, 1.0")
        self._power = power

    @property
    def status(self) -> int:
        """The current status of the manager."""
        return self._status

    @status.setter
    def status(self, status: int) -> None:
        """Safely set the current status of the manager."""
        if status not in All_STATES:
            raise ValueError(f"Valid states are: {', '.join(str(state) for state in All_STATES)}")
        if status == STATUS_ON and self.mode == MODE_OFF:
            raise ValueError("Status may not be set to on while mode is set to off")
        self._status = status
        self.__init_pin_value__()

    def teardown(self) -> None:
        """Clear the manager state and release resources."""
        if self.should_teardown:
            self.mode = MODE_OFF

    @override
    def to_json(self, save_only: bool = False) -> dict:
        data = super().to_json()
        data[KEY_MODE] = self.mode
        data[KEY_PIN] = self.pin
        data[KEY_POWER] = self.power
        data[KEY_TYPE] = self.device_type
        data[KEY_TEARDOWN] = self.should_teardown
        if not save_only:
            data[KEY_STATUS] = self.status
        return data

    def update(
        self,
        new_values: dict,
    ) -> dict:
        """Update the values of a manager.

        Args:
            new_values: New attributes to set on the manager.

        Returns:
            Final manager configuration with the updated values.
        """
        self._validate_config(new_values)
        name = new_values.get(KEY_NAME)
        if name is not None and name != self.name:
            self.name = name
        mode = new_values.get(KEY_MODE)
        if mode is not None and mode != self.mode:
            self.mode = mode
        power = new_values.get(KEY_POWER)
        if power is not None and power != self.power:
            self.power = power
        device_type = new_values.get(KEY_TYPE)
        if device_type is not None and device_type != self.device_type:
            self.device_type = device_type
        self.__init_pin_value__()
        return self.to_json()

    @classmethod
    def _validate_config(cls, config: dict) -> None:
        """Ensure a configuration is valid for use as a PowerManager."""
        get_and_validate(config, KEY_ID, expected_type=str)
        get_and_validate(config, KEY_NAME, expected_type=str)
        get_and_validate(config, KEY_MODE, expected_choices=ALL_MODES)
        get_and_validate(config, KEY_PIN, expected_type=int)
        get_and_validate(
            config,
            KEY_POWER,
            expected_type=float,
            validator=lambda value: 0.0 <= value <= 1.0,
            validation_message=f"Valid power levels are: >= 0.0, <= 1.0",
        )
        get_and_validate(config, KEY_TYPE, expected_choices=ALL_DEVICES)
        get_and_validate(config, KEY_TEARDOWN, expected_type=bool)


class PowerManagers(Collection):
    """Singleton for managing power managers connected to pins on an MCU."""

    _collection: dict[str, PowerManager] = {}
    _collection_lock = DisabledCollectionLock()
    _collection_uri: str = None

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
