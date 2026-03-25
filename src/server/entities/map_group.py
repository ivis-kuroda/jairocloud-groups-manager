#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for schema and entity definition of mAP Core API Group resources."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from server.const import MAP_GROUP_SCHEMA

from .common import camel_case_config, forbid_extra_config


class MapGroup(BaseModel):
    """Model for a group resource in the mAP Core API.

    Handles validation and (de)serialization of group resources.
    """

    schemas: t.Annotated[t.Sequence[str], Field(frozen=True)] = [MAP_GROUP_SCHEMA]
    """Schema URIs that define the attributes present in the Group resource."""

    id: str | None = None
    """The unique identifier for the group."""

    external_id: str | None = None
    """The external identifier for the group. Alias to 'externalId'."""

    display_name: str | None = None
    """The display name of the group. Alias to 'displayName'."""

    public: bool | None = None
    """Whether the group is public or private."""

    description: str | None = None
    """The description of the group."""

    suspended: bool = False
    """Whether the group is suspended."""

    member_list_visibility: Visibility | None = None
    """The visibility of the member list. Alias to 'memberListVisibility'."""

    meta: Meta | None = None
    """Metadata about the group."""

    members: list[Member] | None = None
    """The members of the group."""

    administrators: list[Administrator] | None = None
    """The administrators of the group."""

    services: list[Service] | None = None
    """The services associated with the group."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


type Visibility = t.Literal["Public", "Private", "Hidden"]


class Meta(BaseModel):
    """Model for group resource metadata."""

    resource_type: t.Literal["Group"] = "Group"
    """Type of resource. Always 'Group'. Alias for 'resourceType'."""

    created: datetime
    """Date and time when the resource was created."""

    last_modified: datetime
    """Date and time when the resource was last modified.
    Alias for 'lastModified'.
    """

    model_config = camel_case_config | forbid_extra_config | {"frozen": True}
    """Configure to use camelCase aliasing, forbid extra fields, and make immutable."""


type Member = t.Annotated[MemberUser | MemberGroup, Field(..., discriminator="type")]


class MemberUser(BaseModel):
    """Model for a user member of a group."""

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

    type: t.Annotated[t.Literal["User"], Field(frozen=True)] = "User"
    """Type of the member. Always 'User'."""

    display: str | None = None
    """Display name of the user."""

    value: str
    """User ID."""

    custom_roles: list[str] | None = None
    """Custom roles assigned to the user. Alias for 'customRole'."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class MemberGroup(BaseModel):
    """Model for a group member of a group."""

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

    type: t.Annotated[t.Literal["Group"], Field(frozen=True)] = "Group"
    """Type of the member. Always 'Group'."""

    display: str | None = None
    """Display name of the group."""

    value: str
    """Group ID."""

    model_config = forbid_extra_config | {"validate_by_name": True}
    """Configure to forbid extra fields and validate by attribute names."""


class Administrator(BaseModel):
    """Model for a group administrator."""

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
    """Display name of the user."""

    value: str
    """User ID."""

    model_config = forbid_extra_config | {"validate_by_name": True}
    """Configure to forbid extra fields and validate by attribute names."""


class Service(BaseModel):
    """Model for a service associated with a group."""

    ref: t.Annotated[
        HttpUrl | None,
        Field(
            ...,
            # NOTE: not using `alias` because it changes the constructor arguments.
            validation_alias="$ref",
            serialization_alias="$ref",
        ),
    ] = None
    """URI of the corresponding Service resource. Alias for '$ref'."""

    display: str | None = None
    """Display name of the service."""

    value: str
    """Service ID."""

    administrator_of_group: int | None = None
    """Flag indicating whether the service is an administrator of the group.
    Alias for 'administratorOfGroup'.
    """

    model_config = camel_case_config | forbid_extra_config | {"validate_by_name": True}
    """Configure to use camelCase aliasing, forbid extra fields,
    and validate by attribute names.
    """
