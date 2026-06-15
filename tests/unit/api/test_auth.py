import typing as t

from http import HTTPStatus
from urllib.parse import urlparse

import pytest

from flask import session
from flask_login import current_user, login_user
from redis import RedisError

import server.api.auth

from server.api import auth
from server.api.schemas import LoginUserState
from server.const import USER_ROLES
from server.exc import DatastoreError
from server.messages import E, I, W

from tests.helpers import assert_message, regex, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


def test_check(app, login_users):
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]
    expected = LoginUserState(
        id=user.map_id,
        eppn=user.eppn,
        user_name=user.user_name,
        is_system_admin=False,
    )

    with app.test_request_context():
        login_user(user)
        res, status = unwrap(auth.check)()

    assert status == HTTPStatus.OK
    assert res == expected


def test_login_no_eppn(app, login_users, caplog):
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]
    headers = {
        "IsMemberOf": user.is_member_of,
        "DisplayName": user.user_name,
    }

    with app.test_request_context(headers=headers):
        res = unwrap(auth.login)()

        assert current_user.is_anonymous

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path == "/"
    assert query == "error=401"
    assert_message(caplog.records[0], W.DENIED_LOGIN_MISSING_EPPN)


def test_login_user_not_found(app, login_users, mocker: MockerFixture, caplog):
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]
    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=None)
    headers = {
        "EPPN": user.eppn,
        "IsMemberOf": user.is_member_of,
        "DisplayName": user.user_name,
    }

    with app.test_request_context(headers=headers):
        res = unwrap(auth.login)()

        assert current_user.is_anonymous

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path, query == ("/", "error=401")
    assert_message(caplog.records[0], W.DENIED_LOGIN_USER_NOT_FOUND, {"eppn": user.eppn})


def test_login_no_is_member_of(app, user_affils, login_users, user_details, mocker: MockerFixture, caplog):
    affilis = user_affils[USER_ROLES.REPOSITORY_ADMIN]
    detail = user_details[USER_ROLES.REPOSITORY_ADMIN]
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]

    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=detail)
    mocker.patch.object(server.api.auth, "detect_affiliations", return_value=affilis)

    excepted_is_member_of = ";".join(f"/gr/{group.id}" for group in detail.groups)
    headers = {
        "EPPN": user.eppn,
        "DisplayName": user.user_name,
    }

    with app.test_request_context(headers=headers):
        res = unwrap(auth.login)()

        assert current_user.is_member_of == excepted_is_member_of

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path, query == ("/", "")
    assert_message(caplog.records[0], I.USER_LOGGED_IN, {"eppn": user.eppn})


def test_login_not_user_name(app, user_affils, login_users, user_details, mocker: MockerFixture, caplog):
    affilis = user_affils[USER_ROLES.REPOSITORY_ADMIN]
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]
    detail = user_details[USER_ROLES.REPOSITORY_ADMIN]

    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=detail)
    mocker.patch.object(server.api.auth, "detect_affiliations", return_value=affilis)

    headers = {
        "EPPN": user.eppn,
        "IsMemberOf": user.is_member_of,
    }

    with app.test_request_context(headers=headers):
        res = unwrap(auth.login)()

        assert current_user.user_name == user.user_name

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path, query == ("/", "")
    assert_message(caplog.records[0], I.USER_LOGGED_IN, {"eppn": user.eppn})


def test_login_under_admin(app, login_users, user_details, mocker: MockerFixture, caplog):
    user = login_users[USER_ROLES.CONTRIBUTOR]
    detail = user_details[USER_ROLES.CONTRIBUTOR]

    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=detail)
    mocker.patch.object(server.api.auth, "extract_group_ids", return_value=["group1"])

    headers = {
        "EPPN": user.eppn,
        "IsMemberOf": user.is_member_of,
        "DisplayName": user.user_name,
    }

    with app.test_request_context(headers=headers):
        res = unwrap(auth.login)()

        assert current_user.is_anonymous

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path, query == ("/", "error=403")
    assert_message(caplog.records[0], W.DENIED_LOGIN_INSUFFICIENT_ROLE, {"role": "N/A"})


def test_login_no_session_ttl(
    app, user_affils, config: RuntimeConfig, login_users, user_details, mocker: MockerFixture, caplog
):
    affilis = user_affils[USER_ROLES.REPOSITORY_ADMIN]
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]
    detail = user_details[USER_ROLES.REPOSITORY_ADMIN]

    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=detail)
    mocker.patch.object(server.api.auth, "detect_affiliations", return_value=affilis)
    config.SESSION.sliding_lifetime = -1

    headers = {
        "EPPN": user.eppn,
        "IsMemberOf": user.is_member_of,
        "DisplayName": user.user_name,
    }

    with app.test_request_context(headers=headers):
        res = unwrap(auth.login)()

        assert current_user.user_name == user.user_name

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path, query == ("/", "")
    assert_message(caplog.records[0], I.USER_LOGGED_IN, {"eppn": user.eppn})


def test_login_next(app, login_users, user_affils, user_details, mocker: MockerFixture, caplog):
    user = login_users[USER_ROLES.SYSTEM_ADMIN]
    affilis = user_affils[USER_ROLES.SYSTEM_ADMIN]
    detail = user_details[USER_ROLES.SYSTEM_ADMIN]

    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=detail)
    mocker.patch.object(server.api.auth, "extract_group_ids", return_value=["group1", "jc_roles_sysadm"])
    mocker.patch.object(server.api.auth, "detect_affiliations", return_value=affilis)

    headers = {
        "EPPN": user.eppn,
        "IsMemberOf": user.is_member_of,
        "DisplayName": user.user_name,
    }

    with app.test_request_context(headers=headers, query_string={"next": "/users"}):
        res = unwrap(auth.login)()

        assert current_user.eppn == user.eppn

    assert res.status_code == HTTPStatus.FOUND
    _, _, path, _, query, _ = urlparse(res.location)
    assert path, query == ("/", "next=%2Fusers")
    assert_message(caplog.records[0], I.USER_LOGGED_IN, {"eppn": user.eppn})


def test_login_with_redis_error(app, datastore, user_affils, login_users, user_details, mocker: MockerFixture, caplog):
    affilis = user_affils[USER_ROLES.SYSTEM_ADMIN]
    user = login_users[USER_ROLES.SYSTEM_ADMIN]
    detail = user_details[USER_ROLES.SYSTEM_ADMIN]
    _, account_store, _ = datastore
    account_store.hset.side_effect = RedisError

    mocker.patch.object(server.api.auth.users, "get_by_eppn", return_value=detail)
    mocker.patch.object(server.api.auth, "extract_group_ids", return_value=["group1", "jc_roles_sysadm"])
    mocker.patch.object(server.api.auth, "detect_affiliations", return_value=affilis)

    headers = {
        "EPPN": user.eppn,
        "IsMemberOf": user.is_member_of,
        "DisplayName": user.user_name,
    }

    with (
        pytest.raises(DatastoreError, match=regex(E.FAILED_SET_LOGIN_SESSION)),
        app.test_request_context(headers=headers),
    ):
        unwrap(auth.login)()

    assert_message(caplog.records[0], E.FAILED_SET_LOGIN_SESSION, {"eppn": user.eppn})


def test_logout(app, login_users, mocker):
    user = login_users[USER_ROLES.SYSTEM_ADMIN]
    mock_logout = mocker.patch.object(server.api.auth, "logout_user")

    with app.test_request_context():
        login_user(user)

        res, status = unwrap(auth.logout)()

    assert not res
    assert status == HTTPStatus.NO_CONTENT
    mock_logout.assert_called_once()


def test_logout_no_session_id(app, login_users, mocker):
    user = login_users[USER_ROLES.SYSTEM_ADMIN]
    mock_logout = mocker.patch.object(server.api.auth, "logout_user")

    with app.test_request_context():
        login_user(user)
        session["_id"] = None

        res, status = unwrap(auth.logout)()

    assert status == HTTPStatus.NO_CONTENT
    assert not res
    mock_logout.assert_called_once()


def test_logout_with_redis_error(app, datastore, login_users):
    user = login_users[USER_ROLES.SYSTEM_ADMIN]
    _, account_store, _ = datastore
    account_store.delete.side_effect = RedisError

    with app.test_request_context():
        login_user(user)
        session["_id"] = "test_session_id"
        res, status = unwrap(auth.logout)()

    assert status == HTTPStatus.NO_CONTENT
    assert not res
