#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API router for bulk endpoints."""

from uuid import UUID

from flask import Blueprint, current_app
from flask_login import current_user, login_required
from flask_pydantic import validate

from server.auth import is_user_logged_in
from server.const import DEFAULT_SEARCH_COUNT, USER_ROLES
from server.entities.bulk import (
    ExecuteResults,
    ValidateResults,
)
from server.exc import (
    FileFormatError,
    FileNotFound,
    FileValidationError,
    RecordNotFound,
    TaskExecutionError,
)
from server.messages import E
from server.services import bulks, history_table, repositories
from server.services.utils import get_permitted_repository_ids, require_enabled

from .helpers import roles_required, validate_files
from .schemas import (
    BulkBody,
    BulkFileForm,
    ErrorResponse,
    ExcuteRequest,
    TargetRepositoryForm,
    UploadQuery,
)


STATUS_MAP = {0: "create", 1: "update", 2: "delete", 3: "skip", 4: "error"}


bp = Blueprint("bulk", __name__)


@bp.post("/upload-file")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate_files
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def upload_file(
    form: TargetRepositoryForm, files: BulkFileForm
) -> tuple[BulkBody | ErrorResponse, int]:
    """Upload a file for bulk processing.

    Args:
        form (TargetRepositoryForm): Target repository ID for upload.
        files (BulkFileForm): File to upload.

    Returns:
        BulkBody: The response containing task ID
        ErrorResponse: The response containing task ID or error message.
    """
    if repositories.get_by_id(form.repository_id) is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"id": form.repository_id})
        return ErrorResponse(
            message=E.REPOSITORY_NOT_FOUND % {"id": form.repository_id}
        ), 404
    if (
        not current_user.is_system_admin
        and form.repository_id not in get_permitted_repository_ids()
    ):
        current_app.logger.error(E.REPOSITORY_FORBIDDEN, {"id": form.repository_id})
        return ErrorResponse(
            message=E.REPOSITORY_FORBIDDEN % {"id": form.repository_id}
        ), 403
    temp_file_id = bulks.upload_file(form.repository_id, files.bulk_file)
    task = bulks.validate_upload_data.apply_async(
        (current_user.map_id, current_user.user_name, temp_file_id),
        session_required=True,  # pyright: ignore[reportCallIssue]
    )
    return BulkBody(task_id=task.id, temp_file_id=temp_file_id), 200


@bp.get("/validate/status/<string:task_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def validate_status(task_id: str) -> tuple[BulkBody | ErrorResponse, int]:
    """Get the status of a validation task.

    Args:
        task_id (str): The ID of the validation task.

    Returns:
        BulkBody: The response containing task status
        ErrorResponse: The response containing task status or error message
    """
    try:
        res = bulks.get_validate_task_result(task_id)
    except TaskExecutionError as exc:
        return ErrorResponse(message=exc.message), 404
    return BulkBody(status=res.state), 200


@bp.get("/validate/result/<string:task_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def validate_result(
    query: UploadQuery,
    task_id: str,
) -> tuple[ValidateResults | ErrorResponse, int]:
    """Get the result of a validation task.

    Args:
        query (UploadQuery): Query parameters for filtering results.
        task_id (str): The ID of the validation task.

    Returns:
        ValidateSummary: The response containing validation result
        ErrorResponse: The response containing validation result or error message.
    """
    try:
        res = bulks.get_validate_task_result(task_id)
        match res.result:
            case FileNotFound():
                return ErrorResponse(message=res.result.message), 404
            case FileValidationError() | FileFormatError():
                return ErrorResponse(message=res.result.message), 400
            case UUID():
                pass
            case _:
                return ErrorResponse(message=E.UNEXPECTED_SERVER_ERROR), 500
        history_id = res.result
        status_filter = [STATUS_MAP[status] for status in query.f] if query.f else []
        offset = query.p or 1
        size = query.l or DEFAULT_SEARCH_COUNT
        if not is_user_logged_in(
            current_user
        ) or not bulks.chack_permission_to_operation(history_id, current_user.map_id):
            current_app.logger.error(E.OPERATION_FORBIDDEN)
            return ErrorResponse(message=E.OPERATION_FORBIDDEN), 403
        result = bulks.get_validate_result(
            history_id=history_id, status_filter=status_filter, offset=offset, size=size
        )
    except (RecordNotFound, TaskExecutionError) as exc:
        return ErrorResponse(message=exc.message), 404
    return result, 200


@bp.post("/execute")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def execute(body: ExcuteRequest) -> tuple[BulkBody | ErrorResponse, int]:
    """Execute a bulk upload.

    Args:
        body (UploadBody):
          The request body containing temporary ID, repository ID, task ID,
          and users to delete.

    Returns:
        BulkBody: The response containing task ID
        ErrorResponse: The response containing task ID or error message
    """
    try:
        history_id = history_table.get_history_by_file_id(body.temp_file_id).id
        if not is_user_logged_in(
            current_user
        ) or not bulks.chack_permission_to_operation(history_id, current_user.map_id):
            current_app.logger.error(E.OPERATION_FORBIDDEN)
            return ErrorResponse(message=E.OPERATION_FORBIDDEN), 403
        task = bulks.update_users.apply_async(
            kwargs={
                "history_id": history_id,
                "temp_file_id": body.temp_file_id,
                "delete_users": body.delete_users,
            },
        )
    except RecordNotFound as exc:
        return ErrorResponse(message=exc.message), 404
    return BulkBody(task_id=task.id, history_id=history_id), 200


@bp.get("/execute/status/<string:task_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@validate()
@require_enabled("enable_bulk_operation")
def execute_status(task_id: str) -> tuple[BulkBody | ErrorResponse, int]:
    """Get the status of an execution task.

    Args:
        task_id (str): The ID of the execution task.

    Returns:
        str: The response containing task status
        ErrorResponse: The response containing task status or error message
    """
    try:
        res = bulks.get_execute_task_result(task_id)
    except TaskExecutionError as exc:
        return ErrorResponse(message=exc.message), 404
    return BulkBody(status=res.state), 200


@bp.get("/result/<string:history_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def result(
    history_id: UUID, query: UploadQuery
) -> tuple[ExecuteResults | ErrorResponse, int]:
    """Get the result of a bulk upload.

    Args:
        history_id (UUID):ID of the history to get.
        query(UploadQuery): Query parameters for filtering results.

    Returns:
        ExecuteResults: Summary of displayed history If the get is successful
        ErrorResponse: If the get is failed
    """
    status_filter = [STATUS_MAP[status] for status in query.f] if query.f else []
    offset = query.p or 1
    size = query.l or DEFAULT_SEARCH_COUNT
    try:
        if not bulks.chack_permission_to_view(history_id):
            current_app.logger.error(E.OPERATION_FORBIDDEN)
            return ErrorResponse(message=E.OPERATION_FORBIDDEN), 403
        result = bulks.get_upload_result(
            history_id=history_id, status_filter=status_filter, offset=offset, size=size
        )
    except RecordNotFound as exc:
        return ErrorResponse(message=exc.message), 404

    return result, 200
