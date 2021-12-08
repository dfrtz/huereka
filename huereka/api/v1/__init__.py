"""Root for API version 1."""

import os

from flask import Blueprint
from flask import Response
from flask import jsonify

from huereka.lib import import_utils

api = Blueprint('v1_api', __name__)


@api.route('/health', methods=['GET'])
def health() -> Response:
    """Basic health check to ensure API version is responding."""
    return jsonify({
        'result': 'ok'
    })


# Load all routes on initialization to populate the layouts and callbacks.
import_utils.import_modules(os.path.dirname(__file__), __package__, recursive=True)
