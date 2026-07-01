import typing as t

from datetime import timedelta
from urllib.parse import urlparse

import pytest

from flask import Flask

import server.config

from server.config import GroupsConfig, RepositoriesConfig, safe_eval
from server.ext import JAIROCloudGroupsManager
from server.messages import E

from tests.helpers import regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from werkzeug.local import LocalProxy

    from server.config import RuntimeConfig


class TestRuntimeConfig:
    def test_celery(self, test_config: RuntimeConfig):
        test_config.REDIS.cache_type = "RedisCache"
        redis_url = test_config.REDIS.single.base_url
        rabbitmq_url = test_config.RABBITMQ.url

        celery_config = test_config.CELERY

        scheme, netloc, path, *_ = urlparse(celery_config["broker_url"])
        assert scheme == rabbitmq_url.scheme
        assert netloc == f"{rabbitmq_url.username}:{rabbitmq_url.password}@{rabbitmq_url.host}:{rabbitmq_url.port}"
        assert path == rabbitmq_url.path

        scheme, netloc, path, *_ = urlparse(celery_config["result_backend"])
        assert (scheme, netloc) == (redis_url.scheme, f"{redis_url.host}:{redis_url.port}")
        assert path == f"/{test_config.REDIS.database.result_backend}"

    def test_celery_sentinel(self, test_config: RuntimeConfig):
        test_config.REDIS.cache_type = "RedisSentinelCache"
        sentinel_nodes = test_config.REDIS.sentinel.nodes
        rabbitmq_url = test_config.RABBITMQ.url

        celery_config = test_config.CELERY

        assert celery_config["broker_url"] == rabbitmq_url.encoded_string()

        result_backend = celery_config["result_backend"]
        nodes, db = result_backend[:-2].split(";"), result_backend[-2:]
        assert len(nodes) == len(sentinel_nodes)
        assert all(
            (scheme, netloc) == ("sentinel", f"{sentinel_node.host}:{sentinel_node.port}")
            for node, sentinel_node in zip(nodes, sentinel_nodes, strict=True)
            for scheme, netloc, *_ in [urlparse(node)]
        )
        assert db == f"/{test_config.REDIS.database.result_backend}"

    def test_sqlalchemy_database_uri(self, test_config: RuntimeConfig):
        (_, user), (_, password), (_, host), (_, port), (_, database) = test_config.POSTGRES
        expected = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"

        computed = test_config.SQLALCHEMY_DATABASE_URI

        assert computed.render_as_string(hide_password=False) == expected

    def test_permanent_session_lifetime(self, test_config: RuntimeConfig):
        lifetime = test_config.SESSION.absolute_lifetime = 60 * 60 * 24  # 1 day
        expected = timedelta(seconds=lifetime)

        computed = test_config.PERMANENT_SESSION_LIFETIME

        assert computed == expected

    def test_remember_cookie_duration_absolute(self, test_config: RuntimeConfig):
        test_config.SESSION.strategy = "absolute"
        lifetime = test_config.SESSION.absolute_lifetime = 60 * 60 * 24  # 1 day
        test_config.SESSION.sliding_lifetime = 60 * 60  # 1 hour
        expected = timedelta(seconds=lifetime)

        computed = test_config.REMEMBER_COOKIE_DURATION

        assert computed == expected

    def test_remember_cookie_duration_sliding(self, test_config: RuntimeConfig):
        test_config.SESSION.strategy = "sliding"
        test_config.SESSION.absolute_lifetime = 60 * 60 * 24  # 1 day
        lifetime = test_config.SESSION.sliding_lifetime = 60 * 60  # 1 hour
        expected = timedelta(seconds=lifetime)

        computed = test_config.REMEMBER_COOKIE_DURATION

        assert computed == expected

    def test_flask(self, test_config: RuntimeConfig):
        flask_config = test_config.FLASK

        assert flask_config["SERVER_NAME"] == test_config.SERVER_NAME
        assert flask_config["SECRET_KEY"] == test_config.SECRET_KEY
        assert flask_config["CELERY"] == test_config.CELERY
        assert flask_config["PERMANENT_SESSION_LIFETIME"] == test_config.PERMANENT_SESSION_LIFETIME
        assert flask_config["REMEMBER_COOKIE_DURATION"] == test_config.REMEMBER_COOKIE_DURATION
        assert flask_config["REMEMBER_COOKIE_REFRESH_EACH_REQUEST"] == (test_config.SESSION.strategy == "sliding")
        assert flask_config["SQLALCHEMY_DATABASE_URI"] == test_config.SQLALCHEMY_DATABASE_URI
        assert flask_config["PREFERRED_URL_SCHEME"] == "https"
        assert flask_config["SESSION_COOKIE_SECURE"]
        assert flask_config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_validate_max_url_length(mocker: MockerFixture):
    value, expected = "max(10, 20) + 5", 25
    mocker.patch.object(server.config, "safe_eval", return_value=expected)

    result = RepositoriesConfig.validate_max_url_length(value)

    assert result == expected


def test_validate_max_url_length_syntax_error(mocker: MockerFixture):
    value = "1 + * 2"
    mocker.patch.object(server.config, "safe_eval", side_effect=SyntaxError)

    with pytest.raises(ValueError, match=regex(E.INVALID_EXPRESSION)):
        RepositoriesConfig.validate_max_url_length(value)


def test_validate_max_id_length(mocker: MockerFixture):
    value, expected = "max(10, 20) + 5", 25
    mocker.patch.object(server.config, "safe_eval", return_value=expected)

    result = GroupsConfig.validate_max_id_length(value)

    assert result == expected


def test_validate_max_id_length_syntax_error(mocker: MockerFixture):
    value = "1 + * 2"
    mocker.patch.object(server.config, "safe_eval", side_effect=SyntaxError)

    with pytest.raises(ValueError, match=regex(E.INVALID_EXPRESSION)):
        GroupsConfig.validate_max_id_length(value)


def test_safe_eval():
    expr, expected = "1 + 3 * 2", 7

    evaled = safe_eval(expr)

    assert evaled == expected


def test_safe_eval_len():
    expr, expected = 'len("jcgroups")', 8

    evaled = safe_eval(expr)

    assert evaled == expected


def test_safe_eval_max():
    expr, expected = "max(10, 3, 7)", 10

    evaled = safe_eval(expr)

    assert evaled == expected


def test_safe_eval_min():
    expr, expected = "min(10, 3, 7)", 3

    evaled = safe_eval(expr)

    assert evaled == expected


def test_safe_eval_len_unsupported():
    expr = "len(12345)"

    with pytest.raises(TypeError):
        safe_eval(expr)


def test_safe_eval_unsupported():
    expr = "sum(1, 2)"

    with pytest.raises(ValueError, match=str(E.UNSUPPORTED_EXPRESSION) % {"exp": expr}):
        safe_eval(expr)


def test_proxy(test_config: RuntimeConfig):
    app = Flask(__name__)
    ext = JAIROCloudGroupsManager()
    app.extensions["jairocloud-groups-manager"] = ext
    expected = ext._config = test_config

    proxy = t.cast("LocalProxy[RuntimeConfig]", server.config.config)
    with app.app_context():
        assert proxy == expected
        assert proxy._get_current_object() is expected
