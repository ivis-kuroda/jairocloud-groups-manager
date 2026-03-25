#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for schema and entity definition of mAP Core API Service resources."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from server.const import MAP_SERVICE_SCHEMA

from .common import camel_case_config, forbid_extra_config


class MapService(BaseModel):
    """Model for a service resource in the mAP Core API.

    Handles validation and (de)serialization of service resources.
    """

    schemas: t.Annotated[t.Sequence[str], Field(frozen=True)] = [MAP_SERVICE_SCHEMA]
    """Schema URIs that define the attributes present in the Service resource."""

    id: str
    """The unique identifier for the service."""

    service_name: str | None = None
    """The name of the service. Alias for 'serviceName'."""

    service_url: HttpUrl | None = None
    """The URL of the service. Alias for 'serviceUrl'."""

    suspended: bool | None = None
    """Whether the service is suspended."""

    meta: t.Annotated[Meta | None, Field(frozen=True)] = None
    """Metadata about the service."""

    entity_ids: list[ServiceEntityID] | None = None
    """The entity IDs associated with the service. Alias for 'entityIds'."""

    administrators: list[Administrator] | None = None
    """The administrators of the service."""

    groups: list[Group] | None = None
    """The groups associated with the service."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class Meta(BaseModel):
    """Model for service resource metadata."""

    resource_type: t.Literal["Service"] = "Service"
    """Type of resource. Always 'Service'. Alias for 'resourceType'."""

    created: datetime
    """Date and time when the resource was created."""

    last_modified: datetime
    """Date and time when the resource was last modified. Alias for 'lastModified'."""

    model_config = camel_case_config | forbid_extra_config | {"frozen": True}
    """Configure to use camelCase aliasing, forbid extra fields, and make immutable."""


class ServiceEntityID(BaseModel):
    """Model for a service entity ID."""

    value: str
    """The entity ID value."""

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""


class Administrator(BaseModel):
    """Model for a service administrator."""

    ref: t.Annotated[
        HttpUrl | None,
        Field(
            ...,
            # NOTE: not using `alias` because it changes the constructor arguments.
            validation_alias="$ref",
            serialization_alias="$ref",
        ),
    ] = None
    """URI of the corresponding User resource. Alias for '$ref'."""

    display: str | None = None
    """User's display name."""

    value: str
    """User's ID."""

    model_config = forbid_extra_config | {"validate_by_name": True}
    """Configure to forbid extra fields and validate by attribute names."""


class Group(BaseModel):
    """Model for a group associated with a service."""

    ref: t.Annotated[
        HttpUrl | None,
        Field(
            ...,
            # NOTE: not using `alias` because it changes the constructor arguments.
            validation_alias="$ref",
            serialization_alias="$ref",
        ),
    ] = None
    """URI of the corresponding Group resource. Alias for '$ref'."""

    display: str | None = None
    """Group's display name."""

    value: str
    """Group's ID."""

    model_config = forbid_extra_config | {"validate_by_name": True}
    """Configure to forbid extra fields and validate by attribute names."""
