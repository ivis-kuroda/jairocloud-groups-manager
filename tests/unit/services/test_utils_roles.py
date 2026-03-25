import pytest

from server.const import USER_ROLES
from server.services.utils.roles import get_highest_role


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (
            [USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.COMMUNITY_ADMIN],
            USER_ROLES.SYSTEM_ADMIN,
        ),
        (
            [USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.SYSTEM_ADMIN],
            USER_ROLES.SYSTEM_ADMIN,
        ),
        (
            [USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.GENERAL_USER],
            USER_ROLES.REPOSITORY_ADMIN,
        ),
        (
            [USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.CONTRIBUTOR, USER_ROLES.GENERAL_USER],
            USER_ROLES.COMMUNITY_ADMIN,
        ),
        (
            [USER_ROLES.CONTRIBUTOR, USER_ROLES.GENERAL_USER],
            USER_ROLES.CONTRIBUTOR,
        ),
        (
            [USER_ROLES.GENERAL_USER, USER_ROLES.GENERAL_USER],
            USER_ROLES.GENERAL_USER,
        ),
        (
            [USER_ROLES.REPOSITORY_ADMIN],
            USER_ROLES.REPOSITORY_ADMIN,
        ),
        (
            [USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.REPOSITORY_ADMIN, USER_ROLES.REPOSITORY_ADMIN],
            USER_ROLES.REPOSITORY_ADMIN,
        ),
        ([], None),
    ],
    ids=[
        "original_order",
        "inverse_order",
        "repository_admin",
        "community_admin",
        "contributor",
        "general_user",
        "single",
        "duplicate",
        "empty_list",
    ],
)
def test_get_highest_role(roles, expected):
    actual = get_highest_role(roles)
    assert actual == expected


def test_get_highest_role_invalid_raises():
    with pytest.raises(ValueError, match="not in list"):
        get_highest_role(["UNKNOWN"])  # pyright: ignore[reportArgumentType]
