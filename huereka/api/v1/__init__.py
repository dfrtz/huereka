"""Root for API version 1."""

import os

from flask import Blueprint

from huereka.common import import_utils
from huereka.shared import responses

api = Blueprint("v1_api", __name__)


@api.route("/health", methods=["GET"])
def health() -> tuple:
    """Basic health check to ensure API version is responding."""
    return responses.ok()


# Load all routes on initialization to populate the layouts and callbacks.
import_utils.import_modules(os.path.dirname(__file__), __package__, recursive=True)
