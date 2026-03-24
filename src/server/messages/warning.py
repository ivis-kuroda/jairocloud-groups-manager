#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides warning log messages used in the server application."""

from .base import LogMessage


DATABASE_NOT_EXIST = LogMessage(
    "W010",
    "The database does not exist. Application may not function correctly.",
)


FAILED_CONNECT_REDIS = LogMessage(
    "W020",
    "Failed to connect to Redis. Application may not function correctly: %(error)s",
)


ACCESS_TOKEN_NOT_AVAILABLE = LogMessage(
    "W030",
    "Access token is invalid or expired.",
)


DENIED_LOGIN_MISSING_EPPN = LogMessage(
    "W060",
    "Login denied due to missing ePPN in Shibboleth headers.",
)

DENIED_LOGIN_USER_NOT_FOUND = LogMessage(
    "W061",
    "Login denied because no User resource not found (ePPN: %(eppn)s).",
)

DENIED_LOGIN_INSUFFICIENT_ROLE = LogMessage(
    "W062",
    "Login denied due to insufficient role. User has %(role)s.",
)

FAILED_DELETE_LOGIN_SESSION = LogMessage(
    "W065",
    "Failed to delete login session for user (ePPN: %(eppn)s).",
)


FAILED_SET_CACHE = LogMessage(
    "W080",
    "Failed to set cache (func %(func)s, id: %(id)s).",
)

FAILED_GET_CACHE = LogMessage(
    "W081",
    "Failed to get cache (func %(func)s, id: %(id)s).",
)

FAILED_PARSE_CACHE = LogMessage(
    "W082",
    "Failed to parse cache (func %(func)s, id: %(id)s).",
)

FAILED_DELETE_CACHE = LogMessage(
    "W083",
    "Failed to delete cache (func %(func)s, id: %(id)s).",
)


CONFIRM_DELETE_GROUP = LogMessage(
    "W230",
    "Are you sure to delete the Group (id: %(gid)s)?",
)

FAILED_UPDATE_TASK_PROGRESS = LogMessage(
    "W800",
    "Failed to update current task progress (done: %(done)s, total: %(total)s).",
)

FAILED_UPDATE_TASK_EXECUT_STATUS = LogMessage(
    "W801",
    "Failed to update current task execution status "
    "(repository: %(rid)s, status: %(status)s, retries: %(retries)s).",
)
