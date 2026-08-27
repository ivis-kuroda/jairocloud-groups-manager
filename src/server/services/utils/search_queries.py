#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities for search queries."""

# ruff: file-ignore[docstring-missing-returns, docstring-missing-exception]

import re
import typing as t

from datetime import date, datetime, timedelta
from functools import cache
from types import SimpleNamespace
from typing import get_args, get_type_hints, runtime_checkable
from zoneinfo import ZoneInfo

from flask import current_app

from server.config import config
from server.const import (
    MAP_DEFAULT_SEARCH_COUNT,
    USER_ROLES,
)
from server.entities.map_group import MapGroup
from server.entities.map_service import MapService
from server.entities.map_user import MapUser
from server.entities.search_request import SearchRequestParameter
from server.exc import ConfigurationError, InvalidQueryError
from server.messages import E

from .affiliations import detect_affiliation, detect_affiliations
from .permissions import get_permitted_repository_ids, is_current_user_system_admin


if t.TYPE_CHECKING:
    from pydantic import BaseModel


def build_search_query(criteria: Criteria) -> SearchRequestParameter:
    """Generate search query parameters from criteria model.

    Args:
        criteria (Criteria): The criteria model containing search parameters.

    Returns:
        SearchRequestParameter: The constructed search query parameters.

    Raises:
        InvalidQueryError: If criteria type is unsupported.
    """
    match criteria:
        case UsersCriteria():
            query = build_users_search_query(criteria)
        case GroupsCriteria():
            query = build_groups_search_query(criteria)
        case RepositoriesCriteria():
            query = build_repositories_search_query(criteria)
        case _:
            current_app.logger.error(E.UNRECOGNIZED_SEARCH_CRITERIA)
            raise InvalidQueryError(E.UNRECOGNIZED_SEARCH_CRITERIA)

    return query


def build_repositories_search_query(
    criteria: RepositoriesCriteria,
) -> SearchRequestParameter:
    """Generate repository search query parameters from criteria model.

    Fileter will be constructed based on the following criteria:
    - Partial match search on id, service_name and service_url (q)
    - Force filter by logged-in user's permitted repository IDs
    - Sort by specified attribute key (k) and direction (d)
    - Pagination (p, l)

    Args:
        criteria (RepositoriesCriteria):
            The object containing repository search parameters.

    Returns:
        SearchRequestParameter: The constructed repository search query parameters.
    """
    path = _path_generator(MapService)
    filter_expr: list[str] = []

    if criteria.q:
        # partial match search on id, service_name and service_url
        filter_expr.append(
            " or ".join([
                f'({path("service_name")} co "{criteria.q}")',
                f'({path("service_url")} co "{criteria.q}")',
                f'({path("entity_ids.value")} co "{criteria.q}")',
            ])
        )

    # all repositories must have system admin group
    system_admin_group = config.GROUPS.id_patterns.system_admin
    filter_expr.append(f'{path("groups.value")} eq "{system_admin_group}"')

    specified = set(criteria.i or [])
    if getattr(criteria, "super", False) or is_current_user_system_admin():
        prefix = _get_id_prefix()
        filter_expr.append(f'{path("id")} sw "{prefix}"')
        # no additional filter for system admin
    elif permitted := get_permitted_repository_ids():
        # force filter by logged-in user's permitted repository IDs
        specified = permitted.intersection(specified) if specified else permitted
        if not specified:
            filter_expr.append(_empty_filter(path("id")))
    else:
        # no permitted repositories for non-admin user
        filter_expr.append(_empty_filter(path("id")))

    if specified:
        pattern = config.GROUPS.id_patterns.repository_admin
        filter_expr.append(
            " or ".join([
                f'{path("groups.value")} eq "{pattern.format(repository_id=repo_id)}"'
                for repo_id in specified
            ])
        )

    filter_str = _combine_filter_exprs(filter_expr)

    options = _curculate_options(criteria, path)

    return SearchRequestParameter(
        filter=filter_str,
        start_index=options.start_index,
        count=options.page_count,
        sort_by=options.sort_by,
        sort_order=options.sort_order,
    )


def build_groups_search_query(criteria: GroupsCriteria) -> SearchRequestParameter:
    """Generate group search query parameters from criteria model.

    Fileter will be constructed based on the following criteria:
    - Partial match search on display_name(q)
    - Exact match search on IDs (i)
    - Force filter by logged-in user's permitted repository IDs
    - Filter by specified repository IDs (r)
    - Filter by specified affiliated user IDs (u)
    - Filter by public status (s)
    - Filter by member list visibility (v)
    - Sort by specified attribute key (k) and direction (d)
    - Pagination (p, l)

    Args:
        criteria (GroupsCriteria):
            The object containing group search parameters.

    Returns:
        SearchRequestParameter:
            The constructed group search query parameters.
    """
    path = _path_generator(MapGroup)
    filter_expr: list[str] = []

    if criteria.q:
        # partial match search on display_name
        filter_expr.append(f'({path("display_name")} co "{criteria.q}")')

    filter_expr.append(_group_groups_filter(criteria, path("id")))

    if criteria.u:
        # exact match search on affiliated user IDs
        filter_expr.append(
            " or ".join([
                f'{path("members.type")} eq "User" '
                f'and {path("members.value")} eq "{user_id}"'
                for user_id in criteria.u
            ])
        )

    match criteria.s:
        case 0:
            filter_expr.append(f"{path('public')} eq true")
        case 1:
            filter_expr.append(f"{path('public')} eq false")
        case _:
            pass

    match criteria.v:
        case 0:
            filter_expr.append(f"{path('member_list_visibility')} eq Public")
        case 1:
            filter_expr.append(f"{path('member_list_visibility')} eq Private")
        case 2:
            filter_expr.append(f"{path('member_list_visibility')} eq Hidden")
        case _:
            pass

    filter_str = _combine_filter_exprs(filter_expr)

    options = _curculate_options(criteria, path)

    return SearchRequestParameter(
        filter=filter_str,
        start_index=options.start_index,
        count=options.page_count,
        sort_by=options.sort_by,
        sort_order=options.sort_order,
    )


def _group_groups_filter(criteria: GroupsCriteria, id_path: str) -> str:
    """Generate a filter string for group IDs based on criteria."""
    criteria = _patch_falsey_to_none(criteria, {"r"})
    is_system_admin = (
        getattr(criteria, "super", False) or is_current_user_system_admin()
    )

    if is_system_admin:
        # no additional filter for system admin
        specified = criteria.r
        if criteria.i:
            criteria.i = [gid for gid in criteria.i if detect_affiliation(gid)]
    else:
        # reduce specified group IDs to only user-defined groups
        if criteria.i:
            _, groups = detect_affiliations(criteria.i)
            criteria.i = [aff.group_id for aff in groups]

        # force filter by logged-in user's permitted repository IDs
        permitted = get_permitted_repository_ids()
        specified = list(permitted.intersection(criteria.r or permitted))
        if not specified:
            return _empty_filter(id_path)

    match (criteria.i, specified):
        case (i, r) if i and r:
            return _specified_repository_specified_group_filter(id_path, r, i)
        case (i, None) if i:
            return _all_repository_specified_group_filter(id_path, i)
        case (None, r) if r:
            return _specified_repository_all_group_filter(id_path, r)
        case (None, None):
            return _all_repository_all_group_filter(id_path)
        case _:
            error = E.UNRECOGNIZED_SEARCH_CRITERIA
            raise InvalidQueryError(error)


def build_users_search_query(criteria: UsersCriteria) -> SearchRequestParameter:
    """Generate user search query parameters from criteria model.

    Fileter will be constructed based on the following criteria:
    - Partial match search on user_name, emails, edu_person_principal_names (q)
    - Exact match search on IDs (i)
    - Force filter by logged-in user's permitted repository IDs
    - Filter by specified repository IDs (r) and affiliated roles (a)
    - Filter by specified affiliated group IDs (g)
    - Filter by last modified date (from) (s)
    - Filter by last modified date (to) (e)
    - Sort by specified attribute key (k) and direction (d)
    - Pagination (p, l)

    Args:
        criteria (UsersCriteria):
            The object containing user search parameters.

    Returns:
        SearchRequestParameter:
            The constructed user search query parameters.
    """
    path = _path_generator(MapUser)
    filter_expr: list[str] = []

    if criteria.q:
        # partial match search on user_name, emails, edu_person_principal_names
        term_filter = [f'({path("user_name")} co "{criteria.q}")']
        if not config.FEATURES.search_only_username:
            term_filter.extend([
                f'({path("emails.value")} co "{criteria.q}")',
                f'({path("edu_person_principal_names.value")} co "{criteria.q}")',
            ])
        filter_expr.append(" or ".join(term_filter))

    if criteria.i:
        # exact match search on IDs
        filter_expr.append(
            " or ".join([f'{path("id")} eq "{user_id}"' for user_id in criteria.i])
        )

    filter_expr.append(_user_groups_filter(criteria, path("groups.value")))

    if criteria.s:
        # filter by last modified date (from)
        datetime_str = jst_date_to_utc_datetime(criteria.s).isoformat()
        filter_expr.append(f'{path("meta.last_modified")} ge "{datetime_str}"')

    if criteria.e:
        # filter by last modified date (to)
        end_date = criteria.e + timedelta(days=1)
        datetime_str = jst_date_to_utc_datetime(end_date).isoformat()
        filter_expr.append(f'{path("meta.last_modified")} lt "{datetime_str}"')

    filter_str = _combine_filter_exprs(filter_expr)

    options = _curculate_options(criteria, path)

    return SearchRequestParameter(
        filter=filter_str,
        start_index=options.start_index,
        count=options.page_count,
        sort_by=options.sort_by,
        sort_order=options.sort_order,
    )


def _user_groups_filter(criteria: UsersCriteria, path: str) -> str:
    """Generate a filter string for user affiliated group IDs based on criteria."""
    if criteria.g:
        # reduce specified group IDs to only user-defined groups
        _, groups = detect_affiliations(criteria.g)
        criteria.g = [aff.group_id for aff in groups]

    specified_roles: list[USER_ROLES] = []
    if criteria.a:
        user_roles = list(USER_ROLES)
        specified_roles = [
            user_roles[i] for i in criteria.a if 0 <= i < len(user_roles)
        ]
        if not specified_roles:
            return _empty_filter(path)

    if getattr(criteria, "super", False) or is_current_user_system_admin():
        return _system_admin_user_groups_filter(criteria, path, specified_roles)

    # repository admin could not see System Administrator
    specified_roles = [
        role for role in specified_roles if role != USER_ROLES.SYSTEM_ADMIN
    ]

    permitted: set[str] = get_permitted_repository_ids()
    if criteria.r:
        permitted = permitted.intersection(set(criteria.r))

    if not permitted:
        return _empty_filter(path)

    filter_expr = [
        _repository_admin_user_groups_filter(
            criteria, path, permitted, specified_roles
        ),
    ]
    return t.cast("str", _combine_filter_exprs(filter_expr))


def _system_admin_user_groups_filter(  # ruff: ignore[too-many-return-statements]
    criteria: UsersCriteria, path: str, specified_roles: list[USER_ROLES]
) -> str:
    """Generate a filter string for user affiliated group IDs for system admin."""
    criteria = _patch_falsey_to_none(criteria, {"a", "r", "g"})

    match (criteria.a, criteria.r, criteria.g):
        case (a, r, g) if a and r and g:
            return _specified_repository_specified_role_specified_group_filter(
                path, r, specified_roles, g
            )
        case (a, r, None) if a and r:
            return _specified_repository_specified_role_filter(path, r, specified_roles)
        case (a, None, g) if a and g:
            return _all_repository_specified_role_specified_group_filter(
                path, specified_roles, g
            )
        case (a, None, None) if a:
            return _all_repository_specified_role_filter(path, specified_roles)

        case (None, r, g) if r and g:
            return _specified_repository_specified_group_filter(path, r, g)
        case (None, r, None) if r:
            return _specified_repository_all_group_filter(path, r)
        case (None, None, g) if g:
            return _all_repository_specified_group_filter(path, g)

        case (None, None, None):
            return _all_repository_all_group_filter(path)
        case _:  # pragma: no cover
            error = E.UNRECOGNIZED_SEARCH_CRITERIA
            raise InvalidQueryError(error)


def _repository_admin_user_groups_filter(
    criteria: UsersCriteria,
    path: str,
    permitted: set[str],
    specified_roles: list[USER_ROLES],
) -> str:
    """Generate a filter string for user affiliated group IDs for repository admin."""
    criteria = _patch_falsey_to_none(criteria, {"a", "g"})

    match (criteria.a, criteria.g):
        case (a, g) if a and g:
            return _specified_repository_specified_role_specified_group_filter(
                path, list(permitted), specified_roles, g
            )
        case (a, None) if a:
            return _specified_repository_specified_role_filter(
                path, list(permitted), specified_roles
            )
        case (None, g) if g:
            return _specified_repository_specified_group_filter(
                path, list(permitted), g
            )
        case (None, None):
            return _specified_repository_all_group_filter(path, list(permitted))
        case _:  # pragma: no cover
            error = E.UNRECOGNIZED_SEARCH_CRITERIA
            raise InvalidQueryError(error)


@cache
def _path_generator(model: type[BaseModel]) -> t.Callable[[str], str]:
    """Generate a function to create attribute paths with aliasing."""

    def _func(path: str) -> str:
        alias_generator = model.model_config.get("alias_generator")
        if alias_generator and not callable(alias_generator):
            alias_generator = alias_generator.serialization_alias
        if alias_generator is None:
            alias_generator = lambda x: x  # ruff: ignore[lambda-assignment]

        return ".".join([alias_generator(p) for p in path.split(".")])

    return _func


def _all_repository_all_group_filter(path: str) -> str:
    """Generate a filter string.

    Filter by prefix match for group IDs without specifying a repository.
    """
    prefix_patterns = _get_prefix_patterns()
    return " or ".join([f'{path} sw "{prefix}"' for prefix in prefix_patterns])


def _all_repository_specified_role_filter(path: str, roles: list[USER_ROLES]) -> str:
    """Generate a filter string.

    Filter by prefix/suffix match for role-type group IDs without specifying
    a repository.
    """
    id_patterns = _get_id_patterns()
    filters: list[str] = []
    for role in roles:
        if role == USER_ROLES.SYSTEM_ADMIN:
            filters.append(f'{path} eq "{config.GROUPS.id_patterns.system_admin}"')
            continue
        prefix, suffix = id_patterns[role]
        filters.append(f'{path} sw "{prefix}" and {path} ew "{suffix}"')

    if USER_ROLES.SYSTEM_ADMIN not in roles:
        return (
            f'{path} ne "{config.GROUPS.id_patterns.system_admin}" and ('
            + " or ".join(filters)
            + ")"
        )

    return " or ".join(filters)


def _all_repository_specified_group_filter(path: str, group_ids: list[str]) -> str:
    """Generate a filter string.

    Filter by exact match for group IDs without specifying a repository.
    """
    if path == "id":
        return " or ".join([f'{path} eq "{group_id}"' for group_id in group_ids])
    return (
        f'{path} ne "{config.GROUPS.id_patterns.system_admin}" and ('
        + " or ".join([f'{path} eq "{group_id}"' for group_id in group_ids])
        + ")"
    )


def _all_repository_specified_role_specified_group_filter(
    path: str, roles: list[USER_ROLES], group_ids: list[str]
) -> str:
    """Generate a filter string.

    Filter by exact match for group IDs and prefix/suffix match for role-type group IDs.
    """
    groups_filter = _all_repository_specified_group_filter(path, group_ids)
    roles_filter = _all_repository_specified_role_filter(path, roles)

    return " and ".join([f"({groups_filter})", f"({roles_filter})"])


def _specified_repository_all_group_filter(path: str, repository_ids: list[str]) -> str:
    """Generate a filter string.

    Filter by prefix match for group IDs within specified repositories.
    """
    prefix_patterns = _get_prefix_patterns()
    if path == "id":
        return " or ".join([
            f'{path} sw "{prefix}{repo_id}"'
            for prefix in prefix_patterns
            for repo_id in repository_ids
        ])
    return (
        f'{path} ne "{config.GROUPS.id_patterns.system_admin}" and ('
        + " or ".join([
            f'{path} sw "{prefix}{repo_id}"'
            for prefix in prefix_patterns
            for repo_id in repository_ids
        ])
        + ")"
    )


def _specified_repository_specified_role_filter(
    path: str, repository_ids: list[str], roles: list[USER_ROLES]
) -> str:
    """Generate a filter string.

    Filter by exact match for role-type group IDs within specified repositories.
    """
    if not roles:
        return _empty_filter(path)

    filters: list[str] = []
    for role in roles:
        if role == USER_ROLES.SYSTEM_ADMIN:
            # System admin groups do not belong to any repository
            filters.append(_empty_filter(path))
            continue
        pattern = config.GROUPS.id_patterns[role]
        filters.extend(
            f'{path} eq "{pattern.format(repository_id=repo_id)}"'
            for repo_id in repository_ids
        )

    return (
        f'{path} ne "{config.GROUPS.id_patterns.system_admin}" and ('
        + " or ".join(filters)
        + ")"
    )


def _specified_repository_specified_group_filter(
    path: str, repository_ids: list[str], group_ids: list[str]
) -> str:
    """Generate a filter string.

    Filter by exact match for group IDs within specified repositories.
    """
    _, groups = detect_affiliations(group_ids)
    # filter by repository IDs that the specified group belongs to
    filtered_groups = [aff for aff in groups if aff.repository_id in repository_ids]
    if filtered_groups:
        if path == "id":
            return " or ".join([f'{path} eq "{g.group_id}"' for g in filtered_groups])
        return (
            f'{path} ne "{config.GROUPS.id_patterns.system_admin}" and ('
            + " or ".join([f'{path} eq "{g.group_id}"' for g in filtered_groups])
            + ")"
        )

    return _empty_filter(path)


def _specified_repository_specified_role_specified_group_filter(
    path: str, repository_ids: list[str], roles: list[USER_ROLES], group_ids: list[str]
) -> str:
    """Generate a filter string.

    Filter by exact match for group IDs and role-type group IDs within specified
    repositories.
    """
    groups_filter = _specified_repository_specified_group_filter(
        path, repository_ids, group_ids
    )
    roles_filter = _specified_repository_specified_role_filter(
        path, repository_ids, roles
    )
    if (empty_filter := _empty_filter(path)) in {groups_filter, roles_filter}:
        return empty_filter

    return " and ".join([f"{groups_filter}", f"{roles_filter}"])


def _empty_filter(path: str) -> str:
    """Generate a filter string that matches no results."""
    return f'{path} eq ""'


@cache
def _get_id_prefix() -> str:
    """Get group ID prefix for user-defined groups.

    The return value of this is cached.

    Returns:
        str: The group ID prefix for user-defined groups.
    """
    id_pattern = config.REPOSITORIES.id_patterns.sp_connector
    match = re.match(r"(.*)\{repository_id\}(.*)", id_pattern)
    if not match:
        error = E.INVALID_SERVER_CONFIG
        current_app.logger.error(error)
        raise ConfigurationError(error)

    return match.group(1)


@cache
def _get_prefix_patterns() -> set[str]:
    """Get group ID prefix patterns for all group types.

    The return value of this is cached.

    Returns:
        set: A set of group ID prefix patterns.
    """
    id_patterns = config.GROUPS.id_patterns
    pattern = r"(.*)\{repository_id\}(.*)"
    return {
        match.group(1)
        for group_types in t.cast(
            "set[USER_ROLES | t.Literal['user_defined']]", id_patterns.model_fields_set
        )
        if (match := re.match(pattern, id_patterns[group_types]))
    }


@cache
def _get_id_patterns() -> dict[str, tuple[str, str]]:
    """Get group ID patterns for each group type without sytem admin.

    The return value of this is cached.

    Returns:
        dict: A dictionary mapping group types to their (prefix, suffix) patterns.
    """
    id_patterns = config.GROUPS.id_patterns
    pattern = r"(.*)\{repository_id\}(.*)"
    return {
        group_types: (match.group(1), match.group(2))
        for group_types in t.cast(
            "set[USER_ROLES | t.Literal['user_defined']]", id_patterns.model_fields_set
        )
        if (match := re.match(pattern, id_patterns[group_types]))
    }


def _combine_filter_exprs(filter_exprs: list[str]) -> str | None:
    """Combine multiple filter expressions into a single filter string.

    If only one expression is present, it is returned as is. Otherwise, expressions
    are combined using logical AND, with each expression enclosed in parentheses.

    Args:
        filter_exprs (list[str]): List of filter expressions.

    Returns:
        str: The combined filter string, or None if no expressions are provided.

    """
    if len(filter_exprs) == 1 and "or" not in filter_exprs[0]:
        return filter_exprs[0]
    return " and ".join(f"({expr})" for expr in filter_exprs) if filter_exprs else None


class _Options(t.NamedTuple):
    start_index: int | None
    page_count: int | None
    sort_by: str | None
    sort_order: t.Literal["ascending", "descending"] | None


def _curculate_options(  # ruff: ignore[complex-structure]
    criteria: Criteria, path_generator: t.Callable[[str], str]
) -> _Options:
    """Calculate search options from criteria.

    Args:
        criteria (Criteria): The criteria object.
        path_generator (Callable[[str], str]):
            A function to generate attribute paths.

    Returns:
        Options:
            The calculated search options that is, (`start_index`, `page_size`,
            `sort_by`, `sort_order`).
    """

    def _a(ks: set[str]) -> set[str]:
        return ks | {path_generator(k) for k in ks}

    if criteria.k in _a({"emails", "entity_ids"}):
        sort_by = path_generator(f"{criteria.k}.value")
    elif criteria.k in _a({"eppns", "edu_person_principal_names"}):
        sort_by = path_generator("edu_person_principal_names.value")
    elif criteria.k in _a(
        repository_sortable_keys | group_sortable_keys | user_sortable_keys
    ):
        sort_by = path_generator(criteria.k)
    else:
        sort_by = None

    match criteria.d:
        case "asc":
            sort_order = "ascending"
        case "desc":
            sort_order = "descending"
        case _:
            sort_order = None

    match (criteria.p, criteria.l):
        case (int() as p, int() as l) if p > 0 and l > 0:
            # positive p and positive l; calculate pagination params.
            page_count, start_index = l, (p - 1) * l + 1
        case (int() as p, None) if p > 0:
            # positive p and unspecified l; using default page size.
            page_count = MAP_DEFAULT_SEARCH_COUNT
            start_index = (p - 1) * MAP_DEFAULT_SEARCH_COUNT + 1
        case (_, int() as l) if l >= 0:
            # invalid p and non-negative l; only use page size.
            page_count, start_index = l, None
        case (_, None):
            # invalid p and unspecified l; applying only the default page size.
            page_count, start_index = MAP_DEFAULT_SEARCH_COUNT, None
        case _:
            # negative l; ignore pagination parames. search all results.
            page_count, start_index = None, None

    return _Options(
        start_index=start_index,
        page_count=page_count,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def _patch_falsey_to_none[T: Criteria](value: T, attr: set[str]) -> T:
    """Patch falsey attribute values to None in the criteria object."""
    for key in attr:
        if hasattr(value, key) and not getattr(value, key):
            setattr(value, key, None)
    return value


def jst_date_to_utc_datetime(d: date) -> datetime:
    """Convert a date in JST to a datetime in UTC.

    Args:
        d (date): The date.

    Returns:
        datetime: The corresponding datetime in UTC.

    """
    dt_jst = datetime.combine(d, datetime.min.time(), tzinfo=ZoneInfo("Asia/Tokyo"))
    return dt_jst.astimezone(ZoneInfo("UTC"))


class Criteria(t.Protocol):
    """Protocol for search criteria."""

    q: t.Annotated[str | None, "search term"]
    """Search term to filter results."""

    i: t.Annotated[list[str] | None, "resource IDs"]
    """Filter by IDs."""

    k: t.Annotated[str | None, "sort attribute key"]
    """Attribute key to sort results."""

    d: t.Annotated[t.Literal["asc", "desc"] | None, "sort order"]
    """Sort order: 'asc' (ascending) or 'desc' (descending)."""

    p: t.Annotated[int | None, "page number"]
    """Page number to retrieve."""

    l: t.Annotated[int | None, "page size"]  # ruff: ignore[ambiguous-variable-name]
    """Page size (number of items per page)."""


@runtime_checkable
class RepositoriesCriteria(Criteria, t.Protocol):
    """Protocol for repository search criteria."""


@runtime_checkable
class GroupsCriteria(Criteria, t.Protocol):
    """Protocol for group search criteria."""

    r: t.Annotated[list[str] | None, "affiliated repository IDs"]
    """Filter by affiliated repository IDs."""

    u: t.Annotated[list[str] | None, "affiliated user IDs"]
    """Filter by affiliated user IDs."""

    s: t.Annotated[t.Literal[0, 1] | None, "public status"]
    """Filter by public status: 0 (public), 1 (private)."""

    v: t.Annotated[t.Literal[0, 1, 2] | None, "member list visibility"]
    """Filter by member list visibility: 0 (public), 1 (private), 2 (hidden)."""


@runtime_checkable
class UsersCriteria(Criteria, t.Protocol):
    """Protocol for user search criteria."""

    r: t.Annotated[list[str] | None, "affiliated repository IDs"]
    """Filter by affiliated repository IDs."""

    g: t.Annotated[list[str] | None, "affiliated group IDs"]
    """Filter by affiliated group IDs."""

    a: t.Annotated[list[int] | None, "user roles"]
    """Filter by user roles:

    0 (system admin), 1 (repository admin), 2 (community admin),
    3 (contributor), 4 (general user).
    """

    s: t.Annotated[date | None, "last modified date (from)"]
    """Filter by last modified date (from)."""

    e: t.Annotated[date | None, "last modified date (to)"]
    """Filter by last modified date (to)."""


class ExportUsersCriteria(UsersCriteria, t.Protocol):
    """Protocol for user export criteria."""

    f: t.Annotated[t.Literal["tsv", "csv"], "format"]
    """File format for export."""


type RepositoriesSortableKeys = t.Literal[
    "id", "service_name", "service_url", "entity_ids"
]
repository_sortable_keys: set[str] = set(get_args(RepositoriesSortableKeys.__value__))

type GroupsSortableKeys = t.Literal[
    "id", "display_name", "public", "member_list_visibility"
]
group_sortable_keys: set[str] = set(get_args(GroupsSortableKeys.__value__))

type UsersSortableKeys = t.Literal[
    "id", "user_name", "emails", "eppns", "last_modified"
]
user_sortable_keys: set[str] = set(get_args(UsersSortableKeys.__value__))


@t.overload
def make_criteria_object(
    resource_type: t.Literal["repositories"],
    *,
    q: str | None = None,
    i: list[str] | None = None,
    k: RepositoriesSortableKeys | None = None,
    d: t.Literal["asc", "desc"] | None = None,
    p: int | None = None,
    l: int | None = None,  # ruff: ignore[ambiguous-variable-name]
    super: bool = False,
) -> RepositoriesCriteria: ...
@t.overload
def make_criteria_object(
    resource_type: t.Literal["groups"],
    *,
    q: str | None = None,
    i: list[str] | None = None,
    r: list[str] | None = None,
    u: list[str] | None = None,
    s: t.Literal[0, 1] | None = None,
    v: t.Literal[0, 1, 2] | None = None,
    k: GroupsSortableKeys | None = None,
    d: t.Literal["asc", "desc"] | None = None,
    p: int | None = None,
    l: int | None = None,  # ruff: ignore[ambiguous-variable-name]
    super: bool = False,
) -> GroupsCriteria: ...
@t.overload
def make_criteria_object(
    resource_type: t.Literal["users"],
    *,
    q: str | None = None,
    i: list[str] | None = None,
    r: list[str] | None = None,
    g: list[str] | None = None,
    a: list[int] | None = None,
    s: date | None = None,
    e: date | None = None,
    k: UsersSortableKeys | None = None,
    d: t.Literal["asc", "desc"] | None = None,
    p: int | None = None,
    l: int | None = None,  # ruff: ignore[ambiguous-variable-name]
    super: bool = False,
) -> UsersCriteria: ...
def make_criteria_object(
    resource_type: t.Literal["repositories", "groups", "users"], **kwargs: t.Any
) -> Criteria:
    """Create an instance of a criteria protocol with specified attributes.

    Repositories query attributes:
        - q: search term
        - i: list of repository IDs

    Groups query attributes:
        - q: search term
        - i: list of group IDs
        - r: list of affiliated repository IDs
        - u: list of affiliated user IDs
        - s: public status (0: public, 1: private)
        - v: member list visibility (0: public, 1: private, 2: hidden)

    Users query attributes:
        - q: search term
        - i: list of user IDs
        - r: list of affiliated repository IDs
        - g: list of affiliated group IDs
        - a: list of user roles (0: system admin, 1: repository admin, \
            2: community admin, 3: contributor, 4: general user)
        - s: last modified date (from)
        - e: last modified date (to)

    Common attributes:
        - k: sort attribute key
        - d: sort direction ("asc" or "desc")
        - p: page number
        - l: page size
        - super: force search as system admin

    Args:
        resource_type (str): The type of resource ("users", "groups", "repositories").
        **kwargs: Attribute values to set in the criteria instance.

    Returns:
        Criteria: The created criteria instance.
    """
    match resource_type:
        case "users":
            protocol_cls = UsersCriteria
        case "groups":
            protocol_cls = GroupsCriteria
        case "repositories":
            protocol_cls = RepositoriesCriteria
        case _:
            error = E.UNRECOGNIZED_SEARCH_CRITERIA
            raise InvalidQueryError(error)

    hints = get_type_hints(protocol_cls)

    attrs = dict.fromkeys(hints)
    for key, value in kwargs.items():
        attrs[key] = value

    return t.cast("Criteria", SimpleNamespace(**attrs))


class HistoryCriteria(t.Protocol):
    """Protocol for history search criteria."""

    i: t.Annotated[str | None, "history ID (parent ID)"]
    """Filter by parent history ID."""

    r: t.Annotated[list[str] | None, "repository IDs"]
    """Filter by repository IDs."""

    g: t.Annotated[list[str] | None, "group IDs"]
    """Filter by group IDs."""

    u: t.Annotated[list[str] | None, "user IDs"]
    """Filter by user IDs."""

    o: t.Annotated[list[str] | None, "operator user IDs"]
    """Filter by operator user IDs."""

    s: t.Annotated[date | None, "last modified date (from)"]
    """Filter by last modified date (from)."""

    e: t.Annotated[date | None, "last modified date (to)"]
    """Filter by last modified date (to)."""

    d: t.Annotated[t.Literal["asc", "desc"] | None, "sort order"]
    """Sort order: 'asc' (ascending) or 'desc' (descending)."""

    p: t.Annotated[int | None, "page number"]
    """Page number to retrieve."""

    l: t.Annotated[int | None, "page size"]  # ruff: ignore[ambiguous-variable-name]
    """Page size (number of items per page)."""


class OperatorsCriteria(t.Protocol):
    """Protocol for operator search criteria."""

    q: t.Annotated[str | None, "query"] = None
    """Search term to filter operators."""

    p: t.Annotated[int | None, "page number"] = None
    """Page number to retrieve."""

    l: t.Annotated[int | None, "page size"] = None  # ruff: ignore[ambiguous-variable-name]
    """Page size (number of items per page)."""


class GroupCacheCriteria(t.Protocol):
    """Protocol for group cache search criteria."""

    q: t.Annotated[str | None, "term"] = None
    """Search term for querying cache entries."""

    f: t.Annotated[list[GroupCacheFilter] | None, "filter"] = None
    """Filter expression for querying cache entries. "e" and "n" can be used."""

    p: t.Annotated[int | None, "page"] = None
    """Page number for pagination."""

    l: t.Annotated[int | None, "per"] = None  # ruff: ignore[ambiguous-variable-name]
    """Number of items per page for pagination."""


type GroupCacheFilter = t.Literal["e", "n"]
"""Group cache filter options:
    - "e": Filter existing cache entries.
    - "n": Filter non-existent cache entries.
"""

type GroupCacheOperation = t.Literal["all", "id-specified"]
"""Group cache operation options:
    - "all": Update all cache entries.
    - "id-specified": Update cache entries by specified IDs.
"""
