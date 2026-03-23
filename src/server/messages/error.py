#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides error log messages used in the server application."""

from .base import LogMessage


UNINIT_SERVER_CONFIG = LogMessage(
    "E000",
    "Server configuration has not been initialized.",
)

INVALID_SERVER_CONFIG = LogMessage(
    "E001",
    "Server configuration is invalid or incomplete.",
)

UNSUPPORTED_EXPRESSION = LogMessage(
    "E002",
    "Unsupported expression in server configuration; "
    "supported: 1. int / float literal, 2. literal str for len, "
    "3. +, -, *, / operators, 4. len, max, min functions.",
)

INVALID_EXPRESSION = LogMessage(
    "E003",
    "Invalid syntax in expression in server configuration.",
)


DATABASE_NOT_EXIST = LogMessage(
    "E010",
    "Database does not exist.",
)


INVALID_REDIS_CONFIG = LogMessage(
    "E020",
    "Failed to connect to Redis due to invalid configuration.",
)

FAILED_CONNECT_REDIS = LogMessage(
    "E021",
    "Failed to connect to Redis: %(error)s",
)


FAILED_ISSUE_CREDENTIALS = LogMessage(
    "E030",
    "Failed to issue client credentials.",
)

FAILED_ISSUE_TOKEN = LogMessage(
    "E031",
    "Failed to issue access token.",
)

FAILED_CHECK_TOKEN = LogMessage(
    "E032",
    "Failed to check the validity of the access token.",
)

FAILED_REFRESH_TOKEN = LogMessage(
    "E033",
    "Failed to refresh access token.",
)

CREDENTIALS_NOT_STORED = LogMessage(
    "E034",
    "Client credentials are not stored on the server.",
)

ACCESS_TOKEN_NOT_STORED = LogMessage(
    "E035",
    "Access token is not stored on the server.",
)

REFRESH_TOKEN_NOT_STORED = LogMessage(
    "E036",
    "Refresh token is not stored on the server.",
)

ACCESS_TOKEN_NOT_AVAILABLE = LogMessage(
    "E037",
    "Access token is invalid or expired.",
)

FAILED_GET_TOKEN_OWNER = LogMessage(
    "E038",
    "Failed to get token owner's User resource from mAP Core API.",
)

FAILED_GET_CLIENT_CREDENTIALS = LogMessage(
    "E040",
    "Failed to get client credentials from database.",
)

FAILED_PARSE_CLIENT_CREDENTIALS = LogMessage(
    "E041",
    "Failed to parse client credentials from database.",
)

FAILED_SAVE_CLIENT_CREDENTIALS = LogMessage(
    "E042",
    "Failed to save client credentials to database.",
)

FAILED_DUMP_CLIENT_CREDENTIALS = LogMessage(
    "E043",
    "Failed to dump client credentials for saving to database.",
)

FAILED_GET_OAUTH_TOKEN = LogMessage(
    "E044",
    "Failed to get OAuth token from database.",
)

FAILED_PARSE_OAUTH_TOKEN = LogMessage(
    "E045",
    "Failed to parse OAuth token from database.",
)

FAILED_SAVE_OAUTH_TOKEN = LogMessage(
    "E046",
    "Failed to save OAuth token to database.",
)

FAILED_DUMP_OAUTH_TOKEN = LogMessage(
    "E047",
    "Failed to dump OAuth token for saving to database.",
)


RECEIVE_RESPONSE_MESSAGE = LogMessage(
    "E050",
    "Received error from mAP Core API: %(message)s",
)

RECEIVE_UNEXPECTED_RESPONSE = LogMessage(
    "E051",
    "Received unexpected response from mAP Core API.",
)

FAILED_DECODE_RESPONSE = LogMessage(
    "E052",
    "Failed to decode response from mAP Core API.",
)

FAILED_COMMUNICATE_API = LogMessage(
    "E053",
    "Failed to communicate with mAP Core API.",
)

FAILED_PARSE_RESPONSE = LogMessage(
    "E054",
    "Failed to parse response from mAP Core API.",
)


FAILED_SET_LOGIN_SESSION = LogMessage(
    "E060",
    "Failed to set login session for user (ePPN: %(eppn)s).",
)


UNINIT_RESOURCE_CACHE = LogMessage(
    "E080",
    "Function (name: %(name)s) is not initialized for resource caching.",
)

UNSUPPORTED_SEARCH_FILTER = LogMessage(
    "E090",
    "Unsupported search filter or combination of filters.",
)

UNRECOGNIZED_SEARCH_CRITERIA = LogMessage(
    "E091",
    "Unrecognized search criteria.",
)

CANNOT_RESOLVE_DIFFERENCE = LogMessage(
    "E092",
    "Cannot resolve differences between different types "
    "(original: %(original)s, updated: %(updated)s).",
)


FAILED_SEARCH_REPOSITORIES = LogMessage(
    "E100",
    "Failed to search Service resources for Repositories (filter: %(filter)s).",
)

REPOSITORY_FORBIDDEN = LogMessage(
    "E103",
    "Logged-in user does not have permission to access this Repository (id: %(id)s).",
)

REPOSITORY_NOT_FOUND = LogMessage(
    "E104",
    "Service resource for Repository (id: %(id)s) not found.",
)

FAILED_GET_REPOSITORY = LogMessage(
    "E105",
    "Failed to get Service resource for Repository (id: %(id)s).",
)

FAILED_CREATE_REPOSITORY = LogMessage(
    "E110",
    "Failed to create Service for Repository (id: %(id)s).",
)

REPOSITORY_DUPLICATE_ID = LogMessage(
    "E111",
    "A Service resource for Repository (id: %(id)s) already exists.",
)

NO_RIGHTS_CREATE_REPOSITORY = LogMessage(
    "E113",
    "No creation rights for Repository with current access token.",
)

FAILED_UPDATE_REPOSITORY = LogMessage(
    "E120",
    "Failed to update Service resource for Repository (id: %(id)s).",
)

NO_RIGHTS_UPDATE_REPOSITORY = LogMessage(
    "E123",
    "No update rights for Repository (id: %(id)s) with current access token.",
)

FAILED_DELETE_REPOSITORY = LogMessage(
    "E130",
    "Failed to delete Service resource for Repository (id: %(id)s).",
)

REPOSITORY_NAME_NOT_MATCH = LogMessage(
    "E131",
    "Confirmed Service name does not match to delete Repository (id: %(id)s).",
)

REPOSITORY_REQUIRES_SYSTEM_ADMIN = LogMessage(
    "E140",
    "At least one System Administrator is required for a Repository.",
)

REPOSITORY_REQUIRES_SERVICE_NAME = LogMessage(
    "E141",
    "Service name is required for a Repository.",
)

REPOSITORY_REQUIRES_SERVICE_URL = LogMessage(
    "E142",
    "Service URL is required for a Repository.",
)

REPOSITORY_INVALID_SERVICE_URL = LogMessage(
    "E143",
    "Service URL must contain a valid hostname",
)

REPOSITORY_TOO_LONG_URL = LogMessage(
    "E144",
    "Service URL is too long; maximum length is %(max)s characters.",
)

REPOSITORY_REQUIRES_ENTITY_ID = LogMessage(
    "E145",
    "At least one entity ID is required for a Repository.",
)


UNCHANGEABLE_REPOSITORY_URL = LogMessage(
    "E150",
    "Service URL of Repository cannot be updated.",
)

REPOSITORY_REQUIRES_FQDN_OR_SERVICE_ID = LogMessage(
    "E151",
    "Either 'fqdn' or 'service_id' must be provided.",
)

RESOURCE_REQUIRES_FQDN_OR_REPOSITORY_ID = LogMessage(
    "E152",
    "Either 'fqdn' or 'repository_id' must be provided.",
)


FAILED_SEARCH_GROUPS = LogMessage(
    "E200",
    "Failed to search Group resources (filter: %(filter)s).",
)

GROUP_UNRECOGNIZED_ID = LogMessage(
    "E201",
    "Group ID (id: %(id)s) is unrecognized; it may be out of this service's scope.",
)

GROUP_FORBIDDEN = LogMessage(
    "E203",
    "Logged-in user does not have permission to access Group (id: %(id)s).",
)

GROUP_NOT_FOUND = LogMessage(
    "E204",
    "Group resource (id: %(id)s) not found.",
)

FAILED_GET_GROUP = LogMessage(
    "E205",
    "Failed to get Group resource (id: %(id)s).",
)

GROUP_UNSUPPORTED_PATCH_PATH = LogMessage(
    "E207",
    "Unsupported patch path for Group resource: %(path)s.",
)

FAILED_CREATE_GROUP = LogMessage(
    "E210",
    "Failed to create Group resource (id: %(id)s).",
)

GROUP_DUPLICATE_ID = LogMessage(
    "E211",
    "A Group resource (id: %(id)s) already exists.",
)

FAILED_UPDATE_GROUP = LogMessage(
    "E220",
    "Failed to update Group resource (id: %(id)s).",
)

FAILED_UPDATE_GROUP_MEMBERS = LogMessage(
    "E221",
    "Failed to update members of Group resource "
    "(id: %(id)s, add: %(add)s, remove: %(remove)s).",
)

NO_RIGHTS_UPDATE_GROUP = LogMessage(
    "E223",
    "No update rights for Group (id: %(id)s) with current access token.",
)

FAILED_DELETE_GROUP = LogMessage(
    "E230",
    "Failed to delete Group resource (id: %(id)s).",
)

FAILED_DELETE_GROUPS = LogMessage(
    "E231",
    "Failed to delete Group resources (ids: %(ids)s).",
)

SOME_GROUP_UNRECOGNIZED = LogMessage(
    "E232",
    "Some Group IDs are unrecognized (ids: %(ids)s), "
    "so any of the specified groups has not been deleted.",
)

ROLEGROUP_CANNOT_DELETE = LogMessage(
    "E233",
    "Role-type Group resource cannot be deleted.",
)

GROUP_REQUIRES_SYSTEM_ADMIN = LogMessage(
    "E240",
    "At least one System Administrator is required for a Group.",
)

GROUP_REQUIRES_DISPLAY_NAME = LogMessage(
    "E241",
    "Display name is required for a Group.",
)

GROUP_REQUIRES_REPOSITORY = LogMessage(
    "E242",
    "Group must be affiliated with a Repository.",
)

GROUP_REQUIRES_EXISTING_REPOSITORY = LogMessage(
    "E243",
    "The specified Repository (id: %(rid)s) does not exist.",
)

GROUP_FORBIDDEN_REPOSITORY = LogMessage(
    "E244",
    "Logged-in user does not have permission to create Group "
    "in the Repository (id: %(rid)s).",
)

GROUP_REQUIRES_USER_DEFINED_ID = LogMessage(
    "E245",
    "Group ID is required to create a group.",
)

GROUP_TOO_LONG_ID = LogMessage(
    "E246",
    "Group ID is too long for the Repository (id: %(rid)s); "
    "maximum length is %(max)s characters.",
)

GROUP_REQUIRES_ID = LogMessage(
    "E250",
    "Group ID is required to update a Group.",
)

GROUP_INVALID_ID_PATTERN = LogMessage(
    "E251",
    "Group ID does not follow the expected pattern.",
)


CONFLICT_MEMBER_OPERATION = LogMessage(
    "E260",
    "Conflict in updating Group members (id: %(id)s, users: %(uids)s).",
)


FAILED_SEARCH_USERS = LogMessage(
    "E300",
    "Failed to search User resources (filter: %(filter)s).",
)

FAILED_COUNT_USERS = LogMessage(
    "E301",
    "Failed to count User resources (filter: %(filter)s).",
)

USER_FORBIDDEN = LogMessage(
    "E303",
    "Logged-in user does not have permission to access User (id: %(id)s).",
)

USER_NOT_FOUND = LogMessage(
    "E304",
    "User resource (id: %(id)s) not found.",
)

FAILED_GET_USER = LogMessage(
    "E305",
    "Failed to get User resource (id: %(id)s).",
)

FAILED_GET_USER_BY_EPPN = LogMessage(
    "E306",
    "Failed to get User resource (ePPN: %(eppn)s).",
)

FAILED_CREATE_USER = LogMessage(
    "E310",
    "Failed to create User resource (ePPN: %(eppn)s).",
)

USER_DUPLICATE_ID = LogMessage(
    "E311",
    "A User resource (id: %(id)s) already exists.",
)

USER_ALREADY_TIED_EPPN = LogMessage(
    "E312",
    "The ePPN '%(eppn)s' is already tied to another account.",
)

USER_EPPN_ILLEGAL = LogMessage(
    "E313",
    "The ePPN '%(eppn)s' is illegal.",
)

FAILED_UPDATE_USER = LogMessage(
    "E320",
    "Failed to update User resource (id: %(id)s, ePPN: %(eppn)s).",
)

FAILED_UPDATE_USER_AFFILIATIONS = LogMessage(
    "E321",
    "Failed to update some affiliations for User resource "
    "(id: %(id)s, ePPN: %(eppn)s).",
)

NO_RIGHTS_UPDATE_USER = LogMessage(
    "E323",
    "No update rights for User (id: %(id)s) with current access token.",
)

USER_REQUIRES_USERNAME = LogMessage(
    "E340",
    "Username is required for a User.",
)

USER_REQUIRES_EPPN = LogMessage(
    "E341",
    "At least one ePPN is required for a User.",
)

USER_REQUIRES_EMAIL = LogMessage(
    "E342",
    "At least one email is required for a User.",
)

USER_REQUIRES_REPOSITORY = LogMessage(
    "E343",
    "At least one Repository affiliation is required for a User.",
)

USER_FORBIDDEN_REPOSITORY = LogMessage(
    "E344",
    "Logged-in user does not have permission to add or remove User"
    "to the Repository (id: %(id)s).",
)

USER_REQUIRES_EXISTING_REPOSITORY = LogMessage(
    "E345",
    "The specified Repository (id: %(id)s) does not exist.",
)

USER_REQUIRES_EXISTING_GROUP = LogMessage(
    "E346",
    "The specified Group (id: %(id)s) does not exist.",
)

USER_FORBIDDEN_GROUP = LogMessage(
    "E347",
    "Logged-in user does not have permission to add or remove User"
    "to the Group (id: %(id)s).",
)

USER_REQUIRES_NO_REPOSITORY = LogMessage(
    "E348",
    "System Administrator cannot be affiliated with any repository.",
)

USER_REQUIRES_NO_GROUP = LogMessage(
    "E349",
    "System Administrator cannot be affiliated with any group.",
)

USER_NO_CREATE_SYSTEM_ADMIN = LogMessage(
    "E350",
    "Logged-in user does not have permission to create a System Administrator user.",
)

USER_NO_UPDATE_SYSTEM_ADMIN = LogMessage(
    "E351",
    "Logged-in user does not have permission to update a System Administrator user.",
)

USER_NO_PROMOTE_SYSTEM_ADMIN = LogMessage(
    "E352",
    "Logged-in user does not have permission to promote a user to "
    "System Administrator.",
)

USER_CANNOT_EXPORT_SYSTEM_ADMIN = LogMessage(
    "E361",
    "System Administrator user is not allowed to be exported.",
)

USER_FORBIDDEN_EXPORT = LogMessage(
    "E362",
    "Logged-in user does not have permission to export a User.",
)

FAILED_CREATE_DOWNLOAD_HISTORY_RECORD = LogMessage(
    "E363",
    "Failed to create download history for file (id: %(file_id)s) in database.",
)

UNAUTHORIZED = LogMessage(
    "E401",
    "Login required to access this resource.",
)

FILE_TOO_LARGE = LogMessage(
    "E440",
    "Uploaded file is too large; maximum allowed size is %(max)s bytes.",
)


UNEXPECTED_SERVER_ERROR = LogMessage(
    "E500",
    "An unexpected error occurred in the server application.",
)

SERVER_UNAVAILABLE = LogMessage(
    "E503",
    "The server application is currently unavailable.",
)

FAILED_BULK_OPERATION = LogMessage(
    "E600",
    "Failed to perform bulk operation.",
)

FAILED_SAVE_UPLOADED_FILE = LogMessage(
    "E601",
    "Failed to save uploaded file (path: %(file_path)s).",
)

OPERATION_FORBIDDEN = LogMessage(
    "E602",
    "Logged-in user does not have permission to perform this operation.",
)

VALIDATION_ERROR_BLOCK = LogMessage(
    "E603",
    "Execution is not allowed because there is one or more validation errors.",
)

FAILED_GET_UPLOAD_HISTORY_RECORD = LogMessage(
    "E610",
    "Failed to get upload history (id: %(history_id)s) from database.",
)

FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID = LogMessage(
    "E611",
    "Failed to get upload history by file ID (file_id: %(file_id)s) from database.",
)

FAILED_CREATE_UPLOAD_HISTORY_RECORD = LogMessage(
    "E612",
    "Failed to create upload history for file (id: %(file_id)s) in database.",
)

FAILED_UPDATE_HISTORY_RECORD_STATUS = LogMessage(
    "E613",
    "Failed to update upload history status (id: %(history_id)s) in database.",
)

INVALID_UPLOAD_HISTORY_RECORD_ATTRIBUTES = LogMessage(
    "E614",
    "Results must include 'summary' and 'results' keys",
)

UPDATE_HISTORY_RECORD_NOT_FOUND = LogMessage(
    "E615",
    "Record (id: %(id)s) not found in database.",
)

FAILED_GET_FILE_RECORD = LogMessage(
    "E616",
    "Failed to get file record(file_id: %(file_id)s) from database.",
)

FAILED_DELETE_FILE_RECORD = LogMessage(
    "E617",
    "Failed to delete file record(file_id: %(file_id)s) from database.",
)

INVALID_QUERY = LogMessage(
    "E618",
    "offset: %(offset)s and size: %(size)s must be non-negative integers.",
)

FAILED_CREATE_FILE_RECORD = LogMessage(
    "E620",
    "Failed to create file record for file (path: %(file_path)s) in database.",
)

INVALID_FILE_STRUCTURE = LogMessage(
    "E621",
    "Invalid file structure. Please check the file and try again.",
)

FILE_EXPIRED = LogMessage(
    "E622", " File not found (path: %(path)s). It may have been expired."
)

FILE_FORMAT_UNSUPPORTED = LogMessage(
    "E623",
    "Unsupported file format (extension: %(suffix)s). "
    "only tsv/csv and xlsx formats are supported.",
)

FILE_VERSION_UNSUPPORTED = LogMessage(
    "E624",
    "Unsupported file version (version: %(version)s). only version 1.0 is supported.",
)

FILE_VALIDATION_ERROR = LogMessage(
    "E625",
    "File validation failed for task: %(task_id)s. Please check the file.",
)

FILE_NOT_ACTIVE_SHEET = LogMessage(
    "E626",
    "No active sheet found in the Excel file (path: %(path)s).",
)

TASK_NOT_FOUND = LogMessage(
    "E634",
    "Task (id: %(task_id)s) not found. It may have been expired.",
)

FAILED_GET_HISTORY_RECORDS = LogMessage(
    "E700",
    "Failed to get history records from table: %(table)s.",
)

FAILED_GET_HISTORY_RECORD = LogMessage(
    "E701",
    "Failed to get history record (id: %(history_id)s) from table: %(table)s.",
)

FAILED_UPDATE_PUBLIC = LogMessage(
    "E702",
    "Failed to update public status of history record (id: %(history_id)s)  in"
    " database.",
)

FILE_NOT_FOUND = LogMessage(
    "E704",
    "File not found (path: %(path)s).",
)

FAILED_GET_FILTER_ITEMS = LogMessage(
    "E705",
    "Failed to get filter items for history search (key: %(key)s).",
)

FAILED_GET_FILE_PATH = LogMessage(
    "E706",
    "Failed to get file path for file (id: %(file_id)s) from database.",
)

GROUP_CACHE_UPDATE_CONFLICT = LogMessage(
    "E800",
    "The cache update operation is already in progress.",
)

FAILED_ENQUEUE_CACHE_UPDATE_TASK = LogMessage(
    "E801",
    "Failed to enqueue cache update task.",
)

FAILED_FETCH_UPDATE_TASK_STATUS = LogMessage(
    "E802",
    "Failed to fetch cache update task status.",
)

FAILED_PARSE_UPDATE_TASK_STATUS = LogMessage(
    "E803",
    "Failed to parse cache update task status.",
)

UPDATE_TASK_NOT_RUNNING = LogMessage(
    "E804",
    "No cache update task is currently running.",
)


UNNECESSARY_CONTRIB = LogMessage(
    "E999", "Contrib utilities can only be used in development mode."
)
