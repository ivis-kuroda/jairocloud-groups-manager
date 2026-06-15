#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Redis connection module for weko-group-cache-db."""

import traceback
import typing as t

from flask import Flask, current_app
from redis import Redis, sentinel
from redis.exceptions import ConnectionError as RedisConnectionError
from werkzeug.local import LocalProxy

from server.config import config as server_config
from server.exc import ConfigurationError
from server.messages import E, W


if t.TYPE_CHECKING:
    from server.config import RuntimeConfig
    from server.ext import JAIROCloudGroupsManager


def setup_datastore(app: Flask, config: RuntimeConfig) -> dict[str, Redis]:
    """Setup Redis datastore connections for the application.

    Args:
        app (Flask): The Flask application instance.
        config (RuntimeConfig): The runtime configuration instance.

    Returns:
        dict: Dictionary of Redis connections.
    """
    return {
        name: connection(app, db=db, config=config)
        for name, db in config.REDIS.database.__dict__.items()
    }


def connection(
    app: Flask | None = None, *, db: int, config: RuntimeConfig | None = None
) -> Redis:
    """Establish Redis connection.

    Args:
        app (Flask): The Flask application instance, or None to use current_app.
        db (int): Database number.
        config (RuntimeConfig): The runtime configuration instance.

    Returns:
        Redis: Redis store object.

    Raises:
        ConfigurationError: If configuration for Redis is invalid.

    """
    app = app or current_app
    config = config or server_config
    try:
        if config.REDIS.cache_type == "RedisCache":
            store = __single_connection(config, db)
        else:
            store = __sentinel_connection(config, db)

    except ValueError as exc:
        raise ConfigurationError(E.INVALID_REDIS_CONFIG) from exc

    try:
        store.ping()
    except RedisConnectionError:
        app.logger.warning(W.FAILED_CONNECT_REDIS)
        traceback.print_exc()

    return store


def __single_connection(config: RuntimeConfig, db: int) -> Redis:
    base_url = config.REDIS.single.base_url
    return Redis.from_url(
        f"{base_url}/{db}",
        socket_timeout=config.REDIS.socket_timeout,
        socket_connect_timeout=config.REDIS.socket_timeout,
    )


def __sentinel_connection(config: RuntimeConfig, db: int) -> Redis:
    sentinels = sentinel.Sentinel(
        [(node.host, node.port) for node in config.REDIS.sentinel.nodes],
        socket_timeout=config.REDIS.socket_timeout,
        socket_connect_timeout=config.REDIS.socket_timeout,
        decode_responses=False,
    )
    return sentinels.master_for(
        config.REDIS.sentinel.master_name,
        db=db,
        socket_timeout=config.REDIS.socket_timeout,
        socket_connect_timeout=config.REDIS.socket_timeout,
    )


def _stores(name: str) -> Redis:
    ext: JAIROCloudGroupsManager = current_app.extensions["jairocloud-groups-manager"]
    return ext.datastore[name]


app_cache = t.cast("Redis", LocalProxy(lambda: _stores("app_cache")))
"""Redis datastore connection for application cache."""

account_store = t.cast("Redis", LocalProxy(lambda: _stores("account_store")))
"""Redis datastore connection for storing account information."""

group_cache = t.cast("Redis", LocalProxy(lambda: _stores("group_cache")))
"""Redis datastore connection for group informations cache."""
