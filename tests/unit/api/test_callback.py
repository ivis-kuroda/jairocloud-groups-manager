import typing as t

from http import HTTPStatus
from urllib.parse import urlparse
from uuid import uuid4

from flask import Response

import server.api.callback

from server.api import callback
from server.api.schemas import OAuthTokenQuery
from server.exc import OAuthTokenError
from server.messages import E

from tests.helpers import unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_auth_code_redirect(app, mocker: MockerFixture):
    mock_issue = mocker.patch.object(server.api.callback.token, "issue_access_token")
    query = OAuthTokenQuery(code=(auth_code := uuid4().hex[:8]), state="")

    res = unwrap(callback.auth_code)(query)

    assert res.status_code == HTTPStatus.FOUND
    assert isinstance(res, Response)
    assert urlparse(res.location).path == "/"
    mock_issue.assert_called_once_with(auth_code)


def test_auth_code_oauth_token_error(app, mocker: MockerFixture):
    mock_issue = mocker.patch.object(
        server.api.callback.token, "issue_access_token", side_effect=OAuthTokenError(E.FAILED_DECODE_RESPONSE)
    )
    query = OAuthTokenQuery(code=(invalid_code := uuid4().hex[:8]), state="")

    res = unwrap(callback.auth_code)(query)

    assert res.status_code == HTTPStatus.FOUND
    assert isinstance(res, Response)
    assert urlparse(res.location).path == "/"
    mock_issue.assert_called_once_with(invalid_code)
