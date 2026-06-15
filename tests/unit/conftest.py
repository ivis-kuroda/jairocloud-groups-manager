import typing as t

from datetime import UTC, datetime

import pytest

from flask import Flask
from pydantic import HttpUrl
from redis import Redis
from redis.sentinel import Sentinel

import server.datastore

from server import const
from server.config import RuntimeConfig
from server.const import USER_ROLES
from server.entities.cache import RepositoryCache
from server.entities.group_detail import GroupDetail, Repository as GroupRepository
from server.entities.login_user import LoginUser
from server.entities.map_group import (
    Administrator as GroupAdministrator,
    MapGroup,
    Meta as GroupMeta,
    Service as GroupService,
)
from server.entities.map_user import EPPN, Email, Group as UserGroup, MapUser, Meta as UserMeta
from server.entities.repository_detail import RepositoryDetail
from server.entities.search_request import SearchResult
from server.entities.summaries import GroupSummary, RepositorySummary, UserSummary
from server.entities.user_detail import RepositoryRole, UserDetail
from server.ext import JAIROCloudGroupsManager
from server.services.utils.affiliations import Affiliations, _Group, _RoleGroup


if t.TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

pytest.register_assert_rewrite("tests.helpers")


@pytest.fixture(autouse=True, scope="session")
def set_test_constants():
    const.MAP_USER_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:User"
    const.MAP_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Group"
    const.MAP_SERVICE_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Service"


@pytest.fixture
def instance_path(tmp_path: Path) -> Path:
    return tmp_path / "instance"


@pytest.fixture
def test_config(tmp_path) -> RuntimeConfig:
    """Row RuntimeConfig.

    If the test needs application context, use the `config` fixture instead of this one.
    """
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
            "POSTGRES": {"db": "jctest", "host": "disable"},
            "USERS": {
                "export_format_version": 1.0,
            },
            "REDIS": {
                "cache_type": "RedisCache",
                "key_prefix": "jcgroups-test-",
                "single": {"base_url": "redis://disable:6379/0"},
                "sentinel": {
                    "nodes": [
                        {"host": "sentinel-1", "port": 26379},
                        {"host": "sentinel-2", "port": 26379},
                    ],
                },
            },
            "RABBITMQ": {"url": "amqp://guest:guest@disable:5672//"},
            "STORAGE": {
                "local": {
                    "temporary": str(tmp_path / "tmp" / "jcgroups"),
                    "storage": str(tmp_path / "storage" / "jcgroups"),
                }
            },
            "CACHE_GROUPS": {
                "cache_key_suffix": "_gakunin_groups",
                "api_endpoint": "https://sample.gakunin.jp/api/groups/",
                "directory_path": "/var/mnt",
            },
            "FEATURES": {"search_only_username": False, "enable_bulk_operation": True},
        },
    )


@pytest.fixture
def config(test_config, mocker: MockerFixture) -> RuntimeConfig:
    """Wrapped RuntimeConfig.

    This includes mocking to bypass access to the application context.
    """
    mocker.patch("server.config._get_config", return_value=test_config)
    return test_config


@pytest.fixture(autouse=True)
def sqlalchemy_disable(request: pytest.FixtureRequest, mocker: MockerFixture):
    if request.node.get_closest_marker("sqlalchemy_enabled"):
        return

    error = """SQLAlchemy is disabled in unit tests.
    If you want to enable it, add `@pytest.mark.sqlalchemy_enabled` to the test."""
    mocker.patch("server.db.base.SQLAlchemy", side_effect=RuntimeError(error))
    mocker.patch("server.ext.database_exists")


def pytest_configure(config):
    config.addinivalue_line("markers", "redis_enabled: Mark a test to enable Redis model.")


@pytest.fixture(autouse=True)
def redis_disable(request: pytest.FixtureRequest, mocker: MockerFixture):
    if request.node.get_closest_marker("redis_enabled"):
        return

    mocker.patch.object(server.datastore, "connection", return_value=mocker.MagicMock(spec=Redis))

    error = """Redis is disabled in unit tests.
    If you want to enable it, add `@pytest.mark.redis_enabled` to the test."""
    mocker.patch.object(Redis, "__getattribute__", side_effect=RuntimeError(error))
    mocker.patch.object(Redis, "__init__", side_effect=RuntimeError(error))
    mocker.patch.object(Sentinel, "__getattribute__", side_effect=RuntimeError(error))
    mocker.patch.object(Sentinel, "__init__", side_effect=RuntimeError(error))


@pytest.fixture
def db(mocker: MockerFixture):
    mock_db = mocker.MagicMock()
    mocker.patch("server.db.utils._db", return_value=mock_db)
    return mock_db


@pytest.fixture
def datastore(mocker: MockerFixture):
    app_cache = mocker.create_autospec(Redis, instance=True)
    account_store = mocker.create_autospec(Redis, instance=True)
    group_cache = mocker.create_autospec(Redis, instance=True)

    def _stores(name):
        return {
            "app_cache": app_cache,
            "account_store": account_store,
            "group_cache": group_cache,
        }[name]

    mocker.patch.object(server.datastore, "_stores", side_effect=_stores)

    return app_cache, account_store, group_cache


@pytest.fixture
def base_app(instance_path, sqlalchemy_disable, redis_disable):
    app = Flask(__name__)
    app.instance_path = instance_path
    app.config["TESTING"] = True

    return app


@pytest.fixture
def app(base_app: Flask, test_config):
    JAIROCloudGroupsManager(base_app, config=test_config)
    with base_app.app_context():
        yield base_app


@pytest.fixture
def role_affils():
    return {
        role: _RoleGroup(
            repository_id="Test Repo" if role != USER_ROLES.SYSTEM_ADMIN else None,
            role=role,
        )
        for role in USER_ROLES
    }


@pytest.fixture
def user_affils(test_config, role_affils):
    patterns = test_config.GROUPS.id_patterns
    gid = f"{patterns.user_defined.format(repository_id='test_repo_ac_jp', user_defined_id='test')}"
    groups = [_Group(group_id=gid, repository_id="test_repo_ac_jp", user_defined_id="test")]
    return {role: Affiliations(roles=[role_affils[role]], groups=groups) for role in USER_ROLES}


@pytest.fixture
def login_users(test_config):
    patterns = test_config.GROUPS.id_patterns
    groups = [
        f"{patterns.user_defined.format(repository_id='test_repo_ac_jp', user_defined_id='test')}",
        "group1",
    ]
    return {
        role: LoginUser(
            eppn=f"test-{role.value}@idp.example.com",
            is_member_of=";".join(f"https://cg.gakunin.jp/gr/{group}" for group in [patterns[role], *groups]),
            user_name=f"Test {role.value.title()}",
            map_id=f"test_user_id_{role.value}",
            session_id="",
        )
        for role in USER_ROLES
    }


@pytest.fixture
def user_details(test_config):
    repository_id = "test_repo_ac_jp"
    patterns = test_config.GROUPS.id_patterns
    groups = [
        f"{patterns.user_defined.format(repository_id=repository_id, user_defined_id='test')}",
    ]
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    return {
        role: UserDetail(
            id=f"test_user_id_{role.value}",
            user_name=f"Test {role.value.title()}",
            eppns=[f"test-{role.value}@idp.example.com"],
            emails=[f"test-{role.value}@example.com"],
            preferred_language="en",
            is_system_admin=role == USER_ROLES.SYSTEM_ADMIN,
            groups=[GroupSummary(id=gid) for gid in groups],
            repository_roles=[RepositoryRole(id=repository_id, user_role=role)],
            created=created,
            last_modified=last_modified,
        )
        for role in USER_ROLES
    }


@pytest.fixture
def map_users(test_config):
    patterns = test_config.GROUPS.id_patterns
    repository_id = "test_repo_ac_jp"
    groups = [
        patterns.user_defined.format(repository_id=repository_id, user_defined_id="test"),
        "group1",
    ]
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    return {
        role: MapUser(
            id=f"test_user_id_{role.value}",
            user_name=f"Test {role.value.title()}",
            edu_person_principal_names=[EPPN(value=f"test-{role.value}@idp.example.com")],
            emails=[Email(value=f"test-{role.value}@example.com")],
            meta=UserMeta(created=created, last_modified=last_modified),
            groups=[UserGroup(value=gid) for gid in [*groups, patterns[role].format(repository_id=repository_id)]],
        )
        for role in USER_ROLES
    }


@pytest.fixture
def user_summaries():
    return {
        role: UserSummary(
            id=f"test_user_id_{role.value}",
            user_name=f"Test {role.value.title()}",
            emails=[f"test-{role.value}@example.com"],
            role=role,
            eppns=[f"test-{role.value}@idp.example.com"],
        )
        for role in USER_ROLES
    }


@pytest.fixture
def group_details(test_config):
    gpattern = test_config.GROUPS.id_patterns.user_defined
    repository_id = "test_repo_ac_jp"
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    return [
        GroupDetail(
            id=gpattern.format(repository_id=repository_id, user_defined_id=f"test{i}"),
            display_name=f"Test Group {i}",
            description="This is sample group for test.",
            public=True,
            repository=GroupRepository(id=repository_id, service_name="Test Repository"),
            member_list_visibility="Private",
            type="group",
            created=created,
            last_modified=last_modified,
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def rolegroups(test_config):
    gpatterns = test_config.GROUPS.id_patterns
    repository_id = "test_repo_ac_jp"
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    return {
        role: GroupDetail(
            id=gpatterns[role].format(repository_id=repository_id),
            display_name=f"Test Role Group {role}",
            description="This is sample role group for test.",
            public=True,
            repository=GroupRepository(id=repository_id, service_name="Test Repository")
            if role != USER_ROLES.SYSTEM_ADMIN
            else None,
            member_list_visibility="Private",
            type="role",
            created=created,
            last_modified=last_modified,
        )
        for role in USER_ROLES
    }


@pytest.fixture
def map_groups(test_config, map_users):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    gpattern = test_config.GROUPS.id_patterns.user_defined
    repository_id = "test_repo_ac_jp"
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    return [
        MapGroup(
            id=gpattern.format(repository_id=repository_id, user_defined_id=f"test{i}"),
            display_name=f"Test Group {i}",
            description="This is sample group for test.",
            meta=GroupMeta(created=created, last_modified=last_modified),
            administrators=[GroupAdministrator(value=map_users[USER_ROLES.SYSTEM_ADMIN].id)],
            services=[GroupService(value=rpattern.format(repository_id=repository_id))],
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def group_summaries(test_config):
    gpattern = test_config.GROUPS.id_patterns.user_defined
    repository_id = "test_repo_ac_jp"
    return [
        GroupSummary(
            id=gpattern.format(repository_id=repository_id, user_defined_id=f"test{i}"),
            display_name=f"Test Group {i}",
            repository_name="Test Repository",
            users_count=i * 4,
        )
        for i in range(1, 6)
    ]


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
def repository_details(test_config):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    return [
        RepositoryDetail(
            id=f"test_{i}_repo_ac_jp",
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo_ac_jp"),
            service_id=rpattern.format(repository_id=f"test_{i}_repo_ac_jp"),
            active=True,
            entity_ids=[f"https://test-{i}.repo_ac_jp/shibboleth-sp"],
            created=datetime.fromisoformat(f"2026-03-{i:02d}T03:00:00Z"),
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def repository_summaries():
    return [
        RepositorySummary(
            id=f"test_{i}_repo_ac_jp",
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo_ac_jp"),
            service_id=f"jc_test_{i}_repo_ac_jp",
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def group_caches():
    return [
        RepositoryCache(
            id=f"test_{i}_repo_ac_jp",
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo_ac_jp"),
            updated=datetime.fromisoformat(f"2026-03-{i:02d}T03:00:00Z"),
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def cached_data():
    def _data(
        repositories: list[RepositorySummary],
        now: datetime | None = None,
        *,
        every_other: bool = False,
    ) -> list[RepositoryCache]:
        return [
            RepositoryCache(
                id=repositories[i].id,
                service_name=t.cast(str, repositories[i].service_name),
                service_url=repositories[i].service_url,
                updated=now or datetime.now(UTC) if not every_other or i % 2 == 0 else None,
            )
            for i in range(len(repositories))
        ]

    return _data
