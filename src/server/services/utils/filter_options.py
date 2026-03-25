#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services to provide filter options for search requests."""

import re
import typing as t

from server.const import USER_ROLES
from server.entities.search_request import FilterOption

from .permissions import is_current_user_system_admin
from .search_queries import (
    Criteria,
    GroupsCriteria,
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
    alias = FilterOption._alias_generator  # noqa: SLF001

    options = _initial_options()

    options.extend((
        # sort key
        FilterOption(
            key="k",
            description=_get_description(Criteria, "k"),
            type=_get_type(Criteria, "k"),
            multiple=_allow_multiple(Criteria, "k"),
            items=[{"value": alias(key)} for key in repository_sortable_keys],
        ),
    ))

    options.extend(_common_options())

    return options


def search_groups_options() -> list[FilterOption[GroupSummary]]:
    """Provide filter options for searching groups.

    Returns:
        list[FilterOption]: List of filter options for group search.
    """
    alias = FilterOption._alias_generator  # noqa: SLF001

    options = _initial_options()

    repos: list[dict[str, str]] = [
        # lazy load repositories.
    ]
    options.append(
        # affiliated repositories
        FilterOption(
            key="r",
            description=_get_description(GroupsCriteria, "r"),
            type=_get_type(GroupsCriteria, "r"),
            multiple=_allow_multiple(GroupsCriteria, "r"),
            items=repos,
        )
    )

    options.extend((
        # affiliated users
        FilterOption(
            key="u",
            description=_get_description(GroupsCriteria, "u"),
            type=_get_type(GroupsCriteria, "u"),
            multiple=_allow_multiple(GroupsCriteria, "u"),
        ),
        # public status
        FilterOption(
            key="s",
            description=_get_description(GroupsCriteria, "s"),
            type=_get_type(GroupsCriteria, "s"),
            multiple=_allow_multiple(GroupsCriteria, "s"),
            items=[
                {"value": 0, "label": "public"},
                {"value": 1, "label": "private"},
            ],
        ),
        # member list visibility
        FilterOption(
            key="v",
            description=_get_description(GroupsCriteria, "v"),
            type=_get_type(GroupsCriteria, "v"),
            multiple=_allow_multiple(GroupsCriteria, "v"),
            items=[
                {"value": 0, "label": "Public"},
                {"value": 1, "label": "Private"},
                {"value": 2, "label": "Hidden"},
            ],
        ),
        # sort key
        FilterOption(
            key="k",
            description=_get_description(Criteria, "k"),
            type=_get_type(Criteria, "k"),
            multiple=_allow_multiple(Criteria, "k"),
            items=[{"value": alias(key)} for key in group_sortable_keys],
        ),
    ))

    options.extend(_common_options())

    return options


def search_users_options() -> list[FilterOption[UserSummary]]:
    """Provide filter options for searching users.

    Returns:
        list[FilterOption]: List of filter options for user search.
    """
    alias = FilterOption._alias_generator  # noqa: SLF001
    is_system_admin = is_current_user_system_admin()

    options = _initial_options()

    repos: list[dict[str, str]] = [
        # lazy load repositories.
    ]
    options.append(
        # affiliated repositories
        FilterOption(
            key="r",
            description=_get_description(UsersCriteria, "r"),
            type=_get_type(UsersCriteria, "r"),
            multiple=_allow_multiple(UsersCriteria, "r"),
            items=repos,
        )
    )
    gros: list[dict[str, str]] = [
        # lazy load groups.
    ]
    options.append(
        # affiliated groups
        FilterOption(
            key="g",
            description=_get_description(UsersCriteria, "g"),
            type=_get_type(UsersCriteria, "g"),
            multiple=_allow_multiple(UsersCriteria, "g"),
            items=gros,
        )
    )

    roles = list(USER_ROLES)
    options.append(
        # user roles
        FilterOption(
            key="a",
            description=_get_description(UsersCriteria, "a"),
            type=_get_type(UsersCriteria, "a"),
            multiple=_allow_multiple(UsersCriteria, "a"),
            items=[
                {"value": i, "label": alias(name)}
                for i, name in enumerate(roles)
                if is_system_admin or name != USER_ROLES.SYSTEM_ADMIN
            ],
        )
    )

    options.extend((
        # last modified date (from)
        FilterOption(
            key="s",
            description=_get_description(UsersCriteria, "s"),
            type=_get_type(UsersCriteria, "s"),
            multiple=_allow_multiple(UsersCriteria, "s"),
        ),
        # last modified date (to)
        FilterOption(
            key="e",
            description=_get_description(UsersCriteria, "e"),
            type=_get_type(UsersCriteria, "e"),
            multiple=_allow_multiple(UsersCriteria, "e"),
        ),
        # sort key
        FilterOption(
            key="k",
            description=_get_description(Criteria, "k"),
            type=_get_type(Criteria, "k"),
            multiple=_allow_multiple(Criteria, "k"),
            items=[{"value": alias(key)} for key in user_sortable_keys],
        ),
    ))

    options.extend(_common_options())

    return options


def _initial_options() -> list[FilterOption]:
    return [
        # search term
        FilterOption(
            key="q",
            description=_get_description(Criteria, "q"),
            type=_get_type(Criteria, "q"),
            multiple=_allow_multiple(Criteria, "q"),
        ),
        # IDs
        FilterOption(
            key="i",
            description=_get_description(Criteria, "i"),
            type=_get_type(Criteria, "i"),
            multiple=_allow_multiple(Criteria, "i"),
        ),
    ]


def _common_options() -> list[FilterOption]:

    return [
        # sort order
        FilterOption(
            key="d",
            description=_get_description(Criteria, "d"),
            type=_get_type(Criteria, "d"),
            multiple=_allow_multiple(Criteria, "d"),
            items=[
                {"value": "asc", "label": "Ascending"},
                {"value": "desc", "label": "Descending"},
            ],
        ),
        # page number
        FilterOption(
            key="p",
            description=_get_description(Criteria, "p"),
            type=_get_type(Criteria, "p"),
            multiple=_allow_multiple(Criteria, "p"),
        ),
        # page size
        FilterOption(
            key="l",
            description=_get_description(Criteria, "l"),
            type=_get_type(Criteria, "l"),
            multiple=_allow_multiple(Criteria, "l"),
        ),
    ]


type OptionType = t.Literal["string", "number", "date"]


def _get_description(cls: type, attr_name: str) -> str | None:
    hints = t.get_type_hints(cls, include_extras=True)
    hint = hints.get(attr_name)

    if t.get_origin(hint) is t.Annotated:
        return t.get_args(hint)[1]

    return None


def _get_type(protocol_cls: type, attr_name: str) -> OptionType:
    hints = t.get_type_hints(protocol_cls)
    hint_str = str(hints.get(attr_name, ""))

    if "date" in hint_str:
        return "date"
    if "int" in hint_str or "float" in hint_str or re.search(r"\d", hint_str):
        return "number"

    return "string"


def _allow_multiple(protocol_cls: type, attr_name: str) -> bool:
    hints = t.get_type_hints(protocol_cls)

    if attr_name not in hints:
        return False

    arg_type = hints[attr_name]
    origin = t.get_origin(arg_type)

    if origin is t.Union or (
        hasattr(t, "UnionType") and isinstance(arg_type, t.UnionType)  # pyright: ignore[reportAttributeAccessIssue]
    ):
        args = t.get_args(arg_type)
        return any(t.get_origin(arg) is list or arg is list for arg in args)

    return origin is list or arg_type is list


def search_history_filter_options() -> list[FilterOption]:
    """Provide filter options for searching history data.

    Returns:
        list[FilterOption]: List of filter options for history search.
    """
    items = [
        # lazy load repositories.
    ]

    return [
        FilterOption(
            key="o", description="operator", type="string", multiple=True, items=items
        ),
        FilterOption(
            key="r",
            description="repositories",
            type="string",
            multiple=True,
            items=items,
        ),
        FilterOption(
            key="g", description="groups", type="string", multiple=True, items=items
        ),
        FilterOption(
            key="u", description="users", type="string", multiple=True, items=items
        ),
    ]
