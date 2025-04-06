"""Routes for /managers collection."""

from flask import request

from huereka.api.v1 import api
from huereka.common.led_manager import LEDManager
from huereka.common.led_manager import LEDManagers
from huereka.common.lighting_schedule import LightingSchedules
from huereka.shared import responses


@api.route("/managers", methods=["GET"])
def managers_get() -> tuple:
    """Find all currently saved lighting managers."""
    managers = LEDManagers.to_json()
    response = {
        "item_count": len(managers),
        "items": managers,
    }
    return responses.ok(response)


@api.route("/managers", methods=["POST"])
def managers_post() -> tuple:
    """Create a new lighting manager."""
    body = request.get_json(force=True)
    manager = LEDManager.from_json(body)
    LEDManagers.register(manager)
    LEDManagers.save()
    response = {
        "item_count": 1,
        "items": manager.to_json(),
    }
    return responses.ok(response)


@api.route("/managers/<string:uuid>", methods=["DELETE"])
def managers_delete_entry(uuid: str) -> tuple:
    """Remove a lighting manager."""
    manager = LEDManagers.remove(uuid)
    LEDManagers.save()
    return responses.ok(manager.to_json())


@api.route("/managers/<string:uuid>", methods=["GET"])
def managers_get_entry(uuid: str) -> tuple:
    """Find a lighting manager."""
    return responses.ok(LEDManagers.get(uuid).to_json())


@api.route("/managers/<string:uuid>", methods=["PUT"])
def managers_put_entry(uuid: str) -> tuple:
    """Update a lighting manager's configuration."""
    body = request.get_json(force=True)
    old_manager = LEDManagers.get(uuid).to_json()
    manager = LEDManagers.update(uuid, **body)
    LEDManagers.save()
    if old_manager.get("mode") != manager.get("mode"):
        LightingSchedules.verify_active_schedules()
    return responses.ok(manager)
