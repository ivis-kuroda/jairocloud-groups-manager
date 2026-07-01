import hashlib
import typing as t

from datetime import UTC, datetime, timedelta

from flask import Flask, session
from flask_login import current_user, login_user

import server.auth

from server.auth import build_account_store_key, get_user_from_store, is_user_logged_in, load_user, refresh_session
from server.const import USER_ROLES


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig
    from server.entities.login_user import LoginUser


def test_is_user_logged_in(app: Flask, login_users):
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]

    with app.test_request_context():
        login_user(user)

        assert is_user_logged_in(current_user)


def test_is_user_logged_in_anonymous(app: Flask):
    with app.test_request_context():
        assert not is_user_logged_in(current_user)


def test_is_user_logged_in_no_context():
    assert not is_user_logged_in(current_user)


def test_refresh_session(app: Flask, config: RuntimeConfig, datastore, login_users, mocker: MockerFixture):
    _, account_store, _ = datastore
    config.SESSION.strategy = "sliding"
    config.SESSION.sliding_lifetime = 60 * 60  # 1 hour

    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    user.login_date = datetime.now(UTC) - timedelta(minutes=10)
    mocker.patch.object(server.auth, "build_account_store_key", side_effect=lambda x: f"user-session-{x}")

    with app.test_request_context():
        login_user(user)
        user.session_id = session_id = session["_id"]

        refresh_session()

    account_store.expire.assert_called_once_with(f"user-session-{session_id}", config.SESSION.sliding_lifetime)
    account_store.delete.assert_not_called()


def test_refresh_session_absolute_overdue(
    app: Flask, config: RuntimeConfig, datastore, login_users, mocker: MockerFixture
):
    _, account_store, _ = datastore
    config.SESSION.strategy = "sliding"
    config.SESSION.absolute_lifetime = 60 * 60  # 1 hour

    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    user.login_date = datetime.now(UTC) - timedelta(hours=2)  # 2 hours ago
    mocker.patch.object(server.auth, "build_account_store_key", side_effect=lambda x: f"user-session-{x}")

    with app.test_request_context():
        login_user(user)
        user.session_id = session_id = session["_id"]

        refresh_session()

    account_store.expire.assert_not_called()
    account_store.delete.assert_called_once_with(f"user-session-{session_id}")


def test_refresh_session_sliding_unlimited(
    app: Flask, config: RuntimeConfig, datastore, login_users, mocker: MockerFixture
):
    _, account_store, _ = datastore
    config.SESSION.strategy = "sliding"
    config.SESSION.sliding_lifetime = -1  # Unlimited

    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    user.login_date = datetime.now(UTC) - timedelta(minutes=10)
    mocker.patch.object(server.auth, "build_account_store_key", side_effect=lambda x: f"user-session-{x}")

    with app.test_request_context():
        login_user(user)
        user.session_id = session["_id"]

        refresh_session()

    account_store.expire.assert_not_called()
    account_store.delete.assert_not_called()


def test_refresh_session_anonymous(config: RuntimeConfig, datastore):
    _, account_store, _ = datastore
    config.SESSION.strategy = "sliding"
    config.SESSION.sliding_lifetime = 60 * 60  # 1 hour

    refresh_session()

    account_store.expire.assert_not_called()
    account_store.delete.assert_not_called()


def test_refresh_session_strategy_absolute(config: RuntimeConfig, datastore, mocker: MockerFixture):
    _, account_store, _ = datastore
    config.SESSION.strategy = "absolute"

    refresh_session()

    account_store.expire.assert_not_called()
    account_store.delete.assert_not_called()


def test_load_user(app: Flask, login_users, mocker: MockerFixture):
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    mocker.patch.object(server.auth, "get_user_from_store", return_value=user)

    with app.test_request_context():
        user.session_id = session["_id"] = hashlib.sha256(b"test_session_id").hexdigest()

        result = load_user(user.eppn)

    assert user == result


def test_load_user_empty_eppn():
    assert load_user("") is None


def test_load_user_no_session_id(app: Flask, login_users):
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    with app.test_request_context("/"):
        assert load_user(user.eppn) is None


def test_load_user_invalid_eppn(app: Flask, login_users, mocker: MockerFixture):
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    mocker.patch.object(server.auth, "get_user_from_store", return_value=user)

    with app.test_request_context("/"):
        user.session_id = session["_id"] = hashlib.sha256(b"test_session_id").hexdigest()

        assert load_user("invalid_eppn") is None


def test_get_user_from_store(config, datastore, login_users, mocker: MockerFixture):
    _, account_store, _ = datastore
    session_id = hashlib.sha256(b"test_session_id").hexdigest()
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    user_jsonb = {
        key.encode("utf-8"): str(value).encode("utf-8")
        for key, value in user.model_dump(mode="json", by_alias=True).items()
    }
    account_store.hgetall.return_value = user_jsonb
    user.session_id = session_id

    result = get_user_from_store(session_id)

    assert result == user


def test_get_user_from_store_none(app, datastore):
    _, account_store, _ = datastore
    session_id = hashlib.sha256(b"test_session_id").hexdigest()
    account_store.hgetall.return_value = None

    user = get_user_from_store(session_id)

    assert user is None


def test_build_account_store_key(config: RuntimeConfig):
    session_id = hashlib.sha256(b"test_session_id").hexdigest()
    expected = f"{config.REDIS.key_prefix}user-session-{session_id}"

    key = build_account_store_key(session_id)

    assert key == expected
