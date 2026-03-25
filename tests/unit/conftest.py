import typing as t

from pathlib import Path

import pytest

from pydantic import HttpUrl

from server import const
from server.config import RuntimeConfig
from server.entities.cache import RepositoryCache
from server.entities.search_request import SearchResult
from server.entities.summaries import RepositorySummary
from server.factory import create_app


if t.TYPE_CHECKING:
    from datetime import datetime

    from flask import Flask
    from pytest_mock import MockerFixture


def is_running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


@pytest.fixture(autouse=True)
def set_test_constants():
    const.MAP_USER_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:User"
    const.MAP_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Group"
    const.MAP_SERVICE_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Service"


@pytest.fixture
def instance_path(tmp_path: Path) -> Path:
    return tmp_path / "instance"


@pytest.fixture
def test_config():
    db_host = "postgres" if is_running_in_docker() else "localhost"
    redis_host = "redis" if is_running_in_docker() else "localhost"
    amqp_host = "rabbitmq" if is_running_in_docker() else "localhost"
    return RuntimeConfig.model_validate(
        {
            "SECRET_KEY": "test_secret_key",
            "LOG": {
                "level": "DEBUG",
            },
            "SP": {
                "connector_id": "jairocloud-groups-manager_test",
                "entity_id": "https://test/shibboleth-sp",
                "crt": "/test/server.crt",
                "key": "/test/server.key",
            },
            "MAP_CORE": {
                "base_url": "https://mapcore.test.jp",
                "timeout": 3,
            },
            "REPOSITORIES": {
                "id_patterns": {
                    "sp_connector": "jc_{repository_id}_test",
                },
            },
            "GROUPS": {
                "id_patterns": {
                    "system_admin": "jc_roles_sysadm_test",
                    "repository_admin": "jc_{repository_id}_ro_radm_test",
                    "community_admin": "jc_{repository_id}_ro_cadm_test",
                    "contributor": "jc_{repository_id}_ro_cont_test",
                    "general_user": "jc_{repository_id}_ro_user_test",
                    "user_defined": "jc_{repository_id}_gr_{user_defined_id}_test",
                },
                "name_patterns": {
                    "system_admin": "ジャイロクラウドシステム管理者_テスト",
                    "repository_admin": "{repository_name}管理者_テスト",
                    "community_admin": "{repository_name}コミュニティ管理者_テスト",
                    "contributor": "{repository_name}投稿ユーザー_テスト",
                    "general_user": "{repository_name}一般ユーザー_テスト",
                },
                "max_id_length": "50 - len('jc_') - len('_gr_')",
            },
            "POSTGRES": {"db": "jctest", "host": db_host},
            "USERS": {
                "export_format_version": 1.0,
            },
            "REDIS": {
                "cache_type": "RedisCache",
                "key_prefix": "jcgroups-test-",
                "single": {"base_url": f"redis://{redis_host}:6379/0"},
                "sentinel": {
                    "nodes": [
                        {"host": "sentinel-1", "port": 26379},
                        {"host": "sentinel-2", "port": 26379},
                    ],
                },
            },
            "RABBITMQ": {"url": f"amqp://guest:guest@{amqp_host}:5672//"},
            "STORAGE": {"local": {"temporary": "/var/tmp/jcgroups"}},  # noqa: S108
            "CACHE_GROUPS": {
                "cache_key_suffix": "_gakunin_groups",
                "api_endpoint": "https://sample.gakunin.jp/api/groups/",
                "directory_path": "/var/mnt",
            },
            "FEATURES": {"search_only_username": False, "enable_bulk_operation": True},
        },
    )


@pytest.fixture
def datastore(mocker: MockerFixture):
    app_cache = mocker.MagicMock()
    account_store = mocker.MagicMock()
    group_cache = mocker.MagicMock()

    def _stores(name):
        return {
            "app_cache": app_cache,
            "account_store": account_store,
            "group_cache": group_cache,
        }[name]

    mocker.patch("server.datastore._stores", side_effect=_stores)

    return app_cache, account_store, group_cache


@pytest.fixture
def base_app(instance_path, test_config):
    app = create_app(__name__, config=test_config)
    app.instance_path = instance_path
    app.config["TESTING"] = True

    return app


@pytest.fixture
def app(base_app: Flask):
    with base_app.app_context():
        yield base_app


@pytest.fixture
def gen_summaries():
    def _data(num: int) -> SearchResult[RepositorySummary]:
        resources = [
            RepositorySummary(
                id=f"repo_{i}",
                service_name=f"Repository {i}",
                service_url=HttpUrl(f"https://repo{i}.example.jp"),
                service_id=f"jc_repo_{i}_sp",
            )
            for i in range(1, num + 1)
        ]
        return SearchResult(resources=resources, total=num, page_size=20, offset=1)

    return _data


@pytest.fixture
def cached_data():
    def _data(
        repositories: list[RepositorySummary],
        now: datetime,
        *,
        every_other: bool,
    ) -> list[RepositoryCache]:
        return [
            RepositoryCache(
                id=repositories[i].id,
                service_name=repositories[i].service_name,  # pyright: ignore[reportArgumentType],
                service_url=repositories[i].service_url,
                updated=now if not every_other or i % 2 == 0 else None,
            )
            for i in range(len(repositories))
        ]

    return _data
