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
        from server.services.utils import (  # ruff: ignore[import-outside-top-level]
            is_current_user_system_admin,
        )

        return is_current_user_system_admin()

    @override
    def get_id(self) -> str:
        return self.eppn

    @property
    def permitted_repositories(self) -> set[str]:
        """The list of repository IDs the user has permission to operate on."""
        from server.services.utils import (  # ruff: ignore[import-outside-top-level]
            get_permitted_repository_ids,
        )

        return get_permitted_repository_ids()
