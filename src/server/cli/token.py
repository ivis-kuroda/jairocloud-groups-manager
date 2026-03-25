#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Command-line interface for token management."""

import click

from flask import current_app

from server.const import OAUTH_CALLBACK_CHANNEL
from server.datastore import app_cache
from server.messages import E, I, W
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
    """Issue access token."""  # noqa: DOC501
    url = prepare_issuing_url()
    current_app.logger.info(I.REQUEST_FOR_AUTH_CODE, {"url": url})

    pubsub = app_cache.pubsub()
    pubsub.subscribe(OAUTH_CALLBACK_CHANNEL)

    current_app.logger.info(I.WAITING_TOKEN_ISSUED)
    try:
        for message in pubsub.listen():
            if message["type"] != "message":
                continue

            match message["data"]:
                case b"issued":
                    current_app.logger.info(I.SUCCESS_ISSUE_TOKEN)
                    break
                case b"failed":
                    current_app.logger.error(E.FAILED_ISSUE_TOKEN)
                    break
                case _:
                    pass

    except KeyboardInterrupt:
        current_app.logger.warning(W.STOP_WAITING_TOKEN_ISSUED)
        raise
    finally:
        pubsub.unsubscribe(OAUTH_CALLBACK_CHANNEL)


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
