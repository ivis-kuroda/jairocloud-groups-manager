import pytest

from server.const import USER_ROLES
from server.services.utils.roles import get_highest_role


params = {
    "forward": (
        # when the roles are in order of highest to lowest, the function should return the first role
        [USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.COMMUNITY_ADMIN],
        USER_ROLES.SYSTEM_ADMIN,
    ),
    "reverse": (
        # when the roles are in order of lowest to highest, the function should return the last role
        [USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.SYSTEM_ADMIN],
        USER_ROLES.SYSTEM_ADMIN,
    ),
    "repository_admin": (
        # when the roles contain multiple roles, the function should return the highest role
        [USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.GENERAL_USER],
        USER_ROLES.REPOSITORY_ADMIN,
    ),
    "community_admin": (
        # when the roles contain multiple roles not in order, the function should return the highest role
        [USER_ROLES.CONTRIBUTOR, USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.GENERAL_USER],
        USER_ROLES.COMMUNITY_ADMIN,
    ),
    "contributor": (
        # when the roles contain multiple roles, the function should return the highest role
        [USER_ROLES.CONTRIBUTOR, USER_ROLES.GENERAL_USER],
        USER_ROLES.CONTRIBUTOR,
    ),
    "general_user": (
        # when the roles contain multiple roles, the function should return the highest role
        [USER_ROLES.GENERAL_USER, USER_ROLES.GENERAL_USER],
        USER_ROLES.GENERAL_USER,
    ),
    "single": (
        # when the roles contain only one role, the function should return that role
        [USER_ROLES.REPOSITORY_ADMIN],
        USER_ROLES.REPOSITORY_ADMIN,
    ),
    "duplicate": (
        # when the roles contain duplicate roles, the function should return the highest role
        [USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.CONTRIBUTOR, USER_ROLES.REPOSITORY_ADMIN],
        USER_ROLES.REPOSITORY_ADMIN,
    ),
    "empty": (
        # when the roles are empty, the function should return None
        [],
        None,
    ),
}


@pytest.mark.parametrize(("roles", "expected"), params.values(), ids=params.keys())
def test_get_highest_role(roles: list[USER_ROLES], expected: USER_ROLES | None):
    result = get_highest_role(roles)
    assert result == expected


def test_get_highest_role_invalid_raises():
    with pytest.raises(ValueError, match="not in list"):
        get_highest_role(["UNKNOWN"])  # pyright: ignore[reportArgumentType]
