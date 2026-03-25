#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Model definition for history tables."""

from __future__ import annotations

import typing as t
import uuid

from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import db


class _FileContent(t.TypedDict):
    """Definition for json data of `Files.file_content`."""

    repositories: list[dict[str, str]]
    """Repositories contained in the file."""

    groups: list[dict[str, str]]
    """Groups contained in the file."""

    users: list[dict[str, str]]
    """Users contained in the file."""


class _ResultData(t.TypedDict):
    """Definition for json data of `UploadHistory.results`."""

    summary: dict[str, int]
    """Summary of execution results or check results."""

    items: list[dict]
    """Items of execution results or check results."""

    missing_users: list[dict]
    """Users not contained in the file."""


class Files(db.Model):
    """Model for a files stored as a key-value pair.

    Attributes:
        id (UUID): id (primary key).
        file_path (str): file path.
        file_content (FileContent): file content mapped JSONB.
    """

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid7,
        primary_key=True,
    )
    """File identifier (UUID)."""

    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    """File path."""

    file_content: Mapped[_FileContent] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(postgresql.JSONB, "postgresql")),
        nullable=False,
    )
    """Repositories, groups, and users contained in the file."""

    __table_args__ = (Index(None, "file_content", postgresql_using="gin"),)


class DownloadHistory(db.Model):
    """Model for a download history stored as a key-value pair."""

    __tablename__ = "download_history"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid7,
        primary_key=True,
    )
    """History record ID (uuid.UUID)."""

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.timezone("UTC", func.now()),
    )
    """Download timestamp in UTC (TIMESTAMPTZ(6); server default UTC now)."""

    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Files.id),
        nullable=False,
    )
    """Foreign key to `Files.id` (downloaded file ID)."""

    file: Mapped[Files] = relationship()
    """Relationship to `Files` model."""

    operator_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    """Operator identifier (VARCHAR(50); indexed)."""

    operator_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    """Operator name (VARCHAR(50))."""

    public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    """Public/private flag (BOOLEAN NOT NULL DEFAULT true)."""

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{__tablename__}.id"),
        nullable=True,
    )
    """Self-referencing FK to the first download record (`DownloadHistory.id`)."""

    children: Mapped[list[DownloadHistory]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    """Relationship to child DownloadHistory records."""

    parent: Mapped[DownloadHistory | None] = relationship(
        back_populates="children",
        remote_side=[id],  # noqa: A003
    )
    """Relationship to parent DownloadHistory record."""


class UploadHistory(db.Model):
    """Model for a upload history stored as a key-value pair."""

    __tablename__ = "upload_history"

    type Status = t.Literal["S", "P", "F", "C"]
    """Allowed status values for the upload history.
    - 'S': Success
    - 'P': In Progress
    - 'F': Failed
    - 'C': Cancel
    """

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid7,
        primary_key=True,
    )
    """History record ID (UUID)."""

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.timezone("UTC", func.now()),
    )
    """Upload start timestamp in UTC (TIMESTAMPTZ(6); server default UTC now)."""

    end_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    """Upload end timestamp in UTC (TIMESTAMPTZ(6); nullable)."""

    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Files.id),
        nullable=False,
    )
    """Foreign key to `Files.id` (uploaded file ID)."""

    file: Mapped[Files] = relationship()
    """Relationship to the `Files` model."""

    operator_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    """Operator identifier (VARCHAR(50); indexed)."""

    operator_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    """Operator name (VARCHAR(50))."""

    public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    """Public/private flag (BOOLEAN NOT NULL DEFAULT true)."""

    status: Mapped[Status] = mapped_column(
        String(1),
        default="C",
        nullable=False,
    )
    """Status: 'C' (cancel) 'S' (success), 'F' (failure), 'P' (in progress)."""

    results: Mapped[_ResultData] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(postgresql.JSONB, "postgresql")),
        nullable=False,
    )
    """Upload result data."""

    __table_args__ = (
        CheckConstraint(
            status.in_(t.get_args(Status.__value__)),
            name="status",
        ),
        Index(None, "results", postgresql_using="gin"),
    )
