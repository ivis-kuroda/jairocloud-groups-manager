import typing as t

from server.entities.search_request import FilterOption
from server.services.utils.filter_options import (
    _allow_multiple,
    _common_options,
    _get_description,
    _get_type,
    _initial_options,
    search_groups_options,
    search_history_filter_options,
    search_repositories_options,
    search_users_options,
)
from server.services.utils.search_queries import (
    Criteria,
    UsersCriteria,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_search_repositories_options_normal(mocker: MockerFixture) -> None:
    """Test search_repositories_options returns correct FilterOption list."""
    expected = [
        FilterOption(key="q", description="query", type="string", multiple=False),
        FilterOption(
            key="k",
            description="sort key",
            type="string",
            multiple=False,
            items=[{"value": "name"}, {"value": "created_at"}],
        ),
        FilterOption(key="d", description="direction", type="string", multiple=False),
    ]

    mocker.patch("server.services.utils.filter_options.repository_sortable_keys", ["name", "created_at"])
    mocker.patch.object(FilterOption, "_alias_generator", side_effect=lambda x: x)
    mocker.patch(
        "server.services.utils.filter_options._initial_options",
        return_value=[FilterOption(key="q", description="query", type="string", multiple=False)],
    )
    mocker.patch(
        "server.services.utils.filter_options._common_options",
        return_value=[FilterOption(key="d", description="direction", type="string", multiple=False)],
    )
    mocker.patch(
        "server.services.utils.filter_options._get_description",
        return_value="sort key",
    )

    result = search_repositories_options()
    assert result == expected


def test_search_groups_options_normal(mocker: MockerFixture) -> None:

    expected = [
        FilterOption(key="q", description="query", type="date", multiple=False, items=None),
        FilterOption(key="r", description="sort key", type="string", multiple=True, items=[]),
        FilterOption(key="u", description="sort key", type="string", multiple=True, items=None),
        FilterOption(
            key="s",
            description="sort key",
            type="number",
            multiple=False,
            items=[{"value": 0, "label": "public"}, {"value": 1, "label": "private"}],
        ),
        FilterOption(
            key="v",
            description="sort key",
            type="number",
            multiple=False,
            items=[{"value": 0, "label": "Public"}, {"value": 1, "label": "Private"}, {"value": 2, "label": "Hidden"}],
        ),
        FilterOption(
            key="k",
            description="sort key",
            type="string",
            multiple=False,
            items=[{"value": "gid"}, {"value": "created_at"}],
        ),
        FilterOption(key="d", description="direction", type="string", multiple=False, items=None),
    ]
    mocker.patch("server.services.utils.filter_options.group_sortable_keys", ["gid", "created_at"])
    mocker.patch.object(FilterOption, "_alias_generator", side_effect=lambda x: x)
    mocker.patch(
        "server.services.utils.filter_options._initial_options",
        return_value=[FilterOption(key="q", description="query", type="date", multiple=False)],
    )
    mocker.patch(
        "server.services.utils.filter_options._common_options",
        return_value=[FilterOption(key="d", description="direction", type="string", multiple=False)],
    )
    mocker.patch(
        "server.services.utils.filter_options._get_description",
        return_value="sort key",
    )

    result = search_groups_options()
    assert result == expected


def test_search_users_options_normal(mocker: MockerFixture) -> None:
    expected = [
        FilterOption(key="q", description="query", type="string", multiple=False, items=None),
        FilterOption(
            key="r",
            description="affiliated repository IDs",
            type="string",
            multiple=True,
            items=[],
        ),
        FilterOption(
            key="g",
            description="affiliated group IDs",
            type="string",
            multiple=True,
            items=[],
        ),
        FilterOption(
            key="a",
            description="user roles",
            type="number",
            multiple=True,
            items=[
                {"value": 0, "label": "system_admin"},
                {"value": 1, "label": "repository_admin"},
                {"value": 2, "label": "community_admin"},
                {"value": 3, "label": "contributor"},
                {"value": 4, "label": "general_user"},
            ],
        ),
        FilterOption(key="s", description="last modified date (from)", type="date", multiple=False, items=None),
        FilterOption(key="e", description="last modified date (to)", type="date", multiple=False, items=None),
        FilterOption(
            key="k",
            description="sort attribute key",
            type="string",
            multiple=False,
            items=[{"value": "uid"}, {"value": "created_at"}],
        ),
        FilterOption(key="d", description="direction", type="string", multiple=False, items=None),
    ]

    mocker.patch("server.services.utils.filter_options.user_sortable_keys", ["uid", "created_at"])
    mocker.patch.object(FilterOption, "_alias_generator", side_effect=lambda x: x)
    mocker.patch(
        "server.services.utils.filter_options._initial_options",
        return_value=[FilterOption(key="q", description="query", type="string", multiple=False)],
    )
    mocker.patch(
        "server.services.utils.filter_options._common_options",
        return_value=[FilterOption(key="d", description="direction", type="string", multiple=False)],
    )
    mocker.patch("server.services.utils.filter_options.is_current_user_system_admin", return_value=True)
    result = search_users_options()
    assert result == expected


def test__initial_options_normal() -> None:
    expected = [
        FilterOption(
            key="q",
            description="search term",
            type="string",
            multiple=False,
            items=None,
        ),
        FilterOption(
            key="i",
            description="resource IDs",
            type="string",
            multiple=True,
            items=None,
        ),
    ]
    opts = _initial_options()
    assert opts == expected


def test__common_options_normal() -> None:
    expected = [
        FilterOption(
            key="d",
            description="sort order",
            type="string",
            multiple=False,
            items=[
                {"value": "asc", "label": "Ascending"},
                {"value": "desc", "label": "Descending"},
            ],
        ),
        FilterOption(
            key="p",
            description="page number",
            type="number",
            multiple=False,
            items=None,
        ),
        FilterOption(
            key="l",
            description="page size",
            type="number",
            multiple=False,
            items=None,
        ),
    ]
    opts = _common_options()
    assert opts == expected


def test__get_description_annotated() -> None:

    desc = _get_description(UsersCriteria, "g")
    assert desc == "affiliated group IDs"


def test__get_description_none() -> None:

    desc = _get_description(UsersCriteria, "-")
    assert desc is None


def test__get_type_variants() -> None:
    assert _get_type(UsersCriteria, "r") == "string"
    assert _get_type(UsersCriteria, "g") == "string"
    assert _get_type(UsersCriteria, "a") == "number"
    assert _get_type(UsersCriteria, "s") == "date"
    assert _get_type(UsersCriteria, "e") == "date"
    assert _get_type(Criteria, "q") == "string"
    assert _get_type(Criteria, "i") == "string"
    assert _get_type(Criteria, "k") == "string"
    assert _get_type(Criteria, "d") == "string"
    assert _get_type(Criteria, "p") == "number"
    assert _get_type(Criteria, "l") == "number"


def test__allow_multiple_variants() -> None:
    assert _allow_multiple(UsersCriteria, "r") is True
    assert _allow_multiple(UsersCriteria, "g") is True
    assert _allow_multiple(UsersCriteria, "a") is True
    assert _allow_multiple(UsersCriteria, "s") is False
    assert _allow_multiple(UsersCriteria, "e") is False


class DummyProtocol:
    a: int
    b: list[str]
    c: list[int] | int
    d: str


def test_allow_multiple_returns_false_for_missing_attr():
    result = _allow_multiple(DummyProtocol, "not_exist")
    assert result is False


def test_allow_multiple_returns_true_for_list():
    result = _allow_multiple(DummyProtocol, "b")
    assert result is True


def test_allow_multiple_returns_true_for_union_list():
    result = _allow_multiple(DummyProtocol, "c")
    assert result is True


def test_allow_multiple_returns_false_for_non_list():
    result = _allow_multiple(DummyProtocol, "a")
    assert result is False
    result2 = _allow_multiple(DummyProtocol, "d")
    assert result2 is False


def test_search_history_filter_options_all_lines():

    opts = search_history_filter_options()
    len_opts_limited = 4
    assert isinstance(opts, list)
    assert len(opts) >= len_opts_limited
    keys = {o.key for o in opts}
    assert {"o", "r", "g", "u"}.issubset(keys)
    for o in opts:
        assert isinstance(o, FilterOption)
        assert o.multiple is True
        assert isinstance(o.items, list)
        assert o.items == []
        assert o.type == "string"
        assert isinstance(o.description, str)
