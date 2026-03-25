#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Command-line interface for user management."""

import click

from flask import current_app

from server.messages import E, I
from server.services import users as user_services


@click.group()
def users() -> None:
    """Manage users."""


@users.command()
@click.argument("user_id")
def get(user_id: str) -> None:
    """Get User resource of the User."""
    obj = user_services.get_by_id(user_id, raw=True)
    if obj is None:
        current_app.logger.error(E.USER_NOT_FOUND, {"uid": user_id})
        return

    json = obj.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_USER, {"json": json})


@users.command()
@click.argument("user_id")
@click.option("--more-detail", is_flag=True, help="Show more detailed information.")
def detail(user_id: str, *, more_detail: bool) -> None:
    """Get User details."""
    detail = user_services.get_by_id(user_id, more_detail=more_detail)
    if detail is None:
        current_app.logger.error(E.USER_NOT_FOUND, {"uid": user_id})
        return

    json = detail.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_USER, {"json": json})
