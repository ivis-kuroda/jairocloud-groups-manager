import typing as t

from unittest.mock import MagicMock, patch

import pytest

from pydantic import BaseModel
from redis.exceptions import RedisError

from server.clients import decoraters
from server.clients.decoraters import cache_resource, clear_cache
from server.entities.map_error import MapError
from server.messages import E
from server.messages.base import LogMessage


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


class DummyModel(BaseModel):
    value: int = 0


def test_dummy_model_default():
    model = DummyModel()
    assert model.value == 0


def test_cache_resource_with_callable(app, mocker: MockerFixture) -> None:
    ex_num = 11
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new_callable=mocker.MagicMock)
    app_cache_mock.get.return_value = None

    dummy_json = DummyModel(value=ex_num).model_dump_json()
    app_cache_mock.get.side_effect = [None, dummy_json]
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 10)

    call_count = {"count": 0}

    def func(x: int) -> DummyModel:
        call_count["count"] += 1
        return DummyModel(value=x + 1)

    decorated = cache_resource(func)
    assert decorated(10).value == ex_num
    assert decorated(10).value == ex_num
    assert call_count["count"] == 1
    assert hasattr(decorated, "_import_name")
    assert hasattr(decorated, "clear_cache")


def test_cache_resource_func_raises(app, mocker: MockerFixture) -> None:
    """Tests that cache_resource propagates exceptions from the wrapped function."""
    ex_str = "fail"
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new_callable=mocker.MagicMock)
    app_cache_mock.get.return_value = None
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 10)

    def func(x: int) -> DummyModel:
        raise ValueError(ex_str)

    decorated = cache_resource(func)
    with pytest.raises(ValueError, match=ex_str):
        decorated(1)


def test_cache_resource_maperror_timeout(app, mocker: MockerFixture) -> None:
    cache_timeout = 10
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new_callable=mocker.MagicMock)
    app_cache_mock.get.return_value = None
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", cache_timeout)

    class FakeMapError(BaseModel):
        pass

    def func(x: int) -> FakeMapError:
        return FakeMapError()

    decorated = cache_resource(func)
    decorated(1)
    called_kwargs = app_cache_mock.set.call_args[1]
    assert called_kwargs["ex"] == cache_timeout


def test_cache_resource_sets_timeout_3_on_maperror(app, mocker: MockerFixture) -> None:
    """Tests cache_resource sets timeout=3 when result is MapError."""
    expected_value = 3
    cache_timeout = 300

    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=mocker.MagicMock())
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", cache_timeout)

    app_cache_mock.get.return_value = None

    def func(resource_id: str) -> MapError:
        return MapError(status="400", scim_type="invalidFilter", detail="error detail")

    decorated = decoraters.cache_resource(timeout=None)(func)
    result = decorated("abc")
    assert isinstance(result, MapError)
    app_cache_mock.set.assert_called()
    _, kwargs = app_cache_mock.set.call_args
    assert kwargs["ex"] == expected_value


def test_cache_resource_identifier_generator(app, mocker):
    expected_value = 3
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=MagicMock())
    app_cache_mock.get.return_value = None
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 10)

    def id_gen(x, y):
        return f"{x}-{y}"

    def func(x, y):
        return DummyModel(value=x + y)

    decorated = decoraters.cache_resource(identifier_generator=id_gen)(func)
    result = decorated(1, 2)
    assert result.value == expected_value
    cache_key = app_cache_mock.set.call_args[0][0]
    assert "-2" in cache_key


def test_cache_resource_get_redis_error(app, mocker):
    expected_value = 5

    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=MagicMock())
    app_cache_mock.get.side_effect = RedisError("fail get")
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 10)

    def func(x):
        return DummyModel(value=x)

    with patch("flask.current_app.logger") as mock_logger:
        decorated = decoraters.cache_resource(func)
        result = decorated(expected_value)
        assert result.value == expected_value
        mock_logger.warning.assert_any_call(
            LogMessage("W081", "Failed to get cache (func %(func)s, id: %(id)s)."), mocker.ANY
        )


def test_cache_resource_set_redis_error(app, mocker):
    expected_value = 7
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=MagicMock())
    app_cache_mock.get.return_value = None
    app_cache_mock.set.side_effect = RedisError("fail set")
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 10)

    def func(x):
        return DummyModel(value=x)

    with patch("flask.current_app.logger") as mock_logger:
        decorated = decoraters.cache_resource(func)
        result = decorated(expected_value)
        assert result.value == expected_value
        mock_logger.warning.assert_any_call(
            LogMessage("W080", "Failed to set cache (func %(func)s, id: %(id)s)."), mocker.ANY
        )


def test_cache_resource_no_cache_when_all_timeouts_falsy(app, mocker):
    """Tests that cache_resource does not cache when both timeout and config.REDIS.cache_timeout are falsy."""

    app_cache_mock = mocker.patch("server.datastore.app_cache", new=MagicMock())
    app_cache_mock.get.return_value = None
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 0)
    called: dict[str, bool] = {"called": False}

    class MyModel(BaseModel):
        value: int

    def func(x: int) -> MyModel:
        called["called"] = True
        return MyModel(value=x + 1)

    decorated = decoraters.cache_resource(timeout=None)(func)
    result = decorated(7)

    assert result == MyModel(value=8)
    assert called["called"] is True
    assert not app_cache_mock.set.called
    assert not app_cache_mock.get.called


def test_cache_resource_maperror_ttl_division(app, mocker):
    expected_value = 2

    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=MagicMock())
    app_cache_mock.get.return_value = None
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")
    mocker.patch("server.clients.decoraters.config.REDIS.cache_timeout", 200)

    def func(x):
        return MapError(status="400", scim_type="invalidFilter", detail="error detail")

    decorated = decoraters.cache_resource(timeout=None)(func)
    result = decorated(1)

    assert isinstance(result, MapError)
    assert app_cache_mock.set.call_args[1]["ex"] == expected_value


def test_cache_resource_result_maperror_sets_timeout(app, mocker: MockerFixture) -> None:
    """Tests cache_resource when result is MapError, timeout is set to 3."""

    def func(resource_id: str) -> MapError:
        return MapError(status="400", scim_type="invalidFilter", detail="error detail")

    mocker.patch.object(decoraters.config.REDIS, "cache_timeout", 99)
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=mocker.MagicMock())
    app_cache_mock.get.return_value = None

    decorated = decoraters.cache_resource(timeout=None)(func)
    result = decorated("abc")
    assert isinstance(result, MapError)


def test_cache_resource_args_empty(app, mocker: MockerFixture) -> None:
    """Tests cache_resource when args is empty (should call original function directly)."""
    called = {}
    expected_value = 42

    def func() -> DummyModel:
        called["ok"] = True
        return DummyModel(value=expected_value)

    decorated = cache_resource(func)
    result = decorated()
    assert result.value == expected_value
    assert called["ok"] is True


def test_clear_cache_normal(app, mocker: MockerFixture) -> None:
    """Tests that clear_cache deletes cache keys for given resource_id."""
    scan_keys = [b"prefix:mod.func:1:abc"]

    def dummy_func() -> DummyModel:
        return DummyModel(value=0)

    decorated = cache_resource(dummy_func)
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=mocker.MagicMock())
    app_cache_mock.get.return_value = None
    app_cache_mock.scan.side_effect = [(1, scan_keys), (0, [])]

    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")

    clear_cache(decorated, "1")
    app_cache_mock.delete.assert_called_with(*scan_keys)


def test_clear_cache_not_decorated(app, mocker: MockerFixture) -> None:
    """Tests that clear_cache raises ValueError if function is not decorated."""

    error_msg = "Function is not decorated with @response_cache."
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")

    def dummy_func(x):
        return x

    error_msg = str(E.UNINIT_RESOURCE_CACHE % {"name": dummy_func.__name__})
    with pytest.raises(NotImplementedError, match=error_msg):
        clear_cache(dummy_func, "1")


def test_clear_cache_scan_loop_keys(app, mocker: MockerFixture) -> None:
    """Tests clear_cache scan loop with keys found and deleted."""
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=mocker.MagicMock())
    scan_results = [("1", ["k1", "k2"]), (0, [])]
    scan_index = {"i": 0}

    def scan_side_effect(*_, **__):
        i = scan_index["i"]
        if i < len(scan_results):
            result = scan_results[i]
            scan_index["i"] += 1
            return result
        return (0, [])

    app_cache_mock.scan.side_effect = scan_side_effect
    app_cache_mock.delete = mocker.MagicMock()

    def dummy_func() -> DummyModel:
        return DummyModel(value=0)

    decorated = cache_resource(dummy_func)

    resource_id = ["id1"]
    decoraters.clear_cache(decorated, *resource_id)
    app_cache_mock.scan.assert_called()
    app_cache_mock.delete.assert_called_with("k1", "k2")


def test_clear_cache_empty_resource_id(app, mocker: MockerFixture) -> None:
    """Tests clear_cache when resource_id is empty (should not scan/delete)."""
    mock_cache = mocker.patch("server.clients.decoraters.app_cache", new=mocker.MagicMock())
    mock_cache.scan.side_effect = [(0, [])]
    mock_cache.delete = mocker.MagicMock()

    def dummy_func() -> DummyModel:
        return DummyModel(value=0)

    decorated = cache_resource(dummy_func)

    clear_cache(decorated)
    mock_cache.scan.assert_not_called()
    mock_cache.delete.assert_not_called()


def test_clear_cache_redis_error_on_scan(app, mocker, caplog):
    """Tests that clear_cache handles RedisError from scan and logs warning."""
    app_cache_mock = mocker.patch("server.clients.decoraters.app_cache", new=MagicMock())
    app_cache_mock.scan.side_effect = RedisError("Mocked Redis error")
    mocker.patch("server.clients.decoraters.config.REDIS.key_prefix", "prefix")

    def dummy_func() -> DummyModel:
        return DummyModel(value=0)

    dummy_func._import_name = "dummy.module.func"  # noqa: SLF001  # type: ignore[attr-defined]

    with patch("flask.current_app.logger") as mock_logger:
        decoraters.clear_cache(dummy_func, "id1")
        assert mock_logger.warning.called
