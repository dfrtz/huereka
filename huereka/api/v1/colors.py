"""Routes for /colors collection."""

from flask import request

from huereka.api.v1 import api
from huereka.lib import response_utils as responses
from huereka.lib import colors
from huereka.lib.colors import Color
from huereka.lib.colors import Colors


RESERVED_IDS = (
    colors.DEFAULT_COLOR_BLACK,
    colors.DEFAULT_COLOR_WHITE,
)


@api.route('/colors', methods=['GET'])
def colors_get() -> tuple:
    """Find all currently saved colors."""
    return responses.ok(Colors.to_json())


@api.route('/colors', methods=['POST'])
def colors_post() -> tuple:
    """Create a new reusable color."""
    body = request.get_json(force=True)
    profile = Color.from_json(body)
    if profile.name in RESERVED_IDS:
        raise colors.CollectionValueError('reserved-name')
    Colors.register(profile)
    Colors.save()
    return responses.ok(profile.to_json())


@api.route('/colors/<string:uuid>', methods=['DELETE'])
def colors_delete_entry(uuid: str) -> tuple:
    """Remove a color."""
    if uuid in RESERVED_IDS:
        return responses.not_allowed()
    profile = Colors.remove(uuid)
    Colors.save()
    return responses.ok(profile.to_json())


@api.route('/colors/<string:uuid>', methods=['GET'])
def colors_get_entry(uuid: str) -> tuple:
    """Find a color."""
    return responses.ok(Colors.get(uuid).to_json())


@api.route('/colors/<string:uuid>', methods=['PUT'])
def colors_put_entry(uuid: str) -> tuple:
    """Update a color's values."""
    if uuid in RESERVED_IDS:
        return responses.not_allowed()
    body = request.get_json(force=True)
    profile = Colors.update(uuid, body)
    Colors.save()
    return responses.ok(profile.to_json())
