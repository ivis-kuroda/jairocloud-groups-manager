#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for login user entity for client side."""

import typing as t

from datetime import UTC, datetime
from functools import cached_property
from typing import override

from flask_login import UserMixin
from pydantic import BaseModel, Field, computed_field

from server.config import config

from .common import camel_case_config


class LoginUser(BaseModel, UserMixin):
    """Model for login user information."""

    eppn: str
    """The eduPersonPrincipalName of the user. Used in session management."""

    login_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    """Login date and time. Cached in ISO 6018 format."""

    is_member_of: str
    """login user isMemberOf attribute"""

    user_name: str
    """The display name of the user."""

    map_id: str
    """The mAP Core ID of the user."""

    session_id: t.Annotated[str, Field(exclude=True)]
    """Session ID associated with the login user."""

    model_config = camel_case_config | {"extra": "ignore"}
    """Configure to use camelCase aliasing."""

    @computed_field
    @cached_property
    def is_system_admin(self) -> bool:
        """If the logged-in user is a system administrator, then True."""
        from server.services.utils import extract_group_ids  # noqa: PLC0415

        group_ids = extract_group_ids(self.is_member_of)
        return config.GROUPS.id_patterns.system_admin in group_ids

    @override
    def get_id(self) -> str:
        return self.eppn

    @property
    def permitted_repositories(self) -> set[str]:
        """Get the list of repository IDs the user has permission to operate on."""
        from server.services.utils.permissions import (  # noqa: PLC0415
            get_permitted_repository_ids,
        )

        return get_permitted_repository_ids()
