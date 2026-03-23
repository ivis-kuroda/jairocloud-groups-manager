#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing bulk."""

import csv
import re
import typing as t

from collections import defaultdict
from datetime import UTC, datetime
from http import HTTPStatus
from itertools import zip_longest
from pathlib import Path
from uuid import UUID, uuid7

import openpyxl
import requests

from celery import shared_task
from flask import current_app
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError

from server.clients import bulks
from server.config import config
from server.const import USER_NAME_MAX_LENGTH, USER_ROLES
from server.db import db
from server.entities.bulk import (
    EachResult,
    ExecuteResults,
    RepositoryMember,
    ResultSummary,
    UserAggregated,
    ValidateResults,
)
from server.entities.bulk_request import BulkOperation
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup
from server.entities.map_user import EPPN, Email, Group, MapUser
from server.entities.patch_request import RemoveOperation
from server.entities.summaries import GroupSummary
from server.entities.user_detail import RepositoryRole, UserDetail
from server.exc import (
    DatastoreError,
    FileFormatError,
    FileNotFound,
    FileUploadError,
    FileValidationError,
    InvalidFormError,
    OAuthTokenError,
    RecordNotFound,
    TaskExecutionError,
    UnexpectedResponseError,
)
from server.messages import E, I
from server.services.utils.permissions import (
    get_permitted_repository_ids,
    is_current_user_system_admin,
)
from server.services.utils.transformers import validate_user_to_map_user

from . import groups, history_table, users, utils
from .token import get_access_token, get_client_secret
from .utils import session_required


if t.TYPE_CHECKING:
    from celery.result import AsyncResult
    from werkzeug.datastructures import FileStorage


def upload_file(repository_id: str, bulk_file: FileStorage) -> UUID:
    """Upload a file for bulk processing.

    Args:
        repository_id (str): Target repository ID for upload.
        bulk_file (FileStorage): File to upload.

    Returns:
        UUID: The ID of the temporary file.

    Raises:
        FileUploadError: If there is an error saving the uploaded file.
    """
    temp_id = uuid7()
    temp_dir = Path(config.STORAGE.local.temporary)
    original_filename = bulk_file.filename or "upload_file"
    new_filename = f"{temp_id}_{Path(original_filename).name}"
    file_path = temp_dir / new_filename
    file_content = {"repositories": [{"id": repository_id}]}
    history_table.create_file(
        file_id=temp_id, file_path=str(file_path), file_content=file_content
    )
    try:
        bulk_file.save(str(file_path))
    except (PermissionError, FileNotFoundError) as exc:
        db.session.rollback()
        raise FileUploadError(
            E.FAILED_SAVE_UPLOADED_FILE % {"file_path": file_path}
        ) from exc
    db.session.commit()
    current_app.logger.info(I.SUCCESS_UPLOAD_FILES, {"file_path": file_path})
    delete_temporary_file.apply_async((str(temp_id),), countdown=3600)
    return temp_id


@shared_task()
@session_required
def validate_upload_data(
    operator_id: str, operator_name: str, temp_file_id: UUID
) -> UUID:
    """Validate the uploaded file data for bulk operation.

    Args:
        operator_id (str): The ID of the operator performing the upload.
        operator_name (str): The name of the operator performing the upload.
        temp_file_id (UUID): The ID of the temporary file.

    Returns:
        UUID: The ID of the upload history record.
    """
    record = history_table.get_file_by_id(temp_file_id)
    file_path = record.file_path
    repository_id = record.file_content["repositories"][0]["id"]
    repository_member = get_repository_member(repository_id)

    data, new_data = build_user_from_file(file_path)

    updata_users: list[UserDetail] = build_user_detail_from_dict(
        data, repository_id
    ).root
    create_users: list[UserDetail] = build_user_detail_from_dict_by_name(
        new_data, repository_id
    ).root
    updata_users_id = {u.id for u in updata_users if u.id is not None}
    missing_users = _get_missing_users(repository_member, updata_users_id)
    repo_user_by_id = _get_repo_user_by_id(repository_member, updata_users_id)

    check_results, summary = _build_check_results(
        updata_users, create_users, repository_member, repo_user_by_id
    )

    results = ValidateResults(
        results=check_results,
        summary=summary,
        missing_user=missing_users,
        offset=0,
        page_size=len(check_results),
    )
    result = history_table.create_upload(
        operator_id=operator_id,
        operator_name=operator_name,
        file_id=temp_file_id,
        results=results.model_dump(mode="json"),
    )
    current_app.logger.info(I.SUCCESS_VALIDATE, {"file_id": temp_file_id})
    return result.id


def get_repository_member(repository_id: str) -> RepositoryMember:
    """Get the members of the specified repository from mAP Core API.

    Args:
        repository_id (str): The ID of the repository.

    Returns:
        RepositoryMember: The members of the repository.
    """
    result = groups.search(
        utils.make_criteria_object("groups", r=[repository_id]), raw=True
    ).resources
    group_ids = {g.id for g in result if g.id}
    user_ids = {
        m.value for g in result if g.members for m in g.members if m.type == "User"
    }

    return RepositoryMember(groups=group_ids, users=user_ids)


def build_user_from_file(
    file_path: str,
) -> tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, list[str]]]]:
    """Build UserAggregated from a user data file.

    Args:
        file_path (str): Path to the input file containing user data.

    Returns:
        tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, list[str]]]]:
            A tuple containing two dictionaries:
            - The first dictionary contains user data keyed by user ID.
            - The second dictionary contains new user data keyed by user name.

    Raises:
        FileFormatError : If the format is unsupported or parsing fails.
    """
    rows = _read_file(file_path)
    metadata = next(rows)
    version = (
        metadata[metadata.index("version:") + 1] if "version:" in metadata else None
    )
    if version != "1.0":
        current_app.logger.error(E.FILE_VERSION_UNSUPPORTED, {"version": version})
        raise FileFormatError(E.FILE_VERSION_UNSUPPORTED % {"version": version})

    data = defaultdict(lambda: defaultdict(list))
    new_data = defaultdict(lambda: defaultdict(list))

    idx_of = {}
    id_idx = None
    user_name_idx = None
    header_row_index = 1 - 1

    for i, row in enumerate(rows):
        if i == header_row_index + 1 or not row:
            continue

        if i == header_row_index:
            header = [str(h).strip() if h is not None else "" for h in row]
            idx_of = {name: idx for idx, name in enumerate(header)}
            id_idx = idx_of.get("id")
            user_name_idx = idx_of.get("user_name")
            continue

        columns = list(row)
        rid = columns[id_idx] if id_idx is not None else None

        if rid:
            bucket = data[rid]
            exclude = {"id"}
        else:
            user_name_value = columns[user_name_idx] if user_name_idx else None
            if not user_name_value:
                continue
            bucket = new_data[user_name_value]
            exclude = {"user_name"}
        for col, j in idx_of.items():
            if col not in exclude:
                bucket[col].append(columns[j])

    return dict(data), dict(new_data)


def _read_file(file_path: str):  # noqa: ANN202
    """Read a user data file and return a list of `UserDetail` instances.

    Args:
        file_path (str): Path to the input file containing user data.

    Returns:
        Generator yielding rows of user data from the file.

    Raises:
        FileNotFound: If the file does not exist.
        FileFormatError : If the format is unsupported or parsing fails.
        FileValidationError: If the file content is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFound(E.FILE_EXPIRED % {"path": path})

    iterator = None
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        delimiter = "," if suffix == ".csv" else "\t"
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            iterator = csv.reader(f, delimiter=delimiter)
    elif suffix == ".xlsx":
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        if not ws:
            current_app.logger.error(E.FILE_NOT_ACTIVE_SHEET, {"path": path})
            raise FileValidationError(E.INVALID_FILE_STRUCTURE)

        iterator = ws.iter_rows(values_only=True)

    else:
        raise FileFormatError(E.FILE_FORMAT_UNSUPPORTED % {"suffix": path.suffix})

    return iterator


def build_user_detail_from_dict(
    data: dict[str, dict[str, list[str]]], repository_id: str
) -> UserAggregated:
    """Build UserAggregated from a dictionary of user data.

    Args:
        data (dict[str, dict[str, list[str]]]):
            A dictionary where the key is the user ID and the value is another
            dictionary containing user attributes.
        repository_id (str): The ID of the repository to which the users belong.

    Returns:
        UserAggregated:
            The aggregated user details built from the input dictionary.

    Raises:
        FileValidationError: If there is an error validating the user data.
    """
    users: list[UserDetail] = []

    for raw_uid, columns in data.items():
        uid = str(raw_uid).strip() if raw_uid else ""
        if not uid:
            continue

        user_name_list = columns.get("user_name")
        user_name: str = (
            user_name_list[0] if user_name_list and len(user_name_list) > 0 else ""
        )
        preferred_language_list = columns.get("preferred_language")
        preferred_language: str = (
            preferred_language_list[0]
            if preferred_language_list is not None and len(preferred_language_list) > 0
            else ""
        )
        str_role = columns.get("role")
        role = str_role[0] if str_role and len(str_role) > 0 else None
        repository_roles: list[RepositoryRole] = [
            RepositoryRole(id=repository_id, user_role=_resolve_non_sysadmin_role(role))
        ]

        eppns: list[str] = list(set(columns.get("edu_person_principal_names[]") or []))
        emails: list[str] = list(set(columns.get("emails[]") or []))

        gid_list: list[str] = list(columns.get("groups[].id") or [])
        gname_list: list[str] = list(columns.get("groups[].name") or [])
        groups: list[GroupSummary] = []
        seen = set()
        for gid, gname in zip_longest(gid_list, gname_list, fillvalue=None):
            if not gid or gid in seen:
                continue
            seen.add(gid)
            groups.append(
                GroupSummary.model_construct(
                    id=gid,
                    display_name=gname,
                )
            )

        users.append(
            UserDetail.model_construct(
                id=uid,
                eppns=eppns,
                user_name=user_name,
                emails=emails,
                preferred_language=preferred_language,
                repository_roles=repository_roles,
                groups=groups,
            )
        )
    try:
        return UserAggregated(root=users)
    except ValidationError as exc:
        current_app.logger.error(exc)
        raise FileValidationError(E.INVALID_FILE_STRUCTURE) from exc


def build_user_detail_from_dict_by_name(
    data: dict[str, dict[str, list[str]]], repository_id: str
) -> UserAggregated:
    """Build UserAggregated from a dictionary of user data.

    Args:
        data (dict[str, dict[str, list[str]]]):
            A dictionary where the key is the user name and the value is another
            dictionary containing user attributes.
        repository_id (str): The ID of the repository to which the users belong.

    Returns:
        UserAggregated:
            The aggregated user details built from the input dictionary.

    Raises:
        FileValidationError: If there is an error validating the user data.
    """
    users: list[UserDetail] = []

    for raw_user_name, columns in data.items():
        user_name = str(raw_user_name).strip() if raw_user_name else ""
        if not user_name:
            continue

        preferred_language_list = columns.get("preferred_language")
        preferred_language: str = (
            preferred_language_list[0]
            if preferred_language_list is not None and len(preferred_language_list) > 0
            else ""
        )

        eppns: list[str] = list(set(columns.get("edu_person_principal_names[]") or []))
        emails: list[str] = list(set(columns.get("emails[]") or []))

        gid_list: list[str] = list(columns.get("groups[].id") or [])
        gname_list: list[str] = list(columns.get("groups[].name") or [])
        str_role = columns.get("role")
        role = str_role[0] if str_role and len(str_role) > 0 else None
        repository_roles: list[RepositoryRole] = [
            RepositoryRole(id=repository_id, user_role=_resolve_non_sysadmin_role(role))
        ]
        groups: list[GroupSummary] = []
        seen = set()
        for gid, gname in zip_longest(gid_list, gname_list, fillvalue=None):
            if not gid or gid in seen:
                continue
            seen.add(gid)
            groups.append(
                GroupSummary.model_construct(
                    id=gid,
                    display_name=gname,
                )
            )

        users.append(
            UserDetail.model_construct(
                id=None,
                eppns=eppns,
                user_name=user_name,
                emails=emails,
                preferred_language=preferred_language,
                repository_roles=repository_roles,
                groups=groups,
            )
        )
    try:
        return UserAggregated(root=users)
    except ValidationError as exc:
        current_app.logger.error(exc)
        raise FileValidationError(E.INVALID_FILE_STRUCTURE) from exc


_ROLE_MAP = {m.value: m for m in USER_ROLES if m is not USER_ROLES.SYSTEM_ADMIN}


def _resolve_non_sysadmin_role(role: str | None) -> USER_ROLES | None:
    return _ROLE_MAP.get(role) if role else None


def _get_missing_users(
    repository_member: RepositoryMember, file_users_id: set[str]
) -> list[UserDetail]:
    missing_user_ids = list(repository_member.users - file_users_id)
    if not missing_user_ids:
        return []
    user_list = users.search(
        utils.make_criteria_object("users", i=missing_user_ids), raw=True
    ).resources
    return [UserDetail.from_map_user(u) for u in user_list]


def _get_repo_user_by_id(
    repository_member: RepositoryMember, file_users_id: set[str]
) -> dict[str, UserDetail]:
    update_users_ids = list(repository_member.users & file_users_id)
    if not update_users_ids:
        return {}
    user_list = users.search(
        utils.make_criteria_object("users", i=update_users_ids), raw=True
    ).resources
    return {
        user.id: user
        for user in (UserDetail.from_map_user(u) for u in user_list)
        if user.id
    }


def _build_check_results(
    update_users: list[UserDetail],
    create_users: list[UserDetail],
    repository_member: RepositoryMember,
    repo_user_by_id: dict[str, UserDetail],
) -> tuple[list[EachResult], ResultSummary]:
    count_create = 0
    count_update = 0
    count_delete = 0
    count_skip = 0
    count_error = 0
    check_results: list[EachResult] = []
    for u in create_users:
        code = None
        user_group_ids = {g.id for g in u.groups} if u.groups else set()

        if not user_group_ids.issubset(repository_member.groups):
            code = "Group ID does not exist"
            check_results.append(
                EachResult(
                    id=u.id,
                    eppn=u.eppns or [],
                    user_name=u.user_name,
                    email=u.emails or [],
                    groups=user_group_ids,
                    status="error",
                    code=code,
                )
            )
            count_error += 1
            continue
        try:
            validate_user_to_map_user(u, mode="create")
        except InvalidFormError as exc:
            check_results.append(
                EachResult(
                    id=u.id,
                    eppn=u.eppns or [],
                    user_name=u.user_name,
                    groups=user_group_ids,
                    email=u.emails or [],
                    status="error",
                    code=exc.code,
                    message=exc.string,
                )
            )
            count_error += 1
            continue

        check_results.append(
            EachResult(
                id=u.id,
                eppn=u.eppns or [],
                user_name=u.user_name,
                groups=user_group_ids,
                email=u.emails or [],
                status="create",
                code=code,
            )
        )
        count_create += 1

    for u in update_users:
        if u.id is None:
            continue
        repo_user = repo_user_by_id.get(u.id)
        if repo_user is None:
            continue
        repo_group_ids = {g.id for g in repo_user.groups} if repo_user.groups else set()
        user_group_ids = {g.id for g in u.groups} if u.groups else set()

        if repo_group_ids != user_group_ids:
            status = "update"
            count_update += 1
        else:
            status = "skip"
            count_skip += 1
        code = _check_immutable_attributes(repo_user, u)
        check_results.append(
            EachResult(
                id=u.id,
                eppn=repo_user.eppns or [],
                user_name=repo_user.user_name,
                email=u.emails or [],
                groups=user_group_ids,
                status=status,
                code=code,
            )
        )
    summary = ResultSummary(
        create=count_create,
        update=count_update,
        delete=count_delete,
        skip=count_skip,
        error=count_error,
    )
    return check_results, summary


def _check_value(user: UserDetail) -> bool:
    """Check if the user detail has valid values.

    Args:
        user (UserDetail): The user detail to be checked.

    Returns:
        bool: True if the user detail has valid values, False otherwise.
    """
    if not user.id:
        return False
    if not re.compile(r"^[A-Za-z0-9._-]{1,50}$").fullmatch(user.id):
        return False
    return len(user.user_name) <= USER_NAME_MAX_LENGTH


def _check_immutable_attributes(
    original: UserDetail, update_user: UserDetail
) -> str | None:
    """Verify whether the immutable attribute is indeed immutable.

    Args:
        original (UserDetail): The original user detail.
        update_user (UserDetail): The updated user detail.

    Returns:
        str | None: The name of the immutable attribute if found, None otherwise.
    """
    if original.user_name != update_user.user_name:
        return "user_name is immutable"
    if original.emails != update_user.emails:
        return "emails are immutable"
    if original.eppns != update_user.eppns:
        return "eppns are immutable"
    if original.preferred_language != update_user.preferred_language:
        return "preferred_language is immutable"
    return None


def get_validate_task_result(task_id: str) -> AsyncResult[UUID]:
    """Get the result of a validation task.

    Args:
        task_id (str): The ID of the validation task.

    Returns:
        AsyncResult[UUID]: The result of the validation task.

    Raises:
        DatastoreError: If there is an error connecting to the datastore.
        TaskExecutionError: If the task with the given ID does not exist.
    """
    try:
        res = validate_upload_data.AsyncResult(task_id)
    except RedisConnectionError as exc:
        current_app.logger.error(E.FAILED_CONNECT_REDIS, {"error": str(exc)})
        raise DatastoreError(E.FAILED_CONNECT_REDIS % {"error": str(exc)}) from exc
    if not res:
        current_app.logger.error(E.TASK_NOT_FOUND, {"task_id": task_id})
        raise TaskExecutionError(E.TASK_NOT_FOUND % {"task_id": task_id})
    return res


def get_validate_result(
    history_id: UUID, status_filter: list[str], offset: int, size: int
) -> ValidateResults:
    """Get the validation result summary for the specified upload history ID.

    Args:
        history_id (UUID): The ID of the upload history.
        status_filter (list[str]): Filter for Displayed Status
        offset (int): the offset for pagination
        size (int): page size

    Returns:
        ValidateSummary: The summary of the validation result.
    """
    results = history_table.get_paginated_upload_results(
        history_id, offset, size, status_filter
    )
    check_results = [EachResult.model_validate(it) for it in results]

    summary = history_table.get_upload_results(history_id, "summary")
    missing_user = history_table.get_upload_results(history_id, "missingUser")
    result = ValidateResults.model_validate({
        "results": check_results,
        "summary": summary,
        "missingUser": missing_user or [],
        "offset": offset,
        "pageSize": size,
    })
    current_app.logger.info(I.SUCCESS_GET_VALIDATE_RESULT, {"history_id": history_id})
    return result


@shared_task()
def update_users(
    history_id: UUID, temp_file_id: UUID, remove_users: list[str] | None
) -> UUID:
    """Perform bulk update of users based on the validation results.

    Args:
        history_id (UUID): The ID of the upload history.
        temp_file_id (UUID): The ID of the temporary file.
        remove_users (list[str] | None):
          The list of user IDs to be removed by repository.

    Returns:
        UUID: The ID of the upload history record.

    Raises:
        RecordNotFound: If the upload history does not exist.
        requests.RequestException: If there is an error communicating with mAP Core API.
        ValidationError: If there is an error parsing the response from mAP Core API.
        OAuthTokenError: If there is an issue with the access token.
        UnexpectedResponseError: If there is an unexpected response from mAP Core API.
        FileValidationError: If there are errors in the validation results.
    """
    upload_data = history_table.get_upload_by_id(history_id)
    if not upload_data:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id}
        )
        raise RecordNotFound(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        )

    # file content must contain at least one repository.
    repository_id = upload_data.file.file_content["repositories"][0]["id"]
    check_results: list[EachResult] = upload_data.results.get("results", [])

    summary = upload_data.results.get("summary", {})
    if summary.get("error", 1) > 0:
        current_app.logger.error(E.VALIDATION_ERROR_BLOCK)
        raise FileValidationError(E.VALIDATION_ERROR_BLOCK)

    bulk_ops, count_delete = _build_bulk_operations_from_check_results(
        repository_id, check_results, remove_users
    )
    summary.update({"delete": count_delete})

    file_id = save_file(temp_file_id)
    history_table.update_upload_status(
        history_id=history_id,
        status="P",
        file_id=file_id,
        new_results={"results": check_results, "summary": summary},
    )
    history_table.delete_file_by_id(temp_file_id)

    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result = bulks.post(
            bulk_ops, access_token=access_token, client_secret=client_secret
        )
    except (
        requests.RequestException,
        ValidationError,
        OAuthTokenError,
        UnexpectedResponseError,
    ) as exc:
        history_table.update_upload_status(history_id=history_id, status="F")
        db.session.commit()
        current_app.logger.error(exc)
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        raise UnexpectedResponseError(result.detail)

    count_error = 0
    for i, operation in enumerate(result.operations):
        if (
            operation.status
            and int(operation.status) >= HTTPStatus.BAD_REQUEST
            and i < len(check_results)
        ):
            check_results[i].status = "error"
            count_error += 1

    summary.update({"error": count_error})
    if count_error > 0:
        history_table.update_upload_status(
            history_id=history_id,
            status="F",
            new_results={"results": check_results, "summary": summary},
        )
        db.session.commit()
    else:
        history_table.update_upload_status(
            history_id=history_id,
            status="S",
        )
        db.session.commit()

    current_app.logger.info(I.SUCCESS_BULK_OPERATION, {"history_id": history_id})
    return history_id


def save_file(temp_file_id: UUID) -> UUID:
    """Save the temporary file as a permanent file for bulk operation.

    Args:
        temp_file_id (UUID): The ID of the temporary file.

    Returns:
        UUID: The ID of the saved permanent file.

    Raises:
        FileNotFound: If the temporary file does not exist.
        FileFormatError: If the file format is invalid.
    """
    try:
        files = history_table.get_file_by_id(temp_file_id)
        repository_id = files.file_content["repositories"][0]["id"]
    except (KeyError, AttributeError) as exc:
        current_app.logger.error(exc)
        raise FileNotFound(
            E.FAILED_GET_FILE_RECORD % {"file_id": temp_file_id}
        ) from exc

    file_path = Path(files.file_path)
    if not file_path.exists():
        raise FileNotFound(E.FILE_EXPIRED % {"path": file_path})
    if file_path.suffix not in {".csv", ".tsv", ".xlsx"}:
        raise FileFormatError(E.FILE_FORMAT_UNSUPPORTED % {"suffix": file_path.suffix})

    target_dir = Path(config.STORAGE.local.storage) / datetime.now(UTC).strftime(
        "%Y/%m"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file_path.name
    file_path.rename(target_path)
    return history_table.create_file(
        file_path=str(target_path),
        file_content={"repositories": [{"id": repository_id}]},
    ).id


def build_map_user_from_check_result(user: EachResult) -> MapUser:
    """Build MapUser from CheckResult.

    Args:
        user (CheckResult): The check result containing user information.

    Returns:
        MapUser: The map user built from the check result.
    """
    user_emails = [Email(value=email) for email in user.email]
    user_eppns = [EPPN(value=eppn) for eppn in user.eppn]
    user_groups = [Group(value=group_id) for group_id in user.groups]
    return MapUser(
        id=user.id,
        user_name=user.user_name,
        emails=user_emails,
        edu_person_principal_names=user_eppns,
        groups=user_groups,
    )


def build_remove_user_path(user: UserDetail, repository_id: str) -> BulkOperation:
    """Remove the user from the group belong to the repository.

    Args:
        user (UserDetail):
            The user to be removed from the repository.
        repository_id (str):
            The ID of the repository from which the user will be removed.

    Returns:
        BulkOperation:
            request body representing the bulk remove operation.
    """
    user_groups = [g.id for g in user.groups] if user.groups else []
    affiliations = utils.detect_affiliations(user_groups)
    group_list = affiliations.groups

    condition = " or ".join(
        f"(value eq '{g.group_id}')"
        for g in group_list
        if g.repository_id == repository_id
    )

    path = f"groups[{condition}]"
    remove_op = RemoveOperation(path=path)
    return BulkOperation(method="PATCH", path=f"Users/{user.id}", data=remove_op)


def _build_bulk_operations_from_check_results(
    repository_id: str, check_results: list[EachResult], remove_users: list[str] | None
) -> tuple[list[BulkOperation], int]:
    repository_member = get_repository_member(repository_id)

    update_users_ids = set(
        repository_member.users
        & {user.id for user in check_results if user.id is not None}
    )
    repo_user_by_id = _get_repo_user_by_id(repository_member, update_users_ids)
    count_delete = 0
    group_user_ops: dict[str, dict[str, set[str]]] = {}

    for user in check_results:
        if user.status != "update" or user.id is None:
            continue
        original = repo_user_by_id.get(user.id)
        if not original:
            continue
        original_group_ids = {g.id for g in original.groups or []}
        new_group_ids = set(user.groups)
        add_groups = new_group_ids - original_group_ids
        remove_groups = original_group_ids - new_group_ids
        for gid in add_groups:
            group_user_ops.setdefault(gid, {"add": set(), "remove": set()})["add"].add(
                user.id
            )
        for gid in remove_groups:
            group_user_ops.setdefault(gid, {"add": set(), "remove": set()})[
                "remove"
            ].add(user.id)

    bulk_ops: list[BulkOperation] = _build_groups_update_bulk_operations(group_user_ops)
    bulk_ops.extend([
        BulkOperation(
            method="POST",
            path="/Users",
            data=build_map_user_from_check_result(user),
        )
        for user in check_results
        if user.status == "create"
    ])

    delete_user_list = users.search(
        utils.make_criteria_object("users", i=remove_users), raw=True
    ).resources

    group_user_ops = {}
    for map_user in delete_user_list:
        user = UserDetail.from_map_user(map_user)
        if not user.id:
            continue
        user_groups = [g.id for g in user.groups] if user.groups else []
        group_list = utils.detect_affiliations(user_groups).groups
        for gid in group_list:
            group_user_ops.setdefault(gid.group_id, {"add": set(), "remove": set()})[
                "remove"
            ].add(user.id)
        check_results.append(
            EachResult(
                id=user.id,
                eppn=user.eppns or [],
                user_name=user.user_name,
                email=user.emails or [],
                groups={g.id for g in user.groups} if user.groups else set(),
                status="delete",
                code=None,
            )
        )
        count_delete += 1
    bulk_ops.extend(_build_groups_update_bulk_operations(group_user_ops))
    return bulk_ops, count_delete


def _build_groups_update_bulk_operations(
    group_user_ops: dict[str, dict[str, set[str]]],
) -> list[BulkOperation]:
    bulk_ops: list[BulkOperation] = []
    system_user_id = users.get_system_admins()
    for gid, ops in group_user_ops.items():
        target = groups.get_by_id(gid, raw=True)
        user_list = set()
        if isinstance(target, MapGroup) and target.members:
            user_list = {u.value for u in target.members if u.type == "User"}

        add_user = ops["add"]
        remove_user = ops["remove"]
        data_list = utils.build_update_member_operations(
            add=add_user,
            remove=remove_user,
            system_admins=system_user_id,
            user_list=user_list,
        )
        bulk_ops.extend([
            BulkOperation(
                method="PATCH",
                path=f"Groups/{gid}",
                data=data,
            )
            for data in data_list
        ])

    return bulk_ops


def get_execute_task_result(task_id: str) -> AsyncResult[UUID]:
    """Get the result of an execution task.

    Args:
        task_id (str): The ID of the execution task.

    Returns:
        AsyncResult[UUID]: The result of the execution task.

    Raises:
        DatastoreError: If there is an error connecting to the datastore.
        TaskExecutionError: If the task with the given ID does not exist.
    """
    try:
        res = update_users.AsyncResult(task_id)
    except RedisConnectionError as exc:
        current_app.logger.error(E.FAILED_CONNECT_REDIS, {"error": str(exc)})
        raise DatastoreError(E.FAILED_CONNECT_REDIS % {"error": str(exc)}) from exc
    if not res:
        current_app.logger.error(E.TASK_NOT_FOUND, {"task_id": task_id})
        raise TaskExecutionError(E.TASK_NOT_FOUND % {"task_id": task_id})
    return res


def get_upload_result(
    history_id: UUID, status_filter: list[str], offset: int, size: int
) -> ExecuteResults:
    """Get the bulk operation result summary with filtering and pagination.

    Args:
        history_id (UUID): The ID of the upload history.
        status_filter (list[str]): The list of status filters to apply.
        size (int): The number of items to return.
        offset (int): The offset for pagination.

    Returns:
        ExecuteResults: The summary of the bulk operation result.

    Raises:
        RecordNotFound: If the upload history with the given ID does not exist.
    """
    upload = history_table.get_upload_by_id(history_id)
    if not upload:
        raise RecordNotFound(E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": history_id})

    raw_results: list[dict] = history_table.get_paginated_upload_results(
        history_id, offset, size, status_filter or []
    )

    summary = history_table.get_upload_results(history_id, "summary")

    payload = {
        "items": raw_results,
        "summary": summary,
        "fileId": upload.file_id,
        "fileName": Path(upload.file.file_path).name,
        "operator": upload.operator_name or upload.operator_id,
        "startTimestamp": upload.timestamp,
        "endTimestamp": upload.end_timestamp,
        "total": 0,
        "offset": offset,
        "pageSize": size,
    }
    result = ExecuteResults.model_validate(payload)
    current_app.logger.info(
        I.SUCCESS_GET_BULK_OPERATION_RESULT, {"history_id": history_id}
    )
    return result


@shared_task()
def delete_temporary_file(temp_id: str) -> None:
    """Delete the temporary file with the given ID.

    Args:
        temp_id(str): delete file id
    """
    temp_file_id = UUID(temp_id)
    try:
        file_path = history_table.get_file_by_id(temp_file_id).file_path
    except RecordNotFound:
        return
    if Path(file_path).exists():
        Path(file_path).unlink()
    history_table.delete_file_by_id(temp_file_id)


def chack_permission_to_operation(history_id: UUID, operator_id: str) -> bool:
    """Check if the user has permission to perform bulk operation.

    Args:
        history_id (UUID): The ID of the upload history.
        operator_id (str): The ID of the operator.

    Returns:
        bool: True if the user has permission, False otherwise.

    Raises:
        RecordNotFound: If the upload history with the given ID does not exist.
    """
    upload = history_table.get_upload_by_id(history_id)
    if not upload:
        current_app.logger.error(E.UPDATE_HISTORY_RECORD_NOT_FOUND, {"id": history_id})
        raise RecordNotFound(E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": history_id})
    return upload.operator_id == operator_id


def chack_permission_to_view(history_id: UUID) -> bool:
    """Check if the user has permission to view the specified upload history.

    Args:
        history_id (UUID): The ID of the upload history.

    Returns:
        bool: True if the user has permission, False otherwise.

    Raises:
        RecordNotFound: If the upload history with the given ID does not exist.
    """
    if is_current_user_system_admin():
        return True
    upload = history_table.get_upload_by_id(history_id)
    if not upload:
        current_app.logger.error(E.UPDATE_HISTORY_RECORD_NOT_FOUND, {"id": history_id})
        raise RecordNotFound(E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": history_id})
    repository_id = upload.file.file_content["repositories"][0]["id"]
    return repository_id not in get_permitted_repository_ids() and upload.public
