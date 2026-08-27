import typing as t

from uuid import uuid4

import pytest

from pydantic_core import PydanticSerializationError
from sqlalchemy.exc import SQLAlchemyError

from server.db.service_settings import ServiceSettings
from server.entities.auth import ClientCredentials, OAuthToken
from server.exc import (
    CredentialsError,
    DatabaseError,
    OAuthTokenError,
)
from server.messages import E
from server.services.service_settings import (
    SETTING_KEY,
    _get_setting,
    _save_setting,
    get_client_credentials,
    get_oauth_token,
    save_client_credentials,
    save_oauth_token,
)

from tests.helpers import regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_client_credentials_success(mocker: MockerFixture):
    setting = {
        "client_id": "test_client_id",
        "client_secret": uuid4().hex,
    }
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=setting)

    creds = get_client_credentials()

    assert creds is not None
    assert creds.client_id == setting["client_id"]
    assert creds.client_secret == setting["client_secret"]
    mock_get.assert_called_once_with(SETTING_KEY.CLIENT_CREDENTIALS)


def test_get_client_credentials_no_setting(mocker: MockerFixture):
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=None)

    creds = get_client_credentials()

    assert creds is None
    mock_get.assert_called_once_with(SETTING_KEY.CLIENT_CREDENTIALS)


def test_get_client_credentials_db_error(mocker: MockerFixture):
    mocker.patch("server.services.service_settings._get_setting", side_effect=SQLAlchemyError)

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_CLIENT_CREDENTIALS)):
        get_client_credentials()


def test_get_client_credentials_validation_error(mocker: MockerFixture):
    setting = {
        "client_id": "test_client_id",
        # "client_secret" is missing
    }
    mocker.patch("server.services.service_settings._get_setting", return_value=setting)

    with pytest.raises(CredentialsError, match=regex(E.FAILED_PARSE_CLIENT_CREDENTIALS)):
        get_client_credentials()


def test_save_client_credentials_success(mocker: MockerFixture):
    creds = ClientCredentials(
        client_id="test_client_id",
        client_secret=uuid4().hex,
    )
    mock_save = mocker.patch("server.services.service_settings._save_setting")

    save_client_credentials(creds)

    mock_save.assert_called_once_with(SETTING_KEY.CLIENT_CREDENTIALS, mocker.ANY)
    (_, json_value), _ = mock_save.call_args
    assert json_value["client_id"] == creds.client_id
    assert json_value["client_secret"] == creds.client_secret


def test_save_client_credentials_db_error(mocker: MockerFixture):
    creds = ClientCredentials(
        client_id="test_client_id",
        client_secret=uuid4().hex,
    )
    mocker.patch("server.services.service_settings._save_setting", side_effect=SQLAlchemyError)

    with pytest.raises(DatabaseError, match=regex(E.FAILED_SAVE_CLIENT_CREDENTIALS)):
        save_client_credentials(creds)


def test_save_client_credentials_serialization_error(mocker: MockerFixture):
    creds = ClientCredentials(
        client_id="test_client_id",
        client_secret=uuid4().hex,
    )
    mocker.patch.object(ClientCredentials, "model_dump", side_effect=PydanticSerializationError("serialization error"))
    mocker.patch("server.services.service_settings._save_setting")

    with pytest.raises(CredentialsError, match=regex(E.FAILED_DUMP_CLIENT_CREDENTIALS)):
        save_client_credentials(creds)


def test_get_oauth_token_success(mocker: MockerFixture):
    setting = {
        "access_token": uuid4().hex,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": uuid4().hex,
    }
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=setting)

    token = get_oauth_token()

    assert token is not None
    assert token.access_token == setting["access_token"]
    assert token.token_type == setting["token_type"]
    assert token.expires_in == setting["expires_in"]
    assert token.refresh_token == setting["refresh_token"]

    mock_get.assert_called_once_with(SETTING_KEY.OAUTH_TOKEN)


def test_get_oauth_token_no_setting(mocker: MockerFixture):
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=None)

    token = get_oauth_token()

    assert token is None
    mock_get.assert_called_once_with(SETTING_KEY.OAUTH_TOKEN)


def test_get_oauth_token_db_error(mocker: MockerFixture):
    mocker.patch("server.services.service_settings._get_setting", side_effect=SQLAlchemyError)

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_OAUTH_TOKEN)):
        get_oauth_token()


def test_get_oauth_token_validation_error(mocker: MockerFixture):
    setting = {
        "access_token": uuid4().hex,
        # "token_type" is missing
        # "expires_in" is missing
    }
    mocker.patch("server.services.service_settings._get_setting", return_value=setting)

    with pytest.raises(OAuthTokenError, match=regex(E.FAILED_PARSE_OAUTH_TOKEN)):
        get_oauth_token()


def test_save_oauth_token_success(mocker: MockerFixture):
    token = OAuthToken(
        access_token=uuid4().hex,
        token_type="bearer",
        expires_in=3600,
        refresh_token=uuid4().hex,
    )
    mock_save = mocker.patch("server.services.service_settings._save_setting")

    save_oauth_token(token)

    mock_save.assert_called_once_with(SETTING_KEY.OAUTH_TOKEN, mocker.ANY)
    (_, json_value), _ = mock_save.call_args
    assert json_value["access_token"] == token.access_token
    assert json_value["token_type"] == token.token_type
    assert json_value["expires_in"] == token.expires_in
    assert json_value["refresh_token"] == token.refresh_token
    assert json_value["scope"] == token.scope


def test_save_oauth_token_db_error(mocker: MockerFixture):
    token = OAuthToken(
        access_token=uuid4().hex,
        token_type="bearer",
        expires_in=3600,
        refresh_token=uuid4().hex,
    )
    mocker.patch("server.services.service_settings._save_setting", side_effect=SQLAlchemyError)

    with pytest.raises(DatabaseError, match=regex(E.FAILED_SAVE_OAUTH_TOKEN)):
        save_oauth_token(token)


def test_save_oauth_token_serialization_error(mocker: MockerFixture):
    token = OAuthToken(
        access_token=uuid4().hex,
        token_type="bearer",
        expires_in=3600,
        refresh_token=uuid4().hex,
    )
    mocker.patch.object(OAuthToken, "model_dump", side_effect=PydanticSerializationError("serialization error"))

    with pytest.raises(OAuthTokenError, match=regex(E.FAILED_DUMP_OAUTH_TOKEN)):
        save_oauth_token(token)


def test__get_setting(db):
    setting = ServiceSettings()
    setting.key = SETTING_KEY.CLIENT_CREDENTIALS
    setting.value = {"client_id": "test_client_id"}
    mock_get = db.session.get
    mock_get.return_value = setting

    result = _get_setting(SETTING_KEY.CLIENT_CREDENTIALS)

    assert result == setting.value
    mock_get.assert_called_once_with(ServiceSettings, SETTING_KEY.CLIENT_CREDENTIALS)


def test__get_setting_not_found(db):
    mock_get = db.session.get
    mock_get.return_value = None

    result = _get_setting("nonexistent_key")  # pyright: ignore[reportArgumentType]

    assert result is None
    mock_get.assert_called_once_with(ServiceSettings, "nonexistent_key")


def test__save_setting_create(db):
    mock_get = db.session.get
    mock_get.return_value = None
    mock_add = db.session.add
    mock_commit = db.session.commit

    setting_value = {"client_id": "test_client_id"}

    _save_setting(SETTING_KEY.CLIENT_CREDENTIALS, setting_value)

    mock_get.assert_called_once_with(ServiceSettings, SETTING_KEY.CLIENT_CREDENTIALS)
    mock_commit.assert_called_once()
    mock_add.assert_called_once()
    (added_setting,), _ = mock_add.call_args
    assert added_setting.key == SETTING_KEY.CLIENT_CREDENTIALS
    assert added_setting.value == setting_value


def test__save_setting_update(db):
    setting_value = {"client_id": "test_client_id"}

    existing_setting = ServiceSettings()
    existing_setting.key = SETTING_KEY.CLIENT_CREDENTIALS
    existing_setting.value = setting_value

    mock_get = db.session.get
    mock_get.return_value = existing_setting
    mock_commit = db.session.commit
    updated_value = {"client_id": "updated_client_id"}

    _save_setting(SETTING_KEY.CLIENT_CREDENTIALS, updated_value)

    mock_get.assert_called_once_with(ServiceSettings, SETTING_KEY.CLIENT_CREDENTIALS)
    mock_commit.assert_called_once()
    assert existing_setting.value == updated_value
