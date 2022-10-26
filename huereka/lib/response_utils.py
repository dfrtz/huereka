"""Functions and classes for providing consistent JSON responses from an API."""

from __future__ import annotations

import abc

from http import HTTPStatus
from typing import Any

StatusOK = HTTPStatus.OK
StatusInternalError = HTTPStatus.INTERNAL_SERVER_ERROR
StatusNotFound = HTTPStatus.NOT_FOUND
StatusNotAuthorized = HTTPStatus.UNAUTHORIZED
StatusNotAllowed = HTTPStatus.METHOD_NOT_ALLOWED
StatusInvalidRequest = HTTPStatus.BAD_REQUEST
StatusInvalidData = HTTPStatus.UNPROCESSABLE_ENTITY

_status_texts = {
    StatusOK: 'ok',
    StatusInternalError: 'internal-error',
    StatusNotAuthorized: 'not-authorized',
    StatusNotFound: 'not-found',
    StatusNotAllowed: 'not-allowed',
    StatusInvalidRequest: 'invalid-request',
    StatusInvalidData: 'invalid-data',
}

KEY_ERROR = 'error'
KEY_ERROR_DATA = 'error_data'
KEY_RESULT = 'result'


class APIError(Exception, metaclass=abc.ABCMeta):
    """Base class used to create standardized JSON API responses via error handlers."""

    def __init__(self, error: str, data: Any = None, code: int = 500) -> None:
        """Set up the base error values.

        Args:
            error: User facing error message to show in the response body.
            data: Optional data to return in the response body.
            code: HTTP return code to provide with this error.
        """
        super().__init__()
        self._error = error
        self._data = data
        self._code = code

    @property
    def code(self) -> int:
        """HTTP return code."""
        return self._code

    @property
    def data(self) -> Any:
        """Data to return in the response body to provide more context about the error."""
        return self._data

    @property
    def error(self) -> str:
        """User facing error message to show in the response body."""
        return self._error


def json_error(error: str | int | APIError | Exception, data: Any = None) -> dict:
    """Create a JSON error with a standardized format.

    Args:
        error: Value representing the error message.
        data: Optional data to return in the response.

    Returns:
        A mapping containing the error message, error data, and capable of accepting more key/value pairs.
    """
    if isinstance(error, str):
        msg = error
    elif isinstance(error, int):
        msg = status_text(error)
    elif isinstance(error, APIError):
        msg = error.error
        if data is None:
            data = error.data
    else:
        msg = status_text(StatusInternalError)

    json_data = {KEY_ERROR: msg}
    if data is not None:
        json_data[KEY_ERROR_DATA] = data

    return json_data


def json_result(result: Any) -> dict:
    """Create a JSON response with a standardized format.

    Args:
        result: Primary data to return in the response.

    Returns:
        A mapping containing the result data, and capable of accepting more key/value pairs.
    """
    return result if isinstance(result, dict) else {KEY_RESULT: result}


def status_text(code: int) -> str:
    """Find the standardized message for a status code.

    Args:
        code: HTTP status code to translate into a standardized API response text

    Returns:
        The text message for an HTTP error, or an "unknown-<code>" value if not found.
    """
    status = _status_texts.get(code)
    found = status is not None
    if not found:
        # Fallback to standard HTTP messages if API has no custom message.
        status = f'unknown-{code}'
    return status


# JSON quick responses.

def invalid_data(data: Any = None) -> tuple[dict, int]:
    """Create a JSON API response for a 422 code representing bad data (can read but can't process).

    Args:
        data: Optional data to return in the response body.

    Returns:
        An error response body and 422 error code.
    """
    return json_error(StatusInvalidData, data=data), StatusInvalidData


def invalid_request(data: Any = None) -> tuple[dict, int]:
    """Create a JSON API response for a 400 code representing a bad request (can't read).

    Args:
        data: Optional data to return in the response body.

    Returns:
        An error response body and 400 error code.
    """
    return json_error(StatusInvalidRequest, data=data), StatusInvalidRequest


def not_allowed() -> tuple[dict, int]:
    """Create a JSON API response for a 405 code representing the operation is not allowed.

    Returns:
        An error response body and 405 error code.
    """
    return json_error(StatusNotAllowed), StatusNotAllowed


def not_authorized() -> tuple[dict, int]:
    """Create a JSON API response for a 401 code representing the caller is not authorized to perform the operation.

    Returns:
        And error response body and 401 error code.
    """
    return json_error(StatusNotAuthorized), StatusNotAuthorized


def not_found() -> tuple[dict, int]:
    """Create a JSON API response for a 404 code representing the requested source does not exist.

    Returns:
        An error response body and 404 error code.
    """
    return json_error(StatusNotFound), StatusNotFound


def ok(data: Any = 'ok') -> tuple[dict, int]:  # Intentionally short name. pylint: disable=invalid-name
    """Create a JSON API response for a 200 code representing valid request and response.

    Args:
        data: Optional data to return in the response body.

    Returns:
        A basic response body and 200 response code.
    """
    try:
        response = json_result(data)
        status_code = StatusOK
    except Exception as error:  # pylint: disable=broad-except
        response = json_error(error, data=data)
        status_code = StatusInternalError
    return response, status_code


def server_error(data: Any = None) -> tuple[dict, int]:
    """Create a JSON API response for a 500 code representing server failed in an unexpected way not visible to users.

    Args:
        data: Optional data to return in the response body.

    Returns:
        An error response body and 500 error code.
    """
    return json_error(StatusInternalError, data=data), StatusInternalError
