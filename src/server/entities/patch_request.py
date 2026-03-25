#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Model for PATCH request."""

import typing as t

from pydantic import BaseModel, Field

from server.const import MAP_PATCH_SCHEMA

from .common import forbid_extra_config


class PatchRequestPayload[T: BaseModel](BaseModel):
    """Model for PATCH request payloads."""

    schemas: t.Annotated[t.Sequence[str], Field(frozen=True)] = [MAP_PATCH_SCHEMA]
    """Schema URIs that define the attributes present in the PATCH request payload."""

    operations: t.Annotated[
        list[PatchOperation[T]], Field(..., serialization_alias="Operations")
    ]
    """List of patch operations to be applied to the target resource.
    Alias for 'Operations'.
    """

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""


type PatchOperation[T: BaseModel] = t.Annotated[
    AddOperation[T] | RemoveOperation[T] | ReplaceOperation[T],
    Field(discriminator="op"),
]
"""Union type for patch operations based on the 'op' field."""


class AddOperation[T: BaseModel](BaseModel):
    """Model for 'add' patch operations."""

    op: t.Literal["add"] = "add"
    """The operation type. Always 'add'."""

    path: str
    """The target path for the operation."""

    value: t.Any
    """The value to be added."""

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""


class RemoveOperation[T: BaseModel](BaseModel):
    """Model for 'remove' patch operations."""

    op: t.Literal["remove"] = "remove"
    """The operation type. Always 'remove'."""

    path: str
    """The target path for the operation."""

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""


class ReplaceOperation[T: BaseModel](BaseModel):
    """Model for 'replace' patch operations."""

    op: t.Literal["replace"] = "replace"
    """The operation type. Always 'replace'."""

    path: str
    """The target path for the operation."""

    value: t.Any
    """The value to be used for replacement."""

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""
