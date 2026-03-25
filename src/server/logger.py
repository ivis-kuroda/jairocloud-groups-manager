#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Logging setup for the server application."""

import time
import typing as t

from logging import Formatter, LogRecord, StreamHandler

from flask import has_request_context, request
from flask.logging import default_handler
from flask_login import current_user

from server.auth import is_user_logged_in
from server.const import DEFAULT_LOG_DATEFMT, DEFAULT_LOG_FORMAT, DEFAULT_LOG_FORMAT_DEV


if t.TYPE_CHECKING:
    from flask import Flask

    from server.config import RuntimeConfig


def setup_logger(app: Flask, config: RuntimeConfig) -> None:
    """Setup logging for the application.

    Set logging level, format, and handlers based on the configuration.

    Args:
        app (Flask): The Flask application instance.
        config (RuntimeConfig): The runtime configuration instance.
    """
    app.logger.setLevel(config.LOG.level)

    handler = next(
        (hd for hd in app.logger.handlers if isinstance(hd, StreamHandler)),
        None,
    )
    if handler is None:
        handler = default_handler
        app.logger.addHandler(handler)

    handler.setLevel(config.LOG.level)

    formatter = _create_formatter(app, config)
    handler.setFormatter(formatter)
    handler.addFilter(_request_context_filter)


def _create_formatter(app: Flask, config: RuntimeConfig) -> Formatter:
    format_str = config.LOG.format
    if format_str is None:
        format_str = (
            DEFAULT_LOG_FORMAT
            if not app.debug and app.config.get("ENV") != "development"
            else DEFAULT_LOG_FORMAT_DEV
        )

    datefmt = config.LOG.datefmt or DEFAULT_LOG_DATEFMT
    formatter = Formatter(fmt=format_str, datefmt=datefmt)
    # use UTC time for log timestamps
    formatter.converter = time.gmtime

    return formatter


def _request_context_filter(record: LogRecord) -> t.Literal[True]:
    record.addr = get_remote_addr() or "unknown"
    record.user = current_user.eppn if is_user_logged_in(current_user) else "anonymous"
    return True


def get_remote_addr() -> str | None:
    """Get the remote address from the request context.

    Get the remote address from the `X-Forwarded-For` header if present,
    otherwise use `request.remote_addr`.

    Returns:
        str: The remote address if in a request context, otherwise None.
    """
    if not has_request_context():
        return None

    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.remote_addr
