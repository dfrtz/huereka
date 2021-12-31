"""Helpers for managing lighting schedules on LED strips."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time

from datetime import datetime
from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

import board

from microcontroller import Pin

from huereka.lib import color_profile
from huereka.lib import color_utils
from huereka.lib import led_manager
from huereka.lib import response_utils

logger = logging.getLogger(__name__)

__WATCHDOG__ = None
__WATCHDOG_SLEEP__ = True

KEY_ROUTINES = 'routines'
KEY_NAME = 'name'

KEY_DAYS = 'days'
KEY_ENABLED = 'enabled'
KEY_END = 'end'
KEY_MANAGER = 'manager'
KEY_START = 'start'
KEY_PROFILE = 'profile'

DAY_SUNDAY = 1
DAY_MONDAY = 2
DAY_TUESDAY = 4
DAY_WEDNESDAY = 8
DAY_THURSDAY = 16
DAY_FRIDAY = 32
DAY_SATURDAY = 64
DAY_ALL = DAY_SUNDAY | DAY_MONDAY | DAY_TUESDAY | DAY_WEDNESDAY | DAY_THURSDAY | DAY_FRIDAY | DAY_SATURDAY

DEFAULT_SCHEDULE_DISABLE = 'disable'
DEFAULT_SCHEDULE_ENABLE = 'enable'
DEFAULT_SCHEDULE_OFF = 'off'
DEFAULT_SCHEDULE_ON = 'on'

_iso_days = {
    0: DAY_SUNDAY,
    1: DAY_MONDAY,
    2: DAY_TUESDAY,
    3: DAY_WEDNESDAY,
    4: DAY_THURSDAY,
    5: DAY_FRIDAY,
    6: DAY_SATURDAY,
}


class LightingRoutine:
    """Details for running a specific color/lighting profile during a timeframe."""

    def __init__(  # Approved override of the default argument limit. pylint: disable=too-many-arguments
            self,
            profile: str = None,
            days: Union[int, list[int]] = DAY_ALL,
            start: Union[int, str] = 0,
            end: Union[int, str] = 86400,
            enabled: bool = True,
    ) -> None:
        """Setup the routine to run a profile at specific times.

        Args:
            profile: Name of the color profile to use while this routine is active.
            days: Combination value representing enabled days.
                Can be combined via bitwise operations. e.g. DAY_MONDAY | DAY_TUESDAY == "Monday" and "Tuesday"
            start: Start time in seconds as 0 < value < 86400 or HH:MM.
            end: End time in seconds as 0 < value < 86400 or HH:MM.
            enabled: Whether the routine is currently enabled.
        """
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
        self.enabled = enabled

    def __eq__(self, other: Any) -> bool:
        """Make the routine comparable for equality using unique attributes."""
        return isinstance(other, LightingRoutine) \
            and self.profile == other.profile \
            and self.days == other.days \
            and self.start == other.start \
            and self.end == other.end

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
            in_day = self._days = DAY_ALL or self._days & _iso_days[now.isoweekday()] != 0
            if in_day:
                now_in_seconds = now.hour * 60 * 60 + now.minute * 60 + now.second
                if self.start <= now_in_seconds <= self.end:
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
    def end(self, end: Union[str, int]) -> None:
        """Update time when routine stops within a day.

        Args:
            end: End time in seconds as 0 < value < 86400 or HH:MM.
        """
        if isinstance(end, int):
            if end < 0 or end > 86400:
                raise LightingScheduleValueError('End time must be between 0 and 86400 seconds.')
        elif isinstance(end, str):
            if ':' not in end or end.count(':') > 1:
                raise LightingScheduleValueError('End time must be in format HH:MM')
            hour, minute = end.split(':')
            if hour < 0 or hour > 23:
                raise LightingScheduleValueError('End hour must be between 0 and 23')
            if minute < 0 or minute > 59:
                raise LightingScheduleValueError('End minute must be between 0 and 59')
            self._end = hour * 60 * 60 + minute * 60

    @property
    def end_time(self) -> str:
        """Provide human readable value for end."""
        return f'{int(self.end / 3600):02}:{int(self.end % 3600 / 60):02}'

    @staticmethod
    def from_json(data: dict) -> LightingRoutine:
        """Convert JSON type into schedule instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated routine with the given attributes.
        """
        # Optional arguments.
        profile = data.get(KEY_PROFILE)
        if not profile or not isinstance(profile, str):
            raise LightingScheduleValueError('invalid-lighting-routine-profile')
        days = data.get(KEY_DAYS, DAY_ALL)
        if not isinstance(days, int):
            raise LightingScheduleValueError('invalid-lighting-routine-days')
        start = data.get(KEY_START, 0)
        if not isinstance(start, (int, str)):
            raise LightingScheduleValueError('invalid-lighting-routine-start')
        end = data.get(KEY_END, 86400)
        if not isinstance(end, (int, str)):
            raise LightingScheduleValueError('invalid-lighting-routine-end')
        enabled = data.get(KEY_ENABLED, True)
        if not isinstance(enabled, bool):
            raise LightingScheduleValueError('invalid-lighting-routine-enabled')

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
    def start(self, start: Union[str, int]) -> None:
        """Update time when routine starts within a day.

        Args:
            start: Start time in seconds as 0 < value < 86400 or HH:MM.
        """
        if isinstance(start, int):
            if start < 0 or start > 86400:
                raise LightingScheduleValueError('Start time must be between 0 and 86400 seconds.')
            self._start = start
        elif isinstance(start, str):
            if ':' not in start or start.count(':') > 1:
                raise LightingScheduleValueError('Start time must be in format HH:MM')
            hour, minute = start.split(':')
            if hour < 0 or hour > 23:
                raise LightingScheduleValueError('Start hour must be between 0 and 23')
            if minute < 0 or minute > 59:
                raise LightingScheduleValueError('Start minute must be between 0 and 59')
            self._start = hour * 60 * 60 + minute * 60

    @property
    def start_time(self) -> str:
        """Provide human readable value for start."""
        return f'{int(self.start / 3600):02}:{int(self.start % 3600 / 60):02}'

    def to_json(self) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_PROFILE: self.profile,
            KEY_DAYS: self._days,
            KEY_START: self.start_time,
            KEY_END: self.end_time,
            KEY_ENABLED: self.enabled,
        }


class LightingSchedule:
    """Schedule used to control active color profile on an LED strip."""

    def __init__(
            self,
            name: str,
            manager: Pin = board.D18,
            routines: list[LightingRoutine] = None,
            enabled: bool = True,
    ) -> None:
        """Setup a schedule for managing active color profile.

        Args:
            name: Human readable name used to store/reference in collections.
            manager: ID of the LED manager that will be controlled by this schedule.
            routines: Timeframes to trigger specific color profiles.
            enabled: Whether the schedule is currently enabled.
        """
        self.name = name
        self.manager = manager
        self.routines = routines or []
        self.enabled = enabled

    def __eq__(self, other: Any) -> bool:
        """Make the schedule comparable for equality using unique attributes."""
        return isinstance(other, LightingSchedule) \
            and self.name == other.name \
            and self.manager.id == other.manager.id \
            and self.routines == other.routines

    def __hash__(self) -> int:
        """Make the schedule hashable."""
        return hash(self.name)

    def __gt__(self, other: Any) -> bool:
        """Make the schedule comparable for less greater than operations by name."""
        return isinstance(other, LightingSchedule) and self.name > other.name

    def __lt__(self, other: Any) -> bool:
        """Make the schedule comparable for less than operations by name."""
        return isinstance(other, LightingSchedule) and self.name < other.name

    @property
    def active(self) -> Optional[LightingRoutine]:
        """Get the currently active routine from this schedule if one is available."""
        active_routine = OffLightingRoutine
        if self.enabled:
            for routine in self.routines:
                if routine.active:
                    active_routine = routine
                    break
        return active_routine

    @staticmethod
    def from_json(data: dict) -> LightingSchedule:
        """Convert JSON type into schedule instance.

        Args:
            data: Mapping of the instance attributes.

        Returns:
            Instantiated schedule with the given attributes.
        """
        # Required arguments.
        name = data.get(KEY_NAME)
        if not name or not isinstance(name, str):
            raise LightingScheduleValueError('invalid-lighting-schedule-name')
        manager = data.get(KEY_MANAGER, board.D18.id)
        if not isinstance(manager, int):
            raise LightingScheduleValueError('invalid-lighting-schedule-manager')

        # Optional arguments.
        routines = data.get(KEY_ROUTINES, [])
        if not isinstance(routines, list):
            raise LightingScheduleValueError('invalid-lighting-schedule-routines')
        routines = [LightingRoutine.from_json(routine) for routine in routines]
        enabled = data.get(KEY_ENABLED, True)
        if not isinstance(enabled, bool):
            raise LightingScheduleValueError('invalid-lighting-schedule-enabled')

        return LightingSchedule(
            name,
            Pin(manager),
            routines=routines,
            enabled=enabled,
        )

    def to_json(self) -> dict:
        """Convert the instance into a JSON compatible type.

        Returns:
            Mapping of the instance attributes.
        """
        return {
            KEY_NAME: self.name,
            KEY_MANAGER: self.manager.id,
            KEY_ROUTINES: [routine.to_json() for routine in self.routines],
            KEY_ENABLED: self.enabled,
        }


OffLightingRoutine = LightingRoutine(DEFAULT_SCHEDULE_OFF)


class LightingScheduleValueError(response_utils.APIError, ValueError):
    """Exception subclass to help identify failures that indicate a lighting schedule value was invalid."""

    def __init__(self, error: str, data: Any = None, code: int = 422) -> None:
        """Setup the user details of the error."""
        super().__init__(error, data, code=code)


class LightingScheduleDuplicate(LightingScheduleValueError):
    """Exception subclass to help identify failures that indicate a lighting schedule already exists."""

    def __init__(self, name: str) -> None:
        """Setup the user details of the error.

        Args:
            name: Name of the schedule that already exists.
        """
        super().__init__('duplicate-lighting-schedule', name, code=422)


class LightingScheduleNotFound(LightingScheduleValueError):
    """Exception subclass to help identify failures that indicate a lighting schedule needs to be created first."""

    def __init__(self, name: str) -> None:
        """Setup the user details of the error.

        Args:
            name: Name of the schedule that was not found.
        """
        super().__init__('missing-lighting-schedule', name, code=404)


class LightingSchedules:
    """Singleton for managing reusable lighting schedules."""

    __schedules__: Dict[str, LightingSchedule] = {}
    __schedules_lock__ = threading.Condition()
    __schedules_applied__: dict[int, color_profile.ColorProfile] = {}
    __schedules_uri__: str = None

    @classmethod
    def create(
            cls,
            name: str,
            manager: Pin = board.D18,
            routines: list[LightingRoutine] = None,
            enabled: bool = True,
    ) -> LightingSchedule:
        """Setup a lighting schedule for reuse and concurrent access.

        Args:
            name: Human readable name used to store/reference in collections.
            manager: ID of the LED manager that will be controlled by this schedule.
            routines: Timeframes to trigger specific color profiles.
            enabled: Whether the schedule is currently enabled.

        Returns:
            New lighting schedule if not already created.

        Raises:
            LightingScheduleDuplicate if the schedule is already found, indicating it should updated instead.
        """
        with cls.__schedules_lock__:
            if name in cls.__schedules__:
                raise LightingScheduleDuplicate(name)
            cls.__schedules__[name] = LightingSchedule(
                name,
                manager=manager,
                routines=routines,
                enabled=enabled,
            )
            return cls.__schedules__[name]

    @classmethod
    def disable_all(cls) -> None:
        """Disable all schedules."""
        with cls.__schedules_lock__:
            for schedule in cls.__schedules__.values():
                schedule.enabled = False

    @classmethod
    def enable_all(cls) -> None:
        """Enable all schedules."""
        with cls.__schedules_lock__:
            for schedule in cls.__schedules__.values():
                schedule.enabled = True

    @classmethod
    def get(cls, name: str) -> Any:
        """Find the schedule associated with a given name, or raise an error message for handling downstream.

        Args:
            name: Name of the saved schedule.

        Returns:
            Instance of the schedule matching the name.

        Raises:
            LightingScheduleNotFound if the scheulde is not found in persistent storage.
        """
        schedule = cls.__schedules__.get(name)
        if not schedule:
            raise LightingScheduleNotFound(name)
        return schedule

    @classmethod
    def load(cls, schedule_data: Union[str, list[dict]]) -> None:
        """Initialize the schedule cache by loading saved configurations.

        Args:
            schedule_data: Scheduling data to load as JSON string, JSON file path, or pre-structured python objects.
        """
        loaded_data = []
        if isinstance(schedule_data, str):
            if schedule_data.startswith('['):
                try:
                    loaded_data = json.loads(schedule_data)
                except Exception:  # pylint: disable=broad-except
                    logger.exception('Failed to load lighting schedules from text')
            elif schedule_data.startswith(('/', 'file://')):
                schedule_data = schedule_data.removeprefix('file://')
                cls.__schedules_uri__ = schedule_data
                try:
                    with open(schedule_data, 'rt', encoding='utf-8') as file_in:
                        try:
                            loaded_data = json.load(file_in)
                            logger.info(f'Loaded lighting schedules from {cls.__schedules_uri__}')
                        except Exception:  # pylint: disable=broad-except
                            logger.exception(f'Failed to load lighting schedules from local file {schedule_data}')
                except FileNotFoundError:
                    logger.warning(f'Skipping lighting schedules load, file not found {schedule_data}')
        elif isinstance(schedule_data, list):
            loaded_data = schedule_data
        for index, schedule_config in enumerate(loaded_data):
            name = schedule_config.get(KEY_NAME)
            if name in cls.__schedules__:
                logger.warning(f'Skipping duplicate lighting schedule setup at index {index}')
                continue
            try:
                manager = LightingSchedule.from_json(schedule_config)
                cls.register(manager)
            except Exception:  # pylint: disable=broad-except
                logger.exception(f'Skipping invalid lighting schedule setup at index {index}')

    @classmethod
    def register(cls, schedule: LightingSchedule) -> None:
        """Store a schedule for concurrent access.

        Args:
            schedule: Previously setup lighting schedule to be stored in the cache and used during concurrent calls.
        """
        with cls.__schedules_lock__:
            name = schedule.name
            if name in cls.__schedules__:
                raise LightingScheduleDuplicate(name)
            cls.__schedules__[name] = schedule

    @classmethod
    def remove(cls, name: str) -> LightingSchedule:
        """Remove a schedule from persistent storage.

        Args:
            name: Name of the saved schedule.

        Raises:
            LightingScheduleNotFound if the schedule does not exist and cannot be removed.
        """
        with cls.__schedules_lock__:
            if name not in cls.__schedules__:
                raise LightingScheduleNotFound(name)
            return cls.__schedules__.pop(name)

    @classmethod
    def save(cls) -> None:
        """Persist the current schedules to storage."""
        if cls.__schedules_uri__ is not None:
            os.makedirs(os.path.dirname(cls.__schedules_uri__), exist_ok=True)
            with cls.__schedules_lock__:
                # Write to a temporary file, and then move to expected file, so that if for any reason
                # it is interrupted, the original remains intact and the user can decide which to load.
                tmp_path = f'{cls.__schedules_uri__}.tmp'
                with open(tmp_path, 'w+', encoding='utf-8') as file_out:
                    json.dump(cls.to_json(), file_out, indent=2)
                shutil.move(tmp_path, cls.__schedules_uri__)
                logger.info(f'Saved lighting schedule to {cls.__schedules_uri__}')

    @classmethod
    def to_json(cls) -> list[dict]:
        """Convert all the schedules into JSON compatible types.

        Returns:
            List of schedule configurations.
        """
        with cls.__schedules_lock__:
            return [schedule.to_json() for schedule in cls.__schedules__.values()]

    @classmethod
    def update(
            cls,
            old_schedule: str,
            new_values: dict,
    ) -> LightingSchedule:
        """Update the values of a schedule.

        Args:
            old_schedule: Name of the original schedule to update.
            new_values: New JSON like attributes to set on the schedule.

        Returns:
            Final schedule with the updated values.
        """
        with cls.__schedules_lock__:
            schedule = cls.get(old_schedule)
            name = new_values.get(KEY_NAME)
            if name is not None:
                if not isinstance(name, str):
                    raise LightingScheduleValueError('invalid-lighting-schedule-name')
                original_name = schedule.name
                schedule.name = name
                cls.__schedules__[name] = cls.__schedules__.pop(original_name)
            routines = new_values.get(KEY_ROUTINES)
            if routines is not None:
                if not isinstance(routines, list):
                    raise LightingScheduleValueError('invalid-lighting-schedule-routines')
                try:
                    schedule.routines = [LightingRoutine.from_json(routine) for routine in routines]
                except Exception as error:  # pylint: disable=broad-except
                    raise LightingScheduleValueError('invalid-lighting-schedule-routines') from error
            enabled = new_values.get(KEY_ENABLED)
            if enabled is not None:
                if not isinstance(enabled, bool):
                    raise LightingScheduleValueError('invalid-lighting-schedule-enabled')
                schedule.enabled = enabled
        return schedule

    @classmethod
    def update_profile(cls, old_profile_name: str, new_profile_name: str) -> None:
        """Update all matching profile names in routines.

        Args:
            old_profile_name: Original color profile name to search for in routines.
            new_profile_name: New color profile name to replace matches with in routines.
        """
        with cls.__schedules_lock__:
            for schedule in cls.__schedules__.values():
                for routine in schedule.routines:
                    if routine.profile == old_profile_name:
                        routine.profile = new_profile_name

    @classmethod
    def verify_active_schedules(cls) -> None:
        """Monitor schedules and enable/disable routines based on timing."""
        with cls.__schedules_lock__:
            pending = {}
            for schedule in sorted(cls.__schedules__.values()):
                pending.setdefault(schedule.manager.id, (schedule, OffLightingRoutine))
                if pending.get(schedule.manager.id) == OffLightingRoutine:
                    # First non-off routine takes priority, rest are skipped.
                    continue
                active = schedule.active
                if active != OffLightingRoutine:
                    pending[schedule.manager.id] = (schedule, active)
            for schedule, routine in sorted(pending.values()):
                try:
                    profile = color_profile.ColorProfiles.get(routine.profile)
                except color_profile.ColorProfileNotFound:
                    profile = color_profile.ColorProfiles.get(color_profile.DEFAULT_PROFILE_OFF)
                if cls.__schedules_applied__.get(schedule.manager.id) != profile:
                    try:
                        led_count = len(led_manager.LEDManagers.get(schedule.manager))
                        colors = color_utils.generate_pattern(profile.colors, led_count)
                        led_manager.LEDManagers.set_colors(colors, pin=schedule.manager)
                    except led_manager.LEDManagerNotFound:
                        continue
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
