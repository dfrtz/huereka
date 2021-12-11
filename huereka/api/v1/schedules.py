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
    return responses.ok(LightingSchedules.to_json())


@api.route('/schedules', methods=['POST'])
def schedules_post() -> tuple:
    """Create a new lighting schedule."""
    body = request.get_json(force=True)
    schedule = LightingSchedule.from_json(body)
    LightingSchedules.register(schedule)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:name>', methods=['DELETE'])
def schedules_delete(name: str) -> tuple:
    """Remove a lighting schedule based on name attribute."""
    schedule = LightingSchedules.remove(name)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())


@api.route('/schedules/<string:name>', methods=['GET'])
def schedules_get_entry(name: str) -> tuple:
    """Find a lighting schedule based on name attribute."""
    return responses.ok(LightingSchedules.get(name).to_json())


@api.route('/schedules/<string:name>', methods=['PUT'])
def schedules_put(name: str) -> tuple:
    """Update a lighting schedules' values based on the current name."""
    body = request.get_json(force=True)
    schedule = LightingSchedules.update(name, body)
    LightingSchedules.save()
    return responses.ok(schedule.to_json())
