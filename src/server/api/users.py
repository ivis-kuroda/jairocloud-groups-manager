#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API endpoints for user-related operations."""

import inspect
import sys
import traceback
import typing as t

from flask import Blueprint, Response, current_app, send_file, url_for
from flask_login import current_user, login_required
from flask_pydantic import validate

from server.const import USER_ROLES
from server.entities.login_user import LoginUser
from server.entities.search_request import FilterOption, SearchResult
from server.entities.user_detail import UserDetail
from server.exc import (
    InvalidExportError,
    InvalidFormError,
    InvalidQueryError,
    RequestConflict,
    ResourceInvalid,
    ResourceNotFound,
)
from server.messages import E
from server.services import users
from server.services.utils import (
    is_current_user_system_admin,
    search_users_options,
)

from .auth import logout
from .helpers import roles_required
from .schemas import ErrorResponse, FileQuery, UsersQuery


bp = Blueprint("users", __name__)


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def get(query: UsersQuery) -> tuple[SearchResult | ErrorResponse, int]:
    """Get a list of users based on query parameters.

    Args:
        query (UsersQuery): Query parameters for filtering users.

    Returns:
        - If succeeded in getting users, search result and status code 200
        - If query is invalid, error message and status code 400
    """
    try:
        results = users.search(query)
    except InvalidQueryError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400

    return results, 200


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def post(
    body: UserDetail,
) -> tuple[UserDetail, int, dict[str, str]] | tuple[ErrorResponse, int]:
    """Create user endpoint.

    Args:
        body(UserDetail): User information

    Returns:
        - If succeeded in creating user, user information
            and status code 201 and location header
        - If logged-in user does not have permission, status code 403
        - If id or eppn already exist, status code 409
        - If other error, status code 500

    """
    # permission will be checked in validation process.
    try:
        created = users.create(body)
    except InvalidFormError as exc:
        return ErrorResponse(message=exc.message), 400
    except ResourceInvalid as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 409

    header = {
        "Location": url_for("api.users.id_get", user_id=created.id, _external=True)
    }
    return created, 201, header


@bp.get("/<string:user_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_get(user_id: str) -> tuple[UserDetail | ErrorResponse, int]:
    """Get information of user endpoint.

    Args:
        user_id(str): User id

    Returns:
        - If succeeded in getting user information, user information and status code 200
        - If logged-in user does not have permission, status code 403
        - If user not found, status code 404
        - If other error, status code 500
    """
    user = users.get_by_id(user_id, more_detail=True)
    if user is None:
        current_app.logger.error(E.USER_NOT_FOUND, {"id": user_id})
        return ErrorResponse(message=E.USER_NOT_FOUND % {"id": user_id}), 404

    if not has_permission(user):
        current_app.logger.error(E.USER_FORBIDDEN, {"id": user_id})
        return ErrorResponse(message=E.USER_FORBIDDEN % {"id": user_id}), 403

    return user, 200


@bp.put("/<string:user_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_put(user_id: str, body: UserDetail) -> tuple[UserDetail | ErrorResponse, int]:
    """Update user information endpoint.

    Args:
        user_id(str): User id
        body(UserDetail): User information

    Returns:
        - If succeeded in updating user informaion,
          user information and status code 200
        - If logged-in user does not have permission, status code 403
        - If user not found, status code 404
        - If coflicted user information, status code 409
        - If other error, status code 500

    """
    body.id = user_id

    # permission will be checked in validation process.
    try:
        updated = users.update(body)
    except* InvalidFormError as exc:
        if exc.exceptions[0].message == E.USER_NO_UPDATE_SYSTEM_ADMIN:
            error = ErrorResponse(message=exc.message), 403
        else:
            error = ErrorResponse(message=exc.message), 400
    except* ResourceNotFound as exc:
        error = ErrorResponse(message=exc.message), 404
    except* (ResourceInvalid, RequestConflict) as exc:
        error = ErrorResponse(message=exc.message), 409
    else:
        if t.cast("LoginUser", current_user).map_id == user_id:
            # user is updating their own information, need to refresh session role.
            inspect.unwrap(logout)()
        return updated, 200
    finally:
        if sys.exc_info()[0] is not None:
            traceback.print_exc()

    return error


def has_permission(user: UserDetail) -> bool:
    """Check permmision to access user information.

    Args:
        user (UserDetail): User information.

    Returns:
        bool:
        - True: logged-in user has permission
        - False: logged-in user does not have permission
    """
    if is_current_user_system_admin():
        return True

    if user.is_system_admin:
        return False

    # check affiliations user can read.
    return bool(user.repository_roles)


@bp.get("/filter-options")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_many=True)
def filter_options() -> list[FilterOption]:
    """Get filter options for searching users.

    Returns:
        list[FilterOption]: List of filter options for user search.
    """
    return search_users_options()


@bp.get("/export")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def export_get(query: FileQuery) -> Response | tuple[ErrorResponse, int]:
    """Export users to a file for bulk processing.

    Args:
        query (FileQuery): The query parameters for the export.

    Returns:
        Response: The response containing the exported file
        ErrorResponse: The response containing an error message if the export fails
    """
    try:
        files = users.make_export_file(current_user.map_id, current_user.name, query)
    except InvalidExportError as exc:
        return ErrorResponse(message=exc.message), 403
    return send_file(files)


@bp.post("/export")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def export_post(body: FileQuery) -> Response | tuple[ErrorResponse, int]:
    """Export users to a file for bulk processing.

    Args:
        body (FileQuery): The query parameters for the export.

    Returns:
        Response: The response containing the exported file
        ErrorResponse: The response containing an error message if the export fails
    """
    try:
        files = users.make_export_file(current_user.map_id, current_user.name, body)
    except InvalidExportError as exc:
        return ErrorResponse(message=exc.message), 403
    return send_file(files)
