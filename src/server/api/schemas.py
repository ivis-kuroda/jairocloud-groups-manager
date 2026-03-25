#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Schema definitions for the API endpoints.

These schemas used in request and response validation.
"""

import typing as t

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, RootModel, model_validator
from werkzeug.datastructures import FileStorage

from server.entities.common import camel_case_config
from server.entities.search_request import SearchResult
from server.messages.base import LogMessage


ignore_extra_config = ConfigDict(
    extra="ignore",
    validate_assignment=True,
)
"""Common configuration dict to ignore extra fields.

- extra: "ignore" - Ignores extra fields not defined in the model.
- validate_assignment: True - Validates fields on assignment.
"""


class LoginUserState(BaseModel):
    """Schema for logged-in user state response."""

    id: str
    """The ID of the user."""

    eppn: str
    """The eduPersonPrincipalName of the user."""

    user_name: str
    """The username of the user. Alias to 'userName'."""

    is_system_admin: bool
    """Whether the user is a system administrator. Alias to 'isSystemAdmin'."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""


class OAuthTokenQuery(BaseModel):
    """Schema for OAuth token query parameters."""

    code: str
    """Authorization code received from the Authorization Server."""

    state: str
    """State parameter to prevent CSRF attacks."""

    model_config = ignore_extra_config
    """Configure to ignore extra fields."""


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    code: str | None = None
    """Message code."""

    message: str
    """Error message."""

    @model_validator(mode="before")
    @classmethod
    def preprocess(cls, data: dict) -> dict:
        """Extract error message from string or LogMessage.

        Args:
            data : The error message.

        Returns:
            dict: The processed error message.
        """
        if (message := data.get("message")) and isinstance(message, LogMessage):
            data.setdefault("code", message.code)
            data["message"] = message.data
        return data


class GlobalSearchQuery(BaseModel):
    """Schema for global search query parameters."""

    q: t.Annotated[str | None, "query"] = None
    """Search term to filter results."""

    l: t.Annotated[int | None, "length"] = None  # noqa: E741
    """Page size (number of items per page)."""


class GlobalSearchResult(RootModel):
    """Schema for global search result."""

    root: list[SearchResult]
    """List of search results."""


class RepositoriesQuery(BaseModel):
    """Schema for repositories search query parameters."""

    q: t.Annotated[str | None, "query"] = None
    """Search term to filter repositories."""

    i: t.Annotated[list[str] | None, "ids"] = None
    """Filter by repository IDs."""

    k: t.Annotated[str | None, "key"] = None
    """Attribute key to sort repositories."""

    d: t.Annotated[
        t.Literal["asc", "desc"] | None,
        "direction",
    ] = None
    """Sort order: 'asc' (ascending) or 'desc' (descending)."""

    p: t.Annotated[int | None, "page"] = None
    """Page number to retrieve."""

    l: t.Annotated[int | None, "length"] = None  # noqa: E741
    """Page size (number of items per page)."""

    model_config = ignore_extra_config
    """Configure to ignore extra fields."""


class GroupsQuery(BaseModel):
    """Schema for groups search query parameters."""

    q: t.Annotated[str | None, "query"] = None
    """Search term to filter groups."""

    i: t.Annotated[list[str] | None, "ids"] = None
    """Filter by group IDs."""

    r: t.Annotated[list[str] | None, "repositories"] = None
    """Filter by affiliated repository IDs."""

    u: t.Annotated[list[str] | None, "users"] = None
    """Filter by affiliated user IDs."""

    s: t.Annotated[t.Literal[0, 1] | None, "status"] = None
    """Filter by public status:

    0 (public), 1 (private).
    """

    v: t.Annotated[t.Literal[0, 1, 2] | None, "visibility"] = None
    """Filter by member list visibility:

    0 (public), 1 (private), 2 (hidden).
    """

    k: t.Annotated[str | None, "key"] = None
    """Attribute key to sort groups."""

    d: t.Annotated[
        t.Literal["asc", "desc"] | None,
        "direction",
    ] = None
    """Sort order: 'asc' (ascending) or 'desc' (descending)."""

    p: t.Annotated[int | None, "page"] = None
    """Page number to retrieve."""

    l: t.Annotated[int | None, "length"] = None  # noqa: E741
    """Page size (number of items per page)."""

    model_config = ignore_extra_config
    """Configure to ignore extra fields."""


class UsersQuery(BaseModel):
    """Schema for users search query parameters."""

    q: t.Annotated[str | None, "query"] = None
    """Search term to filter users."""

    i: t.Annotated[list[str] | None, "ids"] = None
    """Filter by user IDs."""

    r: t.Annotated[list[str] | None, "repositories"] = None
    """Filter by affiliated repository IDs."""

    g: t.Annotated[list[str] | None, "groups"] = None
    """Filter by affiliated group IDs."""

    a: t.Annotated[list[int] | None, "authorities"] = None
    """Filter by user roles:

    0 (system admin), 1 (repository admin), 2 (community admin),
    3 (contributor), 4 (general user).
    """

    s: t.Annotated[date | None, "start"] = None
    """Filter by last modified date (from)."""

    e: t.Annotated[date | None, "end"] = None
    """Filter by last modified date (to)."""

    k: t.Annotated[str | None, "key"] = None
    """Attribute key to sort users."""

    d: t.Annotated[
        t.Literal["asc", "desc"] | None,
        "direction",
    ] = None
    """Sort order: 'asc' (ascending) or 'desc' (descending)."""

    p: t.Annotated[int | None, "page"] = None
    """Page number to retrieve."""

    l: t.Annotated[int | None, "length"] = None  # noqa: E741
    """Page size (number of items per page)."""

    model_config = ignore_extra_config
    """Configure to ignore extra fields."""


class RepositoryDeleteQuery(BaseModel):
    """Schema for repository deletion query parameters."""

    confirmation: str
    """Confirmation string to prevent accidental deletion."""


class GroupPatchRequest(BaseModel):
    """Schema for patching group information."""

    operations: list[GroupPatchOperation]
    """List of patch operations."""


class GroupPatchOperation(BaseModel):
    """Schema for patching group members."""

    op: t.Literal["add", "remove"]
    """The patch operation to perform."""

    path: str
    """The target path of the patch operation."""

    value: list[str]
    """Value to be changed."""


class DeleteGroupsBody(BaseModel):
    """Schema for deleting multiple groups."""

    group_ids: set[str]
    """Set of group IDs to delete."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""


class HistoryPublic(BaseModel):
    """History public status."""

    public: bool
    """Public status."""


class OperatorQuery(BaseModel):
    """Schema for operator query parameters."""

    q: t.Annotated[str | None, "query"] = None
    """Search term to filter operators."""

    p: t.Annotated[int | None, "page"] = None
    """Page number to retrieve."""

    l: t.Annotated[int | None, "length"] = None  # noqa: E741
    """Page size (number of items per page)."""

    model_config = ignore_extra_config
    """Configure to ignore extra fields."""


class TargetRepositoryForm(BaseModel):
    """Schema for target repository."""

    repository_id: str
    """ID of the target repository."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""


class BulkFileForm(BaseModel):
    """Schema for upload files."""

    bulk_file: FileStorage
    """File to upload."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    """Configure to allow arbitrary types."""


class BulkBody(BaseModel):
    """Schema for response body of bulk upload processing."""

    temp_file_id: UUID | None = None
    """Temporary ID for the bulk upload session."""

    history_id: UUID | None = None
    """History ID associated with the bulk upload."""

    task_id: str | None = None
    """Task ID associated with the bulk upload."""

    status: str | None = None
    """Status of the bulk upload."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""


class ExcuteRequest(BaseModel):
    """Schema for requset body of bulk upload execution."""

    temp_file_id: UUID
    """Temporary ID for the upload session."""

    repository_id: str | None = None
    """ID of the target repository."""

    delete_users: list[str] | None = None
    """List of users whose files are to be deleted."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""


class UploadQuery(BaseModel):
    """Query parameters for upload history data."""

    f: t.Annotated[list[int] | None, "filter"] = None
    """Filter by status.
    0:create, 1:delete, 2:error, 3:skip, 4:update"""

    p: t.Annotated[int | None, "page"] = None
    """Page number to retrieve."""

    l: t.Annotated[int | None, "length"] = None  # noqa: E741
    """Page size (number of items per page)."""


class FileQuery(UsersQuery):
    """Query parameters for file export."""

    f: t.Annotated[t.Literal["tsv", "csv"], "format"] = "tsv"
    """File format for export."""

    model_config = ignore_extra_config
    """Configure to ignore extra fields."""


class CacheQuery(BaseModel):
    """Schema for cache query parameters."""

    q: t.Annotated[str | None, "term"] = None
    """Search term for querying cache entries."""

    f: t.Annotated[list[t.Literal["e", "n"]] | None, "filter"] = None
    """Filter expression for querying cache entries."""

    p: t.Annotated[int | None, "page"] = None
    """Page number for pagination."""

    l: t.Annotated[int | None, "per"] = None  # noqa: E741
    """Number of items per page for pagination."""


type CacheOperation = t.Literal["all", "id-specified"]


class CacheRequest(BaseModel):
    """Schema for cache update request."""

    ids: list[str] | None = None
    """List of repository IDs to update cache for.
    Required if operation is 'id-specified'.
    """

    op: CacheOperation
    """Operation type: 'all' to update all, 'id-specified' to update specified IDs."""

    model_config = camel_case_config
    """Configure to use camelCase aliasing."""
