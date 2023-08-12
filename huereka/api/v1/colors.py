"""Routes for /colors collection."""

from flask import request

from huereka.api.v1 import api
from huereka.common import response_utils as responses
from huereka.common.colors import Color
from huereka.common.colors import Colors


@api.route("/colors", methods=["GET"])
def colors_get() -> tuple:
    """Find all currently saved colors."""
    colors = Colors.to_json()
    response = {
        "item_count": len(colors),
        "items": colors,
    }
    return responses.ok(response)


@api.route("/colors", methods=["POST"])
def colors_post() -> tuple:
    """Create a new reusable color."""
    body = request.get_json(force=True)
    color = Color.from_json(body)
    Colors.register(color)
    Colors.save()
    response = {
        "item_count": 1,
        "items": color.to_json(),
    }
    return responses.ok(response)


@api.route("/colors/<string:uuid>", methods=["DELETE"])
def colors_delete_entry(uuid: str) -> tuple:
    """Remove a color."""
    color = Colors.remove(uuid)
    Colors.save()
    return responses.ok(color.to_json())


@api.route("/colors/<string:uuid>", methods=["GET"])
def colors_get_entry(uuid: str) -> tuple:
    """Find a color."""
    return responses.ok(Colors.get(uuid).to_json())


@api.route("/colors/<string:uuid>", methods=["PUT"])
def colors_put_entry(uuid: str) -> tuple:
    """Update a color's values."""
    body = request.get_json(force=True)
    color = Colors.update(uuid, body)
    Colors.save()
    return responses.ok(color)
