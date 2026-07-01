#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services to provide filter options for search requests."""

import re
import typing as t

from functools import cache
from typing import get_args, get_origin, get_type_hints

from server.const import USER_ROLES
from server.entities.search_request import FilterOption

from .permissions import is_current_user_system_admin
from .search_queries import (
    Criteria,
    GroupsCriteria,
    HistoryCriteria,
    UsersCriteria,
    group_sortable_keys,
    repository_sortable_keys,
    user_sortable_keys,
)


if t.TYPE_CHECKING:
    from server.entities.summaries import GroupSummary, RepositorySummary, UserSummary


def search_repositories_options() -> list[FilterOption[RepositorySummary]]:
    """Provide filter options for searching repositories.

    Returns:
        list[FilterOption]: List of filter options for repository search.
    """
    options = _initial_options()

    options.extend((
        # sort attribute key
        FilterOption(
            key="k",
            description=__get_description(Criteria, "k"),
            type=__get_type(Criteria, "k"),
            multiple=__allow_multiple(Criteria, "k"),
            items=[{"value": _a(key)} for key in repository_sortable_keys],
        ),
    ))

    options.extend(_common_options())

    return options


def search_groups_options() -> list[FilterOption[GroupSummary]]:
    """Provide filter options for searching groups.

    Returns:
        list[FilterOption]: List of filter options for group search.
    """
    options = _initial_options()

    options.extend((
        # affiliated repository IDs
        FilterOption(
            key="r",
            description=__get_description(GroupsCriteria, "r"),
            type=__get_type(GroupsCriteria, "r"),
            multiple=__allow_multiple(GroupsCriteria, "r"),
            # repositories are lazy loaded.
        ),
        # affiliated user IDs
        FilterOption(
            key="u",
            description=__get_description(GroupsCriteria, "u"),
            type=__get_type(GroupsCriteria, "u"),
            multiple=__allow_multiple(GroupsCriteria, "u"),
            # users are lazy loaded.
        ),
    ))

    options.extend((
        # public status
        FilterOption(
            key="s",
            description=__get_description(GroupsCriteria, "s"),
            type=__get_type(GroupsCriteria, "s"),
            multiple=__allow_multiple(GroupsCriteria, "s"),
            items=[
                {"value": 0, "label": "public"},
                {"value": 1, "label": "private"},
            ],
        ),
        # member list visibility
        FilterOption(
            key="v",
            description=__get_description(GroupsCriteria, "v"),
            type=__get_type(GroupsCriteria, "v"),
            multiple=__allow_multiple(GroupsCriteria, "v"),
            items=[
                {"value": 0, "label": "Public"},
                {"value": 1, "label": "Private"},
                {"value": 2, "label": "Hidden"},
            ],
        ),
        # sort attribute key
        FilterOption(
            key="k",
            description=__get_description(Criteria, "k"),
            type=__get_type(Criteria, "k"),
            multiple=__allow_multiple(Criteria, "k"),
            items=[{"value": _a(key)} for key in group_sortable_keys],
        ),
    ))

    options.extend(_common_options())

    return options


def search_users_options() -> list[FilterOption[UserSummary]]:
    """Provide filter options for searching users.

    Returns:
        list[FilterOption]: List of filter options for user search.
    """
    is_system_admin = is_current_user_system_admin()
    options = _initial_options()

    options.extend((
        # affiliated repository IDs
        FilterOption(
            key="r",
            description=__get_description(UsersCriteria, "r"),
            type=__get_type(UsersCriteria, "r"),
            multiple=__allow_multiple(UsersCriteria, "r"),
            # repositories are lazy loaded.
        ),
        # affiliated group IDs
        FilterOption(
            key="g",
            description=__get_description(UsersCriteria, "g"),
            type=__get_type(UsersCriteria, "g"),
            multiple=__allow_multiple(UsersCriteria, "g"),
            # groups are lazy loaded.
        ),
        # user roles
        FilterOption(
            key="a",
            description=__get_description(UsersCriteria, "a"),
            type=__get_type(UsersCriteria, "a"),
            multiple=__allow_multiple(UsersCriteria, "a"),
            items=[
                {"value": i, "label": _a(name)}
                for i, name in enumerate(list(USER_ROLES))
                if is_system_admin or name != USER_ROLES.SYSTEM_ADMIN
            ],
        ),
    ))

    options.extend((
        # last modified date (from)
        FilterOption(
            key="s",
            description=__get_description(UsersCriteria, "s"),
            type=__get_type(UsersCriteria, "s"),
            multiple=__allow_multiple(UsersCriteria, "s"),
        ),
        # last modified date (to)
        FilterOption(
            key="e",
            description=__get_description(UsersCriteria, "e"),
            type=__get_type(UsersCriteria, "e"),
            multiple=__allow_multiple(UsersCriteria, "e"),
        ),
        # sort attribute key
        FilterOption(
            key="k",
            description=__get_description(Criteria, "k"),
            type=__get_type(Criteria, "k"),
            multiple=__allow_multiple(Criteria, "k"),
            items=[{"value": _a(key)} for key in user_sortable_keys],
        ),
    ))

    options.extend(_common_options())

    return options


@cache
def _a(o: str) -> str:
    return FilterOption._alias_generator(o)  # noqa: SLF001


def _initial_options() -> list[FilterOption]:
    return [
        # search term
        FilterOption(
            key="q",
            description=__get_description(Criteria, "q"),
            type=__get_type(Criteria, "q"),
            multiple=__allow_multiple(Criteria, "q"),
        ),
        # resource IDs
        FilterOption(
            key="i",
            description=__get_description(Criteria, "i"),
            type=__get_type(Criteria, "i"),
            multiple=__allow_multiple(Criteria, "i"),
        ),
    ]


def _common_options() -> list[FilterOption]:

    return [
        # sort order
        FilterOption(
            key="d",
            description=__get_description(Criteria, "d"),
            type=__get_type(Criteria, "d"),
            multiple=__allow_multiple(Criteria, "d"),
            items=[
                {"value": "asc", "label": "Ascending"},
                {"value": "desc", "label": "Descending"},
            ],
        ),
        # page number
        FilterOption(
            key="p",
            description=__get_description(Criteria, "p"),
            type=__get_type(Criteria, "p"),
            multiple=__allow_multiple(Criteria, "p"),
        ),
        # page size
        FilterOption(
            key="l",
            description=__get_description(Criteria, "l"),
            type=__get_type(Criteria, "l"),
            multiple=__allow_multiple(Criteria, "l"),
        ),
    ]


type OptionType = t.Literal["string", "number", "date"]


def __get_description(cls: type, attr_name: str) -> str | None:
    hints = get_type_hints(cls, include_extras=True)
    hint = hints.get(attr_name)

    if get_origin(hint) is t.Annotated:
        return get_args(hint)[1]

    return None


def __get_type(protocol_cls: type, attr_name: str) -> OptionType:
    hints = get_type_hints(protocol_cls)
    hint_str = str(hints.get(attr_name, ""))

    if "date" in hint_str:
        return "date"
    if "int" in hint_str or "float" in hint_str or re.search(r"\d", hint_str):
        return "number"

    return "string"


def __allow_multiple(protocol_cls: type, attr_name: str) -> bool:
    hints = get_type_hints(protocol_cls)

    if attr_name not in hints:
        return False

    arg_type = hints[attr_name]
    origin = get_origin(arg_type)

    if origin is t.Union or (
        hasattr(t, "UnionType") and isinstance(arg_type, t.UnionType)  # pyright: ignore[reportAttributeAccessIssue]
    ):
        args = get_args(arg_type)
        return any(get_origin(arg) is list or arg is list for arg in args)

    return origin is list or arg_type is list


def search_history_filter_options() -> list[FilterOption]:
    """Provide filter options for searching history data.

    Returns:
        list[FilterOption]: List of filter options for history search.
    """
    # Items of options are lazy loaded in the frontend.
    options = [
        # history ID (parent ID)
        FilterOption(
            key="i",
            description=__get_description(HistoryCriteria, "i"),
            type=__get_type(HistoryCriteria, "i"),
            multiple=__allow_multiple(HistoryCriteria, "i"),
        ),
        # repository IDs
        FilterOption(
            key="r",
            description=__get_description(HistoryCriteria, "r"),
            type=__get_type(HistoryCriteria, "r"),
            multiple=__allow_multiple(HistoryCriteria, "r"),
        ),
        # group IDs
        FilterOption(
            key="g",
            description=__get_description(HistoryCriteria, "g"),
            type=__get_type(HistoryCriteria, "g"),
            multiple=__allow_multiple(HistoryCriteria, "g"),
        ),
        # user IDs
        FilterOption(
            key="u",
            description=__get_description(HistoryCriteria, "u"),
            type=__get_type(HistoryCriteria, "u"),
            multiple=__allow_multiple(HistoryCriteria, "u"),
        ),
        # operator user IDs
        FilterOption(
            key="o",
            description=__get_description(HistoryCriteria, "o"),
            type=__get_type(HistoryCriteria, "o"),
            multiple=__allow_multiple(HistoryCriteria, "o"),
        ),
    ]

    options.extend(_common_options())

    return options
