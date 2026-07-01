import typing as t

import pytest

import server.services.utils.filter_options

from server.services.utils.filter_options import (
    _common_options,
    _initial_options,
    search_groups_options,
    search_repositories_options,
    search_users_options,
)
from server.services.utils.search_queries import group_sortable_keys, repository_sortable_keys, user_sortable_keys


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def mute_default_options(mocker: MockerFixture):
    mock_init = mocker.patch.object(server.services.utils.filter_options, "_initial_options", return_value=[])
    mock_common = mocker.patch.object(server.services.utils.filter_options, "_common_options", return_value=[])

    return mock_init, mock_common


@pytest.fixture(autouse=True)
def alias(mocker: MockerFixture):
    original = server.services.utils.filter_options._a
    mock_alias = mocker.patch.object(server.services.utils.filter_options, "_a", side_effect=lambda x: x)

    return original, mock_alias


def test_search_repositories_options_sort_key(mute_default_options):
    mock_init, mock_common = mute_default_options

    options = search_repositories_options()

    assert (option := next(o for o in options if o.key == "k"))
    assert option.description == "sort attribute key"
    assert option.type == "string"
    assert option.multiple is False
    assert option.items == [{"value": key} for key in repository_sortable_keys]
    mock_init.assert_called_once()
    mock_common.assert_called_once()


def test_search_groups_options_affiliated_repositories(mute_default_options):
    mock_init, mock_common = mute_default_options

    options = search_groups_options()

    assert (option := next(o for o in options if o.key == "r"))
    assert option.description == "affiliated repository IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # repositories are lazy loaded
    mock_init.assert_called_once()
    mock_common.assert_called_once()


def test_search_groups_options_affiliated_users(mute_default_options):
    options = search_groups_options()

    assert (option := next(o for o in options if o.key == "u"))
    assert option.description == "affiliated user IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # users are lazy loaded


def test_search_groups_options_public_status(mute_default_options):
    pairs = {0: "public", 1: "private"}

    options = search_groups_options()

    assert (option := next(o for o in options if o.key == "s"))
    assert option.description == "public status"
    assert option.type == "number"
    assert option.multiple is False
    assert option.items
    assert [v["value"] for v in option.items] == list(pairs.keys())
    assert [v["label"] for v in option.items] == list(pairs.values())


def test_search_groups_options_member_list_visibility(mute_default_options):
    pairs = {0: "Public", 1: "Private", 2: "Hidden"}

    options = search_groups_options()

    assert (option := next(o for o in options if o.key == "v"))
    assert option.description == "member list visibility"
    assert option.type == "number"
    assert option.multiple is False
    assert option.items
    assert [v["value"] for v in option.items] == list(pairs.keys())
    assert [v["label"] for v in option.items] == list(pairs.values())


def test_search_groups_options_sort_key(mute_default_options):
    options = search_groups_options()

    assert (option := next(o for o in options if o.key == "k"))
    assert option.description == "sort attribute key"
    assert option.type == "string"
    assert option.multiple is False
    assert option.items == [{"value": key} for key in group_sortable_keys]


def test_search_users_options_affiliated_repositories(mute_default_options):
    mock_init, mock_common = mute_default_options

    options = search_users_options()

    assert (option := next(o for o in options if o.key == "r"))
    assert option.description == "affiliated repository IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # repositories are lazy loaded
    mock_init.assert_called_once()
    mock_common.assert_called_once()


def test_search_users_options_affiliated_groups(mute_default_options):
    options = search_users_options()

    assert (option := next(o for o in options if o.key == "g"))
    assert option.description == "affiliated group IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # groups are lazy loaded


def test_search_users_options_roles(mute_default_options, mocker: MockerFixture):
    mocker.patch.object(server.services.utils.filter_options, "is_current_user_system_admin", return_value=False)
    pairs = {1: "repository_admin", 2: "community_admin", 3: "contributor", 4: "general_user"}

    options = search_users_options()

    assert (option := next(o for o in options if o.key == "a"))
    assert option.description == "user roles"
    assert option.type == "number"
    assert option.multiple is True
    assert option.items
    assert [v["value"] for v in option.items] == list(pairs.keys())
    assert [v["label"] for v in option.items] == list(pairs.values())


def test_search_users_options_roles_for_sysadmin(mute_default_options, mocker: MockerFixture):
    mocker.patch.object(server.services.utils.filter_options, "is_current_user_system_admin", return_value=True)
    pairs = {0: "system_admin", 1: "repository_admin", 2: "community_admin", 3: "contributor", 4: "general_user"}

    options = search_users_options()

    assert (option := next(o for o in options if o.key == "a"))
    assert option.description == "user roles"
    assert option.type == "number"
    assert option.multiple is True
    assert option.items
    assert [v["value"] for v in option.items] == list(pairs.keys())
    assert [v["label"] for v in option.items] == list(pairs.values())


def test_search_users_options_last_modified_from(mute_default_options):
    options = search_users_options()

    assert (option := next(o for o in options if o.key == "s"))
    assert option.description == "last modified date (from)"
    assert option.type == "date"
    assert option.multiple is False
    assert option.items is None  # no predefined items


def test_search_users_options_last_modified_to(mute_default_options):
    options = search_users_options()

    assert (option := next(o for o in options if o.key == "e"))
    assert option.description == "last modified date (to)"
    assert option.type == "date"
    assert option.multiple is False
    assert option.items is None  # no predefined items


def test_search_users_options_sort_key(mute_default_options):
    options = search_users_options()

    assert (option := next(o for o in options if o.key == "k"))
    assert option.description == "sort attribute key"
    assert option.type == "string"
    assert option.multiple is False
    assert option.items == [{"value": key} for key in user_sortable_keys]


def test__initial_options_search_term():
    options = _initial_options()

    assert (option := next(o for o in options if o.key == "q"))
    assert option.description == "search term"
    assert option.type == "string"
    assert option.multiple is False
    assert option.items is None  # no predefined items


def test__initial_options_ids():
    options = _initial_options()

    assert (option := next(o for o in options if o.key == "i"))
    assert option.description == "resource IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # no predefined items


def test__common_options_sort_order():
    pairs = {"asc": "Ascending", "desc": "Descending"}

    options = _common_options()

    assert (option := next(o for o in options if o.key == "d"))
    assert option.description == "sort order"
    assert option.type == "string"
    assert option.multiple is False
    assert option.items
    assert [v["value"] for v in option.items] == list(pairs.keys())
    assert [v["label"] for v in option.items] == list(pairs.values())


def test__common_options_page_number():
    options = _common_options()

    assert (option := next(o for o in options if o.key == "p"))
    assert option.description == "page number"
    assert option.type == "number"
    assert option.multiple is False
    assert option.items is None  # no predefined items


def test__common_options_page_size():
    options = _common_options()

    assert (option := next(o for o in options if o.key == "l"))
    assert option.description == "page size"
    assert option.type == "number"
    assert option.multiple is False
    assert option.items is None  # no predefined items


def test_search_history_filter_options_parent_id(mute_default_options):
    _, mock_common = mute_default_options

    options = server.services.utils.filter_options.search_history_filter_options()

    assert (option := next(o for o in options if o.key == "i"))
    assert option.description == "history ID (parent ID)"
    assert option.type == "string"
    assert option.multiple is False
    assert option.items is None  # history IDs are lazy loaded
    mock_common.assert_called_once()


def test_search_history_filter_options_repository(mute_default_options):
    options = server.services.utils.filter_options.search_history_filter_options()

    assert (option := next(o for o in options if o.key == "r"))
    assert option.description == "repository IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # repositories are lazy loaded


def test_search_history_filter_options_group(mute_default_options):
    options = server.services.utils.filter_options.search_history_filter_options()

    assert (option := next(o for o in options if o.key == "g"))
    assert option.description == "group IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # groups are lazy loaded


def test_search_history_filter_options_user(mute_default_options):
    options = server.services.utils.filter_options.search_history_filter_options()

    assert (option := next(o for o in options if o.key == "u"))
    assert option.description == "user IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # users are lazy loaded


def test_search_history_filter_options_operator(mute_default_options):
    options = server.services.utils.filter_options.search_history_filter_options()

    assert (option := next(o for o in options if o.key == "o"))
    assert option.description == "operator user IDs"
    assert option.type == "string"
    assert option.multiple is True
    assert option.items is None  # operators are lazy loaded
