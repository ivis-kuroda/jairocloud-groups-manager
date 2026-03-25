from unittest.mock import MagicMock

import pytest

from server.config import (
    USER_ROLES,
    E,
    GroupIdPatternsConfig,
    GroupNamePatternsConfig,
    GroupsConfig,
    RepositoriesConfig,
    config,
    safe_eval,
)
from server.factory import celery_init_app, create_app


def test_celery_init_app_once():
    app = create_app(__name__)
    celery = celery_init_app(app)
    assert celery is app.extensions["celery"]


def test_celery_property_redis_sentinel_cache_type(app, mocker):
    """CELERY property returns correct config when cache_type is RedisSentinelCache (mocked)."""
    mocker.patch("pydantic.main._check_frozen")
    mock_redis_config = MagicMock(cache_type="RedisSentinelCache")
    mocker.patch.object(config, "REDIS", mock_redis_config)
    _ = config.CELERY
    assert config.REDIS.cache_type == "RedisSentinelCache"

    mocker.stopall()


def test_celery_property_redis_sentinel_cache_type_no_sentinel(app, mocker):
    """CELERY property: cache_type=RedisSentinelCache but REDIS.sentinel is None (False branch)."""
    mocker.patch("pydantic.main._check_frozen")
    mock_redis_config = MagicMock(cache_type="RedisSentinelCache_false")
    mocker.patch.object(config, "REDIS", mock_redis_config)
    _ = config.CELERY
    assert config.REDIS.cache_type == "RedisSentinelCache_false"

    mocker.stopall()


def test_remember_cookie_duration_absolute(app, mocker):
    mocker.patch.object(config.SESSION, "strategy", "absolute")
    _ = config.REMEMBER_COOKIE_DURATION
    assert config.REDIS.cache_type == "RedisCache"

    mocker.stopall()


def test_remember_cookie_duration_other(app, mocker):

    mocker.patch.object(config.SESSION, "strategy", "invalid")
    with pytest.raises(UnboundLocalError):
        _ = config.REMEMBER_COOKIE_DURATION
    assert config.REDIS.cache_type == "RedisCache"

    mocker.stopall()


def test_validate_max_url_length_syntax_error():
    invalid_expr = "1 + * 2"
    msg = "E003 | Invalid syntax in expression in server configuration."

    with pytest.raises(ValueError, match=msg):
        RepositoriesConfig.validate_max_url_length(invalid_expr)


def test_validate_max_id_length_syntax_error():
    invalid_expr = "abc + * 1"
    msg = "E003 | Invalid syntax in expression in server configuration."

    with pytest.raises(ValueError, match=msg):
        GroupsConfig.validate_max_id_length(invalid_expr)


def test_group_patterns_config_validation_success():

    id_patterns = GroupNamePatternsConfig(
        system_admin="sysadmin",
        repository_admin="repo_admin_{repository_name}",
        community_admin="community_admin_{repository_name}",
        contributor="contributor_{repository_name}",
        general_user="general_user_{repository_name}",
    )
    name_patterns = GroupIdPatternsConfig(
        system_admin="sysadmin_id",
        repository_admin="repo_admin_{repository_id}",
        community_admin="community_admin_{repository_id}",
        contributor="contributor_{repository_id}",
        general_user="general_user_{repository_id}",
        user_defined="user_defined_{repository_id}_{user_defined_id}",
    )
    assert id_patterns[USER_ROLES.SYSTEM_ADMIN] == "sysadmin"
    assert name_patterns[USER_ROLES.SYSTEM_ADMIN] == "sysadmin_id"


def test_safe_eval_unsupported_function():
    with pytest.raises(ValueError, match=str(E.UNSUPPORTED_EXPRESSION) % {"exp": "sum(1,2)"}):
        safe_eval("sum(1,2)")


def test_safe_eval_syntax_error():
    with pytest.raises(SyntaxError):
        safe_eval("1 + * 2")


def test_safe_eval_max_branch():
    excepted_value = 10
    assert safe_eval("max(10, 3, 7)") == excepted_value


def test_safe_eval_min_branch():
    excepted_value = 3
    assert safe_eval("min(10, 3, 7)") == excepted_value


def test_safe_eval_unsupported_ast_node():
    with pytest.raises(ValueError, match=str(E.UNSUPPORTED_EXPRESSION) % {"exp": "[1, 2, 3]"}):
        safe_eval("[1, 2, 3]")
