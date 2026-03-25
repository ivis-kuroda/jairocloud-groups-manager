#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Detect affiliations from group IDs."""

import re
import typing as t

from collections import defaultdict
from functools import cache

from server.config import config
from server.const import USER_ROLES

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
    detect_affiliations = [
        detect for group_id in group_ids if (detect := detect_affiliation(group_id))
    ]

    aggregated: defaultdict[str | None, list[USER_ROLES]] = defaultdict(list)
    for detect in detect_affiliations:
        if detect.type == "role":
            aggregated[detect.repository_id].append(detect.role)

    return Affiliations(
        roles=[
            _RoleGroup(
                repository_id=repo_id,
                role=t.cast("USER_ROLES", get_highest_role(roles)),
            )
            for repo_id, roles in aggregated.items()
        ],
        groups=[aff for aff in detect_affiliations if aff.type == "group"],
    )


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
    combined_re = _build_combined_regex()
    match = combined_re.fullmatch(group_id)
    if not match:
        return None

    # Retrieve the name of the main group that matched (the role type)
    matched_role = match.lastgroup
    if not matched_role:
        return None  # pragma: no cover

    # Extract parameters by filtering groupdict keys with the role prefix
    params: dict[str, str] = {}
    prefix = f"{matched_role}__"
    for k, v in match.groupdict().items():
        if v is not None and k.startswith(prefix):
            original_param_name = k.replace(prefix, "")
            params[original_param_name] = v

    if matched_role not in USER_ROLES:
        return _Group(group_id=group_id, **params)  # pyright: ignore[reportArgumentType]

    return _RoleGroup(
        repository_id=params.get("repository_id"), role=USER_ROLES(matched_role)
    )


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
    repository_id: str
    group_id: str
    user_defined_id: str
    type: t.Literal["group"] = "group"


@cache
def _build_combined_regex() -> re.Pattern[str]:
    combined_parts = []
    for key, fmt in config.GROUPS.id_patterns.model_dump().items():
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


def detect_repository(services: list[Service]) -> Service | None:
    """Detect the affiliated repositor.

    Retrieve the first affiliated repository from the given list of services.

    Args:
        services (list): List of services to analyze.

    Returns:
        Service:
            Detected affiliated repository, otherwise None.
    """
    return next(
        (s for s in services if resolve_repository_id(service_id=s.value)), None
    )
