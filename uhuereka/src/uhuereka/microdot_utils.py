"""Extensions for Microdot web servers."""

import logging
import select
import socket
import time
from typing import Callable

import microdot

logger = logging.getLogger(__name__)


def _accept_connection(app: microdot.Microdot) -> None:
    """Handle a single client connection."""
    try:
        sock, addr = app.server.accept()
    except OSError as exc:
        if exc.errno == microdot.errno.ECONNABORTED:
            return
        else:
            logger.exception(str(exc))
    except Exception as exc:
        logger.exception(str(exc))
    else:
        microdot.create_thread(app.handle_request, sock, addr)


def _call_watchdog(next_time: int, delay: int, watchdog: Callable) -> int:
    """Call a watchdog function and update the next expected run time if the minimum delay has passed."""
    if watchdog is not None:
        current_time = time.time()
        if current_time >= next_time:
            watchdog()
            next_time = current_time + delay
    return next_time


def run(
    app: microdot.Microdot,
    host: str = "0.0.0.0",
    port: int = 5000,
    debug: bool = False,
    ssl: any = None,
    wait: int = 5,
    watchdog: Callable | None = None,
) -> None:
    """Run Microdot web app with time limits to allow concurrent application behavior.

    Matches the design of Microdot.run() with the exception the server.accept() is time-limited between operations.
    See Microdot.run() for full details.

    Args:
        app: Microdot application to run in asynchronous like mode to allow concurrent operations.
        host: The hostname or IP address of the network interface that will be listening for requests.
        port: The port number to listen for requests.
        debug: Whether the server logs debugging information.
        ssl: An SSLContext instance if the server should use TLS.
        wait: How long to wait between client connections before temporarily releasing operations to watchdog.
        watchdog: Function to run periodically to maintain application.
            Will check between client requests, or at least once every wait period if idle.
    """
    app.debug = debug
    app.shutdown_requested = False

    app.server = socket.socket()
    info = socket.getaddrinfo(host, port)
    addr = info[0][-1]

    if app.debug:
        logger.info(f"Starting {microdot.concurrency_mode} server on {host}:{port}")
    app.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    app.server.bind(addr)
    app.server.listen(5)

    if ssl:
        app.server = ssl.wrap_socket(app.server, server_side=True)

    next_watchdog_check = 0
    try:
        while not app.shutdown_requested:
            # Use select for periodic checks, instead of hardware/virtual IRQs, to maximize compatibility.
            ready, _, _ = select.select([app.server], [], [], wait)
            for _ in ready:
                _accept_connection(app)
                # Call between each request to prevent non-stop requests from bypassing watchdog.
                # If watchdog ran recently, it will be skipped.
                next_watchdog_check = _call_watchdog(next_watchdog_check, wait, watchdog)
            next_watchdog_check = _call_watchdog(next_watchdog_check, wait, watchdog)
    finally:
        app.server.close()
        app.server = None
