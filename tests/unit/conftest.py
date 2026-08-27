import typing as t

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from flask import Flask
from pydantic import HttpUrl
from redis import Redis
from redis.sentinel import Sentinel

import server.config
import server.datastore
import server.db
import server.ext
import server.signals

from server import const
from server.config import RuntimeConfig
from server.const import USER_ROLES
from server.entities.auth import ClientCredentials, OAuthToken
from server.entities.cache import RepositoryCache
from server.entities.group_detail import GroupDetail, Repository as GroupRepository
from server.entities.login_user import LoginUser
from server.entities.map_error import MapError
from server.entities.map_group import (
    Administrator as GroupAdministrator,
    MapGroup,
    Meta as GroupMeta,
    Service as GroupService,
)
from server.entities.map_service import Administrator as ServiceAdmin, MapService, Meta as ServiceMeta, ServiceEntityID
from server.entities.map_user import EPPN, Email, Group as UserGroup, MapUser, Meta as UserMeta
from server.entities.repository_detail import RepositoryDetail
from server.entities.summaries import GroupSummary, RepositorySummary, UserSummary
from server.entities.user_detail import RepositoryRole, UserDetail
from server.ext import JAIROCloudGroupsManager
from server.services.utils.affiliations import Affiliations, _Group, _RoleGroup


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture, MockType

pytest.register_assert_rewrite("tests.helpers")

from tests.helpers import load_json_data  # ruff:ignore[module-import-not-at-top-of-file]


@pytest.fixture(autouse=True, scope="session")
def set_test_constants():
    const.MAP_USER_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:User"
    const.MAP_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Group"
    const.MAP_SERVICE_SCHEMA = "urn:ietf:params:scim:schemas:mace:example.jp:core:2.0:Service"


@pytest.fixture
def instance_path(tmp_path: Path) -> Path:
    return tmp_path / "instance"


@pytest.fixture
def test_config(tmp_path: Path, mocker: MockerFixture) -> RuntimeConfig:
    """Row RuntimeConfig.

    If the test needs application context, use the `config` fixture instead of this one.
    """
    mocker.patch("pydantic.main._check_frozen")  # Allow config to be mutable for testing purposes.

    config_path = Path(__file__).parent.parent / "test.config.toml"
    config = RuntimeConfig(_toml_file=config_path)  # pyright: ignore[reportCallIssue]
    config.STORAGE.local.temporary = str(tmp_path / "tmp" / "jcgroups")
    config.STORAGE.local.storage = str(tmp_path / "storage" / "jcgroups")

    return config


@pytest.fixture
def config(test_config, mocker: MockerFixture) -> RuntimeConfig:
    """Wrapped RuntimeConfig.

    This includes mocking to bypass access to the application context.
    """
    mocker.patch.object(server.config, "__get_config", return_value=test_config)
    return test_config


def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "sqlalchemy_enabled: Mark a test to enable SQLAlchemy.")
    config.addinivalue_line("markers", "redis_enabled: Mark a test to enable Redis model.")


@pytest.fixture(autouse=True)
def sqlalchemy_disable(request: pytest.FixtureRequest, mocker: MockerFixture):
    if request.node.get_closest_marker("sqlalchemy_enabled"):
        return

    error = """SQLAlchemy is disabled in unit tests.
    If you want to enable it, add `@pytest.mark.sqlalchemy_enabled` to the test."""
    mocker.patch("server.db.base.SQLAlchemy", side_effect=RuntimeError(error))
    mocker.patch("server.ext.database_exists")


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
    mocker.patch.object(server.db.utils, "__get_db", return_value=mock_db)
    return mock_db


@pytest.fixture
def datastore(mocker: MockerFixture):
    app_cache = mocker.MagicMock(spec=Redis)
    account_store = mocker.MagicMock(spec=Redis)
    group_cache = mocker.MagicMock(spec=Redis)

    def _get_store(name):
        return {
            "app_cache": app_cache,
            "account_store": account_store,
            "group_cache": group_cache,
        }[name]

    mocker.patch.object(server.datastore, "__get_store", side_effect=_get_store)

    return app_cache, account_store, group_cache


@pytest.fixture
def base_app(instance_path, sqlalchemy_disable, redis_disable):
    app = Flask(__name__)
    app.instance_path = instance_path
    app.config["TESTING"] = True

    return app


@pytest.fixture
def blueprint(mocker: MockerFixture):
    original = server.ext.create_api_blueprint
    mock_create = mocker.patch.object(server.ext, "create_api_blueprint")

    return original, mock_create


@pytest.fixture
def use_blueprint(mocker: MockerFixture, blueprint):
    original, _ = blueprint
    server.ext.create_api_blueprint = original


@pytest.fixture
def app(base_app: Flask, test_config, blueprint, mocker: MockerFixture):
    mocker.patch.object(server.ext, "load_models")
    base_app.config["RUNTIME_ROLE"] = "TEST"
    base_app.config["RUNTIME_CONFIG"] = test_config
    JAIROCloudGroupsManager(base_app)
    with base_app.app_context():
        yield base_app


@pytest.fixture
def auth_token():
    return OAuthToken(
        access_token=uuid4().hex[:8],
        token_type="bearer",
        expires_in=3600,
        refresh_token=uuid4().hex[:8],
        scope="scope",
    )


@pytest.fixture
def client_creds():
    return ClientCredentials(
        client_id=uuid4().hex[:8],
        client_secret=uuid4().hex[:16],
    )


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
def user_affils(test_config: RuntimeConfig, role_affils):
    patterns = test_config.GROUPS.id_patterns
    gid = f"{patterns.user_defined.format(repository_id='test_repo_ac_jp', user_defined_id='test')}"
    groups = [_Group(group_id=gid, repository_id="test_repo_ac_jp", user_defined_id="test")]
    return {role: Affiliations([role_affils[role]], groups) for role in USER_ROLES}


@pytest.fixture
def login_users(test_config: RuntimeConfig):
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
def user_details(test_config: RuntimeConfig):
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
def map_users(test_config: RuntimeConfig):
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
            preferred_language="en",
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
def group_details(test_config: RuntimeConfig):
    gpattern = test_config.GROUPS.id_patterns.user_defined
    repository_id = "test_1_repo_ac_jp"
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
def rolegroup_details(test_config: RuntimeConfig):
    gpatterns = test_config.GROUPS.id_patterns
    repository_id = "test_1_repo_ac_jp"
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    repository = GroupRepository(id=repository_id, service_name="Test Repository")
    return {
        role: GroupDetail(
            id=gpatterns[role].format(repository_id=repository_id),
            display_name=f"Test Role Group {role}",
            description="This is sample role group for test.",
            public=True,
            repository=repository if role != USER_ROLES.SYSTEM_ADMIN else None,
            member_list_visibility="Private",
            type="role",
            created=created,
            last_modified=last_modified,
        )
        for role in USER_ROLES
    }


@pytest.fixture
def map_groups(test_config: RuntimeConfig, map_users):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    gpattern = test_config.GROUPS.id_patterns.user_defined
    repository_id = "test_1_repo_ac_jp"
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    admin_uri = f"{test_config.MAP_CORE.base_url}/users/{map_users[USER_ROLES.SYSTEM_ADMIN].id}"
    service_uri = f"{test_config.MAP_CORE.base_url}/services/{rpattern.format(repository_id=repository_id)}"
    return [
        MapGroup(
            id=gpattern.format(repository_id=repository_id, user_defined_id=f"test{i}"),
            display_name=f"Test Group {i}",
            description="This is sample group for test.",
            meta=GroupMeta(created=created, last_modified=last_modified),
            administrators=[GroupAdministrator(value=admin_uri)],
            services=[GroupService(value=service_uri)],
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def map_rolegroups(test_config: RuntimeConfig, map_users):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    gpatterns = test_config.GROUPS.id_patterns
    repository_id = "test_repo_ac_jp"
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    admin_uri = f"{test_config.MAP_CORE.base_url}/users/{map_users[USER_ROLES.SYSTEM_ADMIN].id}"
    service_uri = f"{test_config.MAP_CORE.base_url}/services/{rpattern.format(repository_id=repository_id)}"
    return {
        role: MapGroup(
            id=gpatterns[role].format(repository_id=repository_id),
            display_name=f"Test Role Group {role}",
            description="This is sample role group for test.",
            meta=GroupMeta(created=created, last_modified=last_modified),
            administrators=[GroupAdministrator(value=admin_uri)],
            services=[GroupService(value=service_uri)] if role != USER_ROLES.SYSTEM_ADMIN else [],
        )
        for role in USER_ROLES
    }


@pytest.fixture
def group_summaries(test_config: RuntimeConfig):
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
def repository_details(test_config: RuntimeConfig):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    return [
        RepositoryDetail(
            id=f"test_{i}_repo_ac_jp",
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo.ac.jp"),
            service_id=rpattern.format(repository_id=f"test_{i}_repo_ac_jp"),
            active=True,
            entity_ids=[f"https://test-{i}.repo.ac.jp/shibboleth-sp"],
            created=datetime.fromisoformat(f"2026-03-{i:02d}T03:00:00Z"),
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def map_services(test_config: RuntimeConfig, map_users):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    created = datetime.fromisoformat("2026-03-01T03:00:00Z")
    last_modified = datetime.fromisoformat("2026-03-02T03:00:00Z")
    admin_id = f"{test_config.MAP_CORE.base_url}/users/{map_users[USER_ROLES.SYSTEM_ADMIN].id}"
    return [
        MapService(
            id=rpattern.format(repository_id=f"test_{i}_repo_ac_jp"),
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo.ac.jp"),
            suspended=False,
            meta=ServiceMeta(created=created, last_modified=last_modified),
            entity_ids=[ServiceEntityID(value=f"https://test-{i}.repo.ac.jp/shibboleth-sp")],
            administrators=[ServiceAdmin(value=admin_id)],
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def repository_summaries(test_config: RuntimeConfig):
    rpattern = test_config.REPOSITORIES.id_patterns.sp_connector
    return [
        RepositorySummary(
            id=f"test_{i}_repo_ac_jp",
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo.ac.jp"),
            service_id=rpattern.format(repository_id=f"test_{i}_repo_ac_jp"),
            entity_ids=[f"https://test-{i}.repo.ac.jp/shibboleth-sp"],
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def map_error():
    json_data = load_json_data("data/map_error.json")
    map_error = MapError.model_validate(json_data)
    raw_json = map_error.model_dump_json(ensure_ascii=False, by_alias=True)

    return json_data, map_error, raw_json


@pytest.fixture
def signal_send(mocker: MockerFixture):
    mockes: MockSignal[MockType] = {
        "before_request": mocker.patch.object(server.signals.before_request, "send"),
        "repository_created": mocker.patch.object(server.signals.repository_created, "send"),
        "repository_updated": mocker.patch.object(server.signals.repository_updated, "send"),
        "repository_deleted": mocker.patch.object(server.signals.repository_deleted, "send"),
        "group_created": mocker.patch.object(server.signals.group_created, "send"),
        "group_updated": mocker.patch.object(server.signals.group_updated, "send"),
        "group_deleted": mocker.patch.object(server.signals.group_deleted, "send"),
        "user_created": mocker.patch.object(server.signals.user_created, "send"),
        "user_updated": mocker.patch.object(server.signals.user_updated, "send"),
        "user_deleted": mocker.patch.object(server.signals.user_deleted, "send"),
        "user_promoted": mocker.patch.object(server.signals.user_promoted, "send"),
        "user_demoted": mocker.patch.object(server.signals.user_demoted, "send"),
    }
    return mockes


@pytest.fixture
def repository_caches():
    return [
        RepositoryCache(
            id=f"test_{i}_repo_ac_jp",
            service_name=f"Test Repository {i}",
            service_url=HttpUrl(f"https://test-{i}.repo.ac.jp"),
            updated=datetime.fromisoformat(f"2026-03-{i:02d}T03:00:00Z"),
        )
        for i in range(1, 11)
    ]


class MockSignal[T](t.TypedDict):
    before_request: T

    repository_created: T
    repository_updated: T
    repository_deleted: T

    group_created: T
    group_updated: T
    group_deleted: T

    user_created: T
    user_updated: T
    user_deleted: T
    user_promoted: T
    user_demoted: T
