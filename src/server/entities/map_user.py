#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for schema and entity definition of mAP Core API User resources."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from server.const import MAP_USER_SCHEMA

from .common import camel_case_config, forbid_extra_config


class MapUser(BaseModel):
    """Model for a user resource in the mAP Core API.

    Handles validation and (de)serialization of user resources.
    """

    schemas: t.Annotated[t.Sequence[str], Field(frozen=True)] = [MAP_USER_SCHEMA]
    """Schema URIs that define the attributes present in the user resource."""

    id: str | None = None
    """Unique identifier for the user."""

    external_id: str | None = None
    """External identifier for the user. Alias for 'externalId'."""

    user_name: str | None = None
    """User's name. Alias for 'userName'."""

    preferred_language: t.Literal["en", "ja", ""] | None = None
    """User's preferred language. Alias for 'preferredLanguage'."""

    meta: t.Annotated[Meta | None, Field(frozen=True)] = None
    """Metadata for the user."""

    edu_person_principal_names: list[EPPN] | None = None
    """List of ePPN values associated with the user.
    Alias for 'eduPersonPrincipalNames'.
    """

    emails: list[Email] | None = None
    """List of email addresses associated with the user."""

    groups: list[Group] | None = None
    """List of groups the user belongs to."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class Meta(BaseModel):
    """Model for user resource metadata."""

    resource_type: t.Literal["User"] = "User"
    """Type of resource. Always 'User'. Alias for 'resourceType'."""

    created: datetime
    """Date and time when the resource was created."""

    last_modified: datetime
    """Date and time when the resource was last modified.
    Alias for 'lastModified'.
    """

    created_by: str | None = None
    """ID of the user who created this resource. Alias for 'createdBy'."""

    model_config = camel_case_config | forbid_extra_config | {"frozen": True}
    """Configure to use camelCase aliasing, forbid extra fields, and make immutable."""


class EPPN(BaseModel):
    """Model for an eduPersonPrincipalName (ePPN) value associated with a user."""

    value: str
    """eduPersonPrincipalName value."""

    idp_entity_id: t.Annotated[str | None, Field(exclude=True)] = None
    """Entity ID of the Identity Provider that issued this ePPN.
    Alias for 'idpEntityId'.
    """

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class Email(BaseModel):
    """Model for an email address of a user."""

    value: EmailStr
    """Email address."""

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""


class Group(BaseModel):
    """Model for a group associated with a user."""

    value: str
    """Group ID."""

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

    model_config = forbid_extra_config | {"validate_by_name": True}
    """Configure to forbid extra fields and validate by attribute names."""
