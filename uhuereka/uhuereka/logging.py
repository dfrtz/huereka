"""Simple logging module with similar functionality to CPython logging."""

import sys

import uio
import utime

from uhuereka.typing import Any

CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10

_name_to_level = {
    'CRITICAL': CRITICAL,
    'ERROR': ERROR,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
}
_level_to_name = {
    value: key for key, value in _name_to_level.items()
}
_level_to_short_name = {
    key: value[0] for key, value in _level_to_name.items()
}
_default_fmt = "{asctime} {levelshortname} {message}"
_default_time_format = "{Y}-{m:02}-{d:02} {H:02}:{M:02}:{S:02}"


class Formatter:
    """Configuration for converting a log record into text."""

    default_format = _default_fmt
    default_time_format = _default_time_format

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        """Initialize base formatter configuration.

        Args:
            fmt: Format for logging records to be converted to string.
            datefmt: Optional format for timestamps if message format contains timestamp.
        """
        self._uses_time = False
        self.fmt = fmt
        self.datefmt = datefmt

    @property
    def fmt(self) -> str:
        """Format for logging records to be converted to strings."""
        return self._fmt

    @fmt.setter
    def fmt(self, fmt: str | None) -> None:
        """Safely update the logging format and attributes based on the format.

        Args:
            fmt: New format for logging records to be converted to strings.
        """
        self._fmt = fmt or _default_fmt
        self._uses_time = "asctime" in self._fmt

    def format(self, record: tuple) -> str:
        """Convert a logging record into a string.

        Args:
            record: Configuration and data for the logging record, including level, msg, and values.

        Returns:
            Fully formatted logging message with all formatting values filled, and message values applied.
        """
        name, level, msg, args, kwargs = record
        asctime = None
        if self.usesTime():
            ct = utime.localtime(utime.time())
            datefmt = self.datefmt or self.default_time_format
            asctime = datefmt.format(Y=ct[0], m=ct[1], d=ct[2], H=ct[3], M=ct[4], S=ct[5])
        return self.fmt.format(
            message=msg.format(*args, **kwargs),
            name=name,
            levelname=_level_to_name[level],
            levelshortname=_level_to_short_name[level],
            asctime=asctime,
        )

    def usesTime(self) -> bool:
        """Whether this formatter should build timestamps during formatting.

        Returns:
            True if "asctime" keyword in format, false otherwise.
        """
        return self._uses_time


class Handler:
    """Dispatcher for logging events to specific destinations."""

    def __init__(self) -> None:
        """Initialize base handler configuration."""
        self.formatter = None

    def close(self) -> None:
        """Cleanup any resources used by the handler."""

    def emit(self, record: tuple) -> None:
        """Log the requested record.

        Args:
            record: Configuration and data for the logging record, including level, msg, and values.
        """
        print(self.format(record))

    def format(self, record: tuple) -> str:
        """Convert a logging record into a string.

        Args:
            record: Configuration and data for the logging record, including level, msg, and values.

        Returns:
            Fully formatted logging message with all formatting values filled, and message values applied.
        """
        if self.formatter:
            fmt = self.formatter
        else:
            fmt = _default_formatter
        return fmt.format(record)

    def setFormatter(self, fmt: Formatter) -> None:
        """Update the configured formatter for this handler.

        Args:
            fmt: New formatter to format all emit log records.
        """
        self.formatter = fmt


class Logger:
    """Simple logging class to write records to output."""

    def __init__(self, name: str, level: int | str = INFO) -> None:
        """Initialize the base logger configuration.

        Args:
            name: Name used to uniquely identify logger, and optionally displayed when writing records.
            level: Logging visibility level.
        """
        self._level = None
        self.setLevel(level)
        self.name = name
        self.parent = None
        self.propagate = True
        self.handlers = []

    def addHandler(self, hdlr: Handler) -> None:
        """Add a handler to this logger.

        Args:
            hdlr: New handler that will emit logging records.
        """
        self.handlers.append(hdlr)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Write a critical log record.

        Convenience method for calling log with CRITICAL severity.
        """
        self.log(CRITICAL, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Write a debug log record.

        Convenience method for calling log with DEBUG severity.
        """
        self.log(DEBUG, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Write an error log record.

        Convenience method for calling log with ERROR severity.
        """
        self.log(ERROR, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Write an exception log record.

        Convenience method for calling log with ERROR severity and automatically logging stacktrace.
        """
        buf = uio.StringIO()
        sys.print_exception(sys.exc_info()[1], buf)
        self.log(ERROR, msg + "\n" + buf.getvalue(), *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Write an informational log record.

        Convenience method for calling log with INFO severity.
        """
        self.log(INFO, msg, *args, **kwargs)

    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a record with specified severity level and arguments.

        Args:
            level: Severity level of the message.
            msg: Primary body of the message, with or without value placeholders.
            args: Positional values to format into the message.
            kwargs: Keyword values to format into the message.
        """
        if not isinstance(level, int):
            return
        if level >= self._level:
            current = self
            while current is not None:
                if current.handlers:
                    for handler in current.handlers:
                        handler.emit((current.name, level, msg, args, kwargs))
                    break
                else:
                    if not self.propagate:
                        break
                    current = self.parent

    def setLevel(self, level: str | int) -> None:
        """Set the logging level of this logger.

        Args:
            level: Raw or named logging level.
        """
        if isinstance(level, str):
            level = _name_to_level.get(level.upper(), INFO)
        self._level = level

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Write a warning log record.

        Convenience method for calling log with WARNING severity.
        """
        self.log(WARNING, msg, *args, **kwargs)


def basicConfig(**kwargs: Any) -> None:
    """Perform basic configuration for logging subsystem."""
    level = kwargs.pop("level", None)
    if level is not None:
        root.setLevel(level)
    force = kwargs.pop("force", False)
    if force:
        for handler in root.handlers:
            handler.close()
        root.handlers.clear()
    if len(root.handlers) == 0:
        handlers = kwargs.pop("handlers", None)
        if handlers is None:
            handlers = [Handler()]
        format_string = kwargs.pop("format", _default_fmt)
        for handler in handlers:
            if handler.formatter is None:
                handler.setFormatter(Formatter(format_string))
            root.addHandler(handler)


def critical(msg: str, *args: Any, **kwargs: Any) -> None:
    """Write a critical log record.

    Convenience method for calling root logger with ERROR severity.
    """
    root.critical(msg, *args, **kwargs)


def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """Write a debug log record.

    Convenience method for calling root logger with DEBUG severity.
    """
    root.debug(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    """Write an error log record.

    Convenience method for calling root logger with ERROR severity.
    """
    root.error(msg, *args, **kwargs)


def exception(msg: str, *args: Any, **kwargs: Any) -> None:
    """Write an exception log record.

    Convenience method for calling root logger with ERROR severity and automatically logging stacktrace.
    """
    root.exception(msg, *args, **kwargs)


def getLogger(name: str | None = None) -> Logger:
    """Find or create a logger with the given name.

    Args:
        name: Name of a new or existing logger.

    Returns:
        Logger stored at the name if already created, or new logger stored at the given name
    """
    if name is None:
        name = "root"
    if name in _loggers:
        return _loggers[name]
    logger = Logger(name)
    # Currently only a single level logging hierarchy, all are children of root.
    logger.parent = root
    _loggers[name] = logger
    return logger


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    """Write an informational log record.

    Convenience method for calling root logger with ERROR severity.
    """
    root.info(msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:
    """Write a warning log record.

    Convenience method for calling root logger with WARNING severity.
    """
    root.warning(msg, *args, **kwargs)


root = Logger("root")
_default_formatter = Formatter()
_loggers = {
    "root": root,
}
basicConfig(force=True)
