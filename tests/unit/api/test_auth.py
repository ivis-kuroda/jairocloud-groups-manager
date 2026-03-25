import typing as t

from http import HTTPStatus

import pytest

from flask import session
from flask_login import current_user, login_user
from redis import RedisError

from server.api import auth
from server.const import USER_ROLES
from server.entities.login_user import LoginUser
from server.entities.summaries import GroupSummary
from server.entities.user_detail import UserDetail
from server.exc import DatastoreError
from server.messages import E
from server.services.utils.affiliations import Affiliations, _RoleGroup


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

mock_repoadmin_login_user = LoginUser(
    eppn="test_eppn",
    is_member_of="https://cg.gakunin.jp/gr/jc_test_roles_repoadm;https://cg.gakunin.jp/gr/group1",
    user_name="Test User",
    map_id="test_user_id",
    session_id="",
)
mock_repoadmin_user_detail = UserDetail(
    id="test_user_id",
    user_name="Test User",
    eppns=["test_eppn"],
    groups=[GroupSummary(id="jc_test_roles_repoadm"), GroupSummary(id="group1")],
)


def test_check(app):
    with app.test_request_context("/api/auth/check"):
        login_user(mock_repoadmin_login_user)
        resp = auth.check()
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert data["id"] == mock_repoadmin_login_user.map_id
    assert data["eppn"] == mock_repoadmin_login_user.eppn
    assert data["userName"] == mock_repoadmin_login_user.user_name
    assert data["isSystemAdmin"] is False


def test_login_no_eppn(app):
    with app.test_request_context(
        "/api/auth/login",
        headers={
            "IsMemberOf": "https://cg.gakunin.jp/gr/jc_test_roles_repoadm;https://cg.gakunin.jp/gr/group1",
            "DisplayName": "Test User",
        },
    ):
        resp = auth.login()
        assert current_user.is_anonymous
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/?error=401")


def test_login_not_get_user(app, mocker: MockerFixture):
    with app.test_request_context(
        "/api/auth/login",
        headers={
            "eppn": "test_eppn",
            "IsMemberOf": "https://cg.gakunin.jp/gr/jc_test_roles_repoadm;https://cg.gakunin.jp/gr/group1",
            "DisplayName": "Test User",
        },
    ):
        mocker.patch("server.services.users.get_by_eppn", return_value=None)
        resp = auth.login()
        assert current_user.is_anonymous
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/?error=401")


def test_login_not_is_member_of(app, mocker: MockerFixture):
    mock_affiliations = Affiliations(
        roles=[_RoleGroup(repository_id="test", role=USER_ROLES.REPOSITORY_ADMIN)], groups=[]
    )
    excepted_is_member_of = "/gr/jc_test_roles_repoadm;/gr/group1"
    with app.test_request_context(
        "/api/auth/login",
        headers={
            "eppn": "test_eppn",
            "DisplayName": "Test User",
        },
    ):
        mocker.patch("server.services.users.get_by_eppn", return_value=mock_repoadmin_user_detail)
        mocker.patch("server.api.auth.detect_affiliations", return_value=mock_affiliations)
        resp = auth.login()
        assert current_user.is_member_of == excepted_is_member_of
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/")


def test_login_not_user_name(app, mocker: MockerFixture):
    mock_affiliations = Affiliations(
        roles=[_RoleGroup(repository_id="test", role=USER_ROLES.REPOSITORY_ADMIN)], groups=[]
    )
    with app.test_request_context(
        "/api/auth/login",
        headers={
            "eppn": "test_eppn",
            "IsMemberOf": "https://cg.gakunin.jp/gr/jc_test_roles_repoadm;https://cg.gakunin.jp/gr/group1",
        },
    ):
        mocker.patch("server.services.users.get_by_eppn", return_value=mock_repoadmin_user_detail)
        mocker.patch("server.api.auth.detect_affiliations", return_value=mock_affiliations)
        resp = auth.login()
        assert current_user.user_name == mock_repoadmin_login_user.user_name
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/")


def test_login_not_admin(app, mocker: MockerFixture):
    with app.test_request_context(
        "/api/auth/login",
        headers={
            "eppn": "test_eppn",
            "IsMemberOf": "https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/group2",
            "DisplayName": "Test User",
        },
    ):
        mocker.patch("server.services.users.get_by_eppn", return_value=mock_repoadmin_user_detail)
        mocker.patch("server.services.utils.permissions.extract_group_ids", return_value=["group1", "group2"])
        resp = auth.login()
        assert current_user.is_anonymous
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/?error=403")


def test_login_no_session_ttl(app, mocker: MockerFixture, test_config):
    mock_affiliations = Affiliations(
        roles=[_RoleGroup(repository_id="test", role=USER_ROLES.REPOSITORY_ADMIN)], groups=[]
    )
    with app.test_request_context(
        "/api/auth/login",
        headers={
            "eppn": "test_eppn",
            "IsMemberOf": "https://cg.gakunin.jp/gr/jc_test_roles_repoadm;https://cg.gakunin.jp/gr/group1",
            "DisplayName": "Test User",
        },
    ):
        mocker.patch("server.services.users.get_by_eppn", return_value=mock_repoadmin_user_detail)
        mocker.patch("server.api.auth.detect_affiliations", return_value=mock_affiliations)
        mocker.patch.object(test_config.SESSION, "sliding_lifetime", -1)
        resp = auth.login()
        assert current_user.user_name == mock_repoadmin_login_user.user_name
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/")


def test_login_next(app, mocker: MockerFixture):
    mock_affiliations = Affiliations(roles=[_RoleGroup(repository_id=None, role=USER_ROLES.SYSTEM_ADMIN)], groups=[])
    with app.test_request_context(
        "/api/auth/login?next=users",
        headers={
            "eppn": "test_eppn",
            "IsMemberOf": "https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/jc_roles_sysadm",
            "DisplayName": "Test User",
        },
    ):
        mocker.patch("server.services.users.get_by_eppn", return_value=mock_repoadmin_user_detail)
        mocker.patch("server.api.auth.extract_group_ids", return_value=["group1", "jc_roles_sysadm"])
        mocker.patch("server.api.auth.detect_affiliations", return_value=mock_affiliations)
        resp = auth.login()
        assert current_user.eppn == mock_repoadmin_login_user.eppn
        assert resp.status_code == HTTPStatus.FOUND
        assert resp.location.endswith("/?next=users")


def test_login_with_redis_error(app, datastore, mocker: MockerFixture):
    mock_affiliations = Affiliations(roles=[_RoleGroup(repository_id=None, role=USER_ROLES.SYSTEM_ADMIN)], groups=[])
    with app.test_request_context(
        "/api/auth/login?next=users",
        headers={
            "eppn": "test_eppn",
            "IsMemberOf": "https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/jc_roles_sysadm",
            "DisplayName": "Test User",
        },
    ):
        _, account_store, _ = datastore
        account_store.hset.side_effect = RedisError
        mocker.patch("server.services.users.get_by_eppn", return_value=mock_repoadmin_user_detail)
        mocker.patch("server.api.auth.extract_group_ids", return_value=["group1", "jc_roles_sysadm"])
        mocker.patch("server.api.auth.detect_affiliations", return_value=mock_affiliations)
        expected_code = (E.FAILED_SET_LOGIN_SESSION % {"eppn": "test_eppn"}).code
        expected_message = (E.FAILED_SET_LOGIN_SESSION % {"eppn": "test_eppn"}).data
        with pytest.raises(DatastoreError) as exc_info:
            auth.login()
        assert str(exc_info.value.code) == expected_code
        assert str(exc_info.value.string) == expected_message


@pytest.mark.parametrize("session_id", ["test_eppn", None])
def test_logout(app, session_id):
    app.secret_key = "test-secret"
    with app.test_request_context("/api/auth/logout"):
        login_user(mock_repoadmin_login_user)
        session["_id"] = session_id
        resp, code = auth.logout()
    assert resp == ""  # noqa: PLC1901
    assert code == HTTPStatus.NO_CONTENT


def test_logout_with_redis_error(app, datastore, mocker: MockerFixture):
    _, account_store, _ = datastore
    account_store.delete.side_effect = RedisError
    with app.test_request_context("/api/auth/logout"):
        login_user(mock_repoadmin_login_user)
        session["_id"] = "test_session_id"
        resp, code = auth.logout()
    assert resp == ""  # noqa: PLC1901
    assert code == HTTPStatus.NO_CONTENT
