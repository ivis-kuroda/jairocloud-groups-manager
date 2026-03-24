#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Redis connection module for weko-group-cache-db."""

import typing as t

from flask import Flask, current_app
from redis import Redis, sentinel
from redis.exceptions import ConnectionError as RedisConnectionError
from werkzeug.local import LocalProxy

from server.config import config as config_
from server.exc import ConfigurationError
from server.messages import E, W


if t.TYPE_CHECKING:
    from .config import RuntimeConfig


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
    config = config or config_
    timeout = config.REDIS.socket_timeout
    try:
        if config.REDIS.cache_type == "RedisCache":
            base_url = config.REDIS.single.base_url
            store = Redis.from_url(f"{base_url}/{db}")
        else:
            sentinels = sentinel.Sentinel(
                [(node.host, node.port) for node in config.REDIS.sentinel.nodes],
                socket_timeout=timeout,
                socket_connect_timeout=timeout,
                decode_responses=False,
            )
            store = sentinels.master_for(
                config.REDIS.sentinel.master_name,
                db=db,
                socket_timeout=timeout,
                socket_connect_timeout=timeout,
            )

    except ValueError as exc:
        error = E.INVALID_REDIS_CONFIG % {"error": str(exc)}
        raise ConfigurationError(error) from exc

    try:
        store.ping()
    except RedisConnectionError as exc:
        error = W.FAILED_CONNECT_REDIS % {"error": str(exc)}
        app.logger.warning(error)

    return store


def _stores(name: str) -> Redis:
    ext = current_app.extensions["jairocloud-groups-manager"]
    return ext.datastore[name]


app_cache = t.cast("Redis", LocalProxy(lambda: _stores("app_cache")))
"""Redis datastore connection for application cache."""

account_store = t.cast("Redis", LocalProxy(lambda: _stores("account_store")))
"""Redis datastore connection for storing account information."""

group_cache = t.cast("Redis", LocalProxy(lambda: _stores("group_cache")))
"""Redis datastore connection for group informations cache."""
