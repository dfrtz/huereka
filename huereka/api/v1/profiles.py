"""Routes for /profiles collection."""

import logging

from flask import request

from huereka.api.v1 import api
from huereka.common import color_profile
from huereka.common.color_profile import ColorProfile
from huereka.common.color_profile import ColorProfiles
from huereka.common.lighting_schedule import LightingSchedules
from huereka.shared import responses

logger = logging.getLogger(__name__)


@api.route("/profiles", methods=["GET"])
def profiles_get() -> tuple:
    """Find all currently saved color profiles."""
    profiles = ColorProfiles.to_json()
    response = {
        "item_count": len(profiles),
        "items": profiles,
    }
    return responses.ok(response)


@api.route("/profiles", methods=["POST"])
def profiles_post() -> tuple:
    """Create a new reusable color profile."""
    body = request.get_json(force=True)
    profile = ColorProfile.from_json(body)
    if profile.name == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be overwritten.
        return responses.not_allowed()
    ColorProfiles.register(profile)
    ColorProfiles.save()
    response = {
        "item_count": 1,
        "items": profile.to_json(),
    }
    return responses.ok(response)


@api.route("/profiles/<string:uuid>", methods=["DELETE"])
def profiles_delete_entry(uuid: str) -> tuple:
    """Remove a color profile."""
    if uuid == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be deleted.
        return responses.not_allowed()
    profile = ColorProfiles.remove(uuid)
    ColorProfiles.save()
    return responses.ok(profile.to_json())


@api.route("/profiles/<string:uuid>", methods=["GET"])
def profiles_get_entry(uuid: str) -> tuple:
    """Find a color profile."""
    return responses.ok(ColorProfiles.get(uuid).to_json())


@api.route("/profiles/<string:uuid>", methods=["PUT"])
def profiles_put_entry(uuid: str) -> tuple:
    """Update a color profile's configuration."""
    if uuid == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be modified.
        return responses.not_allowed()
    body = request.get_json(force=True)
    old_profile = ColorProfiles.get(uuid).to_json()
    profile = ColorProfiles.update(uuid, **body)
    ColorProfiles.save()
    if old_profile.get("colors") != profile.get("colors"):
        # Colors were updated, do not wait the watchdog interval and apply immediately.
        LightingSchedules.verify_active_schedules()
    return responses.ok(profile)
