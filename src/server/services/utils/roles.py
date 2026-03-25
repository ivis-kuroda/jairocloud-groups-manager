#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utility functions for role handling."""

from server.const import USER_ROLES


def get_highest_role(roles_list: list[USER_ROLES]) -> USER_ROLES | None:
    """Get the highest role from a list of roles.

    Args:
        roles_list (list of str): List of role names.

    Returns:
        str: The highest role based on predefined hierarchy.
    """
    if not roles_list:
        return None

    role_order = list(USER_ROLES)

    return min(roles_list, key=role_order.index)
