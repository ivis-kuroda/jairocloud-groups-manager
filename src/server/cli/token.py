#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Command-line interface for token management."""

import click

from flask import current_app

from server.messages import E, I
from server.services.token import (
    check_token_validity,
    get_access_token,
    get_token_owner,
    prepare_issuing_url,
    refresh_access_token,
)


@click.group()
def token() -> None:
    """Manage OAuth tokens."""


@token.command()
def issue() -> None:
    """Issue access token."""
    url = prepare_issuing_url()
    current_app.logger.info(I.REQUEST_FOR_AUTH_CODE, {"url": url})


@token.command()
def check() -> None:
    """Check access token validity."""
    token = get_access_token()

    if not check_token_validity(token):
        current_app.logger.info(E.ACCESS_TOKEN_NOT_AVAILABLE)
        return

    current_app.logger.info(I.ACCESS_TOKEN_AVAILABLE)


@token.command()
def refresh() -> None:
    """Refresh access token."""
    refresh_access_token()


@token.command()
def whoami() -> None:
    """Get the user details of the token owner."""
    owner = get_token_owner()
    current_app.logger.info(
        I.SUCCESS_GET_TOKEN_OWNER,
        {
            "user": owner.model_dump_json(indent=2, ensure_ascii=False),
        },
    )
