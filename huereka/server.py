#! /usr/bin/env python

"""Primary Huereka web service."""

import argparse
import logging
import os

from pathlib import Path

from flask import Flask

from huereka.lib import config_utils
from huereka.api.v1 import api as v1_api
from huereka.lib import response_utils as responses
from huereka.lib.colors import Colors
from huereka.lib.color_profile import ColorProfiles
from huereka.lib.led_manager import LEDManagers
from huereka.lib.lighting_schedule import LightingSchedules
from huereka.lib.lighting_schedule import start_schedule_watchdog


app = Flask(__name__)
app.secret_key = config_utils.SECRET_KEY
app.register_blueprint(v1_api, url_prefix='/api/v1')
logger = logging.getLogger(__name__)


@app.errorhandler(responses.APIError)
def handle_api_exception(error: responses.APIError) -> tuple:
    """Return JSON instead of HTML for API errors."""
    return responses.json_error(error), error.code


@app.errorhandler(404)
def handle_not_found(unused_error: Exception) -> tuple:
    """Default handler for 404 Not Found."""
    return responses.not_found()


@app.errorhandler(405)
def handle_not_allowed(unused_error: Exception) -> tuple:
    """Default handler for 405 Not Allowed."""
    return responses.not_allowed()


@app.route('/health', methods=['GET'])
def health() -> tuple:
    """Basic health check to ensure server is online and responding."""
    return responses.ok()


@app.route('/api', methods=['GET'])
def versions() -> tuple:
    """Provide the API versions available."""
    return responses.ok([
        'v1',
    ])


def init_app(
        color_presets: str,
        manager_presets: str,
        profile_presets: str,
        schedule_presets: str,
) -> None:
    """Setup app singletons for managing concurrent access to persistent data.

    Args:
        color_presets: Path to configuration URI, or JSON configuration text, describing user colors.
        manager_presets: Path to configuration URI, or JSON configuration text, describing LED managers.
        profile_presets: Path to configuration URI, or JSON configuration text, describing color profiles.
        schedule_presets: Path to configuration URI, or JSON configuration text, describing lighting schedules.
    """
    home = Path.home()
    if not manager_presets:
        manager_presets = os.path.join(home, '.huereka', 'led_managers.json')
    LEDManagers.load(manager_presets)
    if not color_presets:
        color_presets = os.path.join(home, '.huereka', 'user_colors.json')
    Colors.load(color_presets)
    if not profile_presets:
        profile_presets = os.path.join(home, '.huereka', 'color_profiles.json')
    ColorProfiles.load(profile_presets)
    if not schedule_presets:
        schedule_presets = os.path.join(home, '.huereka', 'lighting_schedules.json')
    LightingSchedules.load(schedule_presets)
    start_schedule_watchdog()


def parse_args() -> argparse.Namespace:
    """Parse user arguments.

    Return:
        args: Namespace with the arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--address', dest='host', default=config_utils.HOST,
                        help=f'Address to listen to for requests. Defaults to {config_utils.HUEREKA_HOST} ENV variable.')
    parser.add_argument('-p', '--port', default=config_utils.PORT,
                        help=f'Port to listen to for requests. Defaults to {config_utils.HUEREKA_PORT} ENV variable.')
    parser.add_argument('-c', '--cert', default=config_utils.CERT,
                        help=f'Path to HTTPS cert. Defaults to {config_utils.HUEREKA_CERT} ENV variable.')
    parser.add_argument('-k', '--key', default=config_utils.KEY,
                        help=f'Path to HTTPS key. Defaults to {config_utils.HUEREKA_KEY} ENV variable.')
    parser.add_argument('--color-presets',
                        help='Path to configuration URI, or JSON configuration text, describing user colors.')
    parser.add_argument('--manager-presets',
                        help='Path to configuration URI, or JSON configuration text, describing LED managers.')
    parser.add_argument('--profile-presets',
                        help='Path to configuration URI, or JSON configuration text, describing color profiles.')
    parser.add_argument('--schedule-presets',
                        help='Path to configuration URI, or JSON configuration text, describing lighting schedules.')
    args = parser.parse_args()
    return args


def main() -> None:
    """Startup web server using development backend and listen for requests."""
    args = parse_args()
    if app.secret_key == config_utils.DEFAULT_SECRET_KEY:
        logger.warning(f'Using default secret key. Recommended to set {config_utils.HUEREKA_SECRET_KEY} to override.')
    try:
        init_app(
            args.color_presets,
            args.manager_presets,
            args.profile_presets,
            args.schedule_presets,
        )
        app.run(
            host=args.host,
            port=args.port,
            debug=config_utils.DEBUG,
            ssl_context=(args.cert, args.key) if args.key and args.cert else None,
        )
    finally:
        LEDManagers.teardown()


if __name__ == '__main__':
    main()
