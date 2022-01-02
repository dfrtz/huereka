"""Routes for /colors collection."""

from flask import request

from huereka.api.v1 import api
from huereka.lib import response_utils as responses
from huereka.lib import colors
from huereka.lib.colors import Color
from huereka.lib.colors import Colors


RESERVED_NAMES = (
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
    if profile.name in RESERVED_NAMES:
        raise colors.ColorValueError('reserved-name')
    Colors.register(profile)
    Colors.save()
    return responses.ok(profile.to_json())


@api.route('/colors/<string:name>', methods=['DELETE'])
def colors_delete_entry(name: str) -> tuple:
    """Remove a color based on name attribute."""
    if name in RESERVED_NAMES:
        return responses.not_allowed()
    profile = Colors.remove(name)
    Colors.save()
    return responses.ok(profile.to_json())


@api.route('/colors/<string:name>', methods=['GET'])
def colors_get_entry(name: str) -> tuple:
    """Find a color based on name attribute."""
    return responses.ok(Colors.get(name).to_json())


@api.route('/colors/<string:name>', methods=['PUT'])
def colors_put_entry(name: str) -> tuple:
    """Update a color's values based on the current name."""
    if name in RESERVED_NAMES:
        return responses.not_allowed()
    body = request.get_json(force=True)
    profile = Colors.update(name, body)
    Colors.save()
    return responses.ok(profile.to_json())
