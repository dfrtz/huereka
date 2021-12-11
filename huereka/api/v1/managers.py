"""Routes for /managers collection."""

from huereka.api.v1 import api
from huereka.lib import response_utils as responses
from huereka.lib.led_manager import LEDManagers


@api.route('/managers', methods=['GET'])
def managers_get() -> tuple:
    """Return the currently configured managers."""
    return responses.ok(LEDManagers.to_json())
