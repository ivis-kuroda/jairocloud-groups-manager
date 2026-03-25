#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Decorators for service functions."""

import typing as t

from functools import wraps

from flask import abort

from server.config import config


def session_required[**P, R](func: t.Callable[P, R]) -> t.Callable[..., R]:
    """Decorator to ensure that a valid session exists.

    Args:
        func: The function to be decorated.

    Returns:
        The decorated function that checks for a valid session before execution.
    """

    @wraps(func)
    def wrapper(*args: P.args, session_id: str | None = None, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportGeneralTypeIssues] # noqa: ARG001
        return func(*args, **kwargs)

    return wrapper


def require_enabled[**P, R](setting: t.Literal["enable_bulk_operation"]):  # noqa: ANN201, D103

    def decorator(func):  # noqa: ANN001, ANN202

        @wraps(func)
        def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            if not getattr(config.FEATURES, setting, False):
                abort(404)
            return func(*args, **kwargs)

        return wrapper

    return decorator
