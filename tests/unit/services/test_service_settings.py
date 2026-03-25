import typing as t

from unittest.mock import ANY

import pytest

from sqlalchemy.exc import SQLAlchemyError

from server.db.service_settings import ServiceSettings
from server.entities.auth import ClientCredentials, OAuthToken
from server.exc import (
    CredentialsError,
    DatabaseError,
    OAuthTokenError,
)
from server.services.service_settings import (
    _get_setting,
    _save_setting,
    get_client_credentials,
    get_oauth_token,
    save_client_credentials,
    save_oauth_token,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_client_credentials(mocker: MockerFixture):
    setting = {"client_id": "351cd8d67ea4ae85", "client_secret": "0a7c880772cec76485e0634370013af0"}
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=setting)

    creds = get_client_credentials()

    assert creds is not None
    assert creds.client_id == "351cd8d67ea4ae85"
    assert creds.client_secret == "0a7c880772cec76485e0634370013af0"
    mock_get.assert_called_once_with("client_credentials")


def test_get_client_credentials_no_setting(mocker: MockerFixture):
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=None)
    creds = get_client_credentials()
    assert creds is None
    mock_get.assert_called_once_with("client_credentials")


def test_get_client_credentials_invalid_setting(mocker: MockerFixture):
    setting = {
        "client_id": "test_client_id",
    }
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=setting)
    msg = "E041 | Failed to parse client credentials from database."

    with pytest.raises(CredentialsError, match=msg):
        get_client_credentials()

    mock_get.assert_called_once_with("client_credentials")


def test_get_client_credentials_db_error(mocker: MockerFixture):

    mocker.patch("server.services.service_settings._get_setting", side_effect=SQLAlchemyError("DB error"))
    msg = "Failed to get client credentials from database."

    with pytest.raises(DatabaseError, match=msg):
        get_client_credentials()


def test_save_client_credentials(mocker: MockerFixture):
    creds = ClientCredentials(
        client_id="save_client_id",
        client_secret="save_client_secret",
    )
    mock_save = mocker.patch("server.services.service_settings._save_setting")

    save_client_credentials(creds)

    mock_save.assert_called_once_with("client_credentials", ANY)
    json_value = mock_save.call_args[0][1]
    assert json_value["client_id"] == "save_client_id"
    assert json_value["client_secret"] == "save_client_secret"


def test_save_client_credentials_db_error(mocker: MockerFixture):
    creds = ClientCredentials(client_id="cid", client_secret="secret")
    mocker.patch("server.services.service_settings._save_setting", side_effect=Exception)
    mocker.patch("server.services.service_settings.SQLAlchemyError", Exception)

    msg = "Failed to save client credentials to database."
    with pytest.raises(DatabaseError, match=msg):
        save_client_credentials(creds)


def test_save_client_credentials_serialization_error(mocker: MockerFixture):
    creds = ClientCredentials(client_id="cid", client_secret="secret")
    mocker.patch("server.services.service_settings.PydanticSerializationError", ValueError)
    mocker.patch("server.services.service_settings.SQLAlchemyError", RuntimeError)
    mocker.patch.object(ClientCredentials, "model_dump", side_effect=ValueError)
    mocker.patch("server.services.service_settings._save_setting")

    msg = "E043 | Failed to dump client credentials for saving to database."
    with pytest.raises(CredentialsError, match=msg):
        save_client_credentials(creds)


def test_get_oauth_token_success(mocker: MockerFixture):
    setting = {
        "scope": None,
        "expires_in": 3600,
        "token_type": "Bearer",
        "access_token": "63bca9bba857b54c4ccd6bf11ea8d2b600440f35",
        "refresh_token": "04de2e30f9101e13b7f7cc460309d8931b7643ed",
    }
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=setting)

    token = get_oauth_token()

    assert token is not None
    assert token.access_token == "63bca9bba857b54c4ccd6bf11ea8d2b600440f35"
    mock_get.assert_called_once_with("oauth_token")


def test_get_oauth_token_none(mocker: MockerFixture):
    mock_get = mocker.patch("server.services.service_settings._get_setting", return_value=None)

    token = get_oauth_token()

    assert token is None
    mock_get.assert_called_once_with("oauth_token")


def test_get_oauth_token_db_error(mocker: MockerFixture):
    mocker.patch("server.services.service_settings._get_setting", side_effect=Exception)
    mocker.patch("server.services.service_settings.SQLAlchemyError", Exception)

    msg = "Failed to get OAuth token from database."
    with pytest.raises(DatabaseError, match=msg):
        get_oauth_token()


def test_get_oauth_token_invalid(mocker: MockerFixture):
    mocker.patch("server.services.service_settings._get_setting", return_value={"access_token": 1})
    mocker.patch("server.services.service_settings.ValidationError", Exception)

    msg = "E045 | Failed to parse OAuth token from database."
    with pytest.raises(OAuthTokenError, match=msg):
        get_oauth_token()


def test_save_oauth_token_success(mocker: MockerFixture):

    token_obj = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token=None, scope="")
    mock_save = mocker.patch("server.services.service_settings._save_setting")

    save_oauth_token(token_obj)

    mock_save.assert_called_once_with("oauth_token", token_obj.model_dump(mode="json"))


def test_save_oauth_token_db_error(mocker: MockerFixture):

    token_obj = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token=None, scope="")
    mocker.patch("server.services.service_settings._save_setting", side_effect=Exception)
    mocker.patch("server.services.service_settings.SQLAlchemyError", Exception)

    msg = "Failed to save OAuth token to database."
    with pytest.raises(DatabaseError, match=msg):
        save_oauth_token(token_obj)


def test_save_oauth_token_serialization_error(mocker: MockerFixture):
    token_obj = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token=None, scope="")
    mocker.patch("server.services.service_settings.PydanticSerializationError", ValueError)
    mocker.patch("server.services.service_settings.SQLAlchemyError", RuntimeError)
    mocker.patch.object(OAuthToken, "model_dump", side_effect=ValueError)
    mocker.patch("server.services.service_settings._save_setting")

    msg = "E047 | Failed to dump OAuth token for saving to database."
    with pytest.raises(OAuthTokenError, match=msg):
        save_oauth_token(token_obj)


def test__get_setting(app, mocker: MockerFixture):
    setting_value = {"foo": "bar"}
    setting = ServiceSettings(key="test_key", value=setting_value)  # pyright: ignore[reportCallIssue]
    mocker.patch("server.services.service_settings.db.session.get", return_value=setting)

    result = _get_setting("test_key")
    assert result == setting_value


def test__get_setting_not_found(app, mocker: MockerFixture):
    mocker.patch("server.services.service_settings.db.session.get", return_value=None)

    result = _get_setting("nonexistent_key")
    assert result is None


def test__save_setting_create(app, mocker: MockerFixture):
    mock_session_get = mocker.patch("server.services.service_settings.db.session.get", return_value=None)
    mock_add = mocker.patch("server.services.service_settings.db.session.add")
    mock_commit = mocker.patch("server.services.service_settings.db.session.commit")

    setting_key = "new_key"
    setting_value = {"new": "value"}

    _save_setting(setting_key, setting_value)

    mock_session_get.assert_called_once_with(ServiceSettings, setting_key)
    mock_commit.assert_called_once()
    mock_add.assert_called_once()
    added_setting = mock_add.call_args[0][0]
    assert added_setting.key == setting_key
    assert added_setting.value == setting_value


def test__save_setting_update(app, mocker: MockerFixture):
    setting_key = "existing_key"
    setting_value = {"existing": "value"}
    existing_setting = ServiceSettings(key=setting_key, value=setting_value)  # pyright: ignore[reportCallIssue]
    mock_session_get = mocker.patch("server.services.service_settings.db.session.get", return_value=existing_setting)
    mock_commit = mocker.patch("server.services.service_settings.db.session.commit")

    updated_value = {"updated": "value"}

    _save_setting(setting_key, updated_value)

    mock_session_get.assert_called_once_with(ServiceSettings, setting_key)
    mock_commit.assert_called_once()
    assert existing_setting.value == updated_value
