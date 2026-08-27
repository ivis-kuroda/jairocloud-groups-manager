import hashlib
import typing as t

from uuid import uuid4

import pytest

from flask_login import login_user
from pydantic import BaseModel
from redis.exceptions import RedisError

import server.clients.decorators

from server.clients.decorators import _clear_cache, cache_resource, default_id_generator
from server.const import USER_ROLES
from server.entities.login_user import LoginUser
from server.entities.map_error import MapError
from server.messages import E, I, W

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


class ResourceModel(BaseModel):
    value: str
    data: dict


def target_func(arg: str, access_token: str, client_secret: str, **kwargs: str) -> ResourceModel | MapError:
    if arg == "error-id":
        return MapError(status="400", scim_type="invalidValue", detail=arg)
    return ResourceModel(value=arg, data=kwargs)


@pytest.fixture
def function(mocker: MockerFixture):
    mock_target = mocker.MagicMock(side_effect=target_func)
    mock_target.__qualname__ = target_func.__qualname__
    mock_target.__module__ = target_func.__module__
    mock_target.__annotations__ = target_func.__annotations__

    namespace = f"{target_func.__module__}.{target_func.__qualname__}"

    return mock_target, namespace


def test_cache_resource_hit(app, config, datastore, function, mocker: MockerFixture, caplog):
    cached_obj = ResourceModel(value=(identifier := "cached-id"), data=(cached_data := {"key": "cached-data"}))

    target, namespace = function
    hashed_args = hashlib.md5(
        f"{(identifier,)}-{list(cached_data.items())!s}".encode(), usedforsecurity=False
    ).hexdigest()
    expected_key = f"{config.REDIS.key_prefix}{namespace}-{identifier}-{hashed_args}"

    app_cache, _, _ = datastore
    app_cache.get.return_value = cached_obj.model_dump_json()

    result = (decorated := cache_resource(target))(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **cached_data
    )

    assert result == cached_obj
    assert decorated._cache_namespace == namespace  # pyright: ignore[reportFunctionMemberAccess]
    assert hasattr(decorated, "clear_cache")
    app_cache.get.assert_called_once_with(expected_key)
    target.assert_not_called()
    assert_message(caplog.records[0], I.RESOURCE_CACHE_HIT)


def test_cache_resource_miss(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture, caplog):
    src_obj = ResourceModel(value=(identifier := "src-id"), data=(src_data := {"key": "src-data"}))

    target, namespace = function
    hashed_args = hashlib.md5(f"{(identifier,)}-{list(src_data.items())!s}".encode(), usedforsecurity=False).hexdigest()
    expected_key = f"{config.REDIS.key_prefix}{namespace}-{identifier}-{hashed_args}"

    app_cache, _, _ = datastore
    app_cache.get.return_value = None

    result = cache_resource(target)(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )

    assert result == src_obj
    app_cache.get.assert_called_once_with(expected_key)
    app_cache.set.assert_called_once_with(
        expected_key, src_obj.model_dump_json(exclude_none=True), ex=config.REDIS.cache_timeout
    )
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)
    assert_message(caplog.records[0], I.RESOURCE_CACHE_CREATED)


def test_cache_resource_maperror(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture, caplog):
    error_obj = MapError(status="400", scim_type="invalidValue", detail=(identifier := "error-id"))
    data = {"key": "value"}

    target, namespace = function
    hashed_args = hashlib.md5(f"{(identifier,)}-{list(data.items())!s}".encode(), usedforsecurity=False).hexdigest()
    expected_key = f"{config.REDIS.key_prefix}{namespace}-{identifier}-{hashed_args}"

    app_cache, _, _ = datastore
    app_cache.get.return_value = None

    result = cache_resource(target)(identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **data)

    assert result == error_obj
    app_cache.get.assert_called_once_with(expected_key)
    app_cache.set.assert_called_once_with(
        expected_key, error_obj.model_dump_json(exclude_none=True), ex=int(config.REDIS.cache_timeout / 100)
    )
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **data)
    assert_message(caplog.records[0], I.RESOURCE_CACHE_CREATED)


def test_cache_resource_redis_error(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture, caplog):
    src_obj = ResourceModel(value=(identifier := "src-id"), data=(src_data := {"key": "src-data"}))

    target, namespace = function
    app_cache, _, _ = datastore
    app_cache.get.side_effect = RedisError("fail get")
    app_cache.set.side_effect = RedisError("fail set")
    config.REDIS.cache_timeout = -1  # when timeout is negative, expire is not set (ex=None)

    result = cache_resource(target)(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )

    assert result == src_obj
    app_cache.get.assert_called_once()
    app_cache.set.assert_called_once_with(mocker.ANY, mocker.ANY, ex=None)
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)
    assert_message(caplog.records[0], W.FAILED_GET_CACHE, {"func": namespace, "id": identifier})
    assert_message(caplog.records[1], W.FAILED_SET_CACHE, {"func": namespace, "id": identifier})


def test_cache_resource_invalid_cache_data(app, datastore, function, mocker: MockerFixture, caplog):
    src_obj = ResourceModel(value=(identifier := "src-id"), data=(src_data := {"key": "src-data"}))

    target, namespace = function
    app_cache, _, _ = datastore
    app_cache.get.return_value = '{"invalid": "json"}'

    result = cache_resource(target)(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )

    assert result == src_obj
    app_cache.get.assert_called_once()
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)
    assert_message(caplog.records[0], W.FAILED_PARSE_CACHE, {"func": namespace, "id": identifier})


def test_cache_resource_zero_timeout(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture):
    config.REDIS.cache_timeout = 0  # when timeout is 0, decorator does nothing

    src_obj = ResourceModel(value=(identifier := "src-id"), data=(src_data := {"key": "src-data"}))

    target, _ = function
    app_cache, _, _ = datastore

    result = cache_resource(target)(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )

    assert result == src_obj
    app_cache.get.assert_not_called()
    app_cache.set.assert_not_called()
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)


def test_cache_resource_no_args(app, datastore, function, mocker: MockerFixture):
    src_obj = ResourceModel(value=(identifier := "kw-id"), data=(src_data := {"key": "src-data"}))

    target, _ = function
    app_cache, _, _ = datastore

    result = cache_resource(target)(
        arg=identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )  # when no positional args, decorator does nothing

    assert result == src_obj
    app_cache.get.assert_not_called()
    app_cache.set.assert_not_called()
    target.assert_called_once_with(arg=identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)


def test_cache_resource_with_id_generator(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture):
    def test_id_generator(*args, **kwargs):
        return f"generated-{args[0]}"

    src_obj = ResourceModel(value=(identifier := "src-id"), data=(src_data := {"key": "src-data"}))

    target, namespace = function
    app_cache, _, _ = datastore
    app_cache.get.return_value = None

    hashed_args = hashlib.md5(f"{(identifier,)}-{list(src_data.items())!s}".encode(), usedforsecurity=False).hexdigest()
    expected_key = f"{config.REDIS.key_prefix}{namespace}-{test_id_generator(identifier)}-{hashed_args}"

    result = cache_resource(id_generator=test_id_generator)(target)(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )

    assert result == src_obj
    app_cache.get.assert_called_once_with(expected_key)
    app_cache.set.assert_called_once_with(expected_key, mocker.ANY, ex=config.REDIS.cache_timeout)
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)


def test_cache_resource_override_timeout(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture):
    override_timeout = 5

    src_obj = ResourceModel(value=(identifier := "src-id"), data=(src_data := {"key": "src-data"}))

    target, namespace = function
    app_cache, _, _ = datastore
    app_cache.get.return_value = None

    hashed_args = hashlib.md5(f"{(identifier,)}-{list(src_data.items())!s}".encode(), usedforsecurity=False).hexdigest()
    expected_key = f"{config.REDIS.key_prefix}{namespace}-{identifier}-{hashed_args}"

    result = cache_resource(timeout=override_timeout)(target)(
        identifier, access_token=uuid4().hex[:8], client_secret=uuid4().hex[:16], **src_data
    )

    assert result == src_obj
    app_cache.get.assert_called_once_with(expected_key)
    app_cache.set.assert_called_once_with(expected_key, mocker.ANY, ex=override_timeout)
    target.assert_called_once_with(identifier, access_token=mocker.ANY, client_secret=mocker.ANY, **src_data)


def test_default_id_generator(app: Flask, login_users, mocker: MockerFixture):
    user = login_users[USER_ROLES.REPOSITORY_ADMIN]
    permitted = {"test_1_repo_ac_jp", "test_2_repo_ac_jp"}
    mocker.patch.object(server.clients.decorators, "is_user_logged_in", return_value=True)
    mocker.patch.object(LoginUser, "permitted_repositories", new_callable=mocker.PropertyMock(return_value=permitted))
    expected = ",".join(sorted(permitted))

    with app.test_request_context():
        login_user(user)
        result = default_id_generator()

    assert result == expected


def test_default_id_unauthenticated(mocker: MockerFixture):
    mocker.patch.object(server.clients.decorators, "is_user_logged_in", return_value=False)

    result = default_id_generator()

    assert result == "by_anonymous"


def test_default_id_system_admin(app: Flask, login_users, mocker: MockerFixture):
    user = login_users[USER_ROLES.SYSTEM_ADMIN]
    mocker.patch.object(server.clients.decorators, "is_user_logged_in", return_value=True)

    with app.test_request_context():
        login_user(user)

        result = default_id_generator()

    assert result == "by_system_admin"


def test__clear_cache(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture):
    identifier = "cached-id"
    target, namespace = function
    target._cache_namespace = namespace

    scan_key = f"{config.REDIS.key_prefix}{namespace}-{identifier}-*"
    delete_key = scan_key.replace("*", hashlib.md5(usedforsecurity=False).hexdigest())
    app_cache, _, _ = datastore
    app_cache.scan.side_effect = [(100, [delete_key]), (0, [])]

    _clear_cache(target, identifier)

    app_cache.scan.assert_any_call(mocker.ANY, scan_key, count=100)
    app_cache.delete.assert_called_once_with(delete_key)


def test__clear_cache_uninitialized(config):
    with pytest.raises(NotImplementedError, match=regex(E.UNINIT_RESOURCE_CACHE)):
        _clear_cache(target_func)  # pyright: ignore[reportArgumentType]


def test__clear_cache_redis_error(app, config: RuntimeConfig, datastore, function, mocker: MockerFixture, caplog):
    identifier = "cached-id"
    target, namespace = function
    target._cache_namespace = namespace
    app_cache, _, _ = datastore
    app_cache.scan.side_effect = RedisError("fail scan")

    _clear_cache(target, identifier)

    app_cache.scan.assert_called_once()
    assert_message(caplog.records[0], W.FAILED_DELETE_CACHE, {"func": namespace, "id": identifier})
