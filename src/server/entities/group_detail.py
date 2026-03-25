#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for Group entity for client side."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, PrivateAttr

from .common import camel_case_config, forbid_extra_config
from .map_group import MapGroup, Visibility


class GroupDetail(BaseModel):
    """Model for detailed Group information in mAP Core API."""

    id: str | None = None
    """The unique identifier for the group."""

    user_defined_id: str | None = None
    """The part of group ID that is user-defined. Alias to 'userDefinedId'."""

    display_name: str | None = None
    """The display name of the group. Alias to 'displayName'."""

    description: str | None = None
    """The description of the group."""

    public: bool | None = None
    """Whether the group is public or private."""

    member_list_visibility: Visibility | None = None
    """The visibility of the member list. Alias to 'memberListVisibility'."""

    repository: Repository | None = None
    """The repository the group belongs to."""

    type: t.Literal["group", "role"] | None = None
    """The type of the group, either 'group' or 'role'."""

    created: datetime | None = None
    """The creation timestamp of the group."""

    last_modified: datetime | None = None
    """The last modification timestamp of the group. Alias to 'lastModified'."""

    users_count: int | None = None
    """The number of users in the group. Alias to 'usersCount'."""

    _users: list[str] | None = PrivateAttr(None)
    """The users in the group."""

    _admins: list[str] | None = PrivateAttr(None)
    """The administrators of the group."""

    _services: list[str] | None = PrivateAttr(None)
    """The services associated with the group."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""

    @classmethod
    def from_map_group(
        cls, group: MapGroup, *, more_detail: bool = False
    ) -> GroupDetail:
        """Create a GroupDetail instance from a MapGroup instance.

        Args:
            group (MapGroup): The MapGroup instance to convert.
            more_detail (bool): Whether to include more detailed information.

        Returns:
            GroupDetail: The created GroupDetail instance.
        """
        from server.services.utils.transformers import (  # noqa: PLC0415
            make_group_detail,
        )

        return make_group_detail(group, more_detail=more_detail)

    def to_map_group(self) -> MapGroup:
        """Convert this GroupDetail instance to a MapGroup instance.

        Returns:
            MapGroup: The created MapGroup instance.
        """
        from server.services.utils.transformers import make_map_group  # noqa: PLC0415

        return make_map_group(self)


class Repository(BaseModel):
    """Model for summary Repository information in mAP Core API."""

    id: str
    """The unique identifier for the repository."""

    service_name: str | None = None
    """The name of the repository. Alias to 'serviceName'."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""
