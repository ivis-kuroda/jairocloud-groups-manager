import typing as t

from datetime import UTC, datetime

import pytest

from pydantic import HttpUrl

from server.const import USER_ROLES
from server.entities.group_detail import (
    GroupDetail,
    Repository as GroupRepository,
)
from server.entities.map_group import (
    Administrator as GroupAdministrator,
    MapGroup,
    MemberUser,
    Meta as GroupMeta,
    Service as GroupService,
)
from server.entities.map_service import (
    Administrator as ServiceAdministrator,
    Group as MapServiceGroup,
    MapService,
    ServiceEntityID,
)
from server.entities.map_user import EPPN, Email, Group as UserGroup, MapUser, Meta as UserMeta
from server.entities.repository_detail import RepositoryDetail
from server.entities.search_request import SearchResult
from server.entities.summaries import GroupSummary, RepositorySummary
from server.entities.user_detail import RepositoryRole, UserDetail
from server.exc import InvalidFormError, SystemAdminNotFound
from server.messages import E
from server.services.utils import transformers
from server.services.utils.affiliations import Affiliations, _Group, _RoleGroup


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def assert_unordered_model_list_equal(list1, list2):
    def to_tuple(x):
        def deep_tuple(obj):
            if isinstance(obj, dict):
                return tuple(sorted((k, deep_tuple(v)) for k, v in obj.items()))
            if isinstance(obj, list):
                return tuple(deep_tuple(i) for i in obj)
            return obj

        return deep_tuple(x.dict())

    assert set(map(to_tuple, list1)) == set(map(to_tuple, list2))


def test_prepare_service(app, mocker: MockerFixture):
    mock_return_value = MapService(
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Service"],
        id="jc_repo1_test",
        service_name="service1",
        service_url=HttpUrl("https://service1.example.com/"),
        suspended=None,
        meta=None,
        entity_ids=[ServiceEntityID(value="https://<FQDN>/shibboleth-sp")],
        administrators=None,
        groups=None,
    )
    expected = MapService(
        id="jc_repo1_test",
        service_name="service1",
        service_url=HttpUrl("https://service1.example.com/"),
        suspended=None,
        meta=None,
        entity_ids=[ServiceEntityID(value="https://<FQDN>/shibboleth-sp")],
        administrators=[
            ServiceAdministrator(ref=None, display=None, value="admin1"),
            ServiceAdministrator(ref=None, display=None, value="admin2"),
        ],
        groups=[
            MapServiceGroup(ref=None, display=None, value="jc_roles_sysadm_test"),
            MapServiceGroup(ref=None, display=None, value="jc_repo1_ro_radm_test"),
            MapServiceGroup(ref=None, display=None, value="jc_repo1_ro_cadm_test"),
            MapServiceGroup(ref=None, display=None, value="jc_repo1_ro_cont_test"),
            MapServiceGroup(ref=None, display=None, value="jc_repo1_ro_user_test"),
        ],
    )
    mocker.patch(
        "server.services.utils.transformers.validate_repository_to_map_service", return_value=mock_return_value
    )
    expected_repository_id = "repo1"
    mocker.patch("server.services.utils.transformers.resolve_repository_id", return_value=expected_repository_id)
    administrators = {"admin1", "admin2"}
    map_service, repository_id = transformers.prepare_service(
        RepositoryDetail(id=expected_repository_id), administrators
    )
    assert repository_id == expected_repository_id
    assert map_service.id == expected.id
    assert map_service.service_name == expected.service_name
    assert map_service.service_url == expected.service_url
    assert map_service.suspended == expected.suspended
    assert map_service.meta == expected.meta
    assert_unordered_model_list_equal(map_service.entity_ids, expected.entity_ids)
    assert_unordered_model_list_equal(map_service.administrators, expected.administrators)
    assert_unordered_model_list_equal(map_service.groups, expected.groups)


def test_prepare_service_no_administrators(app, mocker: MockerFixture):
    mock_return_value = MapService(
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Service"],
        id="jc_repo1_test",
        service_name="service1",
        service_url=HttpUrl("https://service1.example.com/"),
        suspended=None,
        meta=None,
        entity_ids=[ServiceEntityID(value="https://<FQDN>/shibboleth-sp")],
        administrators=None,
        groups=None,
    )
    mocker.patch(
        "server.services.utils.transformers.validate_repository_to_map_service", return_value=mock_return_value
    )
    administrators = set()
    with pytest.raises(SystemAdminNotFound) as exc:
        transformers.prepare_service(RepositoryDetail(), administrators)
    assert str(exc.value) == str(E.REPOSITORY_REQUIRES_SYSTEM_ADMIN)


def test_prepare_role_groups(app, test_config, mocker: MockerFixture):
    repository_id = "repo1"
    service_id = "jc_repo1_test"
    service_name = "service1"
    administrators = {"admin1", "admin2"}
    mocker.patch("server.services.utils.transformers.resolve_service_id", return_value=service_id)
    expected_list = [
        MapGroup(
            id="jc_repo1_ro_radm_test",
            display_name=f"{service_name}管理者_テスト",
            public=False,
            member_list_visibility="Private",
            administrators=[GroupAdministrator(value="admin1"), GroupAdministrator(value="admin2")],
            services=[GroupService(value=test_config.SP.connector_id), GroupService(value=service_id)],
        ),
        MapGroup(
            id="jc_repo1_ro_cadm_test",
            display_name=f"{service_name}コミュニティ管理者_テスト",
            public=False,
            member_list_visibility="Private",
            administrators=[GroupAdministrator(value="admin1"), GroupAdministrator(value="admin2")],
            services=[GroupService(value=test_config.SP.connector_id), GroupService(value=service_id)],
        ),
        MapGroup(
            id="jc_repo1_ro_cont_test",
            display_name=f"{service_name}投稿ユーザー_テスト",
            public=False,
            member_list_visibility="Private",
            administrators=[GroupAdministrator(value="admin1"), GroupAdministrator(value="admin2")],
            services=[GroupService(value=test_config.SP.connector_id), GroupService(value=service_id)],
        ),
        MapGroup(
            id="jc_repo1_ro_user_test",
            display_name=f"{service_name}一般ユーザー_テスト",
            public=False,
            member_list_visibility="Private",
            administrators=[GroupAdministrator(value="admin1"), GroupAdministrator(value="admin2")],
            services=[GroupService(value=test_config.SP.connector_id), GroupService(value=service_id)],
        ),
    ]
    map_group_list = transformers.prepare_role_groups(repository_id, service_name, administrators)
    assert len(map_group_list) == len(expected_list)
    for map_group, expected in zip(map_group_list, expected_list, strict=False):
        assert map_group.id == expected.id
        assert map_group.external_id == expected.external_id
        assert map_group.display_name == expected.display_name
        assert map_group.public == expected.public
        assert map_group.description == expected.description
        assert map_group.suspended == expected.suspended
        assert map_group.member_list_visibility == expected.member_list_visibility
        assert map_group.meta == expected.meta
        assert_unordered_model_list_equal(map_group.administrators, expected.administrators)
        assert_unordered_model_list_equal(map_group.services, expected.services)


def test_prepare_role_groups_no_administrators(app, mocker: MockerFixture):
    repository_id = "repo1"
    service_name = "service1"
    administrators = set()
    mocker.patch("server.services.utils.transformers.resolve_service_id", return_value="jc_repo1_test")
    with pytest.raises(SystemAdminNotFound) as exc:
        transformers.prepare_role_groups(repository_id, service_name, administrators)
    assert str(exc.value) == str(E.REPOSITORY_REQUIRES_SYSTEM_ADMIN)


def test_make_repository_detail(app, mocker: MockerFixture):
    repository_id = "repo1"
    service = MapService(
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Service"],
        id="jc_repo1_test",
        service_name="service1",
        service_url=HttpUrl("https://service1.example.com/"),
        suspended=True,
        meta=None,
        entity_ids=None,
        administrators=None,
        groups=[MapServiceGroup(value="jc_repo1_gr_test_group")],
    )
    expected = RepositoryDetail(
        id=repository_id,
        service_id=service.id,
        service_name=service.service_name,
        service_url=service.service_url,
        active=not service.suspended,
        entity_ids=None,
        groups_count=1,
        users_count=2,
        created=None,
    )
    affiliation = _Group(repository_id=repository_id, group_id="jc_repo1_gr_test_group", user_defined_id="test_group")
    mocker.patch("server.services.utils.transformers.resolve_repository_id", return_value=repository_id)
    mocker.patch("server.services.utils.transformers.detect_affiliation", return_value=affiliation)
    mocker.patch("server.services.users.count", return_value=2)
    service_detail = transformers.make_repository_detail(service)
    assert service_detail.id == expected.id
    assert service_detail.service_id == expected.service_id
    assert service_detail.service_name == expected.service_name
    assert service_detail.service_url == expected.service_url
    assert service_detail.active == expected.active
    assert service_detail.entity_ids == expected.entity_ids


def test_make_repository_detail_more(app, mocker: MockerFixture):
    repository_id = "repo1"
    entity_id = "https://<FQDN>/shibboleth-sp"
    service = MapService(
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Service"],
        id="jc_repo1_test",
        service_name="service1",
        service_url=HttpUrl("https://service1.example.com/"),
        suspended=True,
        meta=None,
        entity_ids=[ServiceEntityID(value=entity_id)],
        administrators=[ServiceAdministrator(value="admin1"), ServiceAdministrator(value="admin2")],
        groups=[MapServiceGroup(value="jc_repo1_gr_test_group")],
    )
    expected = RepositoryDetail(
        id=repository_id,
        service_id=service.id,
        service_name=service.service_name,
        service_url=service.service_url,
        active=not service.suspended,
        entity_ids=[entity_id],
        groups_count=1,
        users_count=2,
        created=None,
    )
    expected._groups = ["jc_repo1_gr_test_group"]  # noqa: SLF001
    expected._rolegroups = []  # noqa: SLF001
    expected._admins = ["admin1", "admin2"]  # noqa: SLF001
    affiliation = _Group(repository_id=repository_id, group_id="jc_repo1_gr_test_group", user_defined_id="test_group")
    mocker.patch("server.services.utils.transformers.resolve_repository_id", return_value=repository_id)
    mocker.patch("server.services.utils.transformers.detect_affiliation", return_value=affiliation)
    mocker.patch("server.services.users.count", return_value=2)
    service_detail = transformers.make_repository_detail(service, more_detail=True)
    assert service_detail == expected
    assert service_detail.id == expected.id
    assert service_detail.service_id == expected.service_id
    assert service_detail.service_name == expected.service_name
    assert service_detail.service_url == expected.service_url
    assert service_detail.active == expected.active
    assert service_detail.entity_ids == expected.entity_ids
    assert service_detail.groups_count == expected.groups_count
    assert service_detail.users_count == expected.users_count
    assert service_detail.created == expected.created


@pytest.mark.parametrize(
    ("repository", "expected", "expected_exception"),
    [
        (
            RepositoryDetail(
                id="test",
                service_name="test",
                service_url=HttpUrl("https://FQDN/example.com/"),
                entity_ids=["https://<FQDN>/shibboleth-sp"],
            ),
            MapService(id="test"),
            None,
        ),
        (
            RepositoryDetail(
                id="test",
                service_name=None,
                service_url=HttpUrl("https://FQDN/example.com/"),
                entity_ids=["https://<FQDN>/shibboleth-sp"],
            ),
            str(E.REPOSITORY_REQUIRES_SERVICE_NAME),
            InvalidFormError,
        ),
        (
            RepositoryDetail(
                id="test", service_name="test", entity_ids=["https://<FQDN>/shibboleth-sp"], service_url=None
            ),
            str(E.REPOSITORY_REQUIRES_SERVICE_URL),
            InvalidFormError,
        ),
        (
            RepositoryDetail(
                id=None,
                service_name="test",
                service_url=HttpUrl("https://FQDN/example.com/"),
                entity_ids=["https://<FQDN>/shibboleth-sp"],
            ),
            str(E.REPOSITORY_INVALID_SERVICE_URL),
            InvalidFormError,
        ),
        (
            RepositoryDetail(
                id="test",
                service_name="test",
                service_url=HttpUrl("https://example.com/very/very/very/very/very/very/very/long/url"),
                entity_ids=["https://<FQDN>/shibboleth-sp"],
            ),
            str(E.REPOSITORY_TOO_LONG_URL % {"max": 50}),
            InvalidFormError,
        ),
        (
            RepositoryDetail(
                id="test", service_name="test", service_url=HttpUrl("https://FQDN/example.com/"), entity_ids=[]
            ),
            str(E.REPOSITORY_REQUIRES_ENTITY_ID),
            InvalidFormError,
        ),
    ],
)
def test_validate_repository_to_map_service(app, mocker: MockerFixture, repository, expected, expected_exception):
    repository_id = repository.id
    service_id = "jc_repo1_test"
    mocker.patch("server.services.utils.transformers.resolve_repository_id", return_value=repository_id)
    mocker.patch("server.services.utils.transformers.resolve_service_id", return_value=service_id)
    expected_return = mocker.patch("server.services.utils.transformers.make_map_service", return_value=expected)
    if expected_exception:
        with pytest.raises(expected_exception) as exc:
            transformers.validate_repository_to_map_service(repository)
        assert str(exc.value) == expected
    else:
        transformers.validate_repository_to_map_service(repository)
        repository.service_id = service_id
        expected_return.assert_called_once_with(repository)


@pytest.mark.parametrize(
    ("repository", "expected"),
    [
        (
            RepositoryDetail(service_id="jc_repo1_test", active=True, entity_ids=["https://<FQDN>/shibboleth-sp"]),
            MapService(
                id="jc_repo1_test", suspended=False, entity_ids=[ServiceEntityID(value="https://<FQDN>/shibboleth-sp")]
            ),
        ),
        (
            RepositoryDetail(service_id="jc_repo1_test", active=None, entity_ids=None),
            MapService(id="jc_repo1_test", suspended=None, entity_ids=None),
        ),
    ],
)
def test_make_map_service(app, mocker: MockerFixture, repository, expected):
    assert transformers.make_map_service(repository) == expected


def test_prepare_group(app, test_config, mocker: MockerFixture):
    detail = GroupDetail(type="group")
    administrators = {"admin1", "admin2"}
    repository_id = "repo1"
    service_id = "jc_repo1_test"
    expected = MapGroup()
    mocker.patch(
        "server.services.utils.transformers.validate_group_to_map_group", return_value=(expected, repository_id)
    )
    expected.administrators = [GroupAdministrator(value=user_id) for user_id in administrators]
    expected.services = [GroupService(value=test_config.SP.connector_id), GroupService(value=service_id)]
    mocker.patch("server.services.utils.transformers.resolve_service_id", return_value=service_id)
    map_group = transformers.prepare_group(detail, administrators)
    assert_unordered_model_list_equal(map_group.administrators, expected.administrators)
    assert_unordered_model_list_equal(map_group.services, expected.services)


def test_prepare_group_no_administrators(app, mocker: MockerFixture):
    detail = GroupDetail(type="group")
    administrators = set()
    expected = E.GROUP_REQUIRES_SYSTEM_ADMIN
    mocker.patch("server.services.utils.transformers.validate_group_to_map_group", return_value=(MapGroup(), "repo1"))
    with pytest.raises(SystemAdminNotFound) as exc:
        transformers.prepare_group(detail, administrators)
    assert str(exc.value) == str(expected)


def test_make_group_detail(app, mocker: MockerFixture):
    group = MapGroup(
        id="jc_repo1_gr_test_group",
        display_name="Test Group",
        public=True,
        meta=GroupMeta(
            created=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC), last_modified=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
        ),
        members=[MemberUser(value="user1"), MemberUser(value="user2")],
        administrators=[GroupAdministrator(value="admin1"), GroupAdministrator(value="admin2")],
        services=[GroupService(value="jc_repo1_test")],
    )
    expected = GroupDetail(
        id="jc_repo1_gr_test_group",
        display_name="Test Group",
        public=True,
        users_count=2,
        type=None,
        created=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        last_modified=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
    )
    expected._users = ["user1", "user2"]  # noqa: SLF001
    expected._admins = ["admin1", "admin2"]  # noqa: SLF001
    expected._services = ["jc_repo1_test"]  # noqa: SLF001
    group_detail = transformers.make_group_detail(group)
    assert group_detail == expected


@pytest.mark.parametrize(
    ("group", "affiliation", "repository_detail", "expected"),
    [
        (
            MapGroup(id="jc_repo1_gr_test_group", display_name="Test Group", public=True),
            None,
            None,
            GroupDetail(
                id="jc_repo1_gr_test_group",
                user_defined_id=None,
                display_name="Test Group",
                public=True,
                type=None,
            ),
        ),
        (
            MapGroup(id="jc_repo1_gr_test_group", display_name="Test Group", public=True),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group"),
            None,
            GroupDetail(
                id="jc_repo1_gr_test_group",
                display_name="Test Group",
                public=True,
                users_count=None,
                type="group",
                user_defined_id="test_group",
                repository=None,
            ),
        ),
        (
            MapGroup(id="jc_repo1_gr_test_group", display_name="Test Group", public=True),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group"),
            RepositoryDetail(service_name="service1"),
            GroupDetail(
                id="jc_repo1_gr_test_group",
                display_name="Test Group",
                public=True,
                users_count=None,
                type="group",
                user_defined_id="test_group",
                repository=GroupRepository(id="repo1", service_name="service1"),
            ),
        ),
    ],
)
def test_make_group_detail_more(app, mocker: MockerFixture, group, affiliation, repository_detail, expected):
    mocker.patch(
        "server.services.utils.transformers.detect_affiliation",
        return_value=affiliation,
    )
    mocker.patch("server.services.repositories.get_by_id", return_value=repository_detail)
    group_detail = transformers.make_group_detail(group, more_detail=True)
    assert group_detail == expected


@pytest.mark.parametrize(
    ("group", "mode", "expected", "expectedarg"),
    [
        (
            GroupDetail(display_name="Test Group", id="jc_repo1_gr_test_group_test", type="group"),
            "update",
            MapGroup(),
            GroupDetail(
                display_name="Test Group",
                id="jc_repo1_gr_test_group_test",
                repository=GroupRepository(id="repo1"),
                type="group",
            ),
        ),
        (
            GroupDetail(
                display_name="Test Group",
                repository=GroupRepository(id="repo1"),
                user_defined_id="test_group",
                public=None,
                member_list_visibility=None,
                type="group",
            ),
            "create",
            (MapGroup(), "repo1"),
            GroupDetail(
                id="jc_repo1_gr_test_group_test",
                display_name="Test Group",
                repository=GroupRepository(id="repo1"),
                user_defined_id="test_group",
                public=False,
                member_list_visibility="Private",
                type="group",
            ),
        ),
        (
            GroupDetail(
                display_name="Test Group",
                repository=GroupRepository(id="repo1"),
                user_defined_id="test_group",
                public=True,
                member_list_visibility="Hidden",
                type="group",
            ),
            "create",
            (MapGroup(), "repo1"),
            GroupDetail(
                id="jc_repo1_gr_test_group_test",
                display_name="Test Group",
                repository=GroupRepository(id="repo1"),
                user_defined_id="test_group",
                public=True,
                member_list_visibility="Hidden",
                type="group",
            ),
        ),
    ],
)
def test_validate_group_to_map_group(app, mocker: MockerFixture, group, mode, expected, expectedarg):
    mocker.patch("server.services.repositories.get_by_id", return_value=RepositoryDetail(id="repo1"))
    mocker.patch("server.services.utils.transformers.get_permitted_repository_ids", return_value={"repo1"})
    mock_make_map_group = mocker.patch("server.services.utils.transformers.make_map_group", return_value=MapGroup())
    assert transformers.validate_group_to_map_group(group=group, mode=mode) == expected
    mock_make_map_group.assert_called_once_with(expectedarg)


def test_validate_group_to_map_group_non_repository_id(app, mocker: MockerFixture):
    group = GroupDetail(
        id="jc_repo1_gr_test_group_test",
        display_name="Test Group",
        repository=GroupRepository(id="repo1"),
        user_defined_id="test_group",
        public=True,
        member_list_visibility="Hidden",
        type="group",
    )
    expectedarg = GroupDetail(
        id="jc_repo1_gr_test_group_test",
        display_name="Test Group",
        repository=GroupRepository(id="repo1"),
        user_defined_id="test_group",
        public=True,
        member_list_visibility="Hidden",
        type="group",
    )
    mocker.patch("server.services.repositories.get_by_id", return_value=RepositoryDetail(id="repo1"))
    mocker.patch("server.services.utils.transformers.get_permitted_repository_ids", return_value={"repo1"})
    mock_make_map_group = mocker.patch("server.services.utils.transformers.make_map_group", return_value=MapGroup())
    mocker.patch(
        "server.services.utils.transformers.detect_affiliation",
        return_value=_Group(repository_id="", group_id="jc__gr_test_1", user_defined_id="test_1"),
    )
    assert transformers.validate_group_to_map_group(group=group, mode="update") == MapGroup()
    mock_make_map_group.assert_called_once_with(expectedarg)


@pytest.mark.parametrize(
    ("group", "mode", "repository_exist", "expected"),
    [
        (GroupDetail(display_name=None, type="group"), "create", False, E.GROUP_REQUIRES_DISPLAY_NAME),
        (
            GroupDetail(display_name="Test Group", id=None, type="group"),
            "update",
            False,
            E.GROUP_REQUIRES_ID,
        ),
        (
            GroupDetail(display_name="Test Group", repository=None, type="group"),
            "create",
            False,
            E.GROUP_REQUIRES_REPOSITORY,
        ),
        (
            GroupDetail(display_name="Test Group", repository=GroupRepository(id="repo1"), type="group"),
            "create",
            False,
            E.GROUP_REQUIRES_EXISTING_REPOSITORY % {"rid": "repo1"},
        ),
        (
            GroupDetail(
                display_name="Test Group", repository=GroupRepository(id="repo1"), user_defined_id=None, type="group"
            ),
            "create",
            True,
            E.GROUP_REQUIRES_USER_DEFINED_ID,
        ),
        (
            GroupDetail(
                display_name="Test Group",
                repository=GroupRepository(id="repo1"),
                user_defined_id="very_very_very_very_very_very_long_group_id",
                type="group",
            ),
            "create",
            True,
            E.GROUP_TOO_LONG_ID % {"rid": "repo1", "max": 50 - len("jc_") - len("_gr_") - len("repo1")},
        ),
        (
            GroupDetail(
                id="invalid_id_pattern",
                display_name="Test Group1",
                repository=None,
                user_defined_id="id",
                type="group",
            ),
            "update",
            True,
            E.GROUP_INVALID_ID_PATTERN,
        ),
        (
            GroupDetail(
                display_name="Test Group",
                repository=GroupRepository(id="repo2"),
                user_defined_id="group_id",
                type="group",
            ),
            "create",
            True,
            E.GROUP_FORBIDDEN_REPOSITORY % {"rid": "repo2"},
        ),
    ],
)
def test_validate_group_to_map_group_error(app, mocker: MockerFixture, group, mode, repository_exist, expected):
    repository = RepositoryDetail(id="repo1") if repository_exist else None
    mocker.patch("server.services.repositories.get_by_id", return_value=repository)
    mocker.patch("server.services.utils.transformers.get_permitted_repository_ids", return_value={"repo1"})
    with pytest.raises(InvalidFormError) as exc:
        transformers.validate_group_to_map_group(group=group, mode=mode)
    assert str(exc.value) == str(expected)


@pytest.mark.parametrize(
    ("private_attr", "expected"),
    [
        (
            (None, None, None),
            MapGroup(
                id="jc_repo1_gr_test_group_test",
                display_name="Test Group",
                public=True,
                description="Test Description",
                member_list_visibility="Public",
                members=None,
                administrators=None,
                services=None,
            ),
        ),
        (
            (["user1"], ["admin1"], ["service1"]),
            MapGroup(
                id="jc_repo1_gr_test_group_test",
                display_name="Test Group",
                public=True,
                description="Test Description",
                member_list_visibility="Public",
                members=[MemberUser(value="user1")],
                administrators=[GroupAdministrator(value="admin1")],
                services=[GroupService(value="service1")],
            ),
        ),
    ],
)
def test_make_map_group(app, mocker: MockerFixture, private_attr, expected):
    group = GroupDetail(
        id="jc_repo1_gr_test_group_test",
        display_name="Test Group",
        public=True,
        description="Test Description",
        member_list_visibility="Public",
        type="group",
    )
    users, admins, services = private_attr
    group._users = users  # noqa: SLF001
    group._admins = admins  # noqa: SLF001
    group._services = services  # noqa: SLF001
    assert transformers.make_map_group(group) == expected


def test_prepare_user(app, mocker: MockerFixture):
    user_detail = UserDetail(id="user1", user_name="Test User")
    return_fnc = mocker.patch(
        "server.services.utils.transformers.validate_user_to_map_user", return_value=MapUser(id="user1")
    )
    transformers.prepare_user(user_detail)
    return_fnc.assert_called_once_with(user_detail, mode="create")


@pytest.mark.parametrize(
    ("map_user", "affiliations", "is_system_admin", "expected"),
    [
        (
            MapUser(
                id="user1",
                user_name="Test User",
                preferred_language="ja",
                edu_person_principal_names=[EPPN(value="test_eppn")],
                emails=[Email(value="test@example.com")],
                meta=UserMeta(
                    created=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
                    last_modified=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
                    created_by=None,
                ),
            ),
            Affiliations(roles=[], groups=[]),
            True,
            UserDetail(
                id="user1",
                user_name="Test User",
                preferred_language="ja",
                eppns=["test_eppn"],
                emails=["test@example.com"],
                created=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
                last_modified=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            ),
        ),
        (
            MapUser(id="user1", user_name="Test User", groups=[UserGroup(value="jc_repo1_gr_test_group")]),
            Affiliations(
                roles=[_RoleGroup(repository_id=None, role=USER_ROLES.SYSTEM_ADMIN)],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group")],
            ),
            True,
            UserDetail(
                id="user1",
                user_name="Test User",
                is_system_admin=True,
            ),
        ),
        (
            MapUser(id="user1", user_name="Test User", groups=[UserGroup(value="jc_repo1_gr_test_group")]),
            Affiliations(
                roles=[_RoleGroup(repository_id="repo1", role=USER_ROLES.REPOSITORY_ADMIN)],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group")],
            ),
            False,
            UserDetail(
                id="user1",
                user_name="Test User",
                repository_roles=[RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN)],
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
            ),
        ),
    ],
)
def test_make_user_detail(app, mocker: MockerFixture, map_user, affiliations, is_system_admin, expected):
    mocker.patch("server.services.utils.transformers.get_permitted_repository_ids", return_value={"repo1"})
    mocker.patch("server.services.utils.transformers.detect_affiliations", return_value=affiliations)
    mocker.patch("server.services.utils.transformers.is_super", return_value=is_system_admin)
    mocker.patch("server.services.utils.transformers.make_criteria_object", return_value=None)
    user_detail = transformers.make_user_detail(map_user)
    assert user_detail == expected


@pytest.mark.parametrize(
    ("map_user", "permitted_repository_ids", "affiliations", "expected"),
    [
        (
            MapUser(id="user1", user_name="Test User", groups=[UserGroup(value="jc_repo1_gr_test_group")]),
            {"repo1"},
            Affiliations(
                roles=[_RoleGroup(repository_id="repo1", role=USER_ROLES.REPOSITORY_ADMIN)],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group")],
            ),
            UserDetail(
                id="user1",
                user_name="Test User",
                repository_roles=[RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN)],
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
            ),
        ),
        (
            MapUser(id="user1", user_name="Test User", groups=[UserGroup(value="jc_repo1_gr_test_group")]),
            set(),
            Affiliations(
                roles=[_RoleGroup(repository_id="repo1", role=USER_ROLES.REPOSITORY_ADMIN)],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group")],
            ),
            UserDetail(
                id="user1",
                user_name="Test User",
            ),
        ),
    ],
)
def test_make_user_detail_more(app, mocker: MockerFixture, map_user, permitted_repository_ids, affiliations, expected):
    mocker.patch(
        "server.services.utils.transformers.get_permitted_repository_ids", return_value=permitted_repository_ids
    )
    mocker.patch("server.services.utils.transformers.detect_affiliations", return_value=affiliations)
    mocker.patch("server.services.utils.transformers.is_super", return_value=False)
    mocker.patch("server.services.utils.transformers.make_criteria_object", return_value=None)
    mocker.patch(
        "server.services.groups.search",
        return_value=SearchResult[GroupSummary](
            total=1, page_size=20, offset=1, resources=[GroupSummary(id="jc_repo1_gr_test_group")]
        ),
    )
    mocker.patch(
        "server.services.repositories.search",
        return_value=SearchResult[RepositorySummary](
            total=1, page_size=20, offset=1, resources=[RepositorySummary(id="repo1")]
        ),
    )
    user_detail = transformers.make_user_detail(map_user, more_detail=True)
    assert user_detail == expected


@pytest.mark.parametrize(
    ("user_detail", "expectedarg", "expected_exception"),
    [
        (
            UserDetail(id="user1", user_name=""),
            E.USER_REQUIRES_USERNAME,
            InvalidFormError,
        ),
        (
            UserDetail(id=None, user_name="Test User", eppns=[]),
            E.USER_REQUIRES_EPPN,
            InvalidFormError,
        ),
        (
            UserDetail(id="user1", user_name="Test User", eppns=["test_eppn"], emails=[]),
            E.USER_REQUIRES_EMAIL,
            InvalidFormError,
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[GroupSummary(id="jc_not_repo_gr_test_group")],
            ),
            E.USER_REQUIRES_REPOSITORY,
            InvalidFormError,
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
                is_system_admin=True,
                repository_roles=[RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN)],
            ),
            E.USER_NO_CREATE_SYSTEM_ADMIN,
            InvalidFormError,
        ),
    ],
)
def test_validate_user_to_map_user_create(app, mocker: MockerFixture, user_detail, expectedarg, expected_exception):
    mocker.patch(
        "server.services.groups.search",
        return_value=SearchResult[GroupSummary](
            total=1, page_size=20, offset=1, resources=[GroupSummary(id="jc_repo1_gr_test_group")]
        ),
    )
    with pytest.raises(expected_exception) as exc:
        transformers.validate_user_to_map_user(user_detail, mode="create")
    assert str(exc.value) == str(expectedarg)


@pytest.mark.parametrize(
    ("user_detail", "exist_repository", "expectedarg", "expected_exception"),
    [
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[],
                is_system_admin=True,
                repository_roles=[RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN)],
            ),
            None,
            str(E.USER_REQUIRES_NO_REPOSITORY),
            InvalidFormError,
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
                is_system_admin=True,
                repository_roles=None,
            ),
            None,
            str(E.USER_REQUIRES_NO_GROUP),
            InvalidFormError,
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[],
                is_system_admin=True,
                repository_roles=[],
            ),
            RepositoryDetail(id="repo1"),
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[GroupSummary(id="jc_roles_sysadm_test")],
                is_system_admin=True,
                repository_roles=[],
            ),
            None,
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[],
                is_system_admin=False,
                repository_roles=[
                    RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN),
                    RepositoryRole(id="repo2", user_role=None),
                ],
            ),
            RepositoryDetail(id="repo1"),
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
                is_system_admin=False,
                repository_roles=[
                    RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN),
                    RepositoryRole(id="repo2", user_role=None),
                ],
            ),
            None,
        ),
    ],
)
def test_validate_user_to_map_user_update(
    app, mocker: MockerFixture, user_detail, exist_repository, expectedarg, expected_exception
):
    mocker.patch(
        "server.services.repositories.get_by_id",
        return_value=exist_repository,
    )
    mocker.patch("server.services.utils.transformers.get_permitted_repository_ids", return_value={"repo1"})
    mocker.patch(
        "server.services.utils.transformers.validate_user_roles",
        return_value=[],
    )
    mocker.patch(
        "server.services.utils.transformers.is_super",
        return_value=True,
    )
    mocker.patch("server.services.utils.transformers.validate_user_groups", return_value=["jc_repo1_gr_test_group"])
    if expected_exception:
        with pytest.raises(expected_exception) as exc:
            transformers.validate_user_to_map_user(user_detail, mode="update")
        assert str(exc.value) == expectedarg
    else:
        return_fnc = mocker.patch(
            "server.services.utils.transformers.make_map_user",
            return_value=SearchResult[GroupSummary](
                total=1, page_size=20, offset=1, resources=[GroupSummary(id="jc_repo1_gr_test_group")]
            ),
        )
        transformers.validate_user_to_map_user(user_detail, mode="update")
        return_fnc.assert_called_once_with(expectedarg)


def test_validate_user_to_map_user_not_promote(app, mocker: MockerFixture):
    user_detail = UserDetail(
        id="user1",
        user_name="Test User",
        eppns=["test_eppn"],
        emails=["test@email.com"],
        groups=[],
        is_system_admin=True,
    )
    mocker.patch(
        "server.services.repositories.get_by_id",
        return_value=RepositoryDetail(id="repo1"),
    )
    mocker.patch("server.services.utils.transformers.get_permitted_repository_ids", return_value={"repo1"})
    mocker.patch(
        "server.services.utils.transformers.validate_user_roles",
        return_value=[],
    )
    mocker.patch(
        "server.services.utils.transformers.is_super",
        return_value=False,
    )
    mocker.patch("server.services.utils.transformers.validate_user_groups", return_value=["jc_repo1_gr_test_group"])
    with pytest.raises(InvalidFormError) as exc:
        transformers.validate_user_to_map_user(user_detail, mode="update")
    assert str(exc.value) == str(E.USER_NO_PROMOTE_SYSTEM_ADMIN)


def test_validate_user_roles(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
        repository_roles=[
            RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN),
            RepositoryRole(id="repo2", user_role=None),
            RepositoryRole(id="", user_role=USER_ROLES.REPOSITORY_ADMIN),
        ],
    )
    permitted = {"repo1", "repo2"}
    mocker.patch(
        "server.services.repositories.search",
        return_value=SearchResult[RepositorySummary](
            total=2, page_size=20, offset=1, resources=[RepositorySummary(id="repo1"), RepositorySummary(id="repo2")]
        ),
    )
    assert transformers.validate_user_roles(user_detail, permitted) == ["jc_repo1_ro_radm_test"]


def test_validate_user_roles_no_existed(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
        repository_roles=[
            RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN),
        ],
    )
    permitted = {"repo1", "repo2"}
    mocker.patch(
        "server.services.repositories.search",
        return_value=SearchResult[RepositorySummary](total=0, page_size=20, offset=1, resources=[]),
    )
    with pytest.raises(InvalidFormError) as exc:
        transformers.validate_user_roles(user_detail, permitted)
    assert str(exc.value) == str(E.USER_REQUIRES_EXISTING_REPOSITORY % {"id": "repo1"})


def test_validate_user_roles_forbidden(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
        repository_roles=[
            RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN),
            RepositoryRole(id="repo2", user_role=None),
        ],
    )
    permitted = set()
    mocker.patch(
        "server.services.repositories.search",
        return_value=SearchResult[RepositorySummary](
            total=2,
            page_size=20,
            offset=1,
            resources=[RepositorySummary(id="repo1"), RepositorySummary(id="repo2")],
        ),
    )
    with pytest.raises(InvalidFormError) as exc:
        transformers.validate_user_roles(user_detail, permitted)
    assert str(exc.value) == str(E.USER_FORBIDDEN_REPOSITORY % {"id": "repo1"})


def test_validate_user_groups(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
        groups=[GroupSummary(id="jc_repo1_gr_test_group")],
    )
    permitted = {"repo1"}
    mocker.patch(
        "server.services.utils.transformers.detect_affiliations",
        return_value=(
            None,
            [
                _Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group"),
            ],
        ),
    )
    mocker.patch(
        "server.services.groups.search",
        return_value=SearchResult[GroupSummary](
            total=1, page_size=20, offset=1, resources=[GroupSummary(id="jc_repo1_gr_test_group")]
        ),
    )
    assert transformers.validate_user_groups(user_detail, permitted) == ["jc_repo1_gr_test_group"]


def test_validate_user_groups_non_existent(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
        groups=[GroupSummary(id="jc_repo1_gr_test_group"), GroupSummary(id="jc_repo2_gr_test_group")],
    )
    permitted = {"repo1"}
    mocker.patch(
        "server.services.utils.transformers.detect_affiliations",
        return_value=(
            None,
            [
                _Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group"),
                _Group(repository_id="repo2", group_id="jc_repo2_gr_test_group", user_defined_id="test_group"),
            ],
        ),
    )
    mocker.patch(
        "server.services.groups.search",
        return_value=SearchResult[GroupSummary](
            total=1, page_size=20, offset=1, resources=[GroupSummary(id="jc_repo1_gr_test_group")]
        ),
    )
    with pytest.raises(InvalidFormError) as exc:
        transformers.validate_user_groups(user_detail, permitted)
    assert str(exc.value) == str(E.USER_REQUIRES_EXISTING_GROUP % {"id": "jc_repo2_gr_test_group"})


def test_validate_user_groups_forbidden(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
        groups=[GroupSummary(id="jc_repo1_gr_test_group"), GroupSummary(id="jc_repo2_gr_test_group")],
    )
    permitted = {"repo1"}
    mocker.patch(
        "server.services.utils.transformers.detect_affiliations",
        return_value=(
            None,
            [
                _Group(repository_id="repo1", group_id="jc_repo1_gr_test_group", user_defined_id="test_group"),
                _Group(repository_id="repo2", group_id="jc_repo2_gr_test_group", user_defined_id="test_group"),
            ],
        ),
    )
    mocker.patch(
        "server.services.groups.search",
        return_value=SearchResult[GroupSummary](
            total=2,
            page_size=20,
            offset=1,
            resources=[GroupSummary(id="jc_repo1_gr_test_group"), GroupSummary(id="jc_repo2_gr_test_group")],
        ),
    )
    with pytest.raises(InvalidFormError) as exc:
        transformers.validate_user_groups(user_detail, permitted)
    assert str(exc.value) == str(E.USER_FORBIDDEN_GROUP % {"id": "jc_repo2_gr_test_group"})


def test_validate_user_groups_non(app, mocker: MockerFixture):
    user_detail = UserDetail(
        user_name="Test User",
    )
    permitted = {"repo1"}
    assert transformers.validate_user_groups(user_detail, permitted) == []


@pytest.mark.parametrize(
    ("user_detail", "expected"),
    [
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
                repository_roles=[RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN)],
            ),
            MapUser(
                id="user1",
                user_name="Test User",
                edu_person_principal_names=[EPPN(value="test_eppn")],
                emails=[Email(value="test@email.com")],
                groups=[UserGroup(value="jc_repo1_gr_test_group"), UserGroup(value="jc_repo1_ro_radm_test")],
            ),
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=["test_eppn"],
                emails=["test@email.com"],
                is_system_admin=True,
                groups=[GroupSummary(id="jc_repo1_gr_test_group")],
            ),
            MapUser(
                id="user1",
                user_name="Test User",
                edu_person_principal_names=[EPPN(value="test_eppn")],
                emails=[Email(value="test@email.com")],
                groups=[UserGroup(value="jc_repo1_gr_test_group"), UserGroup(value="jc_roles_sysadm_test")],
            ),
        ),
        (
            UserDetail(
                id="user1",
                user_name="Test User",
                eppns=[],
                emails=[],
                groups=[],
                repository_roles=[],
            ),
            MapUser(id="user1", user_name="Test User"),
        ),
    ],
)
def test_make_map_user(app, mocker: MockerFixture, user_detail, expected):
    assert transformers.make_map_user(user_detail) == expected
