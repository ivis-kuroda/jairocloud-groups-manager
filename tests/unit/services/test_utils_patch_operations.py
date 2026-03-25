from typing import TYPE_CHECKING

import pytest

from pydantic import AliasGenerator, BaseModel, ConfigDict

from server.entities.patch_request import (
    AddOperation,
    RemoveOperation,
    ReplaceOperation,
)
from server.services.utils.patch_operations import (
    _diff,
    _handle_list_diff,
    _handle_literal_diff,
    build_patch_operations,
    build_update_member_operations,
)


if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def return_str(x):
    return x


config = ConfigDict(
    alias_generator=AliasGenerator(serialization_alias=return_str),
)

config2 = ConfigDict(
    alias_generator=None,
)


class Test(BaseModel):
    id: str
    model_config = config
    test_list: list[Test3]
    test_model: Test2


class Test2(BaseModel):
    id: str
    model_config = config2


class Test3(BaseModel):
    value: str
    type: str


class Test4(BaseModel):
    value: str
    value2: str
    type: str


class Test5(BaseModel):
    value: str
    value2: str


class Test6(BaseModel):
    value: str
    value3: str


@pytest.mark.parametrize(
    ("ori", "up", "expected"),
    [
        (
            Test(id="1", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
            Test(id="2", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
            [
                Test(id="1", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
                Test(id="2", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
                None,
                None,
            ],
        ),
        (Test2(id="1"), Test2(id="2"), [Test2(id="1"), Test2(id="2"), None, None]),
    ],
    ids=["alias_generator", "no_alias_generator"],
)
def test_build_patch_operations(ori, up, expected, mocker: MockerFixture):
    call = mocker.patch("server.services.utils.patch_operations._diff")
    build_patch_operations(ori, up)
    args, kwargs = call.call_args
    assert args[0] == expected[0]
    assert args[1] == expected[1]
    assert callable(kwargs["alias_generator"])
    assert kwargs["include"] is expected[2]
    assert kwargs["exclude"] is expected[3]


def test_build_patch_operations_typeerror():
    original = Test(id="1", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2"))
    updated = Test2(id="2")
    msg = "E092 | Cannot resolve differences between different types (original: Test, updated: Test2)."
    with pytest.raises(TypeError, match=msg):
        build_patch_operations(original, updated)


@pytest.mark.parametrize(
    ("src", "dsc", "include"),
    [
        (
            Test(id="1", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
            Test(id="2", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
            {"id", "test_list", "test_model"},
        ),
        (
            Test(id="1", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
            Test(id="2", test_list=[Test3(value="test", type="test")], test_model=Test2(id="2")),
            None,
        ),
    ],
    ids=["include", "no_include"],
)
def test__diff(src, dsc, include):
    result = _diff(src, dsc, include=include)
    expected_op = "replace"
    expected_path = "id"
    expected_value = "2"
    assert isinstance(result[0], ReplaceOperation)

    assert result[0].op == expected_op
    assert result[0].path == expected_path
    assert result[0].value == expected_value


@pytest.mark.parametrize(
    ("src_value", "dsc_value", "path", "expected_op", "expected_path", "expected_value"),
    [(None, 1, "id", "add", "id", 1), (1, 2, "id", "replace", "id", 2)],
    ids=["no_src_value", "different_value"],
)
def test_handle_literal_diff(src_value, dsc_value, path, expected_op, expected_path, expected_value):
    result = _handle_literal_diff(src_value, dsc_value, path)
    assert isinstance(result[0], (AddOperation, ReplaceOperation))
    assert result[0].op == expected_op
    assert result[0].path == expected_path
    assert result[0].value == expected_value


def test_handle_literal_diff_match_value():
    result = _handle_literal_diff(1, 1, "id")
    assert result == []


def test_handle_literal_diff_no_dst_value():
    expected_op = "remove"
    expected_path = "id"
    result = _handle_literal_diff(1, None, "id")
    assert isinstance(result[0], RemoveOperation)
    assert result[0].op == expected_op
    assert result[0].path == expected_path


@pytest.mark.parametrize(
    (
        "src_list",
        "dsc_list",
        "path",
        "expected_op_1",
        "expected_path_1",
        "expected_op_2",
        "expected_path_2",
        "expected_value",
    ),
    [
        (
            [Test4(value="test", value2="test2", type="test")],
            [Test3(value="test", type="test2")],
            "value",
            "remove",
            'value[value eq "test" and type eq "test"]',
            "add",
            "value",
            Test3(value="test", type="test2"),
        ),
        (
            [Test5(value="test", value2="test2")],
            [Test6(value="test2", value3="test3")],
            "value",
            "remove",
            'value[value eq "test"]',
            "add",
            "value",
            Test6(value="test2", value3="test3"),
        ),
    ],
    ids=["type", "no_type"],
)
def test__handle_list_diff(
    src_list, dsc_list, path, expected_op_1, expected_path_1, expected_op_2, expected_path_2, expected_value
):
    result = _handle_list_diff(src_list, dsc_list, path)
    assert isinstance(result[0], RemoveOperation)
    assert result[0].op == expected_op_1
    assert result[0].path == expected_path_1
    assert isinstance(result[1], AddOperation)
    assert result[1].op == expected_op_2
    assert result[1].path == expected_path_2
    assert result[1].value == expected_value


def test_build_update_member_operations() -> None:

    add = {"u1", "u2"}
    remove = {"u3", "u4"}
    user_list = {"u1", "u3"}
    system_admins = {"admin"}
    ops = build_update_member_operations(add, remove, user_list, system_admins)
    assert any(isinstance(op, AddOperation) and op.value["value"] in {"u2", "admin"} for op in ops)
    assert any(isinstance(op, RemoveOperation) and "u3" in op.path for op in ops)


def test_build_update_member_operations_add_update_system_admins() -> None:

    add = set()
    user_list = set()
    remove = set()
    system_admins = {"admin1", "admin2"}

    ops = build_update_member_operations(set(add), set(remove), set(user_list), set(system_admins))

    added_ids = {op.value["value"] for op in ops if isinstance(op, AddOperation)}
    assert "admin1" in added_ids
    assert "admin2" in added_ids
