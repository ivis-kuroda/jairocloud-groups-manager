#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities for patch operations."""

import typing as t

from pydantic import BaseModel

from server.entities.patch_request import (
    AddOperation,
    PatchOperation,
    RemoveOperation,
    ReplaceOperation,
)
from server.messages import E


def build_patch_operations[T: BaseModel](
    original: T,
    updated: T,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[PatchOperation[T]]:
    """Generate patch operations to transform `original` model into `updated` model.

    Args:
        original (BaseModel): The original model.
        updated (BaseModel): The updated model.
        include (set[str] | None): Attribute names to include.
        exclude (set[str] | None): Attribute names to exclude.

    Returns:
        list[PatchOperation]: The list of patch operations.

    Raises:
        TypeError: If `original` and `updated` are not of the same type.
    """
    if (type_o := type(original)) is not (type_u := type(updated)):
        error = E.CANNOT_RESOLVE_DIFFERENCE % {
            "original": type_o.__name__,
            "updated": type_u.__name__,
        }
        raise TypeError(error)

    gen = original.model_config.get("alias_generator")
    if gen and not callable(gen):
        gen = gen.serialization_alias
    if gen is None:
        gen = lambda x: x  # noqa: E731

    return _diff(
        original, updated, alias_generator=gen, include=include, exclude=exclude
    )


def _diff(
    src: BaseModel | None,
    dst: BaseModel | None,
    /,
    path: str = "",
    alias_generator: t.Callable[[str], str] = lambda x: x,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[PatchOperation]:
    ops = []

    cur_include = {
        attr.removeprefix(f"{path}.")
        for attr in (include or set())
        if attr.startswith(path)
    }
    cur_exclude = {
        attr.removeprefix(f"{path}.")
        for attr in (exclude or set())
        if attr.startswith(path)
    }

    src_fields: set[str] = src.model_fields_set - cur_exclude if src else set()
    dst_fields: set[str] = dst.model_fields_set - cur_exclude if dst else set()
    if include is not None:
        src_fields &= cur_include
        dst_fields &= cur_include

    for field in src_fields | dst_fields:
        src_value = getattr(src, field, None)
        dst_value = getattr(dst, field, None)
        current_path = f"{path}.{field}" if path else field

        if isinstance(src_value, list) or isinstance(dst_value, list):
            ops.extend(_handle_list_diff(src_value, dst_value, current_path))
            continue
        if isinstance(src_value, BaseModel) or isinstance(dst_value, BaseModel):
            ops.extend(
                _diff(
                    src_value,
                    dst_value,
                    current_path,
                    alias_generator,
                    include=include,
                    exclude=exclude,
                )
            )
            continue
        current_path = alias_generator(current_path)
        ops.extend(_handle_literal_diff(src_value, dst_value, current_path))

    return ops


def _handle_literal_diff(
    src_value: object, dst_value: object, path: str
) -> list[PatchOperation]:
    if src_value == dst_value:
        return []
    if src_value is None:
        return [AddOperation(path=path, value=dst_value)]
    if dst_value is None:
        return [RemoveOperation(path=path)]
    return [ReplaceOperation(path=path, value=dst_value)]


@t.runtime_checkable
class _ArrayElement(t.Protocol):
    """Protocol for elements in an array used in patch operations."""

    value: str
    """The value of the array element."""


@t.runtime_checkable
class _TypedArrayElement(_ArrayElement, t.Protocol):
    """Protocol for typed elements in an array used in patch operations."""

    type: str
    """The type of the array element."""


def _handle_list_diff(
    src_list: list[BaseModel] | None,
    dst_list: list[BaseModel] | None,
    path: str,
) -> list[PatchOperation]:
    def get_key(elem: _ArrayElement) -> tuple[str, str | None]:
        if isinstance(elem, _TypedArrayElement):
            return (elem.value, elem.type)
        return (elem.value, None)

    src_map = {get_key(e): e for e in src_list or [] if isinstance(e, _ArrayElement)}
    dst_map = {get_key(e): e for e in dst_list or [] if isinstance(e, _ArrayElement)}

    ops: list[PatchOperation] = []

    for key in src_map.keys() - dst_map.keys():
        value, type_ = key
        if type_ is not None:
            path_str = f'{path}[value eq "{value}" and type eq "{type_}"]'
        else:
            path_str = f'{path}[value eq "{value}"]'
        ops.append(RemoveOperation(path=path_str))

    ops.extend(
        AddOperation(path=path, value=dst_map[key])
        for key in dst_map.keys() - src_map.keys()
    )

    return ops


def build_update_member_operations(
    add: set[str], remove: set[str], user_list: set[str], system_admins: set[str]
) -> list[PatchOperation]:
    """Make patch request body for members from group_id and operation.

    Args:
        add (set[str]): List of user IDs to add .
        remove (set[str]): List of user IDs to remove.
        user_list (set[str]): List of user IDs in the current group.
        system_admins (set[str]): List of system administrator IDs.

    Returns:
        list[PatchOperation]: List of patch operations.
    """
    operations: list[PatchOperation] = []
    add.difference_update(user_list)
    remove.difference_update(system_admins)
    remove.intersection_update(user_list)
    if remove.issuperset(user_list | add):
        add.update(system_admins)
    operations.extend([
        AddOperation(path="members", value={"type": "User", "value": g}) for g in add
    ])
    operations.extend([RemoveOperation(path=f"members[value eq {g}]") for g in remove])

    return operations
