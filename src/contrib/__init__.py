#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities to contribute to development."""

# ruff: file-ignore[non-empty-init-module]

import typing as t

from flask import Flask, current_app, has_app_context

from server.messages import E

from .developers import create_developer_blueprint
from .dump import dump
from .messages import generate_type_stub


if t.TYPE_CHECKING:
    from server.config import RuntimeConfig

if has_app_context() and (
    current_app.config["ENV"] != "development" or not current_app.debug
):
    error = E.UNNECESSARY_CONTRIB
    raise RuntimeError(error)


def setup_contrib(app: Flask, config: RuntimeConfig) -> None:
    """Set up development contribution utilities."""
    generate_type_stub()
    app.register_blueprint(create_developer_blueprint(config), url_prefix="/api/dev")
