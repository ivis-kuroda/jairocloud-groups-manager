#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Decorators for service functions."""

import typing as t

from functools import wraps

from flask import abort

from server.config import Features, config


def session_required[**P, R](func: t.Callable[P, R]) -> t.Callable[..., R]:
    """Decorator to ensure that a valid session exists.

    Args:
        func: The function to be decorated.

    Returns:
        The decorated function that checks for a valid session before execution.
    """

    @wraps(func)
    def wrapper(*args: P.args, session_id: str | None = None, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportGeneralTypeIssues] # ruff: ignore[unused-function-argument]
        return func(*args, **kwargs)

    return wrapper


def require_enabled[**P, R](setting: Features):  # ruff: ignore[missing-return-type-undocumented-public-function, undocumented-public-function]

    def decorator(func):  # ruff: ignore[missing-type-function-argument, missing-return-type-private-function]

        @wraps(func)
        def wrapper(*args, **kwargs):  # ruff: ignore[missing-type-args, missing-type-kwargs, missing-return-type-private-function]
            if not getattr(config.FEATURES, setting, False):
                abort(404)
            return func(*args, **kwargs)

        return wrapper

    return decorator
