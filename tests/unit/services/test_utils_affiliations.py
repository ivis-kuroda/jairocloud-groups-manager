import pytest

from server.entities.map_group import Service
from server.services.utils.affiliations import (
    _build_combined_regex,
    _Group,
    _RoleGroup,
    detect_affiliation,
    detect_affiliations,
    detect_repository,
)


def test_detect_affiliations(app):
    group_ids = [
        "jc_roles_sysadm_test",  # sysado
        "jc_test_ac_jp_ro_radm_test",  # repoado
        "jc_test_ac_jp_ro_cadm_test",  # comado
        "jc_test_ac_jp_ro_cont_test",  # contributer
        "jc_test_ac_jp_ro_user_test",  # generaluser
        "jc_test_ac_jp_gr_test3_test",
    ]  # user

    result = detect_affiliations(group_ids)

    expected_repository_id_sys = None
    expected_ro_sys = ["system_admin"]
    expected_rolegroup_type = "role"

    expected_repository_id = "test_ac_jp"
    expected_roles = ["repository_admin", "community_admin", "contributor", "general_user"]

    expected_group_repository_id = "test_ac_jp"
    expected_group_id = "jc_test_ac_jp_gr_test3_test"
    expected_user_defined_id = "test3"
    expected_group_type = "group"
    expected_length = [2, 1]

    assert len(result.roles) == expected_length[0]
    assert len(result.groups) == expected_length[1]

    result_ro_0 = result.roles[0]
    assert result_ro_0.type == expected_rolegroup_type
    assert result_ro_0.repository_id == expected_repository_id_sys
    assert result_ro_0.role == expected_ro_sys[0]

    result_ro_1 = result.roles[1]
    assert result_ro_1.type == expected_rolegroup_type
    assert result_ro_1.repository_id == expected_repository_id
    assert sorted(result_ro_1.role) == sorted(expected_roles[0])

    result_groups_0 = result.groups[0]
    assert result_groups_0.type == expected_group_type
    assert result_groups_0.repository_id == expected_group_repository_id
    assert result_groups_0.group_id == expected_group_id
    assert result_groups_0.user_defined_id == expected_user_defined_id


def test_detect_affiliation_no_match(app):
    result = detect_affiliation("test1_ro_radm_test")
    expected = None
    assert result == expected


@pytest.mark.parametrize(
    ("group_id", "expected_repository_id", "expected_roles", "expected_type"),
    [
        ("jc_roles_sysadm_test", None, ["system_admin"], "role"),
        ("jc_test_ac_jp_ro_radm_test", "test_ac_jp", ["repository_admin"], "role"),
        ("jc_test_ac_jp_ro_cadm_test", "test_ac_jp", ["community_admin"], "role"),
        ("jc_test_ac_jp_ro_cont_test", "test_ac_jp", ["contributor"], "role"),
        ("jc_test_ac_jp_ro_user_test", "test_ac_jp", ["general_user"], "role"),
    ],
    ids=["sysadm", "radm", "cadm", "cont", "user"],
)
def test_detect_affiliation_role_group(app, group_id, expected_repository_id, expected_roles, expected_type):
    result = detect_affiliation(group_id)
    assert result is not None
    assert isinstance(result, _RoleGroup)
    assert result.repository_id == expected_repository_id
    assert result.role == expected_roles[0]
    assert result.type == expected_type


def test_detect_affiliation_group(app):
    expected_repository_id = "test_ac_jp"
    expected_group_id = "jc_test_ac_jp_gr_test3_test"
    expected_user_defined_id = "test3"
    expected_type = "group"

    result = detect_affiliation("jc_test_ac_jp_gr_test3_test")
    assert result is not None
    assert isinstance(result, _Group)
    assert result.repository_id == expected_repository_id
    assert result.group_id == expected_group_id
    assert result.user_defined_id == expected_user_defined_id
    assert result.type == expected_type


def test_build_combined_regex_sys(app):
    pattern = _build_combined_regex().pattern
    expected = "(?P<system_admin>jc_roles_sysadm_test)"

    assert expected in pattern


def test_build_combined_regex_repo(app):
    pattern = _build_combined_regex().pattern
    expected = "(?P<repository_admin>jc_(?P<repository_admin__repository_id>.+?)_ro_radm_test)"

    assert expected in pattern


def test_build_combined_regex_com(app):
    pattern = _build_combined_regex().pattern
    expected = "(?P<community_admin>jc_(?P<community_admin__repository_id>.+?)_ro_cadm_test)"

    assert expected in pattern


def test_build_combined_regex_con(app):
    pattern = _build_combined_regex().pattern
    expected = "(?P<contributor>jc_(?P<contributor__repository_id>.+?)_ro_cont_test)"

    assert expected in pattern


def test_build_combined_regex_gene(app):
    pattern = _build_combined_regex().pattern
    expected = "(?P<general_user>jc_(?P<general_user__repository_id>.+?)_ro_user_test)"

    assert expected in pattern


def test_build_combined_regex_user(app):
    pattern = _build_combined_regex().pattern
    expected = (
        "(?P<user_defined>jc_(?P<user_defined__repository_id>.+?)_gr_(?P<user_defined__user_defined_id>.+?)_test)"
    )

    assert expected in pattern


def test_build_combined_regex_len(app, test_config):
    pattern = _build_combined_regex().pattern
    patterns_config = test_config.GROUPS.id_patterns.model_dump()

    assert len(patterns_config) == len(pattern.split("|"))


def test_detect_repository_first_match_with_resolver_mock(mocker):
    """detect_repository returns the first Service when resolve_repository_id is mocked to match only the first."""
    service1 = Service(value="repo1")
    service2 = Service(value="repo2")
    services = [service1, service2]
    mocker.patch(
        "server.services.utils.affiliations.resolve_repository_id",
        side_effect=lambda service_id: "matched" if service_id == "repo1" else None,
    )
    result = detect_repository(services)
    assert result is service1
