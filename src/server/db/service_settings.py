#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Model definition for service settings table."""

import typing as t

from datetime import datetime  # ruff: ignore[typing-only-standard-library-import]

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from .base import db


class ServiceSettings(db.Model):
    """Model for a service setting stored as a key-value pair.

    Attributes:
        key (str): Setting name (primary key).
        updated (datetime): Last updated timestamp (auto-set on change).
        value (dict): Setting value as a JSON object.
    """

    __tablename__ = "service_settings"

    key: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    """Setting name (primary key)."""

    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        onupdate=func.timezone("UTC", func.now()),
    )
    """Last updated timestamp (auto-set on change)."""

    value: Mapped[dict[str, t.Any]] = mapped_column(
        MutableDict.as_mutable(JSON().with_variant(postgresql.JSONB, "postgresql")),
    )
    """Setting value as a JSON object."""
