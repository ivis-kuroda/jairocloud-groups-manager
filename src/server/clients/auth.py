#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for mAP Core Authorization Server."""

import typing as t

from http import HTTPStatus

import requests

from flask import current_app, url_for

from server.config import config
from server.const import (
    MAP_OAUTH_CHECK_ENDPOINT,
    MAP_OAUTH_ISSUE_ENDPOINT,
    MAP_OAUTH_TOKEN_ENDPOINT,
)
from server.entities.auth import ClientCredentials, OAuthToken
from server.messages import I


if t.TYPE_CHECKING:
    from .types import _ClientCreds, _SpCerts


def issue_client_credentials(entity_id: str, certs: _SpCerts) -> ClientCredentials:
    """Issue client credentials from mAP Core Authorization Server.

    Args:
        entity_id (str): Entity ID of the Service Provider.
        certs (_SpCerts):
            File paths for certificates and private keys used for mutual
            TLS authentication. It must contain members `crt` and `key`.

    Returns:
        ClientCredentials:
            Issued client credentials. It has members `client_id` and `client_secret`.
    """
    redirect_uri = url_for("api.callback.auth_code", _external=True)

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_OAUTH_ISSUE_ENDPOINT}",
        params={
            "entityid": entity_id,
            "redirect_uri": redirect_uri,
        },
        cert=(certs.crt, certs.key),
        timeout=config.MAP_CORE.timeout,
    )
    response.raise_for_status()

    return ClientCredentials.model_validate(response.json())


def issue_oauth_token(code: str, credentials: _ClientCreds) -> OAuthToken:
    """Issue an OAuth access token using the authorization code.

    Args:
        code (str): Authorization code received from mAP Core Authorization Server.
        credentials (ClientCreds):
            Client credentials. It must contain members `client_id` and `client_secret`.

    Returns:
        OAuthToken:
            Issued OAuth token. It has members `access_token`, `token_type`,
            `expires_in`,`refresh_token` , and `scope`.
    """
    redirect_uri = url_for("api.callback.auth_code", _external=True)

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_OAUTH_TOKEN_ENDPOINT}",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(credentials.client_id, credentials.client_secret),
        timeout=config.MAP_CORE.timeout,
    )
    response.raise_for_status()

    return OAuthToken.model_validate(response.json())


def check_token_validity(access_token: str) -> bool:
    """Check the validity of an access token with mAP Core Authorization Server.

    Args:
        access_token (str): The access token to check.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_OAUTH_CHECK_ENDPOINT}",
        data={"access_token": access_token},
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code == HTTPStatus.UNAUTHORIZED:
        description = response.json().get("error_description")
        current_app.logger.info(I.RECEIVE_RESPONSE_MESSAGE, {"message": description})
        return False

    response.raise_for_status()

    return response.json().get("success", False)


def refresh_oauth_token(refresh_token: str, credentials: _ClientCreds) -> OAuthToken:
    """Refresh an OAuth access token using the refresh token.

    Args:
        refresh_token (str): Refresh token.
        credentials (ClientCreds):
            Client credentials. It must contain members `client_id` and `client_secret`.

    Returns:
        OAuthToken:
            New OAuth token. It has members `access_token`, `token_type`,
            `expires_in`,`refresh_token` , and `scope`.
    """
    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_OAUTH_TOKEN_ENDPOINT}",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(credentials.client_id, credentials.client_secret),
        timeout=config.MAP_CORE.timeout,
    )
    response.raise_for_status()

    return OAuthToken.model_validate(response.json())
