import typing as t

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import urlsplit
from uuid import uuid4

import requests

import server.clients.auth

from server.clients.auth import check_token_validity, issue_client_credentials, issue_oauth_token, refresh_oauth_token
from server.const import MAP_OAUTH_ISSUE_ENDPOINT, MAP_OAUTH_TOKEN_ENDPOINT
from server.messages import I

from tests.helpers import assert_message


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.clients.types import _ClientCreds, _SpCerts
    from server.config import RuntimeConfig
    from server.entities.auth import ClientCredentials, OAuthToken


def test_issue_client_credentials(config: RuntimeConfig, client_creds: ClientCredentials, mocker: MockerFixture):
    entity_id = "https://example.com/shibboleth-sp"
    certs = t.cast("_SpCerts", SimpleNamespace(crt="server.crt", key="server.key"))
    redirect_path = "/api/callback/auth-code"
    mocker.patch.object(server.clients.auth, "url_for", return_value=f"https://{config.SERVER_NAME}{redirect_path}")

    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.json.return_value = client_creds.model_dump(mode="json")
    mock_post = mocker.patch.object(server.clients.auth.requests, "post", return_value=mock_response)
    expected = client_creds

    creds = issue_client_credentials(entity_id, certs)

    assert creds == expected
    (url,), kwargs = mock_post.call_args
    scheme, netloc, path, *_ = urlsplit(url)
    assert f"{scheme}://{netloc}" == f"{config.MAP_CORE.base_url}"
    assert path == MAP_OAUTH_ISSUE_ENDPOINT
    assert kwargs["params"]["entityid"] == entity_id
    scheme, netloc, path, *_ = urlsplit(kwargs["params"]["redirect_uri"])
    assert f"{scheme}://{netloc}" == f"https://{config.SERVER_NAME}"
    assert path == redirect_path
    assert kwargs["cert"] == (certs.crt, certs.key)


def test_issue_oauth_token(config: RuntimeConfig, auth_token: OAuthToken, mocker: MockerFixture):
    code = uuid4().hex[:8]
    creds = t.cast("_ClientCreds", SimpleNamespace(client_id=uuid4().hex[:8], client_secret=uuid4().hex[:16]))
    redirect_path = "/api/callback/auth-code"
    mocker.patch.object(server.clients.auth, "url_for", return_value=f"https://{config.SERVER_NAME}{redirect_path}")

    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.json.return_value = auth_token.model_dump(mode="json")
    mock_post = mocker.patch.object(server.clients.auth.requests, "post", return_value=mock_response)
    expected = auth_token

    token = issue_oauth_token(code, creds)

    assert token == expected
    (url,), kwargs = mock_post.call_args
    scheme, netloc, path, *_ = urlsplit(url)
    assert f"{scheme}://{netloc}" == f"{config.MAP_CORE.base_url}"
    assert path == MAP_OAUTH_TOKEN_ENDPOINT
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["code"] == code
    scheme, netloc, path, *_ = urlsplit(kwargs["data"]["redirect_uri"])
    assert f"{scheme}://{netloc}" == f"https://{config.SERVER_NAME}"
    assert path == redirect_path
    assert kwargs["auth"] == (creds.client_id, creds.client_secret)


def test_check_token_validity(config: RuntimeConfig, mocker: MockerFixture):
    access_token = uuid4().hex[:8]
    mock_response = MagicMock(spec=requests.Response, status_code=HTTPStatus.OK)
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status.return_value = None
    mock_post = mocker.patch.object(server.clients.auth.requests, "post", return_value=mock_response)

    result = check_token_validity(access_token)

    assert result is True
    (url,), kwargs = mock_post.call_args
    scheme, netloc, path, *_ = urlsplit(url)
    assert f"{scheme}://{netloc}" == f"{config.MAP_CORE.base_url}"
    assert path == server.clients.auth.MAP_OAUTH_CHECK_ENDPOINT
    assert kwargs["data"]["access_token"] == access_token


def test_check_token_validity_invalid(app, mocker: MockerFixture, caplog):
    access_token = uuid4().hex[:8]
    mock_response = MagicMock(spec=requests.Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_response.json.return_value = {"error_description": "token is expired."}
    mocker.patch.object(server.clients.auth.requests, "post", return_value=mock_response)

    result = check_token_validity(access_token)

    assert result is False
    assert_message(caplog.records[0], I.RECEIVE_RESPONSE_MESSAGE, {"message": "token is expired."})


def test_refresh_oauth_token(app, config: RuntimeConfig, auth_token: OAuthToken, mocker: MockerFixture):
    refresh_token = uuid4().hex[:8]
    creds = t.cast("_ClientCreds", SimpleNamespace(client_id="cid", client_secret="sec"))

    mock_response = MagicMock(spec=requests.Response)
    mock_response.json.return_value = auth_token.model_dump(mode="json")
    mock_post = mocker.patch.object(server.clients.auth.requests, "post", return_value=mock_response)
    expected = auth_token

    new_token = refresh_oauth_token(refresh_token, creds)

    assert new_token == expected
    (url,), kwargs = mock_post.call_args
    scheme, netloc, path, *_ = urlsplit(url)
    assert f"{scheme}://{netloc}" == f"{config.MAP_CORE.base_url}"
    assert path == MAP_OAUTH_TOKEN_ENDPOINT
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["refresh_token"] == refresh_token
    assert kwargs["auth"] == (creds.client_id, creds.client_secret)
