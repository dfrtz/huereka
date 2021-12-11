"""Routes for /profiles collection."""

import logging

from flask import request

from huereka.api.v1 import api
from huereka.lib import color_profile
from huereka.lib import response_utils as responses
from huereka.lib.color_profile import ColorProfile
from huereka.lib.color_profile import ColorProfiles

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


@api.route('/profiles/<string:name>', methods=['DELETE'])
def profiles_delete(name: str) -> tuple:
    """Remove a color profile based on name attribute."""
    if name == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be deleted.
        return responses.not_allowed()
    profile = ColorProfiles.remove(name)
    ColorProfiles.save()
    return responses.ok(profile.to_json())


@api.route('/profiles/<string:name>', methods=['GET'])
def profiles_get_entry(name: str) -> tuple:
    """Find a color profile based on name attribute."""
    return responses.ok(ColorProfiles.get(name).to_json())


@api.route('/profiles/<string:name>', methods=['PUT'])
def profiles_put(name: str) -> tuple:
    """Update a color profile's values based on the current name."""
    if name == color_profile.DEFAULT_PROFILE_OFF:
        # Do not allow the default "off" profile to be modified.
        return responses.not_allowed()
    body = request.get_json(force=True)
    profile = ColorProfiles.update(name, body)
    ColorProfiles.save()
    return responses.ok(profile.to_json())
