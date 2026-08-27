#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing OAuth tokens."""

import traceback
import typing as t

from http import HTTPStatus

import requests

from flask import current_app, url_for
from pydantic_core import ValidationError

from server.clients import auth, users
from server.config import config
from server.const import MAP_OAUTH_AUTHORIZE_ENDPOINT, OAUTH_CALLBACK_CHANNEL
from server.datastore import app_cache
from server.entities.map_error import MapError
from server.entities.user_detail import UserDetail
from server.exc import (
    CertificatesError,
    CredentialsError,
    OAuthTokenError,
    UnexpectedResponseError,
)
from server.messages import E, I, W
from server.services.service_settings import (
    get_client_credentials,
    get_oauth_token,
    save_client_credentials,
    save_oauth_token,
)


if t.TYPE_CHECKING:
    from server.entities.map_user import MapUser


def get_access_token() -> str:
    """Get the OAuth access token.

    Get the access token from database.
    If the token is expired or invalid, attempt to refresh it.

    Returns:
        str: The access token if available, otherwise None.

    Raises:
        OAuthTokenError: If the token is not available.
    """
    token = get_oauth_token()
    if token is None:
        raise OAuthTokenError(E.ACCESS_TOKEN_NOT_STORED)

    if check_token_validity(token.access_token):
        return token.access_token

    current_app.logger.warning(W.ACCESS_TOKEN_NOT_AVAILABLE)
    return refresh_access_token()


def get_client_secret() -> str:
    """Get the client secret from stored client credentials.

    Returns:
        str: The client secret.

    Raises:
        CredentialsError: If client credentials are not available.
    """
    creds = get_client_credentials()
    if creds is None:
        raise CredentialsError(E.CREDENTIALS_NOT_STORED)

    return creds.client_secret


def prepare_issuing_url() -> str:
    """Prepare the URL to issue authorization code.

    If client credentials are not stored, issue them first.

    Returns:
        str: The URL to redirect the user for issuing client credentials.

    Raises:
        CertificatesError: If invalid config for entity ID or certificates is provided.
        UnexpectedResponseError: If an unexpected response is received.
    """
    entity_id = config.SP.entity_id

    creds = get_client_credentials()
    if creds is None:
        try:
            creds = auth.issue_client_credentials(entity_id, config.SP)
        except requests.HTTPError as exc:
            current_app.logger.error(E.FAILED_ISSUE_CREDENTIALS)

            response = t.cast("requests.Response", exc.response)
            if response.status_code == HTTPStatus.BAD_REQUEST:
                description = response.json().get("error_description")
                current_app.logger.error(
                    E.RECEIVE_RESPONSE_MESSAGE, {"message": description}
                )
                raise CertificatesError(E.FAILED_ISSUE_CREDENTIALS) from exc

            raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

        except requests.JSONDecodeError as exc:
            current_app.logger.error(E.FAILED_ISSUE_CREDENTIALS)
            raise CertificatesError(E.FAILED_DECODE_RESPONSE) from exc

        current_app.logger.info(I.SUCCESS_ISSUE_CREDENTIALS)
        save_client_credentials(creds)

    redirect_uri = url_for("api.callback.auth_code", _external=True)
    return _create_issuing_url(creds.client_id, redirect_uri, entity_id)


def _create_issuing_url(client_id: str, redirect_uri: str, entity_id: str) -> str:
    """Create the URL to issue authorization code.

    Args:
        client_id (str): The client ID.
        redirect_uri (str): The redirect URI.
        entity_id (str): The entity ID of the Service Provider.

    Returns:
        str: The URL to redirect the user for issuing authorization code.
    """
    req = requests.Request(
        url=f"{config.MAP_CORE.base_url}{MAP_OAUTH_AUTHORIZE_ENDPOINT}",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": entity_id,
        },
    )
    return req.prepare().url  # pyright: ignore[reportReturnType]


def issue_access_token(code: str) -> str:
    """Issue a new OAuth access token.

    Args:
        code (str): The authorization code.

    Returns:
        str: The newly issued access token.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If issuing the token fails.
        UnexpectedResponseError: If an unexpected response is received.
    """
    certs = get_client_credentials()
    if certs is None:
        current_app.logger.error(E.CREDENTIALS_NOT_STORED)
        app_cache.publish(OAUTH_CALLBACK_CHANNEL, "failed")
        raise CredentialsError(E.CREDENTIALS_NOT_STORED)

    try:
        token = auth.issue_oauth_token(code, certs)
    except requests.HTTPError as exc:
        app_cache.publish(OAUTH_CALLBACK_CHANNEL, "failed")
        current_app.logger.error(E.FAILED_ISSUE_TOKEN)

        response = t.cast("requests.Response", exc.response)
        if response.status_code == HTTPStatus.BAD_REQUEST:
            description = response.json().get("error_description")
            current_app.logger.error(
                E.RECEIVE_RESPONSE_MESSAGE, {"message": description}
            )
            raise OAuthTokenError(E.FAILED_ISSUE_TOKEN) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.JSONDecodeError as exc:
        app_cache.publish(OAUTH_CALLBACK_CHANNEL, "failed")
        current_app.logger.error(E.FAILED_ISSUE_TOKEN)
        raise OAuthTokenError(E.FAILED_DECODE_RESPONSE) from exc

    current_app.logger.info(I.SUCCESS_ISSUE_TOKEN)
    save_oauth_token(token)
    app_cache.publish(OAUTH_CALLBACK_CHANNEL, "issued")

    return token.access_token


def check_token_validity(token: str) -> bool:
    """Check the validity of an OAuth access token.

    Args:
        token (str): The access token to check.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    try:
        result = auth.check_token_validity(token)
    except requests.RequestException:
        current_app.logger.warning(E.FAILED_CHECK_TOKEN)
        traceback.print_exc()
        return False

    return result


def refresh_access_token() -> str:
    """Refresh the OAuth access token.

    Returns:
        str: The refreshed access token.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If refreshing the token fails.
        UnexpectedResponseError: If an unexpected response is received.
    """
    certs = get_client_credentials()
    if certs is None:
        current_app.logger.error(E.CREDENTIALS_NOT_STORED)
        raise CredentialsError(E.CREDENTIALS_NOT_STORED)

    token = get_oauth_token()
    if token is None or (refresh_token := token.refresh_token) is None:
        current_app.logger.error(E.REFRESH_TOKEN_NOT_STORED)
        raise OAuthTokenError(E.REFRESH_TOKEN_NOT_STORED)

    try:
        new_token = auth.refresh_oauth_token(refresh_token, certs)
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_REFRESH_TOKEN)

        response = t.cast("requests.Response", exc.response)
        if response.status_code == HTTPStatus.BAD_REQUEST:
            description = response.json().get("error_description")
            current_app.logger.error(
                E.RECEIVE_RESPONSE_MESSAGE, {"message": description}
            )
            raise OAuthTokenError(E.FAILED_REFRESH_TOKEN) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.JSONDecodeError as exc:
        current_app.logger.error(E.FAILED_REFRESH_TOKEN)
        raise OAuthTokenError(E.FAILED_DECODE_RESPONSE) from exc

    current_app.logger.info(I.SUCCESS_REFRESH_TOKEN)
    save_oauth_token(new_token)

    return new_token.access_token


def get_token_owner() -> UserDetail:
    """Get the owner of the current access token.

    Returns:
        UserDetail: The user details of the token owner.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result: MapUser | MapError = users.get_self(
            access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_TOKEN_OWNER)

        response = t.cast("requests.Response", exc.response)
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_TOKEN_OWNER)
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_TOKEN_OWNER)
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_TOKEN_OWNER)
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    return UserDetail.from_map_user(result)
