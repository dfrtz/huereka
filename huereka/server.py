#! /usr/bin/env python

"""Primary Huereka web service."""

import argparse

from flask import Flask
from flask import logging

from huereka.lib import config_utils
from huereka.api.v1 import api as v1_api
from huereka.lib import response_utils as responses

app = Flask(__name__)
app.secret_key = config_utils.SECRET_KEY
app.register_blueprint(v1_api, url_prefix='/api/v1')
logger = logging.create_logger(app)  # Use create_logger directly instead of app.logger to prevent pylint warnings.


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
    args = parser.parse_args()
    return args


def main() -> None:
    """Startup web server using development backend and listen for requests."""
    args = parse_args()
    if not args.key or not args.cert:
        raise SystemExit('Operating server without HTTPS is not supported. Please create a key and cert and supply the configuration.')
    if app.secret_key == config_utils.DEFAULT_SECRET_KEY:
        logger.warning(f'Using default secret key. Recommended to set {config_utils.HUEREKA_SECRET_KEY} to override.')
    app.run(host=args.host, port=args.port, debug=config_utils.DEBUG, ssl_context=(args.cert, args.key))


if __name__ == '__main__':
    main()
