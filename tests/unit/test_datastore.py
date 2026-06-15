import typing as t

import pytest

from flask import Flask
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

import server.datastore

from server.datastore import connection, setup_datastore
from server.exc import ConfigurationError
from server.ext import JAIROCloudGroupsManager
from server.messages import E, W

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


def test_setup_datastore(test_config: RuntimeConfig, mocker: MockerFixture):
    app = Flask(__name__)
    mock_stores = [mocker.MagicMock(name=f"redis_{i}", spec=Redis) for i in range(5)]
    mocker.patch.object(server.datastore, "connection", side_effect=lambda _, db, config: mock_stores[db])  # noqa: ARG005

    stores = setup_datastore(app, test_config)

    (_, app_cache), (_, account_store), (_, result_backend), (_, group_cache) = test_config.REDIS.database
    assert stores["app_cache"] == mock_stores[app_cache]
    assert stores["account_store"] == mock_stores[account_store]
    assert stores["result_backend"] == mock_stores[result_backend]
    assert stores["group_cache"] == mock_stores[group_cache]


@pytest.mark.redis_enabled
def test_connection_single(test_config: RuntimeConfig, mocker: MockerFixture):
    app = Flask(__name__)
    test_config.REDIS.cache_type = "RedisCache"
    mock_ping = mocker.patch.object(Redis, "ping")

    store = connection(app, db=0, config=test_config)

    assert isinstance(store, Redis)
    assert store.connection_pool.connection_kwargs["host"] == test_config.REDIS.single.base_url.host
    mock_ping.assert_called_once()


@pytest.mark.redis_enabled
def test_connection_sentinel(test_config: RuntimeConfig, mocker: MockerFixture):
    app = Flask(__name__)
    test_config.REDIS.cache_type = "RedisSentinelCache"
    mock_ping = mocker.patch.object(Redis, "ping")

    store = connection(app, db=0, config=test_config)

    assert isinstance(store, Redis)
    pool = store.connection_pool.connection_kwargs["connection_pool"]
    assert pool.service_name == test_config.REDIS.sentinel.master_name
    mock_ping.assert_called_once()


@pytest.mark.redis_enabled
def test_connection_invalid_value(test_config: RuntimeConfig, mocker: MockerFixture):
    app = Flask(__name__)
    test_config.REDIS.cache_type = "RedisCache"
    mocker.patch.object(Redis, "from_url", side_effect=ValueError("invalid config"))

    with pytest.raises(ConfigurationError, match=regex(E.INVALID_REDIS_CONFIG)):
        connection(app, db=0, config=test_config)


@pytest.mark.redis_enabled
def test_connection_ping_error(test_config: RuntimeConfig, mocker: MockerFixture, caplog):
    app = Flask(__name__)
    test_config.REDIS.cache_type = "RedisCache"
    mock_ping = mocker.patch.object(Redis, "ping", side_effect=RedisConnectionError)

    store = connection(app, db=0, config=test_config)

    assert isinstance(store, Redis)
    mock_ping.assert_called_once()
    assert_message(caplog.records[0], W.FAILED_CONNECT_REDIS)


@pytest.mark.redis_enabled
@pytest.mark.parametrize("name", ["app_cache", "account_store", "group_cache"])
def test_proxy(name: str, base_app, test_config, mocker: MockerFixture):
    mocker.patch.object(Redis, "ping")
    ext = JAIROCloudGroupsManager(base_app, config=test_config)
    expected = ext.datastore[name]

    with base_app.app_context():
        proxy = getattr(server.datastore, name)

        assert proxy == expected
        assert proxy._get_current_object() is expected
