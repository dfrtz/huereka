"""Routes for /schedules collection."""

import logging

from flask import request

from huereka.api.v1 import api
from huereka.lib import response_utils as responses
from huereka.lib.lighting_schedule import LightingSchedule
from huereka.lib.lighting_schedule import LightingSchedules

logger = logging.getLogger(__name__)


@api.route('/schedules', methods=['GET'])
def schedules_get() -> tuple:
    """Find all currently saved lighting schedules."""
    schedules = LightingSchedules.to_json()
    response = {
        'item_count': len(schedules),
        'items': schedules,
    }
    return responses.ok(response)


@api.route('/schedules', methods=['POST'])
def schedules_post() -> tuple:
    """Create a new lighting schedule."""
    body = request.get_json(force=True)
    schedule = LightingSchedule.from_json(body)
    LightingSchedules.register(schedule)
    LightingSchedules.save()
    response = {
        'item_count': 1,
        'items': schedule.to_json(),
    }
    return responses.ok(response)


@api.route('/schedules/<string:uuid>', methods=['DELETE'])
def schedules_delete_entry(uuid: str) -> tuple:
    """Remove a lighting schedule."""
    schedule = LightingSchedules.remove(uuid)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:uuid>', methods=['GET'])
def schedules_get_entry(uuid: str) -> tuple:
    """Find a lighting schedule."""
    return responses.ok(LightingSchedules.get(uuid).to_json())


@api.route('/schedules/<string:uuid>', methods=['PUT'])
def schedules_put_entry(uuid: str) -> tuple:
    """Update a lighting schedule's configuration."""
    body = request.get_json(force=True)
    schedule = LightingSchedules.update(uuid, body)
    LightingSchedules.save()
    LightingSchedules.verify_active_schedules(force=True)
    return responses.ok(schedule)
