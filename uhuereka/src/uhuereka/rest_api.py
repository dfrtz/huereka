"""Primary uHuereka REST API."""

import json
import logging
import time
from typing import override

import machine
import microdot
import network
from microdot import Request

from huereka.shared import responses

from . import microdot_utils
from .power_managers import PowerManager
from .power_managers import PowerManagers

Request.max_content_length = 1024
Request.max_body_length = 1024
Request.max_readline = 1024

logger = logging.getLogger(__name__)


class REST(microdot_utils.Microdot):
    """Microdot web server to manage device."""

    def __init__(self) -> None:
        """Initialize REST server state."""
        super().__init__()
        self._pending_reboot = False

    @override
    def _after_request(self) -> None:
        if self._pending_reboot:
            logger.info("Resetting device")
            machine.reset()


app = REST()


@app.errorhandler(Exception)
async def handle_exception(request: microdot.Request, exception: Exception) -> tuple:
    """Return JSON instead of HTML for internal errors."""
    # Do not display the error to the user in case it contains sensitive information.
    return responses.server_error()


@app.errorhandler(responses.APIError)
async def handle_api_exception(request: microdot.Request, exception: responses.APIError) -> tuple:
    """Return JSON instead of HTML for API errors."""
    return responses.json_error(exception), exception.code


@app.get("/health")
async def health(request: microdot.Request) -> tuple:
    """Basic health check to ensure server is online and responding."""
    return responses.ok()


@app.get("/api")
async def api_root(request: microdot.Request) -> tuple:
    """Provide the available API versions."""
    return responses.ok(
        [
            "v1",
        ]
    )


@app.get("/api/v1")
async def api_v1_root(request: microdot.Request) -> tuple:
    """Provide the available API endpoints for version 1."""
    return responses.ok(
        [
            "/managers",
        ]
    )


@app.get("/api/v1/managers")
async def managers_get(request: microdot.Request) -> tuple:
    """Find all currently saved managers."""
    managers = PowerManagers.to_json()
    response = {
        "item_count": len(managers),
        "items": managers,
    }
    return responses.ok(response)


@app.post("/api/v1/managers")
async def managers_post(request: microdot.Request) -> tuple:
    """Create a new manager."""
    body = get_json_body(request)
    if isinstance(body, tuple):
        return body
    manager = PowerManager.from_json(body)
    PowerManagers.register(manager)
    # Save immediately, this was not a scheduled or interrupt task.
    PowerManagers.save()
    response = {
        "item_count": 1,
        "items": manager.to_json(),
    }
    return responses.ok(response)


@app.delete("/api/v1/managers/<string:uuid>")
async def managers_delete_entry(request: microdot.Request, uuid: str) -> tuple:
    """Remove a manager."""
    manager = PowerManagers.remove(uuid)
    # Save immediately, this was not a scheduled or interrupt task.
    PowerManagers.save()
    return responses.ok(manager.to_json())


@app.get("/api/v1/managers/<string:uuid>")
async def managers_get_entry(request: microdot.Request, uuid: str) -> tuple:
    """Find a manager by ID."""
    try:
        manager = PowerManagers.get(uuid)
    except responses.APIError:
        return responses.not_found()
    return responses.ok(manager.to_json())


@app.put("/api/v1/managers/<string:uuid>")
async def managers_put_entry(request: microdot.Request, uuid: str) -> tuple:
    """Update a manager's configuration."""
    body = get_json_body(request)
    if isinstance(body, tuple):
        return body
    manager = PowerManagers.update(uuid, body)
    # Save immediately, this was not a scheduled or interrupt task.
    PowerManagers.save()
    return responses.ok(manager)


@app.get("/device")
async def device_root(request: microdot.Request) -> tuple:
    """Provide the available device endpoints."""
    return responses.ok(
        [
            "info",
            "reboot",
        ]
    )


@app.get("/device/info")
async def device_info(request: microdot.Request) -> tuple:
    """Provide information about the device running the API."""
    year, month, day, hour, minute, second, _, _ = time.gmtime()
    return responses.ok(
        {
            "hostname": network.hostname(),
            "time": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z",
        }
    )


@app.post("/device/reboot")
def device_reboot(request: microdot.Request) -> tuple:
    """Tell the device to reboot as soon as possible."""
    app._pending_reboot = True
    return responses.ok()


def get_json_body(request: microdot.Request) -> dict | tuple:
    """Pull the body of a request, or create an error for the user, in a consistent manner.

    Args:
        request: Original HTTP request from user to the server.

    Returns:
        The body converted into a python primitive, or tuple if there was an error during processing.
    """
    try:
        body = json.loads(request.body)
    except:  # pylint: disable=broad-except
        return responses.invalid_request(request.body)
    return body
