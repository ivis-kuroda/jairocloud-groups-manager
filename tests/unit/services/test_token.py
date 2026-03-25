import typing as t
import urllib.parse as urlparse

from http import HTTPStatus
from unittest.mock import Mock

import pytest
import requests

from flask import Flask
from pydantic_core import ValidationError

from server.entities.auth import ClientCredentials, OAuthToken
from server.entities.map_error import MapError
from server.entities.map_user import MapUser
from server.entities.user_detail import UserDetail
from server.services import token


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture
from server.exc import (
    CertificatesError,
    CredentialsError,
    OAuthTokenError,
    UnexpectedResponseError,
)
from server.services.token import (
    check_token_validity,
    get_access_token,
    get_client_secret,
    issue_access_token,
    refresh_access_token,
)


def test_get_access_token(app: Flask, mocker: MockerFixture) -> None:
    """Test that get_access_token returns the correct access token value for a typical OAuthToken."""
    token_obj = OAuthToken(
        access_token="token_main",
        token_type="bearer",
        expires_in=3600,
        refresh_token=None,
        scope="",
    )
    expected = "token_main"
    mocker.patch("server.services.token.get_oauth_token", return_value=token_obj)
    mocker.patch("server.clients.auth.requests.post")

    actual = get_access_token()

    assert actual == expected


def test_get_access_token_error(mocker: MockerFixture) -> None:
    """Test that get_access_token raises OAuthTokenError when no token is found."""
    mocker.patch("server.services.token.get_oauth_token", return_value=None)

    msg = "E025 | Access token is not stored on the server."
    with pytest.raises(OAuthTokenError, match=msg):
        token.get_access_token()


def test_get_access_token_refresh_called(app: Flask, mocker: MockerFixture) -> None:
    """Test get_access_token calls refresh_access_token if token is invalid."""
    token_obj = OAuthToken(
        access_token="expired_token",
        token_type="bearer",
        expires_in=3600,
        refresh_token="refresh",
        scope="",
    )
    mocker.patch("server.services.token.get_oauth_token", return_value=token_obj)
    mocker.patch("server.services.token.check_token_validity", return_value=False)
    mock_refresh = mocker.patch("server.services.token.refresh_access_token", return_value="new_token")

    actual = token.get_access_token()

    assert actual == "new_token"
    assert mock_refresh.called


def test_get_client_secret(mocker: MockerFixture) -> None:
    """Test that get_client_secret returns the correct client secret value for a typical ClientCredentials."""
    creds_obj = ClientCredentials(client_secret="client_secret_main", client_id="cid_main")
    expected = "client_secret_main"
    mocker.patch("server.services.token.get_client_credentials", return_value=creds_obj)

    actual = get_client_secret()

    assert actual == expected


def test_get_client_secret_error(mocker: MockerFixture) -> None:
    """Test that get_client_secret raises CredentialsError when no credentials are found."""
    mocker.patch("server.services.token.get_client_credentials", return_value=None)

    msg = "E024 | Client credentials are not stored on the server."
    with pytest.raises(CredentialsError, match=msg):
        get_client_secret()


def test_prepare_issuing_url(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Test that prepare_issuing_url generates a valid issuing URL using client credentials and config."""
    mocker.patch(
        "server.services.token.get_client_credentials",
        return_value=ClientCredentials(client_id="cid", client_secret="s"),
    )

    redirect_uri = app.url_for("api.callback.auth_code", _external=True)
    url = token.prepare_issuing_url()

    expected_redirect = urlparse.quote(redirect_uri, safe="")
    expected_state = urlparse.quote(test_config.SP.entity_id, safe="")

    assert isinstance(url, str)
    assert "client_id=cid" in url
    assert f"redirect_uri={expected_redirect}" in url
    assert f"state={expected_state}" in url


def test_prepare_issuing_url_http_error_bad_request(app: Flask, mocker):
    mocker.patch("server.services.token.get_client_credentials", return_value=None)
    mocker.patch("server.services.token.save_client_credentials", return_value=None)

    mock_response = Mock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.json.return_value = {"error_description": "fail"}
    http_error = requests.HTTPError()
    http_error.response = mock_response
    mocker.patch("server.services.token.auth.issue_client_credentials", side_effect=http_error)
    mocker.patch("server.services.token.current_app")

    msg = "fail"
    with pytest.raises(CertificatesError, match=msg):
        token.prepare_issuing_url()


def test_prepare_issuing_url_http_error_unexpected(app: Flask, mocker):
    mocker.patch("server.services.token.get_client_credentials", return_value=None)
    mocker.patch("server.services.token.save_client_credentials", return_value=None)

    mock_response = Mock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.json.return_value = {"error_description": "fail"}
    http_error = requests.HTTPError()
    http_error.response = mock_response
    mocker.patch("server.services.token.auth.issue_client_credentials", side_effect=http_error)
    mocker.patch("server.services.token.current_app")

    msg = "Received unexpected response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        token.prepare_issuing_url()


def test_prepare_issuing_url_json_decode_error(app: Flask, mocker):
    mocker.patch("server.services.token.get_client_credentials", return_value=None)
    mocker.patch("server.services.token.save_client_credentials", return_value=None)
    mocker.patch(
        "server.services.token.auth.issue_client_credentials", side_effect=requests.JSONDecodeError("msg", "doc", 0)
    )
    mocker.patch("server.services.token.current_app")

    msg = "Failed to decode response from mAP Core API."
    with pytest.raises(CertificatesError, match=msg):
        token.prepare_issuing_url()


def test_prepare_issuing_url_save_client_credentials_called(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Test that prepare_issuing_url calls save_client_credentials when certs are issued."""
    certs_obj = ClientCredentials(client_id="cid", client_secret="secret")
    mocker.patch("server.services.token.get_client_credentials", return_value=None)
    mock_issue = mocker.patch("server.services.token.auth.issue_client_credentials", return_value=certs_obj)
    mock_save = mocker.patch("server.services.token.save_client_credentials")

    url = token.prepare_issuing_url()

    mock_issue.assert_called_once()
    mock_save.assert_called_once_with(certs_obj)
    assert isinstance(url, str)


def test__create_issuing_url(app: Flask):
    """Test that _create_issuing_url generates a valid issuing URL with correct parameters."""
    url = token._create_issuing_url(client_id="cid", redirect_uri="http://localhost/cb", entity_id="eid")  # noqa: SLF001

    assert isinstance(url, str)
    assert "client_id=cid" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%2Fcb" in url
    assert "state=eid" in url


def test_issue_access_token_success(app: Flask, mocker: MockerFixture) -> None:
    """Test that issue_access_token returns the access token on success."""
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    dummy_token = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token=None, scope="")
    expected = dummy_token.access_token
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.auth.issue_oauth_token", return_value=dummy_token)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)

    actual = issue_access_token("code")

    assert actual == expected


def test_issue_access_token_no_creds(datastore, mocker: MockerFixture) -> None:
    """Test that issue_access_token raises CredentialsError when credentials are missing."""
    mocker.patch("server.services.token.get_client_credentials", return_value=None)

    msg = "Client credentials are not stored on the server."
    with pytest.raises(CredentialsError, match=msg):
        issue_access_token("code")


def test_issue_access_token_http_error_bad_request(app: Flask, mocker):
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)

    mock_response = Mock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.json.return_value = {"error_description": "fail"}
    http_error = requests.HTTPError()
    http_error.response = mock_response
    mocker.patch("server.services.token.auth.issue_oauth_token", side_effect=http_error)
    mocker.patch("server.services.token.current_app")

    msg = "fail"
    with pytest.raises(OAuthTokenError, match=msg):
        issue_access_token("code")


def test_issue_access_token_http_error_unexpected(app: Flask, mocker):
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)

    mock_response = Mock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.json.return_value = {"error_description": "fail"}
    http_error = requests.HTTPError()
    http_error.response = mock_response
    mocker.patch("server.services.token.auth.issue_oauth_token", side_effect=http_error)
    mocker.patch("server.services.token.current_app")

    msg = "Received unexpected response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        issue_access_token("code")


def test_issue_access_token_json_decode_error(app: Flask, mocker):
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)
    mocker.patch(
        "server.services.token.auth.issue_oauth_token",
        side_effect=requests.JSONDecodeError("msg", "doc", 0),
    )
    mocker.patch("server.services.token.current_app")

    msg = "Failed to decode response from mAP Core API."
    with pytest.raises(OAuthTokenError, match=msg):
        issue_access_token("code")


def test_check_token_validity_request_exception(app: Flask, mocker: MockerFixture) -> None:
    """Test that check_token_validity logs warning and returns False on RequestException."""
    mocker.patch("server.services.token.auth.check_token_validity", side_effect=requests.RequestException)
    mock_logger = mocker.patch("server.services.token.current_app.logger.warning")
    mock_traceback = mocker.patch("server.services.token.traceback.print_exc")

    result = check_token_validity("dummy_token")

    assert result is False
    mock_logger.assert_called_once()
    mock_traceback.assert_called_once()


def test_refresh_access_token_success(app: Flask, mocker: MockerFixture) -> None:
    """Test that refresh_access_token returns the new access token on success."""
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    dummy_token = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token="rft", scope="")
    dummy_new_token = OAuthToken(
        access_token="newtok", token_type="bearer", expires_in=3600, refresh_token=None, scope=""
    )
    expected = dummy_new_token.access_token
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.get_oauth_token", return_value=dummy_token)
    mocker.patch("server.services.token.auth.refresh_oauth_token", return_value=dummy_new_token)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)

    actual = refresh_access_token()

    assert actual == expected


def test_refresh_access_token_no_creds(mocker: MockerFixture) -> None:
    """Test that refresh_access_token raises CredentialsError when credentials are missing."""
    mocker.patch("server.services.token.get_client_credentials", return_value=None)

    msg = "E024 | Client credentials are not stored on the server."
    with pytest.raises(CredentialsError, match=msg):
        refresh_access_token()


def test_refresh_access_token_no_token(mocker: MockerFixture) -> None:
    """Test that refresh_access_token raises OAuthTokenError when no token is found."""
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.get_oauth_token", return_value=None)

    msg = "E026 | Refresh token is not stored on the server."
    with pytest.raises(OAuthTokenError, match=msg):
        refresh_access_token()


def test_refresh_access_token_no_refresh_token(mocker: MockerFixture) -> None:
    """Test that refresh_access_token raises OAuthTokenError when no refresh token is available."""
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    dummy_token = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token=None, scope="")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.get_oauth_token", return_value=dummy_token)

    msg = "E026 | Refresh token is not stored on the server."
    with pytest.raises(OAuthTokenError, match=msg):
        refresh_access_token()


def test_refresh_access_token_http_error_bad_request(app: Flask, mocker):
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    dummy_token = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token="rft", scope="")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.get_oauth_token", return_value=dummy_token)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)

    mock_response = Mock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.json.return_value = {"error_description": "fail"}
    http_error = requests.HTTPError()
    http_error.response = mock_response
    mocker.patch("server.services.token.auth.refresh_oauth_token", side_effect=http_error)
    mocker.patch("server.services.token.current_app")

    msg = "Received error from mAP Core API: fail"
    with pytest.raises(OAuthTokenError, match=msg):
        refresh_access_token()


def test_refresh_access_token_http_error_unexpected(app: Flask, mocker):
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    dummy_token = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token="rft", scope="")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.get_oauth_token", return_value=dummy_token)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)

    mock_response = Mock()
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_response.json.return_value = {"error_description": "fail"}
    http_error = requests.HTTPError()
    http_error.response = mock_response
    mocker.patch("server.services.token.auth.refresh_oauth_token", side_effect=http_error)
    mocker.patch("server.services.token.current_app")

    msg = "Received unexpected response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        refresh_access_token()


def test_refresh_access_token_json_decode_error(app: Flask, mocker):
    dummy_creds = ClientCredentials(client_secret="secret", client_id="cid")
    dummy_token = OAuthToken(access_token="tok", token_type="bearer", expires_in=3600, refresh_token="rft", scope="")
    mocker.patch("server.services.token.get_client_credentials", return_value=dummy_creds)
    mocker.patch("server.services.token.get_oauth_token", return_value=dummy_token)
    mocker.patch("server.services.token.save_oauth_token", return_value=None)
    mocker.patch(
        "server.services.token.auth.refresh_oauth_token",
        side_effect=requests.JSONDecodeError("msg", "doc", 0),
    )
    mocker.patch("server.services.token.current_app")

    msg = "Failed to decode response from mAP Core API."
    with pytest.raises(OAuthTokenError, match=msg):
        refresh_access_token()


def test_get_token_owner_map_error(app: Flask, mocker: MockerFixture) -> None:
    """Test get_token_owner when users.get_self returns MapError."""
    expected_call_count = 2

    mocker.patch("server.services.token.get_access_token", return_value="tok")
    mocker.patch("server.services.token.get_client_secret", return_value="secret")
    map_error = MapError(status="400", scim_type="invalidValue", detail="detail")
    mocker.patch("server.clients.users.get_self", return_value=map_error)
    mock_logger = mocker.patch("server.services.token.current_app.logger.error")

    msg = "Failed to parse response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        token.get_token_owner()
    assert mock_logger.call_count >= expected_call_count


def test_get_token_owner_success(app: Flask, mocker: MockerFixture) -> None:
    """Test get_token_owner returns UserDetail on success."""

    mocker.patch("server.services.token.get_access_token", return_value="tok")
    mocker.patch("server.services.token.get_client_secret", return_value="secret")
    dummy_map_user = MapUser(id="id", user_name="uname", preferred_language="en")
    mocker.patch("server.clients.users.get_self", return_value=dummy_map_user)
    mock_from_map_user = mocker.patch(
        "server.entities.user_detail.UserDetail.from_map_user", return_value=UserDetail(id="id", user_name="uname")
    )

    result = token.get_token_owner()
    assert isinstance(result, UserDetail)
    assert result.id == "id"
    assert result.user_name == "uname"
    mock_from_map_user.assert_called_once_with(dummy_map_user)


def make_validation_error() -> ValidationError:
    return ValidationError.from_exception_data(
        "UserDetail",  # model name
        [
            {
                "type": "value_error",
                "loc": ("field",),
                "input": None,
                "ctx": {"error": "validation error"},
            }
        ],
        "python",
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_exception", "expected_message"),
    [
        (
            requests.HTTPError(response=Mock(status_code=HTTPStatus.UNAUTHORIZED)),
            OAuthTokenError,
            "Access token is invalid or expired.",
        ),
        (
            requests.HTTPError(response=Mock(status_code=HTTPStatus.BAD_REQUEST)),
            UnexpectedResponseError,
            "Received unexpected response from mAP Core API.",
        ),
        (
            requests.RequestException("request error"),
            UnexpectedResponseError,
            "Failed to communicate with mAP Core API.",
        ),
        (
            make_validation_error(),
            UnexpectedResponseError,
            "Failed to parse response from mAP Core API.",
        ),
        (OAuthTokenError("token error"), OAuthTokenError, "token error"),
        (CredentialsError("creds error"), CredentialsError, "creds error"),
    ],
    ids=[
        "http_401",
        "http_other",
        "request_exception",
        "validation_error",
        "oauth_token_error",
        "credentials_error",
    ],
)
def test_get_token_owner_error_branches(
    app: Flask, mocker: MockerFixture, side_effect, expected_exception, expected_message
) -> None:
    """Test get_token_owner error branches for all exception cases."""
    mocker.patch("server.services.token.get_access_token", return_value="tok")
    mocker.patch("server.services.token.get_client_secret", return_value="secret")
    users_mock = mocker.patch("server.clients.users.get_self")
    users_mock.side_effect = side_effect
    mocker.patch("server.services.token.current_app.logger.error")

    msg = expected_message
    with pytest.raises(expected_exception, match=msg):
        token.get_token_owner()
