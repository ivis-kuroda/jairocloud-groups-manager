#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API endpoints for repository-related operations."""

import traceback
import typing as t

from flask import Blueprint, current_app, url_for
from flask_login import login_required
from flask_pydantic import validate

from server.const import USER_ROLES
from server.entities.repository_detail import RepositoryDetail
from server.entities.search_request import FilterOption, SearchResult
from server.exc import (
    InvalidFormError,
    InvalidQueryError,
    ResourceInvalid,
    ResourceNotFound,
)
from server.messages import E
from server.services.resources import RepositoryService
from server.services.utils import (
    get_permitted_repository_ids,
    is_current_user_system_admin,
    search_repositories_options,
)

from .helpers import roles_required
from .schemas import ErrorResponse, RepositoriesQuery, RepositoryDeleteQuery


bp = Blueprint("repositories", __name__)


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def get(
    query: RepositoriesQuery,
) -> tuple[SearchResult, int] | tuple[ErrorResponse, int]:
    """Get a list of repositories based on query parameters.

    Args:
        query (RepositoriesQuery): Query parameters for filtering repositories.

    Returns:
        - If succeeded in getting repositories, search result and status code 200
        - If query is invalid, error message and status code 400
    """
    try:
        results = RepositoryService.search(query)
    except InvalidQueryError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400

    return results, 200


@bp.post("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate(response_by_alias=True)
def post(
    body: RepositoryDetail,
) -> tuple[RepositoryDetail, int, dict[str, str]] | tuple[ErrorResponse, int]:
    """Create repository endpoint.

    Args:
        body (RepositoryDetail): Repository information to create.

    Returns:
        - If succeeded in creating repository, repository information
            and status code 201 and location header
        - If form is invalid, error message and status code 400
        - If logged-in user does not have permission, status code 403
        - If id already exists, status code 409
    """
    try:
        created = RepositoryService.create(body)
    except InvalidFormError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400
    except ResourceInvalid as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 409

    header = {
        "Location": url_for(
            "api.repositories.id_get", repository_id=created.id, _external=True
        )
    }
    return created, 201, header


@bp.get("/<string:repository_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_get(repository_id: str) -> tuple[RepositoryDetail | ErrorResponse, int]:
    """Get information of repository endpoint.

    Args:
        repository_id(str): Repository id to get.

    Returns:
        - If succeeded in getting repository information,
            repository information and status code 200
        - If logged-in user does not have permission, status code 403
        - If repository not found, status code 404
    """
    result = RepositoryService.get_by_id(repository_id, more_detail=True)
    if result is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"id": repository_id})
        return ErrorResponse(
            message=E.REPOSITORY_NOT_FOUND % {"id": repository_id}
        ), 404

    if not has_permission(repository_id):
        current_app.logger.error(E.REPOSITORY_FORBIDDEN, {"id": repository_id})
        return ErrorResponse(
            message=E.REPOSITORY_FORBIDDEN % {"id": repository_id}
        ), 403

    return result, 200


@bp.put("/<string:repository_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate(response_by_alias=True)
def id_put(
    repository_id: str, body: RepositoryDetail
) -> tuple[RepositoryDetail | ErrorResponse, int]:
    """Update repository endpoint.

    Args:
        repository_id(str): Repository id to update.
        body(RepositoryDetail): Repository information to update.

    Returns:
        - If succeeded in updating repository, repository information
            and status code 200
        - If form data is invalid, error message and status code 400
        - If repository not found, status code 404
    """
    body.id = repository_id
    try:
        updated = RepositoryService.update(body)
    except InvalidFormError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400
    except ResourceNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404

    return updated, 200


@bp.delete("/<string:repository_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN)
@validate(response_by_alias=True)
def id_delete(
    repository_id: str, query: RepositoryDeleteQuery
) -> tuple[t.Literal[""], int] | tuple[ErrorResponse, int]:
    """Delete repository endpoint.

    Args:
        repository_id(str): Repository id to delete.
        query(RepositoryDeleteQuery): Query parameters for deletion.

    Returns:
        - If succeeded in deleting repository, status code 204
        - If repository not found, status code 404
    """
    try:
        RepositoryService.delete_by_id(repository_id, query.confirmation)
    except InvalidFormError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400
    except ResourceNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404

    return "", 204


def has_permission(repository_id: str) -> bool:
    """Check user controll permmision.

    If the logged-in user is a system administrator or
    an administrator of the target repository, that user has permission.

    Args:
        repository_id (str): Repository ID to check permission for.

    Returns:
        bool:
        - True: logged-in user has permission
        - False: logged-in user does not have permission
    """
    if is_current_user_system_admin():
        return True

    permitted_repository_ids = get_permitted_repository_ids()
    return repository_id in permitted_repository_ids


@bp.get("/filter-options")
@validate(response_many=True)
def filter_options() -> list[FilterOption]:
    """Get filter options for repository search.

    Returns:
        list[FilterOption]: List of filter options for repository search.
    """
    return search_repositories_options()
