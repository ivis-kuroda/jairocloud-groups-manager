import typing as t

import pytest

import server.services.utils.affiliations

from server.const import USER_ROLES
from server.services.utils.affiliations import (
    detect_affiliated_repository,
    detect_affiliation,
    detect_affiliations,
    parse_affiliated_group_ids,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockFixture

    from server.config import RuntimeConfig


def test_detect_affiliations(config: RuntimeConfig):
    patterns = config.GROUPS.id_patterns
    repository_id, user_defined_id = "test_repo_ac_jp", "detection_sample"

    group_ids = [
        patterns[USER_ROLES.REPOSITORY_ADMIN].format(repository_id=repository_id),
        patterns["user_defined"].format(repository_id=repository_id, user_defined_id=user_defined_id),
    ]

    detected = detect_affiliations(group_ids)

    assert len(detected.roles) == 1
    assert len(detected.groups) == 1

    assert (repository_admin := next(r for r in detected.roles if r.role == USER_ROLES.REPOSITORY_ADMIN))
    assert repository_admin.type == "role"
    assert repository_admin.repository_id == repository_id

    assert (user_defined_group := next(g for g in detected.groups if g.user_defined_id == user_defined_id))
    assert user_defined_group.type == "group"
    assert user_defined_group.repository_id == repository_id


@pytest.mark.parametrize("sort", ["asc", "desc"])
def test_detect_affiliations_multiple_roles(sort, config: RuntimeConfig):
    patterns = config.GROUPS.id_patterns
    repository_id, user_defined_id = "test_repo_ac_jp", "detection_sample"
    roles = [USER_ROLES.COMMUNITY_ADMIN, USER_ROLES.CONTRIBUTOR]
    roles.sort(reverse=(sort == "desc"))
    # when sort == "asc", first role (COMMUNITY_ADMIN) is preferred over the second role (CONTRIBUTOR).
    # when sort == "desc", first role (CONTRIBUTOR) is overridden by the second role (COMMUNITY_ADMIN).
    group_ids = [
        patterns[roles[0]].format(repository_id=repository_id),
        patterns[roles[1]].format(repository_id=repository_id),
        patterns["user_defined"].format(repository_id=repository_id, user_defined_id=user_defined_id),
    ]

    detected = detect_affiliations(group_ids)

    assert len(detected.roles) == 1
    assert len(detected.groups) == 1

    assert (community_admin := next(r for r in detected.roles if r.role == USER_ROLES.COMMUNITY_ADMIN))
    assert community_admin.type == "role"
    assert community_admin.repository_id == repository_id

    assert next(g for g in detected.groups if g.user_defined_id == user_defined_id)


def test_detect_affiliations_multiple_repositories(config: RuntimeConfig):
    patterns = config.GROUPS.id_patterns
    num_repo = 2
    repository_ids = [f"test_{i}_repo_ac_jp" for i in range(1, num_repo + 1)]
    group_ids = [patterns[USER_ROLES.CONTRIBUTOR].format(repository_id=repository_ids[i]) for i in range(num_repo)]

    detected = detect_affiliations(group_ids)

    assert len(detected.roles) == num_repo
    assert not detected.groups

    assert next(r for r in detected.roles if r.repository_id == repository_ids[0])
    assert next(r for r in detected.roles if r.repository_id == repository_ids[1])


def test_detect_affiliations_multiple_groups(config: RuntimeConfig):
    patterns = config.GROUPS.id_patterns
    num_groups = 2
    repository_id = "test_repo_ac_jp"
    user_defined_ids = [f"detection_sample_{i}" for i in range(1, num_groups + 1)]
    group_ids = [
        patterns["user_defined"].format(repository_id=repository_id, user_defined_id=user_defined_ids[i])
        for i in range(num_groups)
    ]

    detected = detect_affiliations(group_ids)

    assert not detected.roles
    assert len(detected.groups) == num_groups

    assert next(g for g in detected.groups if g.user_defined_id == user_defined_ids[0])
    assert next(g for g in detected.groups if g.user_defined_id == user_defined_ids[1])


def test_detect_affiliation_role_system_admin(config: RuntimeConfig):
    group_id = config.GROUPS.id_patterns[USER_ROLES.SYSTEM_ADMIN]

    detected = detect_affiliation(group_id)

    assert detected is not None
    assert detected.type == "role"
    assert detected.repository_id is None
    assert detected.role == USER_ROLES.SYSTEM_ADMIN


@pytest.mark.parametrize("role", [role for role in USER_ROLES if role != USER_ROLES.SYSTEM_ADMIN])
def test_detect_affiliation_role(role, config: RuntimeConfig):
    pattern = config.GROUPS.id_patterns[role]
    repository_id = "test_repo_ac_jp"
    group_id = pattern.format(repository_id=repository_id)

    detected = detect_affiliation(group_id)

    assert detected is not None
    assert detected.type == "role"
    assert detected.repository_id == repository_id
    assert detected.role == role


def test_detect_affiliation_group(config: RuntimeConfig):
    pattern = config.GROUPS.id_patterns["user_defined"]
    repository_id, user_defined_id = "test_repo_ac_jp", "detection_sample"
    group_id = pattern.format(repository_id=repository_id, user_defined_id=user_defined_id)

    detected = detect_affiliation(group_id)

    assert detected is not None
    assert detected.type == "group"
    assert detected.repository_id == repository_id
    assert detected.group_id == group_id
    assert detected.user_defined_id == user_defined_id


def test_detect_affiliation_no_match(config):
    detected = detect_affiliation("non_following_pattern_group")

    assert detected is None


def test_parse_affiliated_group_ids(test_config: RuntimeConfig):
    patterns = test_config.GROUPS.id_patterns
    uri = "https://cg.gakunin.jp/gr/{group_id}"
    group_ids = [
        patterns.repository_admin.format(repository_id="test_1_repo_ac_jp"),
        patterns.contributor.format(repository_id="test_2_repo_ac_jp"),
    ]
    is_member_of = ";".join(uri.format(group_id=gid) for gid in group_ids)

    result = parse_affiliated_group_ids(is_member_of)

    assert result == group_ids


def test_parse_affiliated_group_ids_include_admin(test_config: RuntimeConfig):
    patterns = test_config.GROUPS.id_patterns
    uri = "https://cg.gakunin.jp/gr/{group_id}"
    group_ids = [
        # group that has admin suffix should be ignored.
        f"{patterns.repository_admin.format(repository_id='test_1_repo_ac_jp')}/admin",
        patterns.system_admin,
    ]
    is_member_of = ";".join(uri.format(group_id=gid) for gid in group_ids)

    result = parse_affiliated_group_ids(is_member_of)

    assert result == [group_ids[1]]  # only non-suffix group.


def test_detect_affiliated_repository(map_groups, mocker: MockFixture):
    service = map_groups[0].services[0]
    repository_id = "test_repo_ac_jp"
    mocker.patch.object(server.services.utils.affiliations, "resolve_repository_id", return_value=repository_id)

    result = detect_affiliated_repository([service])
    assert result is service
