"""Extensions for Microdot web servers."""

import asyncio
import logging
import pathlib
from typing import Callable
from typing import override

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

    def _call_after_request_handlers(self, after_request: Callable) -> None:
        """Run all "after request" handlers."""
        try:
            self._after_request()
            if after_request:
                after_request()
        except Exception as exc:
            logger.exception(f"Failed to handle after request callbacks: {exc}", exc_info=exc)

    def _call_watchdog_handlers(self, watchdog: Callable | None) -> None:
        """Run all watchdog handlers that are expected to execute periodically while server is running."""
        try:
            self._watchdog()
            if watchdog:
                watchdog()
        except Exception as exc:
            logger.exception(f"Failed to run watchdog callbacks: {exc}", exc_info=exc)

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
        """Run Microdot web app with extra callbacks to allow concurrent application behavior.

        This function is blocking, and will handle connections in an endless loop,
        until shutdown is requested. To start asynchronously, see `start_server()`.

        Args:
            host: The hostname or IP address of the network interface that will be listening for requests.
            port: The port number to listen for requests.
            debug: Whether the server logs debugging information.
            ssl: An SSLContext instance if the server should use TLS.
            watchdog: Non-interrupt function to run periodically to maintain application.
            watchdog_interval: Time between client connections before temporarily releasing operations to watchdog.
            after_request: Function to run after every request completes.
        """
        asyncio.get_event_loop().run_until_complete(
            self.start_server(
                host=host,
                port=port,
                debug=debug,
                ssl=ssl,
                watchdog=watchdog,
                watchdog_interval=watchdog_interval,
                after_request=after_request,
            )
        )

    @override
    def shutdown(self) -> None:
        self.shutdown_requested = True
        if self.server:
            self.server.close()

    async def start_server(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        debug: bool = False,
        ssl: any = None,
        watchdog: Callable | None = None,
        watchdog_interval: int = 5,
        after_request: Callable | None = None,
    ) -> None:
        """Start the Microdot web server as a coroutine.

        This is blocking (if awaited) until the server is shutdown.

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

        async def _serve(reader: asyncio.streams.StreamReader, writer: asyncio.streams.StreamReader) -> None:
            """Handle a single request from a connection and perform post request actions."""
            await self.handle_request(reader, writer)
            self._call_after_request_handlers(after_request)

        if self._watchdog or watchdog:

            async def _watchdog() -> None:
                """Run the watchdogs in a background coroutine periodically."""
                while not self.shutdown_requested:
                    self._call_watchdog_handlers(watchdog)
                    # Next run is always post + delay, instead of pre + delay, to prevent back to back runs.
                    await asyncio.sleep(watchdog_interval)

            _watchdog_task = asyncio.create_task(_watchdog())
        else:
            _watchdog_task = None

        if self.debug:
            logger.info(f"Starting async server on {host}:{port}")

        if ssl:
            self.server = await asyncio.start_server(_serve, host, port, ssl=ssl)
        else:
            self.server = await asyncio.start_server(_serve, host, port)

        try:
            while not self.shutdown_requested:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if _watchdog_task:
                _watchdog_task.cancel()
            self.shutdown()
        await self.server.wait_closed()

    def _watchdog(self) -> None:
        """Callback to run periodically to maintain application."""
        # No action by default.
