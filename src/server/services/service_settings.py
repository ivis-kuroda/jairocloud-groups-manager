#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing service settings.

Provides functions to get and save service configuration data in the database.
"""

import typing as t

from pydantic_core import PydanticSerializationError, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from server.db import db
from server.db.service_settings import ServiceSettings
from server.entities.auth import ClientCredentials, OAuthToken
from server.exc import CredentialsError, DatabaseError, OAuthTokenError
from server.messages import E


def get_client_credentials() -> ClientCredentials | None:
    """Get client credentials from service settings.

    Returns:
        ClientCredentials:
            The credentials if present and valid, otherwise None.
            It has members `client_id` and `client_secret`.

    Raises:
        DatabaseError: If some problem occurs in the database operation.
        CredentialsError: If the stored credentials are invalid.
    """
    try:
        setting = _get_setting("client_credentials")
        if setting is None:
            return None

        creds = ClientCredentials(**setting)
    except SQLAlchemyError as exc:
        error = E.FAILED_GET_CLIENT_CREDENTIALS
        raise DatabaseError(error) from exc
    except ValidationError as exc:
        error = E.FAILED_PARSE_CLIENT_CREDENTIALS
        raise CredentialsError(error) from exc

    return creds


def save_client_credentials(credentials: ClientCredentials) -> None:
    """Save client credentials to service settings.

    Args:
        credentials (ClientCredentials): The credentials to save.

    Raises:
        DatabaseError: If some problem occurs in the database operation.
        CredentialsError: If the provided credentials are invalid.
    """
    try:
        _save_setting("client_credentials", credentials.model_dump(mode="json"))
    except SQLAlchemyError as exc:
        error = E.FAILED_SAVE_CLIENT_CREDENTIALS
        raise DatabaseError(error) from exc
    except PydanticSerializationError as exc:
        error = E.FAILED_DUMP_CLIENT_CREDENTIALS
        raise CredentialsError(error) from exc


def get_oauth_token() -> OAuthToken | None:
    """Get OAuth token from service settings.

    Returns:
        OAuthToken: The token if present and valid, otherwise None.

    Raises:
        DatabaseError: If some problem occurs in the database operation.
        OAuthTokenError: If the stored token is invalid.
    """
    try:
        setting = _get_setting("oauth_token")
        if setting is None:
            return None

        token = OAuthToken(**setting)
    except SQLAlchemyError as exc:
        error = E.FAILED_GET_OAUTH_TOKEN
        raise DatabaseError(error) from exc
    except ValidationError as exc:
        error = E.FAILED_PARSE_OAUTH_TOKEN
        raise OAuthTokenError(error) from exc

    return token


def save_oauth_token(token: OAuthToken) -> None:
    """Save OAuth token to service settings.

    Args:
        token (OAuthToken): The token to save.

    Raises:
        DatabaseError: If some problem occurs in the database operation.
        OAuthTokenError: If the provided token is invalid.
    """
    try:
        _save_setting("oauth_token", token.model_dump(mode="json"))
    except SQLAlchemyError as exc:
        error = E.FAILED_SAVE_OAUTH_TOKEN
        raise DatabaseError(error) from exc
    except PydanticSerializationError as exc:
        error = E.FAILED_DUMP_OAUTH_TOKEN
        raise OAuthTokenError(error) from exc


def _get_setting(key: str) -> dict[str, t.Any] | None:
    """Get the value of a service setting by key.

    Args:
        key (str): The setting key.

    Returns:
        dict: The setting value as a dictionary, or None if not found.
    """
    setting = db.session.get(ServiceSettings, key)
    return setting.value if setting else None


def _save_setting(key: str, value: dict[str, t.Any]) -> None:
    """Save or update the value of a service setting.

    Args:
        key (str): The setting key.
        value (dict[str, Any]): The setting value to save.
    """
    setting = db.session.get(ServiceSettings, key)
    if setting:
        setting.value = value
    else:
        setting = ServiceSettings(key=key, value=value)  # pyright: ignore[reportCallIssue]
        db.session.add(setting)
    db.session.commit()
