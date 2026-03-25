#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for Repository entity for client side."""

# ruff: noqa: PLC0415

import typing as t

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, PrivateAttr

from .common import camel_case_config, forbid_extra_config
from .map_service import MapService


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

    @classmethod
    def from_map_service(
        cls, service: MapService, *, more_detail: bool = True
    ) -> RepositoryDetail:
        """Create a RepositoryDetail instance from a MapService instance.

        Args:
            service (MapService): The MapService instance to convert.
            more_detail (bool):
                If True, include more details such as groups and users count.

        Returns:
            RepositoryDetail: The created RepositoryDetail instance.
        """
        from server.services.utils.transformers import make_repository_detail

        return make_repository_detail(service=service, more_detail=more_detail)

    def to_map_service(self) -> MapService:
        """Convert RepositoryDetail to MapService instance.

        Returns:
            MapService: The converted MapService instance.
        """
        from server.services.utils.transformers import make_map_service

        return make_map_service(self)
