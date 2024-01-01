"""Extensions for Microdot web servers."""

import logging
import select
import socket
import time
from typing import Callable

import microdot

logger = logging.getLogger(__name__)


class Microdot(microdot.Microdot):
    """Microdot web server with additional state functionality."""

    def __init__(self) -> None:
        """Initialize Microdot web server."""
        super().__init__()
        self._next_watchdog_check = 0

    def _accept_connection(self) -> None:
        """Handle a single client connection."""
        try:
            sock, addr = self.server.accept()
        except OSError as exc:
            if exc.errno == microdot.errno.ECONNABORTED:
                return
            else:
                logger.exception(str(exc))
        except Exception as exc:
            logger.exception(str(exc))
        else:
            microdot.create_thread(self.handle_request, sock, addr)

    def _call_watchdog(self, delay: int, watchdog: Callable) -> None:
        """Call a watchdog function and update the next expected run time if the minimum delay has passed."""
        if watchdog is not None:
            current_time = time.time()
            if current_time >= self._next_watchdog_check:
                watchdog()
                self._next_watchdog_check = current_time + delay

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        debug: bool = False,
        ssl: any = None,
        wait: int = 5,
        watchdog: Callable | None = None,
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
            wait: How long to wait between client connections before temporarily releasing operations to watchdog.
            watchdog: Non-interrupt function to run periodically to maintain application.
                Will check between client requests, or at least once every wait period if idle.
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
                ready, _, _ = select.select([self.server], [], [], wait)
                for _ in ready:
                    self._accept_connection()
                    # Call between each request to prevent non-stop requests from bypassing watchdog.
                    # If watchdog ran recently, it will be skipped.
                    self._call_watchdog(wait, watchdog)
                self._call_watchdog(wait, watchdog)
        finally:
            self.server.close()
            self.server = None
