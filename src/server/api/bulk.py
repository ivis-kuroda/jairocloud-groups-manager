#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API router for bulk endpoints."""

import traceback
import typing as t

from uuid import UUID

from flask import Blueprint, current_app
from flask_login import current_user, login_required
from flask_pydantic import validate

from server.config import config
from server.const import USER_ROLES
from server.entities.bulk import (
    ExecuteResults,
    ValidateResults,
)
from server.entities.login_user import LoginUser
from server.exc import (
    ApiRequestError,
    BulkOperationError,
    RecordNotFound,
)
from server.messages import E
from server.services import bulks, history_table, repositories
from server.services.utils import get_permitted_repository_ids, require_enabled

from .helpers import roles_required, validate_files
from .schemas import (
    BulkBody,
    BulkFileForm,
    BulkResultQuery,
    ErrorResponse,
    ExcuteRequest,
    TargetRepositoryForm,
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
    user = t.cast("LoginUser", current_user)
    repository_id = form.repository_id

    if repositories.get_by_id(repository_id) is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"id": repository_id})
        return ErrorResponse(
            message=E.REPOSITORY_NOT_FOUND % {"id": repository_id}
        ), 404

    if not user.is_system_admin and repository_id not in get_permitted_repository_ids():
        current_app.logger.error(E.REPOSITORY_FORBIDDEN, {"id": repository_id})
        return ErrorResponse(
            message=E.REPOSITORY_FORBIDDEN % {"id": repository_id}
        ), 403

    tmp_file_id = bulks.upload_file(repository_id, files.bulk_file)
    task = bulks.validate_upload_data.delay(user.map_id, user.user_name, tmp_file_id)

    return BulkBody(task_id=task.id, tmp_file_id=tmp_file_id), 200


@bp.get("/validate/status/<uuid:task_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def validate_status(task_id: UUID) -> BulkBody:
    """Get the status of a validation task.

    Args:
        task_id (UUID): The ID of the validation task.

    Returns:
        BulkBody: The response containing task status
    """
    task = bulks.get_validate_task_result(task_id)
    return BulkBody(status=task.state)


@bp.get("/validate/result/<uuid:task_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def validate_result(
    query: BulkResultQuery,
    task_id: UUID,
) -> tuple[ValidateResults | ErrorResponse, int]:
    """Get the result of a validation task.

    Args:
        query (BulkResultQuery): Query parameters for filtering results.
        task_id (UUID): The ID of the validation task.

    Returns:
        ValidateSummary: The response containing validation result
        ErrorResponse: The response containing validation result or error message.
    """
    user = t.cast("LoginUser", current_user)

    try:
        task = bulks.get_validate_task_result(task_id)
        history_id = task.get(config.REDIS.socket_timeout)

        if not bulks.chack_permission_to_operation(history_id, user.map_id):
            current_app.logger.error(E.OPERATION_FORBIDDEN)
            return ErrorResponse(message=E.OPERATION_FORBIDDEN), 403

        result = bulks.get_validate_result(history_id, query)
    except RecordNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404

    except (ApiRequestError, BulkOperationError) as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400

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
    user = t.cast("LoginUser", current_user)
    try:
        history_id = history_table.get_history_by_file_id(body.tmp_file_id).id

        if not bulks.chack_permission_to_operation(history_id, user.map_id):
            current_app.logger.error(E.OPERATION_FORBIDDEN)
            return ErrorResponse(message=E.OPERATION_FORBIDDEN), 403

        task = bulks.update_users.delay(history_id, body.tmp_file_id, body.delete_users)
    except RecordNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404

    return BulkBody(task_id=task.id, history_id=history_id), 200


@bp.get("/execute/status/<uuid:task_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@validate()
@require_enabled("enable_bulk_operation")
def execute_status(task_id: UUID) -> BulkBody:
    """Get the status of an execution task.

    Args:
        task_id (UUID): The ID of the execution task.

    Returns:
        BulkBody: The response containing task status.
    """
    task = bulks.get_execute_task_result(task_id)
    return BulkBody(status=task.state)


@bp.get("/result/<string:history_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
@require_enabled("enable_bulk_operation")
def result(
    history_id: UUID, query: BulkResultQuery
) -> tuple[ExecuteResults | ErrorResponse, int]:
    """Get the result of a bulk upload.

    Args:
        history_id (UUID):ID of the history to get.
        query(BulkResultQuery): Query parameters for filtering results.

    Returns:
        ExecuteResults: Summary of displayed history If the get is successful
        ErrorResponse: If the get is failed
    """
    try:
        if not bulks.chack_permission_to_view(history_id):
            current_app.logger.error(E.OPERATION_FORBIDDEN)
            return ErrorResponse(message=E.OPERATION_FORBIDDEN), 403

        result = bulks.get_upload_result(history_id, query)
    except RecordNotFound as exc:
        return ErrorResponse(message=exc.message), 404

    return result, 200
