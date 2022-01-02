"""Routes for /schedules collection."""

import logging

from flask import request

from huereka.api.v1 import api
from huereka.lib import response_utils as responses
from huereka.lib import lighting_schedule
from huereka.lib.lighting_schedule import LightingSchedule
from huereka.lib.lighting_schedule import LightingSchedules

logger = logging.getLogger(__name__)

RESERVED_NAMES = (
    lighting_schedule.DEFAULT_SCHEDULE_DISABLE,
    lighting_schedule.DEFAULT_SCHEDULE_ENABLE,
    lighting_schedule.DEFAULT_SCHEDULE_OFF,
    lighting_schedule.DEFAULT_SCHEDULE_ON,
)


@api.route('/schedules', methods=['GET'])
def schedules_get() -> tuple:
    """Find all currently saved lighting schedules."""
    return responses.ok(LightingSchedules.to_json())


@api.route('/schedules', methods=['POST'])
def schedules_post() -> tuple:
    """Create a new lighting schedule."""
    body = request.get_json(force=True)
    schedule = LightingSchedule.from_json(body)
    if schedule.name in RESERVED_NAMES:
        raise lighting_schedule.CollectionValueError('reserved-name')
    LightingSchedules.register(schedule)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:name>', methods=['DELETE'])
def schedules_delete_entry(name: str) -> tuple:
    """Remove a lighting schedule based on name attribute."""
    if name in RESERVED_NAMES:
        return responses.not_allowed()
    schedule = LightingSchedules.remove(name)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:name>', methods=['GET'])
def schedules_get_entry(name: str) -> tuple:
    """Find a lighting schedule based on name attribute."""
    if name in RESERVED_NAMES:
        return responses.not_allowed()
    return responses.ok(LightingSchedules.get(name).to_json())


@api.route('/schedules/<string:name>', methods=['PUT'])
def schedules_put_entry(name: str) -> tuple:
    """Update a lighting schedules' values based on the current name."""
    if name == lighting_schedule.DEFAULT_SCHEDULE_ENABLE:
        lighting_schedule.start_schedule_watchdog()
        return responses.ok()
    if name == lighting_schedule.DEFAULT_SCHEDULE_DISABLE:
        lighting_schedule.stop_schedule_watchdog()
        return responses.ok()
    if name == lighting_schedule.DEFAULT_SCHEDULE_OFF:
        LightingSchedules.disable_all()
        LightingSchedules.save()
        LightingSchedules.verify_active_schedules()
        return responses.ok()
    if name == lighting_schedule.DEFAULT_SCHEDULE_ON:
        LightingSchedules.enable_all()
        LightingSchedules.save()
        LightingSchedules.verify_active_schedules()
        return responses.ok()
    if name in RESERVED_NAMES:
        # Safety catch-all in case one is added to reserved list but no custom logic.
        return responses.not_allowed()
    body = request.get_json(force=True)
    schedule = LightingSchedules.update(name, body)
    LightingSchedules.save()
    LightingSchedules.verify_active_schedules()
    return responses.ok(schedule.to_json())
