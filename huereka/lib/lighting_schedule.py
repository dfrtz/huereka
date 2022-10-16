"""Helpers for managing lighting schedules on LED strips."""

from __future__ import annotations

import logging
import threading
import time

from datetime import datetime
from typing import Any

import board

from microcontroller import Pin

from huereka.lib import color_profile
from huereka.lib import color_utils
from huereka.lib import led_manager
from huereka.lib import response_utils
from huereka.lib.collections import Collection
from huereka.lib.collections import CollectionEntry
from huereka.lib.collections import CollectionValueError
from huereka.lib.collections import KEY_ID
from huereka.lib.collections import get_and_validate

logger = logging.getLogger(__name__)

__WATCHDOG__ = None
__WATCHDOG_SLEEP__ = True

KEY_ROUTINES = 'routines'
KEY_NAME = 'name'

KEY_BRIGHTNESS = 'brightness'
KEY_DAYS = 'days'
KEY_ENABLED = 'enabled'
KEY_END = 'end'
KEY_LED_DELAY = 'led_delay'
KEY_MANAGER = 'manager'
KEY_MODE = 'mode'
KEY_PROFILE = 'profile'
KEY_START = 'start'
KEY_STATUS = 'status'

BRIGHTNESS_DISABLED = -1.0

DAY_MONDAY = 1
DAY_TUESDAY = 2
DAY_WEDNESDAY = 4
DAY_THURSDAY = 8
DAY_FRIDAY = 16
DAY_SATURDAY = 32
DAY_SUNDAY = 64
DAYS_ALL = DAY_MONDAY | DAY_TUESDAY | DAY_WEDNESDAY | DAY_THURSDAY | DAY_FRIDAY | DAY_SATURDAY | DAY_SUNDAY

DEFAULT_SCHEDULE_DISABLE = 'disable'
DEFAULT_SCHEDULE_ENABLE = 'enable'
DEFAULT_SCHEDULE_OFF = 'off'
DEFAULT_SCHEDULE_ON = 'on'

MODE_OFF = 0
MODE_ON = 1
MODE_AUTO = 2

STATUS_OFF = 0
STATUS_ON = 1


class LightingRoutine:  # Approved override of default. pylint: disable=too-many-instance-attributes
    """Details for running a specific color/lighting profile during a timeframe."""

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
            self,
            profile: str = None,
            days: int | list[int] = DAYS_ALL,
            start: int | float | str = 0,
            end: int | float | str = 86400,
            enabled: bool = True,
            brightness: float = BRIGHTNESS_DISABLED,
    ) -> None:
        """Set up the routine to run a profile at specific times.

        Args:
            profile: ID of the color profile to use while this routine is active.
            days: Combination value representing enabled days.
                Can be combined via bitwise operations. e.g. DAY_MONDAY | DAY_TUESDAY == "Monday" and "Tuesday"
            start: Start time in seconds as 0 < value < 86400 or HH:MM.
            end: End time in seconds as 0 < value < 86400 or HH:MM.
            enabled: Whether the routine is currently enabled.
            brightness: Brightness as a percent between 0.0 and 1.0.
                Overrides schedule brightness. Defaults to -1 to indicate override being disabled.
        """
        self._start = 0
        self._end = 86400
        self._status = STATUS_OFF
        self.profile = profile
        self.start = start
        self.end = end
        if isinstance(days, int):
            self._days = days
        else:
            for day in days:
                self._set_day(day)
        self.enabled = enabled
        self.brightness = brightness

    def __eq__(self, other: Any) -> bool:
        """Make the routine comparable for equality using unique attributes."""
        return isinstance(other, LightingRoutine) \
            and self.profile == other.profile \
            and self.days == other.days \
            and self.start == other.start \
            and self.end == other.end \
            and self.brightness == other.brightness

    def _set_day(self, day: int) -> None:
        """Toggle combination flag for a day on."""
        self._days |= day

    def _unset_day(self, mode: int) -> None:
        """Toggle combination flag for a day off."""
        self._days &= ~mode

    @property
    def active(self) -> bool:
        """Determine if the current time is in the active window (inclusive start and end)."""
        if self.enabled and self.profile:
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
        days = ''
        days += 'S' if self.days & DAY_SUNDAY != 0 else '-'
        days += 'M' if self.days & DAY_MONDAY != 0 else '-'
        days += 'T' if self.days & DAY_TUESDAY != 0 else '-'
        days += 'W' if self.days & DAY_WEDNESDAY != 0 else '-'
        days += 'T' if self.days & DAY_THURSDAY != 0 else '-'
        days += 'F' if self.days & DAY_FRIDAY != 0 else '-'
        days += 'S' if self.days & DAY_SATURDAY != 0 else '-'
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
                raise CollectionValueError('End time must be between 0 and 86400 seconds.')
            self._end = end
        elif isinstance(end, str):
            if ':' not in end or end.count(':') > 1:
                raise CollectionValueError('End time must be in format HH:MM')
            hour, minute = end.split(':')
            hour = int(hour)
            minute = int(minute)
            if hour < 0 or hour > 24:
                raise CollectionValueError('End hour must be between 0 and 24')
            if hour == 24 and minute > 0:
                raise CollectionValueError('End minute must be 0 if hour is 24')
            if minute < 0 or minute > 59:
                raise CollectionValueError('End minute must be between 0 and 59')
            self._end = hour * 60 * 60 + minute * 60

    @property
    def end_time(self) -> str:
        """Provide human readable value for end."""
        return f'{int(self.end / 3600):02}:{int(self.end % 3600 / 60):02}'

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
            raise CollectionValueError('invalid-lighting-routine-profile')
        days = data.get(KEY_DAYS, DAYS_ALL)
        if not isinstance(days, int):
            raise CollectionValueError('invalid-lighting-routine-days')
        start = data.get(KEY_START, 0)
        if not isinstance(start, (int, float, str)):
            raise CollectionValueError('invalid-lighting-routine-start')
        end = data.get(KEY_END, 86400)
        if not isinstance(end, (int, float, str)):
            raise CollectionValueError('invalid-lighting-routine-end')
        enabled = data.get(KEY_ENABLED, True)
        if not isinstance(enabled, bool):
            raise CollectionValueError('invalid-lighting-routine-enabled')
        brightness = data.get(KEY_BRIGHTNESS, BRIGHTNESS_DISABLED)
        if not isinstance(brightness, float):
            raise CollectionValueError('invalid-lighting-routine-brightness')

        return LightingRoutine(
            profile=profile,
            days=days,
            start=start,
            end=end,
            enabled=enabled,
        )

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
                raise CollectionValueError('Start time must be between 0 and 86400 seconds.')
            self._start = int(start)
        elif isinstance(start, str):
            if ':' not in start or start.count(':') > 1:
                raise CollectionValueError('Start time must be in format HH:MM')
            hour, minute = start.split(':')
            hour = int(hour)
            minute = int(minute)
            if hour < 0 or hour > 23:
                raise CollectionValueError('Start hour must be between 0 and 23')
            if minute < 0 or minute > 59:
                raise CollectionValueError('Start minute must be between 0 and 59')
            self._start = hour * 60 * 60 + minute * 60

    @property
    def start_time(self) -> str:
        """Provide human readable value for start."""
        return f'{int(self.start / 3600):02}:{int(self.start % 3600 / 60):02}'

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
            KEY_ENABLED: self.enabled,
            KEY_BRIGHTNESS: self.brightness,
        }
        if not save_only:
            data.update({
                KEY_STATUS: self._status,
            })
        return data


class LightingSchedule(CollectionEntry):
    """Schedule used to control active color profile on an LED strip."""

    def __init__(  # Approved override of default. pylint: disable=too-many-arguments
            self,
            name: str,
            uuid: str = None,
            manager: Pin = board.D18,
            routines: list[LightingRoutine] = None,
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
        super().__init__(name, uuid)
        self.manager = manager
        self.routines = routines or []
        self.led_delay = led_delay
        self.mode = mode
        self.brightness = brightness

    def __eq__(self, other: Any) -> bool:
        """Make the schedule comparable for equality using unique attributes."""
        return isinstance(other, LightingSchedule) \
            and self.name == other.name \
            and self.manager.id == other.manager.id \
            and self.routines == other.routines \
            and self.led_delay == other.led_delay \
            and self.mode == other.mode \
            and self.brightness == other.brightness

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

    @classmethod
    def from_json(cls, data: dict) -> LightingSchedule:
        """Convert JSON type into schedule instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated schedule with the given attributes.
        """
        # Required arguments.
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise CollectionValueError('invalid-lighting-schedule-name')
        manager = data.get(KEY_MANAGER, board.D18.id)
        if not isinstance(manager, int):
            raise CollectionValueError('invalid-lighting-schedule-manager')

        # Optional arguments.
        uuid = data.get(KEY_ID)
        if not isinstance(uuid, str) and uuid is not None:
            raise CollectionValueError('invalid-lighting-schedule-id')
        routines = data.get(KEY_ROUTINES, [])
        if not isinstance(routines, list):
            raise CollectionValueError('invalid-lighting-schedule-routines')
        routines = [LightingRoutine.from_json(routine) for routine in routines]
        mode = data.get(KEY_MODE, MODE_OFF)
        if not isinstance(mode, int):
            raise CollectionValueError('invalid-lighting-schedule-mode')
        led_delay = data.get(KEY_LED_DELAY, led_manager.DEFAULT_LED_UPDATE_DELAY)
        if not isinstance(led_delay, float):
            raise CollectionValueError('invalid-lighting-schedule-led-delay')
        brightness = data.get(KEY_BRIGHTNESS, BRIGHTNESS_DISABLED)
        if not isinstance(led_delay, float):
            raise CollectionValueError('invalid-lighting-schedule-led-brightness')

        return LightingSchedule(
            name,
            uuid=uuid,
            manager=Pin(manager),
            routines=routines,
            led_delay=led_delay,
            mode=mode,
            brightness=brightness,
        )

    def to_json(self, save_only: bool = False) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        data = {
            KEY_ID: self.uuid,
            KEY_NAME: self.name,
            KEY_MANAGER: self.manager.id,
            KEY_ROUTINES: [routine.to_json(save_only=save_only) for routine in self.routines],
            KEY_MODE: self.mode,
            KEY_LED_DELAY: self.led_delay,
            KEY_BRIGHTNESS: self.brightness,
        }
        return data


OffLightingRoutine = LightingRoutine(
    DEFAULT_SCHEDULE_OFF,
    days=DAYS_ALL,
    start=0,
    end=86400,
    enabled=True,
    brightness=0.0,
)


class LightingSchedules(Collection):
    """Singleton for managing reusable lighting schedules."""

    __schedules_applied__: dict[int, color_profile.ColorProfile] = {}

    _collection: dict[str, LightingSchedule] = {}
    _collection_lock: threading.Condition = threading.Condition()
    _collection_uri: str = None

    collection_help: str = 'lighting schedule'
    entry_cls: str = LightingSchedule

    @classmethod
    def disable_all(cls) -> None:
        """Disable all schedules."""
        with cls._collection_lock:
            for schedule in cls._collection.values():
                schedule.enabled = False

    @classmethod
    def enable_all(cls) -> None:
        """Enable all schedules."""
        with cls._collection_lock:
            for schedule in cls._collection.values():
                schedule.enabled = True

    @classmethod
    def get(cls, key: str) -> LightingSchedule:
        """Find the lighting schedule associated with a given key.

        Override to update typehint and simplify caller typechecks.
        """
        return super().get(key)

    @classmethod
    def pending_routines(cls) -> dict[int, tuple[LightingSchedule, LightingRoutine]]:
        """Find all scheduled lighting routines that should be active.

        Returns:
            Mapping of routines that should be active by manager ID.
        """
        with cls._collection_lock:
            pending = {}
            for schedule in sorted(cls._collection.values()):
                pending.setdefault(schedule.manager.id, (schedule, OffLightingRoutine))
                active = schedule.active
                if active != OffLightingRoutine:
                    pending[schedule.manager.id] = (schedule, active)
        return pending

    @classmethod
    def update(
            cls,
            uuid: str,
            new_values: dict,
    ) -> LightingSchedule:
        """Update the values of a schedule.

        Args:
            uuid: ID of the original schedule to update.
            new_values: New JSON like attributes to set on the schedule.

        Returns:
            Final schedule with the updated values.
        """
        with cls._collection_lock:
            schedule = cls.get(uuid)
            invalid_prefix = 'invalid-lighting-schedule'
            name = get_and_validate(new_values, KEY_NAME, str, nullable=True, error_prefix=invalid_prefix)
            if name is not None and name != schedule.name:
                schedule.name = name
            routines = get_and_validate(new_values, KEY_ROUTINES, list, nullable=True, error_prefix=invalid_prefix)
            if routines is not None:
                try:
                    schedule.routines = [LightingRoutine.from_json(routine) for routine in routines]
                except Exception as error:  # pylint: disable=broad-except
                    raise CollectionValueError(f'{invalid_prefix}-routines') from error
            mode = get_and_validate(new_values, KEY_MODE, int, nullable=True, error_prefix=invalid_prefix)
            if mode is not None:
                schedule.mode = mode
            led_delay = get_and_validate(new_values, KEY_LED_DELAY, float, nullable=True, error_prefix=invalid_prefix)
            if led_delay is not None:
                schedule.led_delay = led_delay
            brightness = get_and_validate(new_values, KEY_BRIGHTNESS, float, nullable=True, error_prefix=invalid_prefix)
            if brightness is not None:
                schedule.brightness = brightness
        return schedule

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
    def validate_entry(cls, data: dict, index: int) -> bool:
        """Actions to perform on every collection entry load."""
        uuid = data.get(KEY_NAME)
        if uuid in cls._collection:
            logger.warning(f'Skipping duplicate {cls.collection_help} setup at index {index} using uuid {uuid}')
            return False
        return True

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
                    profile = color_profile.ColorProfiles.get(routine.profile)
                except response_utils.APIError as error:
                    if error.code != 404:
                        raise error
                    # Fallback to off, the profile was not found.
                    profile = color_profile.ColorProfiles.get(color_profile.DEFAULT_PROFILE_OFF)
                if force or cls.__schedules_applied__.get(schedule.manager.id) != profile:
                    try:
                        led_count = len(led_manager.LEDManagers.get(schedule.manager))
                        led_delay = schedule.led_delay if not schedule.mode == MODE_ON else 0
                        colors = color_utils.generate_pattern(profile.corrected_colors, led_count)
                        led_manager.LEDManagers.set_colors(colors, pin=schedule.manager, delay=led_delay, show=False)
                        if routine.brightness != BRIGHTNESS_DISABLED:
                            brightness = routine.brightness
                        elif schedule.brightness != BRIGHTNESS_DISABLED:
                            brightness = schedule.brightness
                        else:
                            brightness = led_manager.LEDManagers.get(schedule.manager).brightness
                        led_manager.LEDManagers.set_brightness(brightness, pin=schedule.manager, show=False, save=False)
                        led_manager.LEDManagers.show(pin=schedule.manager)
                    except response_utils.APIError as error:
                        if error.code != 404:
                            raise error
                        continue
                    for old_schedule in cls._collection.values():
                        for old_routine in old_schedule.routines:
                            old_routine._status = STATUS_OFF
                    routine._status = STATUS_ON
                    # Copy the profile so that changes will be detected instead of comparing to self.
                    cls.__schedules_applied__[schedule.manager.id] = profile.copy()
                    if profile.name == color_profile.DEFAULT_PROFILE_OFF:
                        logger.info(f'Turned off LEDs on manager {schedule.manager.id} due to no enabled routines')
                    else:
                        logger.info(f'Applied {schedule.name} schedule using {routine.profile} profile to manager {schedule.manager.id} due to matching {routine.days_human} {routine.start_time} - {routine.end_time} routine')


def start_schedule_watchdog() -> None:
    """Create a watchdog for monitoring the schedules and enabling/disabling them based on their routines."""
    global __WATCHDOG__  # pylint: disable=global-statement
    global __WATCHDOG_SLEEP__  # pylint: disable=global-statement
    interval = 5
    if __WATCHDOG__ is None or not __WATCHDOG__.is_alive():
        def _release_the_hound() -> None:
            """Monitor schedules and enable/disable as appropriate."""
            logger.info('Schedule watchdog is running')
            while True:
                if __WATCHDOG_SLEEP__:
                    global __WATCHDOG__  # pylint: disable=global-statement
                    __WATCHDOG__ = None
                    break
                try:
                    LightingSchedules.verify_active_schedules()
                except:  # pylint: disable=bare-except
                    logger.exception('Failed to verify lighting schedules')
                time.sleep(interval)
            logger.info('Schedule watchdog is sleeping')

        # This must be a daemon to ensure that the primary thread does not wait for it.
        __WATCHDOG_SLEEP__ = False
        __WATCHDOG__ = threading.Thread(target=_release_the_hound, daemon=True)
        __WATCHDOG__.start()


def stop_schedule_watchdog() -> None:
    """Stop the schedule watchdog to prevent changing the active color profile routines."""
    global __WATCHDOG_SLEEP__  # pylint: disable=global-statement
    __WATCHDOG_SLEEP__ = True
