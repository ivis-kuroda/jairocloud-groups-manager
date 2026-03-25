#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Schemas for the mAP Core API Error resource."""

import typing as t

from pydantic import BaseModel, Field

from server.const import MAP_ERROR_SCHEMA

from .common import camel_case_config, forbid_extra_config


class MapError(BaseModel):
    """Model for an Error resource in the mAP Core API."""

    schemas: t.Annotated[t.Sequence[str], Field(frozen=True)] = [MAP_ERROR_SCHEMA]
    """Schema URIs that define the attributes present in the Error resource."""

    status: t.Literal[
        "307",
        "308",
        "400",
        "401",
        "403",
        "404",
        "409",
        "412",
        "413",
        "415",
        "500",
        "501",
    ]
    """The HTTP status code of the error as a string."""

    scim_type: t.Literal[
        "invalidFilter",
        "tooMany",
        "uniqueness",
        "mutability",
        "invalidValue",
        "invalidSyntax",
        "noTarget",
        "invalidVers",
        "sensitive",
        "invalidId",  # additional
    ]
    """The SCIM error type. Alias to 'scimType'."""

    detail: str
    """A detailed description of the error."""

    error_code: int | None = None
    """An error response code. Alias to 'errorCode'."""

    model_config = camel_case_config | forbid_extra_config | {"frozen": True}
    """Configure to use camelCase aliasing, forbid extra fields, and make immutable."""
