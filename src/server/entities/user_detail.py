#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for User entity for client side."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator
from pydantic.alias_generators import to_snake

from server.const import USER_ROLES

from .common import camel_case_config, forbid_extra_config
from .map_user import MapUser
from .summaries import GroupSummary


class UserDetail(BaseModel):
    """Model for detailed User information in mAP Core API."""

    id: str | None = None
    """The unique identifier for the user."""

    eppns: list[str] | None = None
    """The eduPersonPrincipalNames of the user."""

    user_name: str
    """The username of the user. Alias to 'userName'."""

    emails: list[EmailStr] | None = None
    """The email addresses of the user."""

    preferred_language: t.Literal["en", "ja", ""] | None = None
    """The preferred language of the user. Alias to 'preferredLanguage'."""

    is_system_admin: bool | None = None
    """Whether the user is a system administrator. Alias to 'isSystemAdmin'."""

    repository_roles: list[RepositoryRole] | None = None
    """The affiliated repositories of the user."""

    groups: list[GroupSummary] | None = None
    """The affiliated user-defined groups of the user."""

    created: datetime | None = None
    """The creation timestamp of the user."""

    last_modified: datetime | None = None
    """The last modification timestamp of the user. Alias to 'lastModified'."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""

    @classmethod
    def from_map_user(cls, user: MapUser, *, more_detail: bool = False) -> UserDetail:
        """Create a UserDetail instance from a MapUser instance.

        Args:
            user (MapUser): The MapUser instance to convert.
            more_detail (bool):
                Whether to include more details such as groups and repositories.

        Returns:
            UserDetail: The created UserDetail instance.
        """
        from server.services.utils.transformers import make_user_detail  # noqa: PLC0415

        return make_user_detail(user, more_detail=more_detail)

    def to_map_user(self) -> MapUser:
        """Convert this UserDetail instance to a MapUser instance.

        Returns:
            MapUser: The created MapUser instance.
        """
        from server.services.utils.transformers import make_map_user  # noqa: PLC0415

        return make_map_user(self)


class RepositoryRole(BaseModel):
    """Model for summary Repository information in mAP Core API."""

    id: str
    """The unique identifier for the repository."""

    service_name: str | None = None
    """The name of the repository. Alias to 'serviceName'."""

    user_role: USER_ROLES | None = None
    """The role of the user in the repository. Alias to 'userRole'."""

    @field_validator("user_role", mode="before")
    @classmethod
    def transform_user_role(cls, v: t.Any) -> t.Any:  # noqa: ANN401
        """Transform the user_role field to USER_ROLES enum.

        Args:
            v (Any): The value to transform.

        Returns:
            Any: The transformed value.
        """
        if isinstance(v, str):
            return to_snake(v)
        return v

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""
