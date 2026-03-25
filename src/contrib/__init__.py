#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities to contribute to development."""

# ruff: noqa: RUF067

from flask import current_app, has_app_context

from server.messages import E

from .dump import dump
from .messages import generate_type_stub


if has_app_context() and (
    current_app.config["ENV"] != "development" or not current_app.debug
):
    error = E.UNNECESSARY_CONTRIB
    raise RuntimeError(error)
