#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Constant values for the server application."""

# ruff: noqa: N801

from enum import StrEnum
from typing import Final


class RUNTIME_ROLE(StrEnum):
    """Constants for runtime roles of the application."""

    SERVER = "server"
    """Role identifier for the server application."""

    WORKER = "worker"
    """Role identifier for the worker application."""

    CLI = "cli"
    """Role identifier for the command-line interface application."""


DEFAULT_CONFIG_PATH: Final = "configs/server.config.toml"
"""Default path to the server configuration TOML file."""

DEFAULT_LOG_FORMAT: Final = (
    "[%(asctime)s.%(msecs)03dZ] %(levelname)-8s %(message)s (%(addr)s - %(user)s)"
)
"""Default log format string for production environment."""

DEFAULT_LOG_FORMAT_DEV: Final = (
    "[%(asctime)s.%(msecs)03dZ] %(levelname)-8s %(message)s (%(pathname)s:%(lineno)d)"
)
"""Default log format string for development environment."""

DEFAULT_LOG_DATEFMT: Final = "%Y-%m-%dT%H:%M:%S"
"""Default date format string for log timestamps."""

DEFAULT_SEARCH_COUNT: Final = 20
"""Default number of records to return in search from database."""


class SHIB_HEADERS(StrEnum):
    """Constants for Shibboleth headers."""

    EPPN = "eppn".upper()
    """Header name for eduPersonPrincipalName."""

    IS_MEMBER_OF = "isMemberOf".upper()
    """Header name for isMemberOf attribute."""

    DISPLAY_NAME = "displayName".upper()
    """Header name for display name."""

    JA_DISPLAY_NAME = "jaDisplayName".upper()
    """Header name for Japanese display name."""


MAP_USER_SCHEMA: Final = "urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:User"
"""Schema URI for mAP User resources."""

MAP_GROUP_SCHEMA: Final = "urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Group"
"""Schema URI for mAP Group resources."""

MAP_SERVICE_SCHEMA: Final = (
    "urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Service"
)
"""Schema URI for mAP Service resources."""

MAP_LIST_RESPONSE_SCHEMA: Final = (
    "urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:ListResponse"
)
"""Schema URI for mAP List Response resources."""

MAP_ERROR_SCHEMA: Final = "urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Error"
"""Schema URI for mAP Error resources."""

MAP_PATCH_SCHEMA: Final = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
"""Schema URI for PATCH request payloads."""

MAP_BULK_REQUEST_SCHEMA: Final = "urn:ietf:params:scim:api:messages:2.0:BulkRequest"
"""Schema URI for Bulk request payloads."""

MAP_BULK_RESPONSE_SCHEMA: Final = "urn:ietf:params:scim:api:messages:2.0:BulkResponse"
"""Schema URI for Bulk response payloads."""

MAP_OAUTH_ISSUE_ENDPOINT: Final = "/oauth/sslauth/issue.php"
"""Endpoint for issuing client credentials in mAP Core Authorization Server."""

MAP_OAUTH_AUTHORIZE_ENDPOINT: Final = "/oauth/shib/authrequest.php"
"""Endpoint for issuing authorization code from mAP Core Authorization Server."""

MAP_OAUTH_TOKEN_ENDPOINT: Final = "/oauth/token.php"  # noqa: S105
"""Endpoint for issuing access tokens from mAP Core Authorization Server."""

MAP_OAUTH_CHECK_ENDPOINT: Final = "/oauth/resource.php"
"""Endpoint for checking token validity in mAP Core Authorization Server."""


MAP_USERS_ENDPOINT: Final = "/api/v2/Users"
"""Endpoint for User resources in mAP Core API."""

MAP_EXIST_EPPN_ENDPOINT: Final = "/api/v2/Existeppn"
"""Endpoint to check existence of ePPN in mAP Core API."""

MAP_SELF_ENDPOINT: Final = "/api/v2/Self"
"""Endpoint for getting access token owner's User resource in mAP Core API."""

MAP_GROUPS_ENDPOINT: Final = "/api/v2/Groups"
"""Endpoint for Group resources in mAP Core API."""

MAP_SERVICES_ENDPOINT: Final = "/api/v2/Services"
"""Endpoint for Service resources in mAP Core API."""

MAP_BULK_ENDPOINT: Final = "/api/v2/Bulk"
"""Endpoint for Bulk resources in mAP Core API."""

MAP_DEFAULT_SEARCH_COUNT: Final = 20
"""Default number of resources to return in search results from mAP Core API."""

MAP_NOT_FOUND_PATTERN: Final = r"'(.*)' Not Found"
"""Pattern to identify 'Not Found' errors from mAP Core API."""

MAP_DUPLICATE_ID_PATTERN: Final = r"Duplicate id '(.*)'"
"""Pattern to identify 'Duplicate ID' errors from mAP Core API."""

MAP_ALREADY_TIED_PATTERN: Final = r"(.*) is already tied to another account"
"""Pattern to identify 'Already Tied' errors from mAP Core API."""

MAP_ILLEGAL_EPPN_PATTERN: Final = (
    r"'(.*)' illegal (eduPersonPrincipalNames needs idpEntityId)"
)
"""Pattern to identify 'Illegal ePPN' errors from mAP Core API."""

MAP_NO_RIGHTS_CREATE_PATTERN: Final = r"You do not have creation right of (.*)"
"""Pattern to identify 'No Creation Rights' errors from mAP Core API."""

MAP_NO_RIGHTS_UPDATE_PATTERN: Final = r"No update rights for '(.*)'"
"""Pattern to identify 'No Update Rights' errors from mAP Core API."""

MAP_NO_RIGHTS_APPEND_PATTERN: Final = r"No append rights for '(.*)'"
"""Pattern to identify 'No Append Rights' errors from mAP Core API."""


OAUTH_CALLBACK_CHANNEL: Final = "oauth-callback"
"""Channel name for receiving token issuance callbacks."""


GROUP_DEFAULT_PUBLIC: Final = False
"""Default value for the 'public' attribute of groups."""

GROUP_DEFAULT_MEMBER_LIST_VISIBILITY: Final = "Private"
"""Default value for the 'memberListVisibility' attribute of groups."""


class USER_ROLES(StrEnum):
    """Constants for user roles.

    Note: These are listed in descending order of authority.
    """

    SYSTEM_ADMIN = "system_admin"
    """Role identifier for System Administrators."""

    REPOSITORY_ADMIN = "repository_admin"
    """Role identifier for Repository Administrators."""

    COMMUNITY_ADMIN = "community_admin"
    """Role identifier for Community Administrators."""

    CONTRIBUTOR = "contributor"
    """Role identifier for Contributors."""

    GENERAL_USER = "general_user"
    """Role identifier for General Users."""


USER_NAME_MAX_LENGTH: Final = 50
"""Maximum allowed length for user names."""

USER_EXPORT_HEADERS_V1 = [
    "id",
    "user_name",
    "groups[].id",
    "groups[].name",
    "role",
    "edu_person_principal_names[]",
    "preferred_language",
    "emails[]",
]
"""List of fields to include in user export files for version 1.0."""


HAS_REPO_ID_PATTERN: Final = r"^(?!(?:.*\{repository_id\}){2}).*\{repository_id\}.*$"
"""Regular expression pattern for role-type group IDs.

It should include one `{repository_id}` placeholder.
"""

HAS_REPO_ID_AND_USER_DEFINED_ID_PATTERN: Final = (
    r"^"
    r"(?!.*\{repository_id\}.*\{repository_id\})"
    r"(?!.*\{user_defined_id\}.*\{user_defined_id\})"
    r".*\{repository_id\}.*"
    r"\{user_defined_id\}.*$"
)
"""Regular expression pattern for user-defined group IDs.

It should include one `{repository_id}`, followed by one `{user_defined_id}`
placeholders.
"""

HAS_REPO_NAME_PATTERN: Final = (
    r"^(?!(?:.*\{repository_name\}){2}).*\{repository_name\}.*$"
)
"""Regular expression pattern for role-type group names.

It should include one `{repository_name}` placeholder.
"""

IS_MEMBER_OF_PATTERN: Final = r"/gr/([^/;]+)(?=;|$)(?!/admin)"
"""Regular expression pattern to extract group IDs from isMemberOf attribute.

This pattern extracts group IDs from URLs in the isMemberOf attribute under the
following conditions:

- The URL contains the path segment "/gr/".
- The group ID is the substring immediately following "/gr/".
- The group ID does not contain "/" or ";" characters.
- The URL ends with a semicolon (";") or the end of the string.
- URLs ending with "/admin" are excluded from matching.
"""

GROUP_CACHE_KEY_PATTERN: Final = "weko-group-cache-db"
"""Regular expression pattern to identify cache keys in Redis."""
