"""Extensions for Microdot web servers."""

import logging
import pathlib
import select
import socket
import time
from typing import Callable

import microdot

CONTENT_TYPES = {
    "css": "text/css",
    "html": "text/html",
    "js": "application/javascript",
    "plain": "text/plain",
}

logger = logging.getLogger(__name__)


class Microdot(microdot.Microdot):
    """Microdot web server with additional state functionality."""

    def __init__(self, *, static_root: str | None = None) -> None:
        """Initialize Microdot web server.

        Args:
            static_root: Path to a folder to serve static web files from.
        """
        super().__init__()
        self._next_watchdog_check = 0
        self.static_root: str | None = static_root

    def _after_request(self) -> None:
        """Callback to run after every request completes."""
        # No action by default.

    def _accept_connection(self, after_request: Callable | None = None) -> None:
        """Accept a single client connection."""
        try:
            sock, addr = self.server.accept()
        except OSError as exc:
            if exc.errno == microdot.errno.ECONNABORTED:
                return
            else:
                logger.exception(f"Failed to accept connection: {exc}", exc_info=exc)
        except Exception as exc:
            logger.exception(f"Failed to accept connection: {exc}", exc_info=exc)
        else:
            microdot.create_thread(self._handle_request, sock, addr, after_request)

    def _handle_request(
        self,
        sock: socket.socket,
        addr: tuple[str, str],
        after_request: Callable | None = None,
    ) -> None:
        """Handle a single request from a connection and perform post request actions."""
        self.handle_request(sock, addr)
        self._call_after_request_handlers(after_request)

    def _call_after_request_handlers(self, after_request: Callable) -> None:
        """Run all "after request" handlers."""
        try:
            self._after_request()
            if after_request:
                after_request()
        except Exception as exc:
            logger.exception(f"Failed to handle after request callbacks: {exc}", exc_info=exc)

    def _call_watchdog_handlers(self, watchdog: Callable | None, delay: int) -> None:
        """Run all watchdog handlers if the minimum delay has passed, and update the next expected run time."""
        if time.time() >= self._next_watchdog_check:
            try:
                self._watchdog()
                if watchdog:
                    watchdog()
            except Exception as exc:
                logger.exception(f"Failed to run watchdog callbacks: {exc}", exc_info=exc)
            # Next run is always post + delay, instead of pre + delay, to prevent back to back runs.
            self._next_watchdog_check = time.time() + delay

    def _static(self, request: microdot.Request, path: str) -> tuple:
        """Serve a static web file."""
        extension = path.rsplit(".", 1)[-1]
        full_path = f"{self.static_root}/{path}"
        if (
            not self.static_root
            or ".." in path
            or extension not in CONTENT_TYPES
            or not pathlib.Path(full_path).exists()
        ):
            return "not-found", 404, {"Content-Type": "text/plain"}
        return pathlib.Path(f"{self.static_root}/{path}").read_text(), 200, {"Content-Type": CONTENT_TYPES[extension]}

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        debug: bool = False,
        ssl: any = None,
        watchdog: Callable | None = None,
        watchdog_interval: int = 5,
        after_request: Callable | None = None,
    ) -> None:
        """Run Microdot web app with time limits to allow concurrent application behavior.

        Matches the design of Microdot.run() with the exception that listening for new connections is
        time-limited between periodic application checks. This function is blocking, and will handle
        connections in an endless loop, until shutdown is requested and the time limit is reached
        between periodic application checks. See Microdot.run() for full details.

        Args:
            host: The hostname or IP address of the network interface that will be listening for requests.
            port: The port number to listen for requests.
            debug: Whether the server logs debugging information.
            ssl: An SSLContext instance if the server should use TLS.
            watchdog: Non-interrupt function to run periodically to maintain application.
            watchdog_interval: Time between client connections before temporarily releasing operations to watchdog.
            after_request: Function to run after every request completes.
        """
        self.debug = debug
        self.shutdown_requested = False

        self.server = socket.socket()
        info = socket.getaddrinfo(host, port)
        addr = info[0][-1]

        if self.debug:
            logger.info(f"Starting {microdot.concurrency_mode} server on {host}:{port}")
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(addr)
        self.server.listen(5)

        if ssl:
            self.server = ssl.wrap_socket(self.server, server_side=True)

        try:
            while not self.shutdown_requested:
                # Use select for periodic checks, instead of hardware/virtual IRQs, to maximize compatibility.
                # Call watchdogs between each connection, as well as each connection batch, to prevent incoming
                # requests from bypassing watchdog. If watchdog ran recently, it will be skipped.
                ready, _, _ = select.select([self.server], [], [], watchdog_interval)
                for _ in ready:
                    self._accept_connection(after_request)
                    self._call_watchdog_handlers(watchdog, watchdog_interval)
                self._call_watchdog_handlers(watchdog, watchdog_interval)
        finally:
            self.server.close()
            self.server = None

    def _watchdog(self) -> None:
        """Callback to run periodically to maintain application."""
        # No action by default.
