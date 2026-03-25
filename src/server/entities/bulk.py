#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for Bulk entity for client side."""

import typing as t

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, RootModel

from server.entities.common import camel_case_config, forbid_extra_config
from server.entities.user_detail import UserDetail


class RepositoryMember(BaseModel):
    """Model for members of a repository."""

    groups: set[str]
    """The groups belonging to the repository."""

    users: set[str]
    """The users belonging to the repository."""


class ValidateResults(BaseModel):
    """Model for summary of bulk validation result."""

    results: list[EachResult]
    """The list of validation results for each user."""

    summary: ResultSummary
    """The summary of the validation operation."""

    missing_user: list[UserDetail] = []
    """The list of missing users."""

    offset: int
    """The offset for pagination."""

    page_size: int
    """The page size for pagination."""

    model_config = camel_case_config | forbid_extra_config
    """Configure camelCase aliasing and forbid extra fields."""


class ResultSummary(BaseModel):
    """Summary of the history operation."""

    create: int
    """Number of created items."""
    update: int
    """Number of updated items."""
    delete: int
    """Number of deleted items."""
    skip: int
    """Number of skipped items."""
    error: int
    """Number of error items."""

    model_config = camel_case_config | forbid_extra_config
    """Configure camelCase aliasing and forbid extra fields."""


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


class Aggregated(t.TypedDict):
    """Model for aggregated data."""

    summary: dict[str, int]
    """Summary of the aggregation."""

    results: list[EachResult]
    """List of check results."""

    missing_user: list[UserDetail]
    """List of missing users."""


class FileContent(t.TypedDict):
    """Model for file content as dictionary."""

    repositories: dict[str, str]
    """Dictionary of repositories."""

    groups: dict[str, str]
    """Dictionary of groups."""

    users: dict[str, str]
    """Dictionary of users."""
