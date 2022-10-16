"""Routes for /profiles collection."""

import logging

from flask import request

from huereka.api.v1 import api
from huereka.lib import color_profile
from huereka.lib import response_utils as responses
from huereka.lib.color_profile import ColorProfile
from huereka.lib.color_profile import ColorProfiles
from huereka.lib.lighting_schedule import LightingSchedules

logger = logging.getLogger(__name__)


@api.route('/profiles', methods=['GET'])
def profiles_get() -> tuple:
    """Find all currently saved color profiles."""
    return responses.ok(ColorProfiles.to_json())


@api.route('/profiles', methods=['POST'])
def profiles_post() -> tuple:
    """Create a new reusable color profile."""
    body = request.get_json(force=True)
    profile = ColorProfile.from_json(body)
    if profile.name == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be overwritten.
        return responses.not_allowed()
    ColorProfiles.register(profile)
    ColorProfiles.save()
    return responses.ok(profile.to_json())


@api.route('/profiles/<string:uuid>', methods=['DELETE'])
def profiles_delete_entry(uuid: str) -> tuple:
    """Remove a color profile."""
    if uuid == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be deleted.
        return responses.not_allowed()
    profile = ColorProfiles.remove(uuid)
    ColorProfiles.save()
    return responses.ok(profile.to_json())


@api.route('/profiles/<string:uuid>', methods=['GET'])
def profiles_get_entry(uuid: str) -> tuple:
    """Find a color profile."""
    return responses.ok(ColorProfiles.get(uuid).to_json())


@api.route('/profiles/<string:uuid>', methods=['PUT'])
def profiles_put_entry(uuid: str) -> tuple:
    """Update a color profile's values."""
    if uuid == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be modified.
        return responses.not_allowed()
    body = request.get_json(force=True)
    old_profile = ColorProfiles.get(uuid).copy()
    profile = ColorProfiles.update(uuid, body)
    ColorProfiles.save()
    if old_profile.colors != profile.colors:
        # Colors were updated, do not wait the watchdog interval and apply immediately.
        LightingSchedules.verify_active_schedules()
    return responses.ok(profile.to_json())
