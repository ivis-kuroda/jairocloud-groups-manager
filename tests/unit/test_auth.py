import typing as t

from datetime import UTC, datetime

from flask import session
from flask_login import current_user, login_user

from server import auth
from server.entities.login_user import LoginUser


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

mock_repoadmin_login_user = LoginUser(
    eppn="test_eppn",
    is_member_of="https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/jc_test_roles_repoadm",
    user_name="Test User",
    map_id="test_user_id",
    session_id="",
)


def test_is_user_logged_in(app):
    with app.test_request_context("/"):
        login_user(mock_repoadmin_login_user)
        assert auth.is_user_logged_in(current_user)


def test_is_user_logged_in_not_logged_in(app):
    with app.test_request_context("/"):
        assert not auth.is_user_logged_in(current_user)


def test_refresh_session_not_logged_in(app, datastore):
    _, account_store, _ = datastore
    with app.test_request_context("/"):
        res = auth.refresh_session()
    assert res is None
    account_store.expire.assert_not_called()
    account_store.delete.assert_not_called()


def test_refresh_session(app, datastore, mocker: MockerFixture):
    _, account_store, _ = datastore
    test_session_id = "test_session_id"
    test_login_date = datetime.now(UTC).isoformat()
    account_store.hget.return_value = test_login_date.encode("utf-8")
    with app.test_request_context("/"):
        login_user(mock_repoadmin_login_user)
        session["_id"] = test_session_id
        res = auth.refresh_session()
    assert res is None
    account_store.expire.assert_called_once()


def test_refresh_session_over(app, datastore, mocker: MockerFixture):
    _, account_store, _ = datastore
    test_session_id = "test_session_id"
    with app.test_request_context("/"):
        mocker.patch("server.config.config.SESSION.absolute_lifetime", 0)
        login_user(mock_repoadmin_login_user)
        session["_id"] = test_session_id
        res = auth.refresh_session()
    assert res is None
    account_store.delete.assert_called_once()


def test_refresh_session_absolute(app, datastore, mocker: MockerFixture):
    _, account_store, _ = datastore
    with app.test_request_context("/"):
        mocker.patch("server.config.config.SESSION.strategy", "absolute")
        res = auth.refresh_session()
    assert res is None
    account_store.expire.assert_not_called()
    account_store.delete.assert_not_called()


def test_refresh_session_invalid_ttl(app, datastore, mocker: MockerFixture):
    _, account_store, _ = datastore
    test_session_id = "test_session_id"
    with app.test_request_context("/"):
        mocker.patch("server.config.config.SESSION.sliding_lifetime", -1)
        login_user(mock_repoadmin_login_user)
        session["_id"] = test_session_id
        res = auth.refresh_session()
    assert res is None
    account_store.expire.assert_not_called()


def test_load_user_not_eppn():
    empty_eppn = ""
    user = auth.load_user(empty_eppn)
    assert user is None


def test_load_user_not_session_id(app):
    test_eppn = "test_eppn"
    with app.test_request_context("/"):
        user = auth.load_user(test_eppn)
    assert user is None


def test_load_user_invalid_eppn(app, mocker: MockerFixture):
    test_invalid_eppn = "test_invalid_eppn"
    test_session_id = "test_session_id"
    with app.test_request_context("/"):
        mocker.patch("server.auth.get_user_from_store", return_value=mock_repoadmin_login_user)
        session["_id"] = test_session_id
        user = auth.load_user(test_invalid_eppn)
    assert user is None


def test_load_user(app, mocker: MockerFixture):
    test_eppn = "test_eppn"
    test_session_id = "test_session_id"
    with app.test_request_context("/"):
        mocker.patch("server.auth.get_user_from_store", return_value=mock_repoadmin_login_user)
        session["_id"] = test_session_id
        user = auth.load_user(test_eppn)
    assert user == mock_repoadmin_login_user


def test_get_user_from_store_valid(app, datastore):
    _, account_store, _ = datastore
    test_session_id = "test_session_id"
    user_dict = {
        b"eppn": b"test_eppn",
        b"is_member_of": b"https://cg.gakunin.jp/gr/group1",
        b"user_name": b"Test User",
        b"map_id": b"test_user_id",
    }
    account_store.hgetall.return_value = user_dict
    with app.test_request_context("/"):
        user = auth.get_user_from_store(test_session_id)
    assert isinstance(user, LoginUser)
    assert user.eppn == "test_eppn"
    assert user.session_id == test_session_id


def test_get_user_from_store_none(app, datastore):
    _, account_store, _ = datastore
    test_session_id = "test_session_id"
    account_store.hgetall.return_value = None
    with app.test_request_context("/"):
        user = auth.get_user_from_store(test_session_id)
    assert user is None


def test_build_account_store_key(app, test_config):
    session_id = "test_session_id"
    with app.test_request_context("/"):
        key = auth.build_account_store_key(session_id)
    prefix = test_config.REDIS.key_prefix
    assert key == f"{prefix}login-{session_id}"
