#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Detect affiliations from group IDs."""

import re
import typing as t

from functools import cache

from server.config import config
from server.const import IS_MEMBER_OF_PATTERN, USER_ROLES

from .resolvers import resolve_repository_id
from .roles import get_highest_role


if t.TYPE_CHECKING:
    from server.entities.map_group import Service


def detect_affiliations(group_ids: list[str]) -> Affiliations:
    """Detect affiliations for the given list of group IDs.

    Verify each group ID and determine whether it is role-type group
    or user-defined group. Aggregate the results accordingly.

    Args:
        group_ids (list[str]): List of group IDs.

    Returns:
        Affiliations:
            Detected affiliations including `roles` and `groups`.
            - roles: list of role-type groups.
              that is, (`repository_id`, `roles`, `type`="role")
            - groups: list of user-defined groups
              that is, (`repository_id`, `group_id`, `user_defined_id`, `type`="group").
    """
    detected_affiliations = [d for gid in group_ids if (d := detect_affiliation(gid))]

    groups: list[_Group] = []
    roles_by_repository: dict[str | None, _RoleGroup] = {}

    for affil in detected_affiliations:
        if affil.type == "group":
            groups.append(affil)
            continue

        current = roles_by_repository.get(affil.repository_id)
        if current is None:
            roles_by_repository[affil.repository_id] = affil
            continue

        highest_role = get_highest_role([current.role, affil.role])
        if highest_role == affil.role:
            roles_by_repository[affil.repository_id] = affil

    return Affiliations(list(roles_by_repository.values()), groups)


def detect_affiliation(group_id: str) -> Affiliation | None:
    """Detect the affiliation of a single group ID.

    Verify the group ID and determine whether it is role-type group
    or user-defined group.

    Args:
        group_id (str): The group ID to analyze.

    Returns:
        Affiliation:
            Detected affiliation information, otherwise None. <br>
            - if the group is role-type group, returns
              (`repository_id`, `roles`, `type`="role").
            - if the group is user-defined group, returns
              (`repository_id`, `group_id`, `user_defined_id`, `type`="group").

    """
    combined_re = __build_combined_regex()
    match = combined_re.fullmatch(group_id)
    if not match or not (matched := match.lastgroup):
        return None

    # Extract parameters by filtering groupdict keys with the role prefix
    params: dict[str, str] = {}
    prefix = f"{matched}__"
    for k, v in match.groupdict().items():
        if v is not None and k.startswith(prefix):
            param_name = k.replace(prefix, "")
            params[param_name] = v

    if matched not in USER_ROLES:
        return _Group(group_id, type="group", **params)

    return _RoleGroup(params.get("repository_id"), USER_ROLES(matched), type="role")


class Affiliations(t.NamedTuple):
    """Detected affiliations including roles and groups."""

    roles: list[_RoleGroup]
    groups: list[_Group]


type Affiliation = _RoleGroup | _Group


class _RoleGroup(t.NamedTuple):
    repository_id: str | None
    role: USER_ROLES
    type: t.Literal["role"] = "role"


class _Group(t.NamedTuple):
    group_id: str
    repository_id: str
    user_defined_id: str
    type: t.Literal["group"] = "group"


@cache
def __build_combined_regex() -> re.Pattern[str]:
    combined_parts = []
    for key, fmt in config.GROUPS.id_patterns:
        # Replace {variable} with a named capturing group (?P<key__variable>.+?)
        # k=key captures the current loop value to avoid binding issues
        # .+? allows underscores while matching until the next fixed delimiter
        regex_part = re.sub(
            r"\{(\w+)\}",
            lambda m, k=key: f"(?P<{k}__{m.group(1)}>.+?)",
            fmt,
        )
        # Wrap each pattern in a main named group to identify the matched type
        combined_parts.append(f"(?P<{key}>{regex_part})")

    # Combine all patterns into one large regex using the OR (|) operator
    return re.compile("|".join(combined_parts))


def parse_affiliated_group_ids(is_member_of: str) -> list[str]:
    """Parse group id from isMemberOf attribute string.

    Only extract group IDs that match the expected pattern for affiliated groups.
    Groups that have '/admin' suffix are excluded from the results.

    Args:
        is_member_of (str): isMemberOf attribute of the login user

    Returns:
        list[str]: List of group IDs to which the login user belongs.
    """
    return re.findall(IS_MEMBER_OF_PATTERN, is_member_of)


def detect_affiliations_from_is_member_of(is_member_of: str) -> Affiliations:
    """Detect affiliations from the isMemberOf attribute string.

    Args:
        is_member_of (str): isMemberOf attribute of the login user

    Returns:
        Affiliations:
            Detected affiliations including `roles` and `groups`.
            - roles: list of role-type groups.
              that is, (`repository_id`, `roles`, `type`="role")
            - groups: list of user-defined groups
              that is, (`repository_id`, `group_id`, `user_defined_id`, `type`="group").
    """
    group_ids = parse_affiliated_group_ids(is_member_of)
    return detect_affiliations(group_ids)


def detect_affiliated_repository(services: list[Service]) -> Service | None:
    """Detect the affiliated repository.

    Retrieve the first affiliated repository from the given list of services.

    Args:
        services (list): List of services to analyze.

    Returns:
        Service | None:
            Detected affiliated repository, otherwise None.
    """
    return next(
        (s for s in services if resolve_repository_id(service_id=s.value)), None
    )
