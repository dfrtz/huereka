"""Helpers for managing lighting schedules on LED strips."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

from huereka.common import color_profile
from huereka.common import color_utils
from huereka.common import led_manager
from huereka.shared import responses
from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.collections import CollectionValueError
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property
from huereka.shared.properties import get_and_validate

logger = logging.getLogger(__name__)

__WATCHDOG__ = None
__WATCHDOG_SLEEP__ = True

KEY_ROUTINES = "routines"
KEY_NAME = "name"

KEY_BRIGHTNESS = "brightness"
KEY_DAYS = "days"
KEY_END = "end"
KEY_LED_DELAY = "led_delay"
KEY_MANAGER = "manager"
KEY_MODE = "mode"
KEY_PROFILE = "profile"
KEY_START = "start"
KEY_STATUS = "status"

BRIGHTNESS_DISABLED = -1.0

DAY_MONDAY = 1
DAY_TUESDAY = 2
DAY_WEDNESDAY = 4
DAY_THURSDAY = 8
DAY_FRIDAY = 16
DAY_SATURDAY = 32
DAY_SUNDAY = 64
DAYS_ALL = DAY_MONDAY | DAY_TUESDAY | DAY_WEDNESDAY | DAY_THURSDAY | DAY_FRIDAY | DAY_SATURDAY | DAY_SUNDAY

MODE_OFF = 0
MODE_ON = 1
MODE_AUTO = 2

STATUS_OFF = 0
STATUS_ON = 1


class LightingRoutine:
    """Details for running a specific color/lighting profile during a timeframe."""

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
        self,
        *,
        profile: str = None,
        days: int | list[int] = DAYS_ALL,
        start: int | float | str = 0,
        end: int | float | str = 86400,
        mode: int = MODE_ON,
        brightness: float = BRIGHTNESS_DISABLED,
    ) -> None:
        """Set up the routine to run a profile at specific times.

        Args:
            profile: ID of the color profile to use while this routine is active.
            days: Combination value representing enabled days.
                Can be combined via bitwise operations. e.g. DAY_MONDAY | DAY_TUESDAY == "Monday" and "Tuesday"
            start: Start time in seconds as 0 < value < 86400 or HH:MM.
            end: End time in seconds as 0 < value < 86400 or HH:MM.
            mode: Activity mode for the schedule as 0, 1 (off, on).
            brightness: Brightness as a percent between 0.0 and 1.0.
                Overrides schedule brightness. Defaults to -1 to indicate override being disabled.
        """
        self._mode = MODE_ON
        self._status = STATUS_OFF
        self._start = 0
        self._end = 86400
        self.profile = profile
        self.start = start
        self.end = end
        if isinstance(days, int):
            self._days = days
        else:
            for day in days:
                self._set_day(day)
        self.mode = mode
        self.brightness = brightness

    def __eq__(self, other: Any) -> bool:
        """Make the routine comparable for equality using unique attributes."""
        return (
            isinstance(other, LightingRoutine)
            and self.profile == other.profile
            and self.days == other.days
            and self.start == other.start
            and self.end == other.end
            and self.brightness == other.brightness
        )

    def _set_day(self, day: int) -> None:
        """Toggle combination flag for a day on."""
        self._days |= day

    def _unset_day(self, mode: int) -> None:
        """Toggle combination flag for a day off."""
        self._days &= ~mode

    @property
    def active(self) -> bool:
        """Determine if the current time is in the active window (inclusive start and end)."""
        if self.mode == MODE_ON and self.profile:
            now = datetime.now()
            if self.start < self.end:
                # Start is before end, routine is active if between the two.
                if self._days == DAYS_ALL or self._days & now.isoweekday() != 0:
                    now_in_seconds = now.hour * 60 * 60 + now.minute * 60 + now.second
                    if self.start <= now_in_seconds <= self.end:
                        return True
            else:
                # End is before start, routine is active if falls into daily rollover window to next day.
                today = now.isoweekday()
                next_day = today - 1
                if next_day == 8:
                    next_day = 1
                now_in_seconds = now.hour * 60 * 60 + now.minute * 60 + now.second
                if now_in_seconds >= self.start and (self.days == DAYS_ALL or self._days & today != 0):
                    return True
                if now_in_seconds <= self.end and (self.days == DAYS_ALL or self._days & next_day != 0):
                    return True
        return False

    @property
    def days(self) -> int:
        """Provide the combination value for enabled days."""
        return self._days

    @property
    def days_human(self) -> str:
        """Provide human readable string for days."""
        days = ""
        days += "S" if self.days & DAY_SUNDAY != 0 else "-"
        days += "M" if self.days & DAY_MONDAY != 0 else "-"
        days += "T" if self.days & DAY_TUESDAY != 0 else "-"
        days += "W" if self.days & DAY_WEDNESDAY != 0 else "-"
        days += "T" if self.days & DAY_THURSDAY != 0 else "-"
        days += "F" if self.days & DAY_FRIDAY != 0 else "-"
        days += "S" if self.days & DAY_SATURDAY != 0 else "-"
        return days

    @property
    def end(self) -> int:
        """When this routine stops within a day (seconds)."""
        return self._end

    @end.setter
    def end(self, end: int | float | str) -> None:
        """Update time when routine stops within a day.

        Args:
            end: End time in seconds as 0 < value < 86400 or HH:MM.
        """
        if isinstance(end, (int, float)):
            if end < 0 or end > 86400:
                raise CollectionValueError("End time must be between 0 and 86400 seconds.")
            self._end = end
        elif isinstance(end, str):
            if ":" not in end or end.count(":") > 1:
                raise CollectionValueError("End time must be in format HH:MM")
            hour, minute = end.split(":")
            hour = int(hour)
            minute = int(minute)
            if hour < 0 or hour > 24:
                raise CollectionValueError("End hour must be between 0 and 24")
            if hour == 24 and minute > 0:
                raise CollectionValueError("End minute must be 0 if hour is 24")
            if minute < 0 or minute > 59:
                raise CollectionValueError("End minute must be between 0 and 59")
            self._end = hour * 60 * 60 + minute * 60

    @property
    def end_time(self) -> str:
        """Provide human readable value for end."""
        return f"{int(self.end / 3600):02}:{int(self.end % 3600 / 60):02}"

    @classmethod
    def from_json(cls, data: dict) -> LightingRoutine:
        """Convert JSON type into schedule instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated routine with the given attributes.
        """
        # Optional arguments.
        profile = data.get(KEY_PROFILE)
        if not profile or not isinstance(profile, str):
            raise CollectionValueError("invalid-lighting_routine-profile")
        days = data.get(KEY_DAYS, DAYS_ALL)
        if not isinstance(days, int):
            raise CollectionValueError("invalid-lighting_routine-days")
        start = data.get(KEY_START, 0)
        if not isinstance(start, (int, float, str)):
            raise CollectionValueError("invalid-lighting_routine-start")
        end = data.get(KEY_END, 86400)
        if not isinstance(end, (int, float, str)):
            raise CollectionValueError("invalid-lighting_routine-end")
        mode = data.get(KEY_MODE, MODE_ON)
        if not isinstance(mode, int):
            raise CollectionValueError("invalid-lighting_routine-mode")
        brightness = data.get(KEY_BRIGHTNESS, BRIGHTNESS_DISABLED)
        if not isinstance(brightness, float):
            raise CollectionValueError("invalid-lighting_routine-brightness")

        return LightingRoutine(
            profile=profile,
            days=days,
            start=start,
            end=end,
            mode=mode,
        )

    @property
    def mode(self) -> int:
        """Return the current mode set on the routine."""
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        """Safely set the current mode of the routine."""
        valid_modes = (MODE_OFF, MODE_ON)
        if mode not in valid_modes:
            raise ValueError(f"Valid modes are: {valid_modes}")
        self._mode = mode

    @property
    def start(self) -> int:
        """When this routine starts within a day (seconds)."""
        return self._start

    @start.setter
    def start(self, start: int | float | str) -> None:
        """Update time when routine starts within a day.

        Args:
            start: Start time in seconds as 0 < value < 86400 or HH:MM.
        """
        if isinstance(start, (int, float)):
            if start < 0 or start > 86400:
                raise CollectionValueError("Start time must be between 0 and 86400 seconds.")
            self._start = int(start)
        elif isinstance(start, str):
            if ":" not in start or start.count(":") > 1:
                raise CollectionValueError("Start time must be in format HH:MM")
            hour, minute = start.split(":")
            hour = int(hour)
            minute = int(minute)
            if hour < 0 or hour > 23:
                raise CollectionValueError("Start hour must be between 0 and 23")
            if minute < 0 or minute > 59:
                raise CollectionValueError("Start minute must be between 0 and 59")
            self._start = hour * 60 * 60 + minute * 60

    @property
    def start_time(self) -> str:
        """Provide human readable value for start."""
        return f"{int(self.start / 3600):02}:{int(self.start % 3600 / 60):02}"

    @property
    def status(self) -> int:
        """Return the current status of the routine."""
        return self._status

    @status.setter
    def status(self, status: int) -> None:
        """Safely set the current status of the routine."""
        valid_states = (STATUS_OFF, STATUS_ON)
        if status not in valid_states:
            raise ValueError(f"Valid states are: {valid_states}")
        if status == STATUS_ON and self.mode == MODE_OFF:
            raise ValueError("Status may not be set to on while mode is set to off")
        self._status = status

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        data = {
            KEY_PROFILE: self.profile,
            KEY_DAYS: self._days,
            KEY_START: self.start_time,
            KEY_END: self.end_time,
            KEY_MODE: self.mode,
            KEY_BRIGHTNESS: self.brightness,
        }
        if not save_only:
            data[KEY_STATUS] = self.status
        return data


@uclass()
class LightingSchedule(CollectionEntry):
    """Schedule used to control active color profile on an LED strip."""

    def __init__(  # Approved override of default. pylint: disable=too-many-arguments
        self,
        name: str,
        *,
        uuid: str | None = None,
        manager: str = "default",
        routines: list[LightingRoutine] | None = None,
        led_delay: float = led_manager.DEFAULT_LED_UPDATE_DELAY,
        mode: int = MODE_OFF,
        brightness: float = BRIGHTNESS_DISABLED,
    ) -> None:
        """Set up a schedule for managing active color profile.

        Args:
            name: Human readable name used to store/reference in collections.
            uuid: Unique identifier.
            manager: ID of the LED manager that will be controlled by this schedule.
            routines: Timeframes to trigger specific color profiles.
            led_delay: Time in seconds to delay updates between individual LEDs.
            mode: Activity mode for the schedule as 0, 1, or 2 (off, on, or auto).
            brightness: Brightness as a percent between 0.0 and 1.0.
                Overrides LED manager brightness. Defaults to -1 to indicate override being disabled.
        """
        super().__init__(uuid=uuid, name=name)
        self._mode = MODE_OFF
        self._status = STATUS_OFF
        self._manager = None
        self._routines = None
        self._led_delay = led_manager.DEFAULT_LED_UPDATE_DELAY
        self._brightness = BRIGHTNESS_DISABLED

        self.manager = manager
        self.routines = routines or []
        self.led_delay = led_delay
        self.brightness = brightness
        self.mode = mode

    def __eq__(self, other: Any) -> bool:
        """Make the schedule comparable for equality using unique attributes."""
        return (
            isinstance(other, LightingSchedule)
            and self.name == other.name
            and self.manager == other.manager
            and self.routines == other.routines
            and self.led_delay == other.led_delay
            and self.mode == other.mode
            and self.brightness == other.brightness
        )

    @property
    def active(self) -> LightingRoutine | None:
        """Get the currently active routine from this schedule if one is available."""
        active_routine = OffLightingRoutine
        if self.mode == MODE_AUTO:
            for routine in self.routines:
                if routine.active:
                    active_routine = routine
                    break
        if self.mode == MODE_ON and active_routine is OffLightingRoutine and len(self.routines) > 0:
            active_routine = self.routines[0]
        return active_routine

    @property
    def brightness(self) -> float:
        """Brightness as a percent between 0.0 and 1.0."""
        return self._brightness

    @data_property(float, default=BRIGHTNESS_DISABLED)
    @brightness.setter
    def brightness(self, brightness: float) -> None:
        """Safely set the percent brightness."""
        self._brightness = brightness

    @property
    def led_delay(self) -> float:
        """Time in seconds to delay updates between individual LEDs."""
        return self._led_delay

    @data_property(float, default=led_manager.DEFAULT_LED_UPDATE_DELAY)
    @led_delay.setter
    def led_delay(self, led_delay: float) -> None:
        """Safely set the time in seconds to delay updates between individual LEDs."""
        self._led_delay = led_delay

    @property
    def manager(self) -> str:
        """ID of the LED manager that will be controlled by this schedule."""
        return self._manager

    @data_property(str, default="default")
    @manager.setter
    def manager(self, manager: str) -> None:
        """Safely set the ID of the LED manager that will be controlled by this schedule."""
        self._manager = manager

    @property
    def mode(self) -> int:
        """Return the current mode set on the schedules."""
        return self._mode

    @data_property(int, default=MODE_OFF, choices=(MODE_OFF, MODE_ON, MODE_AUTO))
    @mode.setter
    def mode(self, mode: int) -> None:
        """Safely set the current mode of the schedule."""
        self._mode = mode

    @property
    def routines(self) -> list[LightingRoutine]:
        """Timeframes to trigger specific color profiles."""
        return self._routines

    @data_property(
        list,
        validator=lambda items: all(isinstance(item, dict) for item in items),
        convert=LightingRoutine,
    )
    @routines.setter
    def routines(self, routines: list[LightingRoutine]) -> None:
        """Safely set the timeframes to trigger specific color profiles."""
        self._routines = routines

    @property
    def status(self) -> int:
        """Return the current status of the schedule."""
        return self._status

    @data_property(int, choices=(STATUS_OFF, STATUS_ON), save=False, update=False)
    @status.setter
    def status(self, status: int) -> None:
        """Safely set the current status of the schedule."""
        self._status = status


OffLightingRoutine = LightingRoutine(
    profile=color_profile.DEFAULT_PROFILE_OFF,
    days=DAYS_ALL,
    start=0,
    end=86400,
    mode=MODE_ON,
    brightness=BRIGHTNESS_DISABLED,
)


class LightingSchedules(Collection):
    """Singleton for managing reusable lighting schedules."""

    __schedules_applied__: dict[str, color_profile.ColorProfile] = {}

    collection_help: str = "lighting schedules"
    entry_cls: str = LightingSchedule

    @classmethod
    def _apply_schedule(
        cls,
        schedule: LightingSchedule,
        routine: LightingRoutine,
        profile: color_profile.ColorProfile,
        manager: led_manager.LEDManager,
    ) -> None:
        """Apply a lighting schedule."""
        # Allow animating if turning on/off, or automatically changing between schedules.
        if (
            cls.__schedules_applied__.get(schedule.manager).name == color_profile.DEFAULT_PROFILE_OFF
            or profile.name == color_profile.DEFAULT_PROFILE_OFF
            or schedule.mode == MODE_AUTO
        ):
            led_delay = schedule.led_delay
        else:
            led_delay = None
        if routine.brightness != BRIGHTNESS_DISABLED:
            brightness = routine.brightness
        elif schedule.brightness != BRIGHTNESS_DISABLED:
            brightness = schedule.brightness
        else:
            brightness = manager.brightness

        colors = color_utils.generate_pattern(profile.corrected_colors, len(manager))
        manager.set_brightness(brightness, show=True, save=False)
        time.sleep(0.25)
        time.sleep(led_delay or manager.led_delay)
        manager.set_colors(colors, delay=0 if led_delay is None else max(led_delay, manager.led_delay), show=True)
        for old_schedule in cls._collection.values():
            old_schedule.status = STATUS_OFF
            for old_routine in old_schedule.routines:
                old_routine.status = STATUS_OFF

        schedule.status = STATUS_ON
        routine.status = STATUS_ON
        # Copy the profile so that changes will be detected instead of comparing to self.
        cls.__schedules_applied__[schedule.manager] = profile.copy()
        if profile.name == color_profile.DEFAULT_PROFILE_OFF:
            manager.status = STATUS_OFF
            logger.info(f"Turned off LEDs on manager {schedule.manager} due to no enabled routines")
        else:
            manager.status = STATUS_ON
            logger.info(
                f"Applied {schedule.name} schedule using {routine.profile} profile to manager {schedule.manager} due to matching {routine.days_human} {routine.start_time} - {routine.end_time} routine"
            )

    @classmethod
    def pending_routines(cls) -> dict[str, tuple[LightingSchedule, LightingRoutine]]:
        """Find all scheduled lighting routines that should be active.

        Returns:
            Mapping of routines that should be active by manager ID.
        """
        with cls._collection_lock:
            pending = {}
            for schedule in sorted(cls._collection.values()):
                pending.setdefault(schedule.manager, (schedule, OffLightingRoutine))
                active = schedule.active
                if active != OffLightingRoutine:
                    pending[schedule.manager] = (schedule, active)
        return pending

    @classmethod
    def update(
        cls,
        entry: str | LightingSchedule,
        **values: Any,
    ) -> dict:
        """Update the values of a schedule.

        Args:
            entry: ID of the original schedule, or the original schedule, to update.
            values: New JSON like attributes to set on the schedule.

        Returns:
            Final schedule configuration with the updated values.
        """
        with cls._collection_lock:
            schedule = cls.get(entry)
            name = get_and_validate(values, KEY_NAME, expected_type=str)
            if name is not None and name != schedule.name:
                schedule.name = name
            routines = get_and_validate(values, KEY_ROUTINES, expected_type=list)
            if routines is not None:
                try:
                    schedule.routines = [LightingRoutine.from_json(routine) for routine in routines]
                except Exception as error:  # pylint: disable=broad-except
                    raise CollectionValueError("invalid-lighting_schedule-routines") from error
            mode = get_and_validate(values, KEY_MODE, expected_type=int)
            if mode is not None:
                schedule.mode = mode
            led_delay = get_and_validate(values, KEY_LED_DELAY, expected_type=float)
            if led_delay is not None:
                schedule.led_delay = led_delay
            brightness = get_and_validate(values, KEY_BRIGHTNESS, expected_type=float)
            if brightness is not None:
                schedule.brightness = brightness
            result = schedule.to_json()
        return result

    @classmethod
    def update_profile(cls, old_profile_name: str, new_profile_name: str) -> None:
        """Update all matching profile names in routines.

        Args:
            old_profile_name: Original color profile name to search for in routines.
            new_profile_name: New color profile name to replace matches with in routines.
        """
        with cls._collection_lock:
            for schedule in cls._collection.values():
                for routine in schedule.routines:
                    if routine.profile == old_profile_name:
                        routine.profile = new_profile_name

    @classmethod
    def verify_active_schedules(cls, force: bool = False) -> None:
        """Monitor schedules and enable/disable routines based on timing.

        Args:
            force: Force the schedule to re-apply in case of changes, even if already active.
        """
        pending = cls.pending_routines()
        with cls._collection_lock:
            for schedule, routine in sorted(pending.values()):
                try:
                    manager = led_manager.LEDManagers.get(schedule.manager)
                    if schedule.manager not in cls.__schedules_applied__:
                        cls.__schedules_applied__[schedule.manager] = color_profile.ColorProfiles.get(
                            color_profile.DEFAULT_PROFILE_OFF
                        )
                except responses.APIError as error:
                    if error.code != 404:
                        raise error
                    logger.warning(f"Skipping update of LEDs on non-existent manager {schedule.manager}")
                    continue
                if manager.mode == MODE_OFF:
                    profile = color_profile.ColorProfiles.get(color_profile.DEFAULT_PROFILE_OFF)
                else:
                    try:
                        profile = color_profile.ColorProfiles.get(routine.profile)
                    except responses.APIError as error:
                        if error.code != 404:
                            raise error
                        # Fallback to off, the profile was not found.
                        profile = color_profile.ColorProfiles.get(color_profile.DEFAULT_PROFILE_OFF)
                if force or cls.__schedules_applied__.get(schedule.manager) != profile:
                    cls._apply_schedule(schedule, routine, profile, manager)


def start_schedule_watchdog() -> None:
    """Create a watchdog for monitoring the schedules and enabling/disabling them based on their routines."""
    global __WATCHDOG__  # pylint: disable=global-statement
    global __WATCHDOG_SLEEP__  # pylint: disable=global-statement
    interval = 5
    if __WATCHDOG__ is None or not __WATCHDOG__.is_alive():

        def _release_the_hound() -> None:
            """Monitor schedules and enable/disable as appropriate."""
            logger.info("Schedule watchdog is running")
            while True:
                if __WATCHDOG_SLEEP__:
                    global __WATCHDOG__  # pylint: disable=global-statement
                    __WATCHDOG__ = None
                    break
                try:
                    LightingSchedules.verify_active_schedules()
                except:  # pylint: disable=bare-except
                    logger.exception("Failed to verify lighting schedules")
                time.sleep(interval)
            logger.info("Schedule watchdog is sleeping")

        # This must be a daemon to ensure that the primary thread does not wait for it.
        __WATCHDOG_SLEEP__ = False
        __WATCHDOG__ = threading.Thread(target=_release_the_hound, daemon=True)
        __WATCHDOG__.start()


def stop_schedule_watchdog() -> None:
    """Stop the schedule watchdog to prevent changing the active color profile routines."""
    global __WATCHDOG_SLEEP__  # pylint: disable=global-statement
    __WATCHDOG_SLEEP__ = True
