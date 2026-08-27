#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides informational log messages used in the server application."""

from .base import LogMessage


DATABASE_CREATED = LogMessage(
    "I010",
    "Database has been created.",
)

DATABASE_ALREADY_EXISTS = LogMessage(
    "I011",
    "Database already exists. No action taken.",
)

DATABASE_DESTROYED = LogMessage(
    "I012",
    "Database has been destroyed.",
)

DATABASE_NOT_EXIST = LogMessage(
    "I013",
    "Database does not exist. No action taken.",
)

TABLE_CREATED = LogMessage(
    "I014",
    "Database tables created.",
)

TABLE_DROPPED = LogMessage(
    "I015",
    "Database tables dropped.",
)


SUCCESS_ISSUE_CREDENTIALS = LogMessage(
    "I030",
    "Successfully issued client credentials for the mAP Core API.",
)

REQUEST_FOR_AUTH_CODE = LogMessage(
    "I031",
    "Please authenticate at the following URL to issue an access token: %(url)s",
)

WAITING_TOKEN_ISSUED = LogMessage(
    "I032",
    "Waiting for the access token to be issued. "
    "Press Ctrl+C to stop waiting (it does not cancel the token issuance).",
)

SUCCESS_ISSUE_TOKEN = LogMessage(
    "I033",
    "Successfully issued access token for the mAP Core API.",
)

SUCCESS_REFRESH_TOKEN = LogMessage(
    "I034",
    "Successfully refreshed access token for the mAP Core API.",
)

ACCESS_TOKEN_AVAILABLE = LogMessage(
    "I035",
    "Access token is valid and available.",
)

SUCCESS_GET_TOKEN_OWNER = LogMessage(
    "I036",
    "Successfully get token owner's User resource from mAP Core API. \n%(json)s",
)


RECEIVE_RESPONSE_MESSAGE = LogMessage(
    "I050",
    "Received response from mAP Core API: %(message)s",
)


USER_LOGGED_IN = LogMessage(
    "I060",
    "User (ePPN: %(eppn)s) logged in.",
)

USER_LOGGED_OUT = LogMessage(
    "I061",
    "User (ePPN: %(eppn)s) logged out.",
)

USER_SESSION_EXPIRED = LogMessage(
    "I062",
    "Session terminated due to expiration for user (ePPN: %(eppn)s).",
)

USER_CONTEXT_PREPARED = LogMessage(
    "I065",
    "User context prepared for task (ePPN: %(eppn)s).",
)


RESOURCE_CACHE_CREATED = LogMessage(
    "I080", "Cache created for resource (func %(func)s, id: %(id)s)."
)

RESOURCE_CACHE_HIT = LogMessage(
    "I081",
    "Cache hit for resource (func %(func)s, id: %(id)s).",
)

RESOURCE_CACHE_DELETED = LogMessage(
    "I082",
    "Cache deleted for resource (func %(func)s, id: %(id)s).",
)

SUCCESS_GET_REPOSITORY = LogMessage(
    "I105",
    "Successfully get Repository resource. \n%(json)s",
)

SUCCESS_CREATE_REPOSITORY = LogMessage(
    "I110",
    "Successfully created Service resource for Repository (id: %(id)s)",
)

SUCCESS_CREATE_ROLEGROUPS = LogMessage(
    "I111",
    "Successfully created role-type groups for Repository (id: %(id)s)",
)

SUCCESS_UPDATE_REPOSITORY = LogMessage(
    "I120",
    "Successfully updated Service resource for Repository (id: %(id)s)",
)

SUCCESS_DELETE_REPOSITORY = LogMessage(
    "I130",
    "Successfully deleted Service resource for Repository (id: %(id)s)",
)


SUCCESS_GET_GROUP = LogMessage(
    "I205",
    "Successfully get Group resource. \n%(json)s",
)

SUCCESS_CREATE_GROUP = LogMessage(
    "I210",
    "Successfully created Group resource (id: %(id)s) in Repository (id: %(rid)s).",
)

SUCCESS_UPDATE_GROUP = LogMessage(
    "I220",
    "Successfully updated Group resource (id: %(id)s) in Repository (id: %(rid)s).",
)

SUCCESS_UPDATE_GROUP_MEMBERS = LogMessage(
    "I221",
    "Successfully updated members of Group resource "
    "(id: %(id)s, added: %(add)s, removed: %(remove)s).",
)

SUCCESS_DELETE_GROUP = LogMessage(
    "I230",
    "Successfully deleted Group resource (id: %(id)s) in Repository (id: %(rid)s).",
)

SUCCESS_DELETE_GROUPS = LogMessage(
    "I231",
    "Successfully deleted Group resources (ids: %(ids)s) in Repository (id: %(rid)s).",
)


SEARCHED_SYSTEM_ADMINS = LogMessage(
    "I301",
    "Search performed on System Administrator.",
)

SUCCESS_GET_USER = LogMessage(
    "I305",
    "Successfully get User resource. \n%(json)s",
)

SUCCESS_CREATE_USER = LogMessage(
    "I310",
    "Successfully created User resource (id: %(id)s, ePPN: %(eppn)s).",
)

SUCCESS_UPDATE_USER = LogMessage(
    "I320",
    "Successfully updated User resource (id: %(id)s, ePPN: %(eppn)s).",
)

SUCCESS_UPDATE_USER_AFFILIATIONS = LogMessage(
    "I321",
    "Successfully updated affiliations of User resource (id: %(id)s, ePPN: %(eppn)s).",
)


SUCCESS_UPLOAD_FILES = LogMessage(
    "I601",
    "successfully uploaded file and create Files record: %(file_path)s",
)

SUCCESS_VALIDATE = LogMessage(
    "I602",
    "successfully validated the uploaded file: %(file_id)s",
)

SUCCESS_GET_VALIDATE_RESULT = LogMessage(
    "I603",
    "successfully retrieved validation result for history record: %(history_id)s",
)

SUCCESS_BULK_OPERATION = LogMessage(
    "I604",
    "successfully completed bulk operation for history record: %(history_id)s",
)

SUCCESS_GET_BULK_OPERATION_RESULT = LogMessage(
    "I605",
    "successfully retrieved bulk operation result for history record: %(history_id)s",
)


SUCCESS_UPDATE_PUBLIC_STATUS = LogMessage(
    "I700",
    "successfully update public status of history record (id: %(history_id)s)  in"
    " database.",
)


GROUP_CACHE_UPDATE_STARTED = LogMessage(
    "I800",
    "Group cache update task started (operation: %(op)s, task: %(task_id)s).",
)
