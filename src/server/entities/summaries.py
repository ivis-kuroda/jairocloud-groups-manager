#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for Summary entities for client side."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, EmailStr, HttpUrl

from server.const import USER_ROLES

from .common import camel_case_config, forbid_extra_config
from .map_group import Visibility
from .map_user import MapUser


class RepositorySummary(BaseModel):
    """Model for summary Repository information in mAP Core API."""

    id: str
    """The unique identifier for the repository."""

    service_name: str | None = None
    """The name of the repository. Alias to 'serviceName'."""

    service_url: HttpUrl | None = None
    """The URL of the service. Alias for 'serviceUrl'."""

    service_id: str | None = None
    """The service ID of the repository. Alias to 'serviceId'."""

    entity_ids: list[str] | None = None
    """The entity IDs of the repository. Alias to 'entityIds'."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class GroupSummary(BaseModel):
    """Model for summary Group information in mAP Core API."""

    id: str
    """The unique identifier for the group."""

    display_name: str | None = None
    """The display name of the group. Alias to 'displayName'."""

    repository_name: str | None = None
    """The name of the repository the group belongs to. Alias to 'repositoryName'."""

    public: bool | None = None
    """Whether the group is public or private."""

    member_list_visibility: Visibility | None = None
    """The visibility of the member list. Alias to 'memberListVisibility'."""

    users_count: int | None = None
    """The number of users in the group. Alias to 'usersCount'."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class UserSummary(BaseModel):
    """Model for summary User information in mAP Core API."""

    id: str
    """The unique identifier for the user."""

    user_name: str | None = None
    """The username of the user. Alias to 'userName'."""

    role: USER_ROLES | None = None
    """The highest role of the user in logged-in user could see."""

    emails: list[EmailStr] | None = None
    """The first email address of the user."""

    eppns: list[str] | None = None
    """The first eduPersonPrincipalName of the user."""

    last_modified: datetime | None = None
    """The last modification timestamp of the user. Alias to 'lastModified'."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""

    @classmethod
    def from_map_user(cls, user: MapUser) -> UserSummary:
        """Create a UserSummary instance from this UserDetail instance.

        Returns:
            UserSummary: The created UserSummary instance.
        """
        from server.services.utils import (  # noqa: PLC0415
            detect_affiliations,
            get_highest_role,
            get_permitted_repository_ids,
            is_current_user_system_admin,
        )

        highest_role: USER_ROLES | None = None
        if user.groups:
            group_ids = [group.value for group in user.groups]
            roles, _ = detect_affiliations(group_ids)
            if not is_current_user_system_admin():
                permitted_repo_ids = get_permitted_repository_ids()
                roles = [
                    role for role in roles if role.repository_id in permitted_repo_ids
                ]
            highest_role = get_highest_role([repo.role for repo in roles])

        return cls(
            id=t.cast("str", user.id),
            user_name=user.user_name,
            role=highest_role,
            emails=[email.value for email in user.emails or []],
            eppns=[eppn.value for eppn in user.edu_person_principal_names or []],
            last_modified=user.meta.last_modified if user.meta else None,
        )
