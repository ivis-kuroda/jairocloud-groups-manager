#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for Bulk entity for client side."""

import typing as t

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, RootModel

from server.entities.common import camel_case_config, forbid_extra_config
from server.entities.summaries import GroupSummary, RepositorySummary, UserSummary
from server.entities.user_detail import UserDetail


class ValidateResults(BaseModel):
    """Model for summary of bulk validation result."""

    items: list[EachResult]
    """The list of validation results for each user."""

    summary: ResultSummary
    """The summary of the validation operation."""

    missing_users: list[UserDetail] = Field(default_factory=list)
    """The list of users not contained in the file."""

    offset: int | None = None
    """The offset for pagination."""

    page_size: int | None = None
    """The page size for pagination."""

    model_config = camel_case_config | forbid_extra_config
    """Configure camelCase aliasing and forbid extra fields."""


class ResultSummary(BaseModel):
    """Summary of the history operation."""

    create: int = 0
    """Number of created items."""

    update: int = 0
    """Number of updated items."""

    delete: int = 0
    """Number of deleted items."""

    skip: int = 0
    """Number of skipped items."""

    error: int = 0
    """Number of error items."""

    model_config = forbid_extra_config
    """Configure forbid extra fields."""


class EachResult(BaseModel):
    """Model for result of validation check for each user."""

    id: str | None = None
    """The unique identifier for the user."""

    eppn: list[str]
    """The eduPersonPrincipalNames of the user."""

    email: list[EmailStr]
    """The e-mail of the user."""

    user_name: str
    """The username of the user."""

    groups: set[str]
    """The groups of the user."""

    status: t.Literal["create", "update", "delete", "skip", "error"]
    """The status of the validation check."""

    code: str | None = None
    """The code representing the result of the validation check."""

    message: str | None = None
    """The message describing the result of the validation check."""

    model_config = camel_case_config | forbid_extra_config
    """Configure camelCase aliasing and forbid extra fields."""


class ExecuteResults(BaseModel):
    """Model for summary of bulk upload result."""

    items: list[EachResult]
    """The list of upload results for each user."""

    summary: ResultSummary
    """The summary of the upload operation."""

    file_id: UUID
    """The ID of the uploaded file."""

    file_name: str
    """The name of the uploaded file."""

    operator: str
    """The operator who performed the upload."""

    start_timestamp: datetime
    """The timestamp when the upload started."""

    end_timestamp: datetime | None = None
    """The timestamp when the upload ended."""

    total: int
    """The total number of users processed."""

    offset: int
    """The offset for pagination."""

    page_size: int
    """The page size for pagination."""

    model_config = camel_case_config | forbid_extra_config
    """Configure camelCase aliasing and forbid extra fields."""


class UserAggregated(RootModel):
    """Model for aggregated user data."""

    root: list[UserDetail]
    """List of user details."""


class FileContent(BaseModel):
    """Model for file content as dictionary."""

    repositories: list[RepositorySummary] = Field(default_factory=list)
    """List of repositories."""

    groups: list[GroupSummary] = Field(default_factory=list)
    """List of groups."""

    users: list[UserSummary] = Field(default_factory=list)
    """List of users."""

    model_config = camel_case_config | forbid_extra_config
    """Configure camelCase aliasing and forbid extra fields."""
