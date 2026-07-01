import typing as t

from datetime import datetime
from uuid import uuid4

import pytest

from pydantic import AliasGenerator
from pydantic.alias_generators import to_camel

import server.services.utils.patch_operations

from server.const import USER_ROLES
from server.entities.map_group import MapGroup, MemberUser
from server.entities.map_user import EPPN, Email, MapUser
from server.entities.patch_request import (
    AddOperation,
    RemoveOperation,
    ReplaceOperation,
)
from server.exc import SystemAdminNotFound
from server.messages import E
from server.services.utils import patch_operations
from server.services.utils.patch_operations import (
    _diff,
    _select_fields,
    build_patch_operations,
    build_update_member_operations,
)

from tests.helpers import regex, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.entities.user_detail import UserDetail


@pytest.fixture(autouse=True)
def alias(mocker: MockerFixture):
    original = server.services.utils.patch_operations._a
    mock_alias = mocker.patch.object(server.services.utils.patch_operations, "_a", side_effect=lambda _, x: x)

    return original, mock_alias


@pytest.fixture
def original_alias(alias):
    original, _ = alias
    server.services.utils.patch_operations._a = original

    return original


def test_build_patch_operations(map_users, mocker: MockerFixture):
    base: MapUser = map_users[USER_ROLES.CONTRIBUTOR]
    head = base.model_copy(
        update={
            "user_name": f"Updated {base.user_name}",
        },
        deep=True,
    )

    mock_diff = mocker.patch.object(server.services.utils.patch_operations, "_diff")
    mock_diff.return_value = expected = [ReplaceOperation(path="user_name", value=head.user_name)]

    result = build_patch_operations(base, head)

    assert result == expected
    mock_diff.assert_called_once_with(MapUser, base, head, include=None, exclude=None)


def test_build_patch_operations_with_different_types(config, user_details):
    base: UserDetail = user_details[USER_ROLES.CONTRIBUTOR]
    head = base.to_map_user().model_copy(
        update={
            "user_name": f"updated_{base.user_name}",
        },
        deep=True,
    )

    with pytest.raises(TypeError, match=regex(E.CANNOT_RESOLVE_DIFFERENCE)):
        build_patch_operations(base, head)


def test__diff_literal_add(map_users, mocker: MockerFixture):
    base: MapUser = map_users[USER_ROLES.CONTRIBUTOR]
    base.preferred_language = None
    head = base.model_copy(
        update={"preferred_language": (updated_language := "ja")},
        deep=True,
    )

    spy_literal_diff = mocker.spy(server.services.utils.patch_operations, "_handle_literal_diff")
    expected = [AddOperation(path="preferred_language", value=updated_language)]

    result = _diff(MapUser, base, head)

    assert len(result) == len(expected)
    assert next(op for op in result if op.path == "preferred_language") == expected[0]
    spy_literal_diff.assert_any_call(base.id, head.id, path="id")
    spy_literal_diff.assert_any_call(base.user_name, head.user_name, path="user_name")
    spy_literal_diff.assert_any_call(base.preferred_language, updated_language, path="preferred_language")


def test__diff_literal_remove(map_users, mocker: MockerFixture):
    base: MapUser = map_users[USER_ROLES.CONTRIBUTOR]
    base.external_id = uuid4().hex
    head = base.model_copy(
        update={"external_id": None},
        deep=True,
    )

    spy_literal_diff = mocker.spy(server.services.utils.patch_operations, "_handle_literal_diff")
    expected = [RemoveOperation(path="external_id")]

    result = _diff(MapUser, base, head)

    assert len(result) == len(expected)
    assert next(op for op in result if op.path == "external_id") == expected[0]
    spy_literal_diff.assert_any_call(base.external_id, head.external_id, path="external_id")


def test__diff_literal_replace(map_users, mocker: MockerFixture):
    base: MapUser = map_users[USER_ROLES.CONTRIBUTOR]
    head = base.model_copy(
        update={"user_name": (updated_user_name := f"Updated {base.user_name}")},
        deep=True,
    )

    spy_literal_diff = mocker.spy(server.services.utils.patch_operations, "_handle_literal_diff")
    expected = [ReplaceOperation(path="user_name", value=updated_user_name)]

    result = _diff(MapUser, base, head)

    assert len(result) == len(expected)
    assert next(op for op in result if op.path == "user_name") == expected[0]
    spy_literal_diff.assert_any_call(base.user_name, updated_user_name, path="user_name")


def test__diff_list_add(map_users, mocker: MockerFixture):
    base: MapUser = map_users[USER_ROLES.CONTRIBUTOR]
    assert base.emails
    head = base.model_copy(
        update={"emails": [*base.emails, added_email := Email(value="test-addition@example.com")]},
        deep=True,
    )

    spy_list_diff = mocker.spy(server.services.utils.patch_operations, "_handle_list_diff")
    expected = [AddOperation(path="emails", value=added_email)]

    result = _diff(MapUser, base, head)

    assert len(result) == len(expected)
    assert next(op for op in result if op.path == "emails") == expected[0]
    spy_list_diff.assert_any_call(base.emails, head.emails, path="emails")
    spy_list_diff.assert_any_call(
        base.edu_person_principal_names, head.edu_person_principal_names, path="edu_person_principal_names"
    )
    spy_list_diff.assert_any_call(base.groups, head.groups, path="groups")


def test__diff_list_remove(map_users, mocker: MockerFixture):
    base: MapUser = map_users[USER_ROLES.CONTRIBUTOR]
    assert base.edu_person_principal_names
    base.edu_person_principal_names.append(EPPN(value=(removed_eppn := "test-remove@@idp.example.com")))
    head = base.model_copy(
        update={"edu_person_principal_names": [*base.edu_person_principal_names[:-1]]},
        deep=True,
    )

    spy_list_diff = mocker.spy(server.services.utils.patch_operations, "_handle_list_diff")
    expected = [RemoveOperation(path=f'edu_person_principal_names[value eq "{removed_eppn}"]')]

    result = _diff(MapUser, base, head)

    assert len(result) == len(expected)
    assert next(op for op in result if op.path.startswith("edu_person_principal_names")) == expected[0]
    spy_list_diff.assert_any_call(
        base.edu_person_principal_names, head.edu_person_principal_names, path="edu_person_principal_names"
    )


def test__diff_list_typed_element(map_groups, mocker: MockerFixture):
    origin: MapGroup = map_groups[0]
    base = origin.model_copy(
        update={"members": [MemberUser(value=(removed_member_id := "removing_user_id"))]},
        deep=True,
    )
    head = origin.model_copy(
        update={"members": [added_member := MemberUser(value="adding_user_id")]},
        deep=True,
    )

    spy_list_diff = mocker.spy(server.services.utils.patch_operations, "_handle_list_diff")
    expected = [
        RemoveOperation(path=f'members[value eq "{removed_member_id}" and type eq "User"]'),
        AddOperation(path="members", value=added_member),
    ]

    result = _diff(MapGroup, base, head)

    assert len(result) == len(expected)
    assert next(op for op in result if op.op == "remove") == expected[0]
    assert next(op for op in result if op.op == "add") == expected[1]
    spy_list_diff.assert_any_call(base.members, head.members, path="members")


def test__select_fields(map_groups):
    base: MapGroup = map_groups[0]
    head = base.model_copy(update={"external_id": uuid4().hex}, deep=True)
    assert base.model_fields_set.issubset(head.model_fields_set)
    expected = head.model_fields_set

    fields = _select_fields(base, head)

    assert fields == expected


def test__select_fields_with_include(map_groups):
    base: MapGroup = map_groups[0]
    head = base.model_copy(update={"external_id": uuid4().hex}, deep=True)
    include = {"display_name", "external_id"}
    assert include.issubset(head.model_fields_set)
    expected = include

    fields = _select_fields(base, head, include=include)

    assert fields == expected


def test__select_fields_with_exclude(map_groups):
    base: MapGroup = map_groups[0]
    head = base.model_copy(update={"external_id": uuid4().hex}, deep=True)
    exclude = {"meta", "external_id"}
    assert exclude.issubset(head.model_fields_set)
    expected = head.model_fields_set - exclude

    fields = _select_fields(base, head, exclude=exclude)

    assert fields == expected


def test__select_fields_nested(map_groups):
    base: MapGroup = map_groups[0]
    assert base.meta
    head = base.model_copy(
        update={
            "meta": base.meta.model_copy(
                update={
                    "created": datetime.fromisoformat("2026-03-01T03:00:00Z"),
                    "last_modified": datetime.fromisoformat("2026-04-01T09:00:00Z"),
                },
                deep=True,
            )
        },
        deep=True,
    )
    include = {"display_name", "meta.created"}
    expected = {"created"}

    fields = _select_fields(base.meta, head.meta, path="meta", include=include)

    assert fields == expected


def test__alias_generator(original_alias, mocker: MockerFixture):
    mock_generator = mocker.MagicMock(side_effect=to_camel)
    mocker.patch.object(MapUser, "model_config", {"alias_generator": mock_generator})

    assert unwrap(patch_operations._a)(MapUser, "user_name") == "userName"

    mock_generator.assert_called_once_with("user_name")


def test__alias_serialization(original_alias, mocker: MockerFixture):
    mock_generator = mocker.NonCallableMock(spec_set=AliasGenerator)
    mock_generator.serialization_alias.side_effect = to_camel
    mocker.patch.object(MapUser, "model_config", {"alias_generator": mock_generator})

    assert unwrap(patch_operations._a)(MapUser, "user_name") == "userName"

    mock_generator.serialization_alias.assert_called_once_with("user_name")


def test__alias_not_set(original_alias, mocker: MockerFixture):
    mock_config = mocker.MagicMock(spec=dict)
    mock_config.get.return_value = None
    mocker.patch.object(MapUser, "model_config", mock_config)

    assert unwrap(patch_operations._a)(MapUser, "user_name") == "user_name"
    mock_config.get.assert_called_once_with("alias_generator")


def test_build_update_member_operations_add() -> None:
    current_users = {
        "current_user_id_1",
        "current_user_id_2",
        "system_admin",
    }
    add = {"adding_user_id_3", "adding_user_id_4"}
    remove = set()
    system_admins = {"system_admin"}

    ops = build_update_member_operations(add, remove, current_users, system_admins)

    assert len(ops) == len(add)
    assert next(op for op in ops if op.op == "add" and op.value.value == "adding_user_id_3")
    assert next(op for op in ops if op.op == "add" and op.value.value == "adding_user_id_4")


def test_build_update_member_operations_already_existing() -> None:
    current_users = {
        "current_user_id_1",
        "current_user_id_2",
        "system_admin",
    }
    add = {"current_user_id_2", "adding_user_id_4"}
    remove = set()
    system_admins = {"system_admin"}

    ops = build_update_member_operations(add, remove, current_users, system_admins)

    assert len(ops) == len(add - current_users)
    assert not any(op for op in ops if op.op == "add" and op.value.value == "current_user_id_2")


def test_build_update_member_operations_remove() -> None:
    current_users = {
        "current_user_id_1",
        "current_user_id_2",
        "removing_user_id_3",
        "removing_user_id_4",
        "system_admin",
    }
    add = set()
    remove = {"removing_user_id_3", "removing_user_id_4"}
    system_admins = {"system_admin"}

    ops = build_update_member_operations(add, remove, current_users, system_admins)

    assert len(ops) == len(remove & current_users)
    assert next(op for op in ops if op.op == "remove" and op.path == 'members[value eq "removing_user_id_3"]')
    assert next(op for op in ops if op.op == "remove" and op.path == 'members[value eq "removing_user_id_4"]')


def test_build_update_member_operations_unexisting():
    current_users = {
        "current_user_id_1",
        "current_user_id_2",
        "removing_user_id_3",
        "system_admin",
    }
    add = set()
    remove = {"removing_user_id_3", "unexisting_user_id_4"}
    system_admins = {"system_admin"}

    ops = build_update_member_operations(add, remove, current_users, system_admins)

    assert len(ops) == len(remove & current_users)
    assert not any(op for op in ops if op.op == "remove" and op.path == 'members[value eq "unexisting_user_id_4"]')


def test_build_update_member_operations_remove_system_admins():
    current_users = {
        "current_user_id_1",
        "current_user_id_2",
        "removing_user_id_3",
        "system_admin",
    }
    add = set()
    remove = {"removing_user_id_3", "system_admin"}
    system_admins = {"system_admin"}

    ops = build_update_member_operations(add, remove, current_users, system_admins)

    # could not remove system_admin
    assert len(ops) == len(remove & current_users - system_admins)
    assert not any(op for op in ops if op.op == "remove" and op.path == 'members[value eq "system_admin"]')


def test_build_update_member_operations_no_members_left():
    current_users = {
        "removing_user_id_3",
        # "system_admin",    # In the unlikely event that a system administrator does not belong to a group
    }
    add = set()
    remove = {"removing_user_id_3"}
    system_admins = {"system_admin"}

    ops = build_update_member_operations(add, remove, current_users, system_admins)

    # If this would leave the group with no members, add system admins instead.
    assert len(ops) == len(remove | system_admins)
    assert next(op for op in ops if op.op == "add" and op.value.value == "system_admin")


def test_build_update_member_operations_no_system_admins():
    current_users = {
        "current_user_id_1",
        "current_user_id_2",
        "removing_user_id_3",
    }
    add = {"adding_user_id_3"}
    remove = {"removing_user_id_3"}
    system_admins = set()

    with pytest.raises(SystemAdminNotFound, match=regex(E.GROUP_REQUIRES_SYSTEM_ADMIN)):
        build_update_member_operations(add, remove, current_users, system_admins)
