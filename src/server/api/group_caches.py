#
# Copyright (C) 2025 National Institute of Informatics.
#
"""API router for cache group endpoints."""

import traceback
import typing as t

from flask import Blueprint, current_app
from flask_login import login_required
from flask_pydantic import validate
from weko_group_cache_db.config import setup_config as setup_weko_group_cache_db_config

from server.config import config
from server.const import USER_ROLES
from server.entities.cache import TaskDetail
from server.entities.search_request import SearchResult
from server.exc import InvalidQueryError, RequestConflict
from server.messages import E
from server.services import group_caches

from .helpers import roles_required
from .schemas import (
    CacheQuery,
    CacheRequest,
    ErrorResponse,
)


bp = Blueprint("group-caches", __name__)


@bp.before_request
def init_settings() -> None:
    """Initialize settings for the request."""
    setup_weko_group_cache_db_config(config.CACHE_DB)


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate(response_by_alias=True)
def get(query: CacheQuery) -> tuple[SearchResult, int] | tuple[ErrorResponse, int]:
    """Retrieve repository cache entries based on the provided query.

    Args:
        query (CacheQuery): Query parameters for filtering and pagination.

    Returns:
        - If succeeded in getting repository cache, search result and status code 200
        - If query is invalid, error message and status code 400
    """
    try:
        cache_result = group_caches.get_repository_cache(query)
    except InvalidQueryError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400

    return cache_result, 200


@bp.post("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate()
def post(body: CacheRequest) -> tuple[t.Literal[""], int] | tuple[ErrorResponse, int]:
    """Update cache groups for the specified repositories.

    Args:
        body (CacheRequest): Request body containing repositories and operation.

    Returns:
        - If the update task is successfully started, empty response and status code 202
        - If there is a conflict in starting the task, error message and status code 409
    """
    try:
        group_caches.update(body.op, body.ids)
    except RequestConflict as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 409

    return "", 202


@bp.get("/status", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate()
def status() -> tuple[TaskDetail | ErrorResponse, int]:
    """Get the status of the cache update task.

    Returns:
        - If a task is running, details of the task and status code 200
        - If no task is running, error message and status code 400
    """
    task_status = group_caches.get_task_status()
    if task_status is None:
        current_app.logger.error(E.UPDATE_TASK_NOT_RUNNING)
        return ErrorResponse(message=E.UPDATE_TASK_NOT_RUNNING), 400

    return task_status, 200
