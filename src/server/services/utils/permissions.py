#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Permission-related services for the server application."""

from flask_login import current_user

from server.auth import is_user_logged_in
from server.config import config
from server.const import USER_ROLES

from .affiliations import detect_affiliations, parse_affiliated_group_ids


def is_current_user_system_admin() -> bool:
    """Determine whether the logged-in user is a system administrator.

    Returns:
        bool: True if the logged-in user is a system administrator, False otherwise.
    """
    if not is_user_logged_in(current_user):
        return False

    group_ids = parse_affiliated_group_ids(current_user.is_member_of)
    return config.GROUPS.id_patterns.system_admin in group_ids


def get_permitted_repository_ids() -> set[str]:
    """Get the list of repository IDs the current user has permission to access.

    Detect roles of the current user and return the repository IDs where the user has
    the repository administrator role.
    If the user is a system administrator, return all repository IDs.

    Returns:
        set[str]: Set of current user's permitted repository IDs.
    """
    if not is_user_logged_in(current_user):
        return set()

    if current_user.is_system_admin:
        return {"*"}

    is_member_of: str = current_user.is_member_of
    group_ids = parse_affiliated_group_ids(is_member_of)
    affiliated_roles, _ = detect_affiliations(group_ids)

    return {
        role.repository_id
        for role in affiliated_roles
        if role.repository_id and role.role == USER_ROLES.REPOSITORY_ADMIN
    }


def filter_permitted_group_ids(*group_ids: str) -> set[str]:
    """Check if the given group ID is manageable by the current user.

    Args:
        *group_ids (str): The group IDs.

    Returns:
        set[str]: Set of manageable group IDs.
    """
    if not is_user_logged_in(current_user):
        return set()

    if current_user.is_system_admin:
        return set(group_ids)

    repository_ids = get_permitted_repository_ids()
    _, affiliated_groups = detect_affiliations(list(group_ids))

    return {g.group_id for g in affiliated_groups if g.repository_id in repository_ids}
