#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for Repository entity for client side."""

import typing as t

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, PrivateAttr

from .common import camel_case_config, forbid_extra_config


class RepositoryDetail(BaseModel):
    """Model for detailed Repository information in mAP Core API."""

    id: str | None = None
    """The unique identifier for the repository."""

    service_name: str | None = None
    """The name of the repository. Alias to 'serviceName'."""

    service_url: HttpUrl | None = None
    """The URL of the service. Alias for 'serviceUrl'."""

    active: bool | None = None
    """Whether the service is active."""

    service_id: t.Annotated[
        str | None,
        Field(
            validation_alias="spConnectorId",
            serialization_alias="spConnectorId",
        ),
    ] = None
    """The ID of the corresponding resource. Alias to 'spConnectorId'."""
    entity_ids: list[str] | None = None
    """The entity IDs associated with the repository. Alias to 'entityIds'."""

    created: datetime | None = None
    """The creation timestamp of sp connector."""

    users_count: int | None = None
    """The number of users in the group. Alias to 'usersCount'."""

    groups_count: int | None = None
    """The number of user-defined groups in the repository. Alias to 'groupsCount'."""

    _groups: list[str] | None = PrivateAttr(None)
    """The user-defined groups in the repository."""

    _rolegroups: list[str] | None = PrivateAttr(None)
    """The role-type groups in the repository."""

    _admins: list[str] | None = PrivateAttr(None)
    """The administrators of the group."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""
