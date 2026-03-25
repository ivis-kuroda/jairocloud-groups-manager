import inspect
import typing as t

from server.api.callback import auth_code
from server.api.schemas import OAuthTokenQuery
from server.exc import CredentialsError, DatabaseError, OAuthTokenError


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_auth_code_redirect(mocker: MockerFixture):
    """Normal case: valid code should redirect"""
    mocker.patch("server.services.token.issue_access_token")
    query = OAuthTokenQuery(code="valid_code", state="abc123")
    expected_status_code = 200
    expected_result = ""

    original_func = inspect.unwrap(auth_code)
    result, status = original_func(query)

    assert result == expected_result
    assert status == expected_status_code


def test_auth_code_oauth_token_error(mocker: MockerFixture):
    """Error case: token.issue_access_token raises OAuthTokenError"""
    mocker.patch("server.services.token.issue_access_token", side_effect=OAuthTokenError("Invalid code"))
    query = OAuthTokenQuery(code="", state="abc123")
    expected_status_code = 202
    expected_result = ""

    original_func = inspect.unwrap(auth_code)
    result, status = original_func(query)

    assert result == expected_result
    assert status == expected_status_code


def test_auth_code_database_error(mocker: MockerFixture):
    """Error case: token.issue_access_token raises DatabaseError"""
    mocker.patch("server.services.token.issue_access_token", side_effect=DatabaseError("Database error"))
    query = OAuthTokenQuery(code="", state="abc123")

    expected_status_code = 202
    expected_result = ""

    original_func = inspect.unwrap(auth_code)
    result, status = original_func(query)

    assert result == expected_result
    assert status == expected_status_code


def test_auth_code_credentials_error(mocker: MockerFixture):
    """Error case: token.issue_access_token raises CredentialsError"""
    mocker.patch("server.services.token.issue_access_token", side_effect=CredentialsError("Invalid code"))
    query = OAuthTokenQuery(code="", state="abc123")

    expected_status_code = 202
    expected_result = ""

    original_func = inspect.unwrap(auth_code)
    result, status = original_func(query)

    assert result == expected_result
    assert status == expected_status_code
