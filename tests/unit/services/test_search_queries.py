import inspect
import typing as t

from datetime import date

import pytest

from pydantic import AliasGenerator, BaseModel, ConfigDict

from server.api.schemas import GroupsQuery, RepositoriesQuery, UsersQuery
from server.entities.search_request import SearchRequestParameter
from server.exc import ConfigurationError, InvalidQueryError
from server.messages import E
from server.services.utils import search_queries
from server.services.utils.affiliations import Affiliations, _Group


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("search_query", "expected_function"),
    [
        (RepositoriesQuery(), "server.services.utils.search_queries.build_repositories_search_query"),
        (GroupsQuery(), "server.services.utils.search_queries.build_groups_search_query"),
        (UsersQuery(), "server.services.utils.search_queries.build_users_search_query"),
    ],
)
def test_build_search_query(app, mocker: MockerFixture, search_query, expected_function):
    mock_build_search_query = mocker.patch(expected_function, return_value="mocked_query")
    assert search_queries.build_search_query(search_query) == "mocked_query"
    mock_build_search_query.assert_called_once_with(search_query)


def test_build_search_query_invalid_query(app, mocker: MockerFixture):
    class DummyCriteria:
        pass

    with pytest.raises(InvalidQueryError) as exc:
        search_queries.build_search_query(DummyCriteria())  # pyright: ignore[reportArgumentType]
    assert str(exc.value) == str(E.UNRECOGNIZED_SEARCH_CRITERIA)


@pytest.mark.parametrize(
    ("search_query", "is_system_admin", "permitted", "expected"),
    [
        (
            RepositoriesQuery(q="test", i=["repo1"], k="id", d="asc", p=1, l=20),
            True,
            {"repo1", "repo2"},
            SearchRequestParameter(
                filter=(
                    '((serviceName co "test") or (serviceUrl co "test") or (entityIds.value co "test")) and '
                    '(groups.value eq "jc_roles_sysadm_test") and (id sw "jc_") and '
                    '(groups.value eq "jc_repo1_ro_radm_test")'
                ),
                start_index=1,
                count=20,
                sort_by="id",
                sort_order="ascending",
            ),
        ),
        (
            RepositoriesQuery(q=None, i=["repo1"], k="entityIds", d="desc", p=None, l=20),
            False,
            {"repo1", "repo2"},
            SearchRequestParameter(
                filter='(groups.value eq "jc_roles_sysadm_test") and (groups.value eq "jc_repo1_ro_radm_test")',
                start_index=None,
                count=20,
                sort_by="entityIds.value",
                sort_order="descending",
            ),
        ),
        (
            RepositoriesQuery(q=None, i=["repo2"], k="invalid_key", d=None, p=1, l=None),
            False,
            {"repo1"},
            SearchRequestParameter(
                filter='(groups.value eq "jc_roles_sysadm_test") and (id eq "")',
                start_index=1,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            RepositoriesQuery(q=None, i=["repo1"], k=None, d=None, p=None, l=None),
            False,
            set(),
            SearchRequestParameter(
                filter=(
                    '(groups.value eq "jc_roles_sysadm_test") and (id eq "") and '
                    '(groups.value eq "jc_repo1_ro_radm_test")'
                ),
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
    ],
)
def test_build_repositories_search_query(
    app, mocker: MockerFixture, search_query, is_system_admin, permitted, expected
):
    mocker.patch("server.services.utils.search_queries.is_current_user_system_admin", return_value=is_system_admin)
    mocker.patch("server.services.utils.search_queries.get_permitted_repository_ids", return_value=permitted)
    assert search_queries.build_repositories_search_query(search_query) == expected


@pytest.mark.parametrize(
    ("search_query", "is_system_admin", "permitted", "affiliations", "affiliation", "expected"),
    [
        (
            GroupsQuery(
                q="test",
                i=None,
                r=None,
                u=["test_user_id"],
                s=0,
                v=0,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            False,
            set(),
            Affiliations(roles=[], groups=[]),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1"),
            SearchRequestParameter(
                filter=(
                    '((displayName co "test")) and (id eq "") and '
                    '(members.type eq "User" and members.value eq "test_user_id") and '
                    "(public eq true) and (memberListVisibility eq Public)"
                ),
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            GroupsQuery(q=None, i=["jc_repo1_gr_test1"], r=None, u=None, s=1, v=1, k=None, d=None, p=None, l=None),
            False,
            {"repo1"},
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1"),
            SearchRequestParameter(
                filter='(id eq "jc_repo1_gr_test1") and (public eq false) and (memberListVisibility eq Private)',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            GroupsQuery(
                q=None,
                i=["jc_repo1_gr_test1"],
                r=None,
                u=None,
                s=None,
                v=2,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            True,
            {"repo1"},
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1"),
            SearchRequestParameter(
                filter='(id eq "jc_repo1_gr_test1") and (memberListVisibility eq Hidden)',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            GroupsQuery(q=None, i=None, r=None, u=None, s=None, v=None, k=None, d=None, p=-1, l=-1),
            False,
            {"repo1"},
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1"),
            SearchRequestParameter(
                filter='id sw "jc_repo1"', start_index=None, count=None, sort_by=None, sort_order=None
            ),
        ),
        (
            GroupsQuery(q=None, i=None, r=None, u=None, s=None, v=None, k=None, d=None, p=None, l=None),
            True,
            set(),
            Affiliations(roles=[], groups=[]),
            _Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1"),
            SearchRequestParameter(filter='id sw "jc_"', start_index=None, count=20, sort_by=None, sort_order=None),
        ),
    ],
)
def test_build_groups_search_query(
    app, mocker: MockerFixture, search_query, is_system_admin, permitted, affiliations, affiliation, expected
):
    mocker.patch("server.services.utils.search_queries.is_current_user_system_admin", return_value=is_system_admin)
    mocker.patch("server.services.utils.search_queries.get_permitted_repository_ids", return_value=permitted)
    mocker.patch("server.services.utils.search_queries.detect_affiliations", return_value=affiliations)
    mocker.patch("server.services.utils.search_queries.detect_affiliation", return_value=affiliation)
    assert search_queries.build_groups_search_query(search_query) == expected


def test_build_groups_search_query_invalid_query(app, mocker: MockerFixture):
    mocker.patch("server.services.utils.search_queries.is_current_user_system_admin", return_value=False)
    mocker.patch("server.services.utils.search_queries.get_permitted_repository_ids", return_value={"repo1"})
    mocker.patch(
        "server.services.utils.search_queries.detect_affiliations", return_value=Affiliations(roles=[], groups=[])
    )
    with pytest.raises(InvalidQueryError) as exc:
        search_queries.build_groups_search_query(GroupsQuery(i=["jc_repo1_gr_test1"]))
    assert str(exc.value) == str(E.UNRECOGNIZED_SEARCH_CRITERIA)


@pytest.mark.parametrize(
    ("search_query", "permitted", "affiliations", "expected"),
    [
        (
            UsersQuery(
                q="test",
                i=["test_user"],
                r=["repo1"],
                g=["jc_repo1_gr_test1"],
                a=[0],
                s=date(2026, 1, 1),
                e=date(2026, 1, 31),
                k="eppns",
                d="asc",
                p=None,
                l=None,
            ),
            set(),
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter=(
                    '((userName co "test") or (emails.value co "test") or (eduPersonPrincipalNames.value co "test")) '
                    'and (id eq "test_user") and (groups.value ne "jc_roles_sysadm_test" and '
                    '(groups.value eq "jc_repo1_gr_test1") and groups.value ne '
                    '"jc_roles_sysadm_test" and (groups.value eq "")) and (meta.lastModified ge '
                    '"2025-12-31T15:00:00+00:00") and (meta.lastModified lt "2026-01-31T15:00:00+00:00")'
                ),
                start_index=None,
                count=20,
                sort_by="eduPersonPrincipalNames.value",
                sort_order="ascending",
            ),
        ),
        (
            UsersQuery(
                q=None,
                i=None,
                r=None,
                g=["jc_repo1_gr_test1"],
                a=[1],
                s=None,
                e=None,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            set(),
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter=(
                    '(groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_gr_test1")) and '
                    '(groups.value ne "jc_roles_sysadm_test" and (groups.value sw "jc_" and '
                    'groups.value ew "_ro_radm_test"))'
                ),
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=["repo1"], g=None, a=[2], s=None, e=None, k=None, d=None, p=None, l=None),
            set(),
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_ro_cadm_test")',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(
                q=None,
                i=None,
                r=["repo2"],
                g=["jc_repo1_gr_test1"],
                a=None,
                s=None,
                e=None,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            set(),
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter='groups.value eq ""',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=["repo1"], g=None, a=None, s=None, e=None, k=None, d=None, p=None, l=None),
            set(),
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value ne "jc_roles_sysadm_test" and (groups.value sw "jc_repo1")',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(
                q=None,
                i=None,
                r=None,
                g=["jc_repo1_gr_test1"],
                a=None,
                s=None,
                e=None,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            set(),
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter='groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_gr_test1")',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=None, g=None, a=[0, 1, 3], s=None, e=None, k=None, d=None, p=None, l=None),
            set(),
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter=(
                    '(groups.value eq "jc_roles_sysadm_test" or groups.value sw "jc_" and '
                    'groups.value ew "_ro_radm_test" or groups.value sw "jc_" and '
                    'groups.value ew "_ro_cont_test")'
                ),
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=None, g=None, a=[5], s=None, e=None, k=None, d=None, p=None, l=None),
            set(),
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value eq ""',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=None, g=None, a=None, s=None, e=None, k=None, d=None, p=None, l=None),
            set(),
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value sw "jc_"',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
    ],
)
def test_build_users_search_query_system_admin(
    app, mocker: MockerFixture, search_query, permitted, affiliations, expected
):
    mocker.patch("server.services.utils.search_queries.is_current_user_system_admin", return_value=True)
    mocker.patch("server.services.utils.search_queries.get_permitted_repository_ids", return_value=permitted)
    mocker.patch("server.services.utils.search_queries.detect_affiliations", return_value=affiliations)
    assert search_queries.build_users_search_query(search_query) == expected


@pytest.mark.parametrize(
    ("search_query", "permitted", "affiliations", "expected"),
    [
        (
            UsersQuery(q=None, i=None, r=["repo1"], g=None, a=None, s=None, e=None, k=None, d=None, p=None, l=None),
            set(),
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value eq ""',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=None, g=None, a=None, s=None, e=None, k=None, d=None, p=None, l=None),
            {"repo1"},
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value ne "jc_roles_sysadm_test" and (groups.value sw "jc_repo1")',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(
                q=None,
                i=None,
                r=None,
                g=["jc_repo1_gr_test1"],
                a=[1],
                s=None,
                e=None,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            {"repo1"},
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter=(
                    'groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_gr_test1") '
                    'and groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_ro_radm_test")'
                ),
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(
                q=None,
                i=None,
                r=None,
                g=["jc_repo1_gr_test1"],
                a=None,
                s=None,
                e=None,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            {"repo1"},
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter='groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_gr_test1")',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(q=None, i=None, r=None, g=None, a=[1], s=None, e=None, k=None, d=None, p=None, l=None),
            {"repo1"},
            Affiliations(roles=[], groups=[]),
            SearchRequestParameter(
                filter='groups.value ne "jc_roles_sysadm_test" and (groups.value eq "jc_repo1_ro_radm_test")',
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
        (
            UsersQuery(
                q=None,
                i=None,
                r=None,
                g=["jc_repo1_gr_test1"],
                a=[0],
                s=None,
                e=None,
                k=None,
                d=None,
                p=None,
                l=None,
            ),
            {"repo1"},
            Affiliations(
                roles=[],
                groups=[_Group(repository_id="repo1", group_id="jc_repo1_gr_test1", user_defined_id="test1")],
            ),
            SearchRequestParameter(
                filter=('groups.value eq ""'),
                start_index=None,
                count=20,
                sort_by=None,
                sort_order=None,
            ),
        ),
    ],
)
def test_build_users_search_query_repo_admin(
    app, mocker: MockerFixture, search_query, permitted, affiliations, expected
):
    mocker.patch("server.services.utils.search_queries.is_current_user_system_admin", return_value=False)
    mocker.patch("server.services.utils.search_queries.get_permitted_repository_ids", return_value=permitted)
    mocker.patch("server.services.utils.search_queries.detect_affiliations", return_value=affiliations)
    assert search_queries.build_users_search_query(search_query) == expected


@pytest.mark.parametrize(
    ("resource_type", "kwargs", "expected"),
    [
        ("users", {"q": "test"}, search_queries.UsersCriteria),
        ("groups", {"u": ["user1"], "v": 2}, search_queries.GroupsCriteria),
        ("repositories", {}, search_queries.RepositoriesCriteria),
        ("invalid_resource", {}, InvalidQueryError),
    ],
)
def test_make_criteria_object(app, mocker: MockerFixture, resource_type, kwargs, expected):
    if expected is InvalidQueryError:
        with pytest.raises(InvalidQueryError):
            search_queries.make_criteria_object(resource_type=resource_type, **kwargs)
    else:
        obj = search_queries.make_criteria_object(resource_type=resource_type, **kwargs)
        assert isinstance(obj, expected)


class DummyModel(BaseModel):
    dummy_name: str


class DummyModelWithAlias(BaseModel):
    dummy_name: str
    model_config = ConfigDict(alias_generator=AliasGenerator(serialization_alias=lambda x: x.upper()))


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (DummyModel, "dummy_name"),
        (DummyModelWithAlias, "DUMMY_NAME"),
    ],
)
def test__path_generator(app, mocker: MockerFixture, model, expected):
    path = search_queries._path_generator(model)  # noqa: SLF001
    assert path("dummy_name") == expected


def test__get_id_prefix_not_match(app, test_config, mocker: MockerFixture):
    mocker.patch("server.config.config.REPOSITORIES.id_patterns.sp_connector", "invalid_pattern")
    test_func = inspect.unwrap(search_queries._get_id_prefix)  # noqa: SLF001
    with pytest.raises(ConfigurationError) as exc:
        test_func()
    assert str(exc.value) == str(E.INVALID_SERVER_CONFIG)
