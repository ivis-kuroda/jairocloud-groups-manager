import typing as t

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from server.clients.auth import check_token_validity, issue_client_credentials, issue_oauth_token, refresh_oauth_token
from server.clients.types import _ClientCreds, _SpCerts
from server.entities.auth import ClientCredentials, OAuthToken


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_issue_client_credentials(app: Flask, mocker: MockerFixture) -> None:
    """Test that correct client ID and secret are issued from client certificate."""
    entity_id = "https://entity"
    certs = t.cast(_SpCerts, SimpleNamespace(crt="server.crt", key="server.key"))
    expected_creds = ClientCredentials(client_id="cid", client_secret="sec")

    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"client_id": expected_creds.client_id, "client_secret": expected_creds.client_secret}
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    creds = issue_client_credentials(entity_id, certs)

    assert creds == expected_creds


def test_issue_client_credentials_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that issue_client_credentials raises HTTPError when requests.post fails."""
    mocker.patch("server.clients.auth.requests.post", side_effect=requests.HTTPError)
    certs = t.cast(_SpCerts, SimpleNamespace(crt="server.crt", key="server.key"))

    msg: str = ""
    with pytest.raises(requests.HTTPError, match=msg):
        issue_client_credentials("eid", certs)


def test_issue_client_credentials_json_decode_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that issue_client_credentials raises JSONDecodeError when response is invalid JSON."""
    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.json.side_effect = requests.JSONDecodeError("msg", "doc", 0)
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp
    certs = t.cast(_SpCerts, SimpleNamespace(crt="server.crt", key="server.key"))

    msg: str = "msg"
    with pytest.raises(requests.JSONDecodeError, match=msg):
        issue_client_credentials("eid", certs)


def test_issue_oauth_token(app: Flask, mocker: MockerFixture) -> None:
    """Test that a valid OAuth token is issued from authorization code and client credentials."""
    code = "code"
    creds = t.cast(_ClientCreds, SimpleNamespace(client_id="cid", client_secret="sec"))
    expected_token = OAuthToken(
        access_token="tok", token_type="bearer", expires_in=3600, refresh_token="rft", scope="scope"
    )

    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": expected_token.access_token,
        "token_type": expected_token.token_type,
        "expires_in": expected_token.expires_in,
        "refresh_token": expected_token.refresh_token,
        "scope": expected_token.scope,
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    token = issue_oauth_token(code, creds)

    assert token == expected_token


def test_issue_oauth_token_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that issue_oauth_token raises HTTPError when requests.post fails."""
    mocker.patch("server.clients.auth.requests.post", side_effect=requests.HTTPError)
    creds = t.cast(_ClientCreds, SimpleNamespace(client_id="cid", client_secret="sec"))

    msg: str = ""
    with pytest.raises(requests.HTTPError, match=msg):
        issue_oauth_token("code", creds)


def test_issue_oauth_token_json_decode_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that issue_oauth_token raises JSONDecodeError when response is invalid JSON."""
    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.json.side_effect = requests.JSONDecodeError("msg", "doc", 0)
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp
    creds = t.cast(_ClientCreds, SimpleNamespace(client_id="cid", client_secret="sec"))

    msg: str = "msg"
    with pytest.raises(requests.JSONDecodeError, match=msg):
        issue_oauth_token("code", creds)


def test_refresh_oauth_token(app: Flask, mocker: MockerFixture) -> None:
    """Test that a new OAuth token is issued from refresh token and client credentials."""
    refresh_token = "rft"
    creds = t.cast(_ClientCreds, SimpleNamespace(client_id="cid", client_secret="sec"))
    expected_token = OAuthToken(
        access_token="tok", token_type="bearer", expires_in=3600, refresh_token="rft", scope="scope"
    )

    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": expected_token.access_token,
        "token_type": expected_token.token_type,
        "expires_in": expected_token.expires_in,
        "refresh_token": expected_token.refresh_token,
        "scope": expected_token.scope,
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    token = refresh_oauth_token(refresh_token, creds)
    assert token == expected_token


def test_refresh_oauth_token_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that refresh_oauth_token raises HTTPError when requests.post fails."""

    mocker.patch("server.clients.auth.requests.post", side_effect=requests.HTTPError)
    creds = t.cast(_ClientCreds, SimpleNamespace(client_id="cid", client_secret="sec"))

    msg: str = ""
    with pytest.raises(requests.HTTPError, match=msg):
        refresh_oauth_token("rft", creds)


def test_refresh_oauth_token_json_decode_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that refresh_oauth_token raises JSONDecodeError when response is invalid JSON."""

    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.json.side_effect = requests.JSONDecodeError("msg", "doc", 0)
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp
    creds = t.cast(_ClientCreds, SimpleNamespace(client_id="cid", client_secret="sec"))

    msg: str = "msg"
    with pytest.raises(requests.JSONDecodeError, match=msg):
        refresh_oauth_token("rft", creds)


def test_check_token_validity_success(app: Flask, mocker: MockerFixture) -> None:
    """Test that check_token_validity returns True when token is valid."""
    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    result: bool = check_token_validity("valid_token")

    assert result is True


def test_check_token_validity_invalid(app: Flask, mocker: MockerFixture, caplog) -> None:
    """Test that check_token_validity returns False when token is unauthorized."""
    mock_resp = MagicMock()
    mock_resp.status_code = HTTPStatus.UNAUTHORIZED
    mock_resp.json.return_value = {"error_description": "invalid token"}
    mock_resp.raise_for_status.return_value = None
    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_post.return_value = mock_resp

    with caplog.at_level("INFO"):
        result = check_token_validity("dummy_token")

    assert result is False
    assert "invalid token" in caplog.text


def test_check_token_validity_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that check_token_validity raises HTTPError when requests.post fails."""
    mocker.patch("server.clients.auth.requests.post", side_effect=requests.HTTPError)

    msg: str = ""
    with pytest.raises(requests.HTTPError, match=msg):
        check_token_validity("any_token")


def test_check_token_validity_json_decode_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that check_token_validity raises JSONDecodeError when response is invalid JSON."""
    mock_post = mocker.patch("server.clients.auth.requests.post")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = requests.JSONDecodeError("msg", "doc", 0)
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    msg: str = "msg"
    with pytest.raises(requests.JSONDecodeError, match=msg):
        check_token_validity("any_token")
