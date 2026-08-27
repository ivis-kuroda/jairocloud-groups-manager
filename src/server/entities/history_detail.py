#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for history entity for client side."""

import typing as t

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from server.entities.summaries import UserSummary

from .common import camel_case_config


class DownloadHistoryData(BaseModel):
    """Download history data model."""

    id: UUID
    """Download history ID."""

    timestamp: datetime
    """Timestamp of the download event."""

    operator: UserSummary
    """Operator who performed the download."""

    public: bool
    """Indicates if the download was public."""

    parent_id: UUID | None = None
    """Parent download history ID, if applicable."""

    file_id: UUID
    """ID of the downloaded file."""

    file_path: str
    """Path of the downloaded file."""

    file_exists: bool = False
    """Indicates if the downloaded file still exists."""

    repository_count: int
    """Number of repositories involved in the download."""

    group_count: int
    """Number of groups involved in the download."""

    user_count: int
    """Number of users involved in the download."""

    children_count: int = 0
    """Number of related child elements."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""


class UploadHistoryData(BaseModel):
    """Upload history data model."""

    id: UUID
    """Upload history ID."""

    timestamp: datetime
    """Timestamp of the upload event."""

    end_timestamp: datetime | None = None
    """Timestamp end of the upload event."""

    public: bool
    """Indicates if the upload was public."""

    operator: UserSummary
    """Operator who performed the upload."""

    status: t.Literal["S", "F", "P"]
    """Status of the upload operation."""

    file_path: str
    """Path of the uploaded file."""

    file_id: UUID
    """ID of the uploaded file."""

    repository_count: int
    """Number of repositories involved in the upload."""

    group_count: int
    """Number of groups involved in the upload."""

    user_count: int
    """Number of users involved in the upload."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""
