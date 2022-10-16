"""Routes for /schedules collection."""

import logging

from flask import request

from huereka.api.v1 import api
from huereka.lib import response_utils as responses
from huereka.lib import lighting_schedule
from huereka.lib.lighting_schedule import LightingSchedule
from huereka.lib.lighting_schedule import LightingSchedules

logger = logging.getLogger(__name__)

RESERVED_IDS = (
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
    if schedule.name in RESERVED_IDS:
        raise lighting_schedule.CollectionValueError('reserved-name')
    LightingSchedules.register(schedule)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:uuid>', methods=['DELETE'])
def schedules_delete_entry(uuid: str) -> tuple:
    """Remove a lighting schedule."""
    if uuid in RESERVED_IDS:
        return responses.not_allowed()
    schedule = LightingSchedules.remove(uuid)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:uuid>', methods=['GET'])
def schedules_get_entry(uuid: str) -> tuple:
    """Find a lighting schedule."""
    if uuid in RESERVED_IDS:
        return responses.not_allowed()
    return responses.ok(LightingSchedules.get(uuid).to_json())


@api.route('/schedules/<string:uuid>', methods=['PUT'])
def schedules_put_entry(uuid: str) -> tuple:
    """Update a lighting schedules' values."""
    if uuid == lighting_schedule.DEFAULT_SCHEDULE_ENABLE:
        lighting_schedule.start_schedule_watchdog()
        return responses.ok()
    if uuid == lighting_schedule.DEFAULT_SCHEDULE_DISABLE:
        lighting_schedule.stop_schedule_watchdog()
        return responses.ok()
    if uuid == lighting_schedule.DEFAULT_SCHEDULE_OFF:
        LightingSchedules.disable_all()
        LightingSchedules.save()
        LightingSchedules.verify_active_schedules()
        return responses.ok()
    if uuid == lighting_schedule.DEFAULT_SCHEDULE_ON:
        LightingSchedules.enable_all()
        LightingSchedules.save()
        LightingSchedules.verify_active_schedules()
        return responses.ok()
    if uuid in RESERVED_IDS:
        # Safety catch-all in case one is added to reserved list but no custom logic.
        return responses.not_allowed()
    body = request.get_json(force=True)
    schedule = LightingSchedules.update(uuid, body)
    LightingSchedules.save()
    LightingSchedules.verify_active_schedules(force=True)
    return responses.ok(schedule.to_json())
