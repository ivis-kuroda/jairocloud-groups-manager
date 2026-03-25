#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API router for history endpoints."""

import typing as t

from pathlib import Path
from uuid import UUID

from flask import Blueprint, Response, current_app, send_file
from flask_login import login_required
from flask_pydantic import validate

from server.const import USER_ROLES
from server.entities.history_detail import HistoryQuery
from server.entities.search_request import FilterOption, SearchResult
from server.exc import InvalidQueryError, RecordNotFound
from server.messages import E
from server.services import history
from server.services.utils import search_history_filter_options

from .helpers import roles_required
from .schemas import ErrorResponse, HistoryPublic, OperatorQuery


bp = Blueprint("history", __name__)


@bp.get("/filter-options")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_many=True)
def filter_options() -> list[FilterOption]:
    """Get filter options for history data.

    Returns:
        list[FilterOption]: list of filter options for history data
    """
    return search_history_filter_options()


@bp.get("/<tab>/filter-options/operators")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True, exclude_none=True)
def filter_options_operators(
    tab: t.Literal["download", "upload"], query: OperatorQuery
) -> tuple[SearchResult, int] | tuple[ErrorResponse, int]:
    """Get filter options for history data.

    Args:
        tab (t.Literal["download", "upload"]): Type of history (download or upload)
        query (OperatorQuery): Query parameters for filtering operator options

    Returns:
        SearchResult: if successful and status code 200
        ErrorResponse: if an error occurs  and status code 400
    """
    try:
        result = history.get_filter_items(tab, key="o", criteria=query)
    except InvalidQueryError as exc:
        return ErrorResponse(message=exc.message), 400
    return result, 200


@bp.get("/<string:tab>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True, exclude_none=True)
def get(
    tab: t.Literal["download", "upload"], query: HistoryQuery
) -> tuple[SearchResult | ErrorResponse, int]:
    """Get history data.

    Args:
        query (HistoryQuery): Query parameters for filtering history data
        tab (t.Literal["download", "upload"]): Type of history (download or upload)

    Returns:
        SearchResult: if successful and status code 200
        ErrorResponse: if a connection error occurs and status code 503
    """
    if tab == "download":
        result = history.get_download_history_data(query)
    else:
        result = history.get_upload_history_data(query)
    return result, 200


@bp.put("/<tab>/<history_id>/public-status")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate(response_by_alias=True)
def public_status(
    tab: t.Literal["download", "upload"], history_id: UUID, body: HistoryPublic
) -> tuple[HistoryPublic | ErrorResponse, int]:
    """Update the public status of a history item.

    Args:
        tab (t.Literal["download", "upload"]): Type of history (download or upload)
        history_id (UUID): Unique identifier of the history item
        body (HistoryPublic): Request body containing the new public status

    Returns:
        HistoryPublic: The updated public status of the history item
        int: HTTP status code
    """
    try:
        result: bool = history.update_public_status(
            tab=tab, history_id=history_id, public=body.public
        )
    except RecordNotFound as exc:
        return ErrorResponse(message=exc.message), 404
    return HistoryPublic(public=result), 200


@bp.get("/files/<file_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def files(file_id: UUID) -> Response | tuple[ErrorResponse, int]:
    """Download a file associated with a history item.

    Args:
        file_id (UUID): Unique identifier of the file to be downloaded

    Returns:
        Response: Flask response object to send the file
    """
    try:
        path_str = history.get_file_path(file_id)
        file_path = Path(path_str)
    except RecordNotFound as exc:
        return ErrorResponse(message=exc.message), 404
    if not file_path.exists():
        current_app.logger.error(E.FILE_NOT_FOUND, {"path": file_path})
        return ErrorResponse(message=E.FILE_NOT_FOUND % {"path": file_path}), 404
    return send_file(path_or_file=file_path)
