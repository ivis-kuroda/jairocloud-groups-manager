#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Custom exceptions for the server application."""

from server.messages.base import LogMessage


class JAIROCloudGroupsManagerError(Exception):
    """Base exception for the server application."""

    def __init__(self, message: str) -> None:
        """Initialize the exception instance.

        Args:
            message (str | LogMessage): The error message.

        """
        self.code = None
        self.message = message
        if isinstance(message, LogMessage):
            self.code = message.code
            message = message.data
        super().__init__(message)

        self.string = message

    def __str__(self) -> str:
        """Return the string representation of the exception."""
        if self.code:
            return f"{self.code} | {self.string}"
        return self.string


class ConfigurationError(JAIROCloudGroupsManagerError):
    """Exception for configuration errors."""


class CertificatesError(JAIROCloudGroupsManagerError):
    """Exception for certificate errors.

    Errors caused by entity ID or certificates issues.
    """


class ServiceSettingsError(JAIROCloudGroupsManagerError):
    """Exception for service settings."""


class CredentialsError(ServiceSettingsError):
    """Exception for client credentials.

    Error caused by client ID and client secret issues.
    """


class OAuthTokenError(ServiceSettingsError):
    """Exception for OAuth token.

    Error caused by access token and refresh token issues.
    """


class UnsafeOperationError(JAIROCloudGroupsManagerError):
    """Exception for unsafe operations.

    Error caused by operations considered unsafe calling unexpectedly.
    """


class SystemAdminNotFound(UnsafeOperationError):  # noqa: N818
    """Exception for system administrator not found.

    Error caused by the absence of a system administrator in the system.
    """


class InfrastructureError(JAIROCloudGroupsManagerError):
    """Exception for infrastructure errors.

    Error caused by issues in the underlying infrastructure.
    """


class DatabaseError(InfrastructureError):
    """Exception for database errors.

    Error caused by database operation issues.
    """


class DatastoreError(InfrastructureError):
    """Exception for datastore errors.

    Error caused by datastore operation issues.
    """


class TaskExecutionError(DatastoreError):
    """Exception for task execution errors.

    Error caused by issues during task execution.
    """


class RecordNotFound(JAIROCloudGroupsManagerError):  # noqa: N818
    """Exception for record not found errors.

    Error caused by requests for non-existing records.
    """


class InvalidRecordError(JAIROCloudGroupsManagerError):
    """Exception for invalid record errors.

    Error caused by invalid record data or structure.
    """


class ApiClientError(JAIROCloudGroupsManagerError):
    """Exception for mAP Core API errors.

    Error caused by mAP Core API server issues.
    """


class ResourceInvalid(ApiClientError):  # noqa: N818
    """Exception for resource invalid errors from mAP Core API server.

    Error caused by invalid resource data in requests.
    """


class ResourceNotFound(ApiClientError):  # noqa: N818
    """Exception for resource not found errors from mAP Core API server.

    Error caused by requests for non-existing resources.
    """


class UnexpectedResponseError(ApiClientError):
    """Exception for unexpected responses from mAP Core API server.

    Error caused by unexpected response structure or data from mAP Core API server.
    """


class ApiRequestError(JAIROCloudGroupsManagerError):
    """Exception for the server application API errors.

    Error caused by API request issues.
    """


class RequestConflict(ApiRequestError):  # noqa: N818
    """Exception for the request conflict errors.

    Error caused by conflicts in the request content.
    """


class InvalidQueryError(ApiRequestError):
    """Exception for unexpected query construction errors.

    Error caused by unexpected query structure or data during query construction.
    """


class InvalidFormError(ApiRequestError):
    """Exception for invalid form data errors.

    Error caused by invalid form data in API requests.
    """


class ImmutableError(JAIROCloudGroupsManagerError):
    """Exception for immutable attribute modification errors.

    Error caused by attempts to modify immutable attributes.
    """


class BulkOperationError(JAIROCloudGroupsManagerError):
    """Exception for bulk operation errors.

    Error caused by issues during bulk operations.
    """


class FileValidationError(BulkOperationError):
    """Exception for validation errors in bulk operations.

    Error caused by validation failures during bulk operations.
    """


class FileNotFound(BulkOperationError):  # noqa: N818
    """Exception for file not found errors in bulk operations.

    Error caused by missing files during bulk operations.
    """


class FileFormatError(BulkOperationError):
    """Exception for file format errors in bulk operations.

    Error caused by invalid file formats during bulk operations.
    """


class FileUploadError(BulkOperationError):
    """Exception for file upload errors in bulk operations.

    Error caused by issues during file upload in bulk operations.
    """


class InvalidExportError(BulkOperationError):
    """Exception for invalid export errors.

    Error caused by issues during export operations.
    """


class GroupCacheError(JAIROCloudGroupsManagerError):
    """Exception for group cache errors.

    Error caused by issues in group cache operations.
    """


class ProgrammingError(JAIROCloudGroupsManagerError):
    """Exception for programming errors.

    Error caused by issues in the code logic or structure.
    """
