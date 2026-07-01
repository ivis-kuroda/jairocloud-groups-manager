#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities for patch operations."""

import typing as t

from functools import cache

from pydantic import BaseModel

from server.entities.map_group import MemberUser
from server.entities.patch_request import (
    AddOperation,
    PatchOperation,
    RemoveOperation,
    ReplaceOperation,
)
from server.exc import SystemAdminNotFound
from server.messages import E


def build_patch_operations[T: BaseModel](
    base: T,
    head: T,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[PatchOperation[T]]:
    """Generate SCIM patch operations to transform `base` into `head`.

    Both `base` and `head` must be instances of the same model type.

    Args:
        base (BaseModel): The base model.
        head (BaseModel): The head model.
        include (set[str] | None): Attribute names to include.
        exclude (set[str] | None): Attribute names to exclude.

    Returns:
        list[PatchOperation]: The list of patch operations.

    Raises:
        TypeError: If `base` and `head` are not of the same type.
    """
    if (base_type := type(base)) is not (head_type := type(head)):
        raise TypeError(
            E.CANNOT_RESOLVE_DIFFERENCE
            % {
                "original": base_type.__name__,
                "updated": head_type.__name__,
            }
        )

    return _diff(base_type, base, head, include=include, exclude=exclude)


def _diff(
    ty: type[BaseModel],
    base: BaseModel | None,
    head: BaseModel | None,
    path: str = "",
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[PatchOperation]:
    selected_fields = _select_fields(base, head, path, include, exclude)

    ops: list[PatchOperation] = []
    for field in sorted(selected_fields):
        base_value = getattr(base, field, None)
        head_value = getattr(head, field, None)
        current_path = f"{path}.{field}" if path else field

        if isinstance(base_value, list) or isinstance(head_value, list):
            ops.extend(_handle_list_diff(base_value, head_value, path=current_path))
            continue

        if isinstance(base_value, BaseModel) or isinstance(head_value, BaseModel):
            ops.extend(
                _diff(ty, base_value, head_value, current_path, include, exclude)
            )
            continue

        current_path = _a(ty, current_path)
        ops.extend(_handle_literal_diff(base_value, head_value, path=current_path))

    return ops


def _select_fields(
    base: BaseModel | None,
    head: BaseModel | None,
    path: str = "",
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> set[str]:
    prefix = f"{path}." if path else ""

    base_fields = base.model_fields_set if base else set[str]()
    head_fields = head.model_fields_set if head else set[str]()

    fields = base_fields | head_fields
    if not include and not exclude:
        return fields

    if exclude:
        exclude_fields = {
            field.removeprefix(prefix) for field in exclude if field.startswith(prefix)
        }
        fields -= exclude_fields
    if include:
        include_fields = {
            field.removeprefix(prefix) for field in include if field.startswith(prefix)
        }
        fields &= include_fields

    return fields


def _handle_literal_diff(
    base_value: object, head_value: object, path: str
) -> list[PatchOperation]:
    if base_value == head_value:
        return []

    if base_value is None:
        return [AddOperation(path=path, value=head_value)]

    if head_value is None:
        return [RemoveOperation(path=path)]

    return [ReplaceOperation(path=path, value=head_value)]


def _handle_list_diff(
    base_list: list[BaseModel] | None,
    head_list: list[BaseModel] | None,
    path: str,
) -> list[PatchOperation]:
    base_map = {__key_of_elem(e): e for e in base_list or [] if __is_array_element(e)}
    head_map = {__key_of_elem(e): e for e in head_list or [] if __is_array_element(e)}

    add = head_map.keys() - base_map.keys()
    remove = base_map.keys() - head_map.keys()

    ops: list[PatchOperation] = []
    ops.extend(AddOperation(path=path, value=head_map[key]) for key in sorted(add))
    for key in sorted(remove):
        value, ty = key
        path_filter = f'value eq "{_e(value)}"'
        if ty:
            path_filter += f' and type eq "{_e(ty)}"'

        path_str = f"{path}[{path_filter}]"
        ops.append(RemoveOperation(path=path_str))

    return ops


class _ArrayElement(t.Protocol):
    """Protocol for elements of SCIM array attributes.

    This element must have a :attr:`value` attribute, which is used to identify
    the element in the array.
    """

    value: object
    """The value of the array element."""


class _TypedElement(t.Protocol):
    """Protocol for elements of SCIM array attributes.

    This element must have a :attr:`type` attribute, which is used to identify
    the type of the element in the array.
    """

    type: str
    """The type of the array element."""


def __is_array_element(elem: object) -> t.TypeIs[_ArrayElement]:
    return hasattr(elem, "value")


def __is_typed_element(elem: object) -> t.TypeIs[_TypedElement]:
    return hasattr(elem, "type")


def __key_of_elem(elem: _ArrayElement) -> tuple[object, str | None]:
    if __is_typed_element(elem):
        return (elem.value, elem.type)
    return (elem.value, None)


@cache
def _a(ty: type[BaseModel], o: str) -> str:
    ag = ty.model_config.get("alias_generator")
    fnc = ag if callable(ag) else ag.serialization_alias if ag else None
    return fnc(o) if fnc else o


def _e(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def build_update_member_operations(
    add: set[str], remove: set[str], current_users: set[str], system_admins: set[str]
) -> list[PatchOperation]:
    """Make patch request body for members from group_id and operation.

    This function could not add/remove system administrators from the group.

    Args:
        add (set[str]): List of user IDs to add .
        remove (set[str]): List of user IDs to remove.
        current_users (set[str]): List of user IDs in the current group.
        system_admins (set[str]): List of system administrator IDs.

    Returns:
        list[PatchOperation]: List of patch operations.

    Raises:
        SystemAdminNotFound: If there are no system administrators available.
    """
    members_path = "members"

    if not system_admins:
        raise SystemAdminNotFound(E.GROUP_REQUIRES_SYSTEM_ADMIN)

    # Avoid adding users already in the group
    users_to_add = add - current_users
    # Avoid removing system admins, removing users not in the group
    users_to_remove = (remove - system_admins) & current_users

    if not (current_users - users_to_remove) | users_to_add:
        # If this would leave the group with no members, add system admins instead.
        # This situation is highly unlikely.
        users_to_add |= system_admins

    operations: list[PatchOperation] = []
    operations.extend(
        AddOperation(path=members_path, value=MemberUser(value=uid))
        for uid in sorted(users_to_add)
    )
    operations.extend(
        RemoveOperation(path=(f'{members_path}[value eq "{_e(uid)}"]'))
        for uid in sorted(users_to_remove)
    )

    return operations
