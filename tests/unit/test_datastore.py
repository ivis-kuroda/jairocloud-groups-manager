import pytest

from redis.exceptions import ConnectionError as RedisConnectionError

from server.datastore import connection
from server.exc import ConfigurationError


def test_redis_connection_error_logs_warning_1(app, mocker):
    mocker.patch("server.config.config.REDIS.cache_type", new="DummyCache")
    sentinel_mock = mocker.patch("server.datastore.sentinel.Sentinel")
    instance = sentinel_mock.return_value
    store_mock = mocker.Mock()
    store_mock.ping.side_effect = RedisConnectionError("connection failed")
    instance.master_for.return_value = store_mock
    logger_mock = mocker.patch.object(app.logger, "warning")
    connection(db=1)
    logger_mock.assert_called()
    assert "connection failed" in logger_mock.call_args[0][0]


def test_redis_connection_error_logs_warning(app, mocker):

    mocker.patch("server.config.config.REDIS.cache_type", new="RedisCache")
    mocker.patch("server.datastore.Redis.from_url", side_effect=ValueError("invalid config"))
    with pytest.raises(ConfigurationError) as exc_info:
        connection(db=1)
    assert "invalid config" in str(exc_info.value)
