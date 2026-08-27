import typing as t

from http import HTTPStatus
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
import requests

from pydantic_core import ValidationError

import server.services.token

from server.const import MAP_OAUTH_AUTHORIZE_ENDPOINT, OAUTH_CALLBACK_CHANNEL, USER_ROLES
from server.exc import (
    CertificatesError,
    CredentialsError,
    OAuthTokenError,
    UnexpectedResponseError,
)
from server.messages import E, I, W
from server.services.token import (
    _create_issuing_url,
    check_token_validity,
    get_access_token,
    get_client_secret,
    get_token_owner,
    issue_access_token,
    prepare_issuing_url,
    refresh_access_token,
)

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig
    from server.entities.auth import ClientCredentials, OAuthToken
    from server.entities.map_user import MapUser
    from server.entities.user_detail import UserDetail


def test_get_access_token(auth_token: OAuthToken, mocker: MockerFixture):
    expected = auth_token.access_token
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=auth_token)
    mocker.patch.object(server.services.token, "check_token_validity", return_value=True)

    result = get_access_token()

    assert result == expected


def test_get_access_token_not_existent(mocker: MockerFixture):
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=None)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_STORED)):
        get_access_token()


def test_get_access_token_expired(app, auth_token: OAuthToken, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=auth_token)
    mocker.patch.object(server.services.token, "check_token_validity", return_value=False)
    new_token = uuid4().hex[:8]
    mock_refresh = mocker.patch.object(server.services.token, "refresh_access_token", return_value=new_token)

    result = get_access_token()

    assert result == new_token
    mock_refresh.assert_called_once()
    assert_message(caplog.records[0], W.ACCESS_TOKEN_NOT_AVAILABLE)


def test_get_client_secret(client_creds: ClientCredentials, mocker: MockerFixture):
    expected = client_creds.client_secret
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)

    result = get_client_secret()

    assert result == expected


def test_get_client_secret_not_existent(mocker: MockerFixture):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)

    with pytest.raises(CredentialsError, match=regex(E.CREDENTIALS_NOT_STORED)):
        get_client_secret()


def test_prepare_issuing_url(config: RuntimeConfig, client_creds: ClientCredentials, mocker: MockerFixture):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    redirect_path = "/api/callback/auth-code"
    mocker.patch.object(server.services.token, "url_for", return_value=f"https://{config.SERVER_NAME}{redirect_path}")
    expected = issuing_url = f"{config.MAP_CORE.base_url}{MAP_OAUTH_AUTHORIZE_ENDPOINT}"
    mock_create_url = mocker.patch.object(server.services.token, "_create_issuing_url", return_value=issuing_url)

    result = prepare_issuing_url()

    assert result == expected
    mock_create_url.assert_called_once_with(client_creds.client_id, mocker.ANY, config.SP.entity_id)


def test_prepare_issuing_url_no_credentials(
    use_blueprint, app, config: RuntimeConfig, client_creds: ClientCredentials, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_client_credentials", return_value=client_creds)
    mock_save = mocker.patch.object(server.services.token, "save_client_credentials")

    expected = issuing_url = f"{config.MAP_CORE.base_url}{MAP_OAUTH_AUTHORIZE_ENDPOINT}"
    mocker.patch.object(server.services.token, "_create_issuing_url", return_value=issuing_url)

    result = prepare_issuing_url()

    assert result == expected
    mock_issue.assert_called_once_with(config.SP.entity_id, config.SP)
    mock_save.assert_called_once_with(client_creds)
    assert_message(caplog.records[0], I.SUCCESS_ISSUE_CREDENTIALS)


def test_prepare_issuing_url_bad_request(app, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)
    mock_response = mocker.Mock(status_code=HTTPStatus.BAD_REQUEST)
    mock_response.json.return_value = error_json = {"error_description": "failed to issue."}
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_client_credentials")
    mock_issue.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(CertificatesError, match=regex(E.FAILED_ISSUE_CREDENTIALS)):
        prepare_issuing_url()

    assert_message(caplog.records[0], E.FAILED_ISSUE_CREDENTIALS)
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": error_json["error_description"]})


def test_prepare_issuing_url_unexpected_http_error(app, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)
    mock_response = mocker.Mock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_client_credentials")
    mock_issue.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        prepare_issuing_url()

    assert_message(caplog.records[0], E.FAILED_ISSUE_CREDENTIALS)


def test_prepare_issuing_url_json_decode_error(app, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)
    mocker.patch.object(server.services.token, "save_client_credentials", return_value=None)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_client_credentials")
    mock_issue.side_effect = requests.JSONDecodeError("msg", "doc", 0)

    with pytest.raises(CertificatesError, match=regex(E.FAILED_DECODE_RESPONSE)):
        prepare_issuing_url()

    assert_message(caplog.records[0], E.FAILED_ISSUE_CREDENTIALS)


def test__create_issuing_url(client_creds: ClientCredentials, config: RuntimeConfig):
    client_id = client_creds.client_id
    redirect_uri = f"https://{config.SERVER_NAME}/api/callback/auth-code"
    entity_id = config.SP.entity_id

    result = _create_issuing_url(client_id, redirect_uri, entity_id)

    scheme, netloc, path, query, _ = urlsplit(result)
    assert f"{scheme}://{netloc}" == config.MAP_CORE.base_url
    assert path == MAP_OAUTH_AUTHORIZE_ENDPOINT
    qs = parse_qs(query)
    assert qs["response_type"] == ["code"]
    assert qs["client_id"] == [client_id]
    assert qs["redirect_uri"] == [redirect_uri]
    assert qs["state"] == [entity_id]


def test_issue_access_token(app, datastore, client_creds, auth_token, mocker: MockerFixture, caplog):
    app_cache, *_ = datastore

    auth_code = uuid4().hex[:8]
    expected = auth_token.access_token
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_oauth_token", return_value=auth_token)
    mock_save = mocker.patch.object(server.services.token, "save_oauth_token")

    result = issue_access_token(auth_code)

    assert result == expected
    mock_issue.assert_called_once_with(auth_code, client_creds)
    mock_save.assert_called_once_with(auth_token)
    app_cache.publish.assert_called_once_with(OAUTH_CALLBACK_CHANNEL, "issued")
    assert_message(caplog.records[0], I.SUCCESS_ISSUE_TOKEN)


def test_issue_access_token_no_credentials(app, datastore, mocker: MockerFixture, caplog):
    app_cache, *_ = datastore

    auth_code = uuid4().hex[:8]
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)

    with pytest.raises(CredentialsError, match=regex(E.CREDENTIALS_NOT_STORED)):
        issue_access_token(auth_code)

    app_cache.publish.assert_called_once_with(OAUTH_CALLBACK_CHANNEL, "failed")
    assert_message(caplog.records[0], E.CREDENTIALS_NOT_STORED)


def test_issue_access_token_bad_request(app, datastore, client_creds, mocker: MockerFixture, caplog):
    app_cache, *_ = datastore

    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_oauth_token")
    mock_response = mocker.Mock(status_code=HTTPStatus.BAD_REQUEST)
    mock_response.json.return_value = error_json = {"error_description": "failed to issue."}
    mock_issue.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.FAILED_ISSUE_TOKEN)):
        issue_access_token("code")

    app_cache.publish.assert_called_once_with(OAUTH_CALLBACK_CHANNEL, "failed")
    assert_message(caplog.records[0], E.FAILED_ISSUE_TOKEN)
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": error_json["error_description"]})


def test_issue_access_token_unexpected_http_error(app, datastore, client_creds, mocker: MockerFixture, caplog):
    app_cache, *_ = datastore

    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_oauth_token")
    mock_response = mocker.Mock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_issue.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        issue_access_token("code")

    app_cache.publish.assert_called_once_with(OAUTH_CALLBACK_CHANNEL, "failed")
    assert_message(caplog.records[0], E.FAILED_ISSUE_TOKEN)


def test_issue_access_token_json_decode_error(app, datastore, client_creds, mocker: MockerFixture, caplog):
    app_cache, *_ = datastore

    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mock_issue = mocker.patch.object(server.services.token.auth, "issue_oauth_token")
    mock_issue.side_effect = requests.JSONDecodeError("msg", "doc", 0)

    with pytest.raises(OAuthTokenError, match=regex(E.FAILED_DECODE_RESPONSE)):
        issue_access_token("code")

    app_cache.publish.assert_called_once_with(OAUTH_CALLBACK_CHANNEL, "failed")
    assert_message(caplog.records[0], E.FAILED_ISSUE_TOKEN)


def test_check_token_validity(auth_token: OAuthToken, mocker: MockerFixture):
    mocker.patch.object(server.services.token.auth, "check_token_validity", return_value=True)

    result = check_token_validity(auth_token.access_token)

    assert result is True


def test_check_token_validity_request_exception(app, auth_token: OAuthToken, mocker: MockerFixture, caplog):
    mock_check = mocker.patch.object(server.services.token.auth, "check_token_validity")
    mock_check.side_effect = requests.RequestException("failed to check.")

    result = check_token_validity(auth_token.access_token)

    assert result is False
    assert_message(caplog.records[0], E.FAILED_CHECK_TOKEN)


def test_refresh_access_token(app, client_creds, auth_token: OAuthToken, mocker: MockerFixture, caplog):
    new_token = auth_token.model_copy(update={"access_token": (expected := uuid4().hex[:8])}, deep=True)
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=auth_token)
    mock_refresh = mocker.patch.object(server.services.token.auth, "refresh_oauth_token", return_value=new_token)
    mock_save = mocker.patch.object(server.services.token, "save_oauth_token", return_value=None)

    result = refresh_access_token()

    assert result == expected
    mock_refresh.assert_called_once_with(auth_token.refresh_token, client_creds)
    mock_save.assert_called_once_with(new_token)
    assert_message(caplog.records[0], I.SUCCESS_REFRESH_TOKEN)


def test_refresh_access_token_no_credentials(app, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=None)

    with pytest.raises(CredentialsError, match=regex(E.CREDENTIALS_NOT_STORED)):
        refresh_access_token()

    assert_message(caplog.records[0], E.CREDENTIALS_NOT_STORED)


def test_refresh_access_token_no_token(app, client_creds, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=None)

    with pytest.raises(OAuthTokenError, match=regex(E.REFRESH_TOKEN_NOT_STORED)):
        refresh_access_token()

    assert_message(caplog.records[0], E.REFRESH_TOKEN_NOT_STORED)


def test_refresh_access_token_bad_request(app, client_creds, auth_token: OAuthToken, mocker: MockerFixture, caplog):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=auth_token)
    mock_refresh = mocker.patch.object(server.services.token.auth, "refresh_oauth_token")
    mock_response = mocker.Mock(status_code=HTTPStatus.BAD_REQUEST)
    mock_response.json.return_value = error_json = {"error_description": "failed to refresh."}
    mock_refresh.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.FAILED_REFRESH_TOKEN)):
        refresh_access_token()

    assert_message(caplog.records[0], E.FAILED_REFRESH_TOKEN)
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": error_json["error_description"]})


def test_refresh_access_token_unexpected_http_error(
    app, client_creds, auth_token: OAuthToken, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=auth_token)
    mock_refresh = mocker.patch.object(server.services.token.auth, "refresh_oauth_token")
    mock_response = mocker.Mock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_refresh.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        refresh_access_token()

    assert_message(caplog.records[0], E.FAILED_REFRESH_TOKEN)


def test_refresh_access_token_json_decode_error(
    app, client_creds, auth_token: OAuthToken, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_client_credentials", return_value=client_creds)
    mocker.patch.object(server.services.token, "get_oauth_token", return_value=auth_token)
    mock_refresh = mocker.patch.object(server.services.token.auth, "refresh_oauth_token")
    mock_refresh.side_effect = requests.JSONDecodeError("msg", "doc", 0)

    with pytest.raises(OAuthTokenError, match=regex(E.FAILED_DECODE_RESPONSE)):
        refresh_access_token()

    assert_message(caplog.records[0], E.FAILED_REFRESH_TOKEN)


def test_get_token_owner(
    client_creds: ClientCredentials, auth_token: OAuthToken, map_users, user_details, mocker: MockerFixture
):
    owner: MapUser = map_users[USER_ROLES.SYSTEM_ADMIN]
    expected: UserDetail = user_details[USER_ROLES.SYSTEM_ADMIN]
    mocker.patch.object(server.services.token, "get_access_token", return_value=auth_token.access_token)
    mocker.patch.object(server.services.token, "get_client_secret", return_value=client_creds.client_secret)
    mock_get = mocker.patch.object(server.services.token.users, "get_self", return_value=owner)
    mocker.patch.object(server.services.token.UserDetail, "from_map_user", return_value=expected)

    result = get_token_owner()

    assert result == expected
    mock_get.assert_called_once_with(access_token=auth_token.access_token, client_secret=client_creds.client_secret)


def test_get_token_owner_map_error(
    app, client_creds: ClientCredentials, auth_token: OAuthToken, map_error, mocker: MockerFixture, caplog
):
    _, error, _ = map_error
    mocker.patch.object(server.services.token, "get_access_token", return_value=auth_token.access_token)
    mocker.patch.object(server.services.token, "get_client_secret", return_value=client_creds.client_secret)
    mocker.patch.object(server.services.token.users, "get_self", return_value=error)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        get_token_owner()

    assert_message(caplog.records[0], E.FAILED_GET_TOKEN_OWNER)
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": error.detail})


def test_get_token_owner_unauthorized(
    app, client_creds: ClientCredentials, auth_token: OAuthToken, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_access_token", return_value=auth_token.access_token)
    mocker.patch.object(server.services.token, "get_client_secret", return_value=client_creds.client_secret)
    mock_get = mocker.patch.object(server.services.token.users, "get_self")
    mock_response = mocker.Mock(status_code=HTTPStatus.UNAUTHORIZED)
    mock_get.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        get_token_owner()

    assert_message(caplog.records[0], E.FAILED_GET_TOKEN_OWNER)


def test_get_token_owner_unexpected_http_error(
    app, client_creds: ClientCredentials, auth_token: OAuthToken, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_access_token", return_value=auth_token.access_token)
    mocker.patch.object(server.services.token, "get_client_secret", return_value=client_creds.client_secret)
    mock_get = mocker.patch.object(server.services.token.users, "get_self")
    mock_response = mocker.Mock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_get.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        get_token_owner()

    assert_message(caplog.records[0], E.FAILED_GET_TOKEN_OWNER)


def test_get_token_owner_request_exception(
    app, client_creds: ClientCredentials, auth_token: OAuthToken, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_access_token", return_value=auth_token.access_token)
    mocker.patch.object(server.services.token, "get_client_secret", return_value=client_creds.client_secret)
    mock_get = mocker.patch.object(server.services.token.users, "get_self")
    mock_get.side_effect = requests.RequestException("failed to get.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        get_token_owner()

    assert_message(caplog.records[0], E.FAILED_GET_TOKEN_OWNER)


def test_get_token_owner_validation_error(
    app, client_creds: ClientCredentials, auth_token: OAuthToken, mocker: MockerFixture, caplog
):
    mocker.patch.object(server.services.token, "get_access_token", return_value=auth_token.access_token)
    mocker.patch.object(server.services.token, "get_client_secret", return_value=client_creds.client_secret)
    mock_get = mocker.patch.object(server.services.token.users, "get_self")
    mock_get.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        get_token_owner()

    assert_message(caplog.records[0], E.FAILED_GET_TOKEN_OWNER)
