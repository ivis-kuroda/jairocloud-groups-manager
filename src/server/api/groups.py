#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API endpoints for group-related operations."""

import traceback
import typing as t

from flask import Blueprint, current_app, url_for
from flask_login import login_required
from flask_pydantic import validate

from server.api.helpers import roles_required
from server.const import USER_ROLES
from server.entities.group_detail import GroupDetail
from server.entities.search_request import FilterOption, SearchResult
from server.exc import (
    InvalidFormError,
    InvalidQueryError,
    RequestConflict,
    ResourceInvalid,
    ResourceNotFound,
)
from server.messages import E
from server.services import groups
from server.services.utils import (
    detect_affiliation,
    detect_affiliations,
    filter_permitted_group_ids,
    is_current_user_system_admin,
    search_groups_options,
)

from .schemas import (
    DeleteGroupsBody,
    ErrorResponse,
    GroupPatchRequest,
    GroupsQuery,
)


bp = Blueprint("groups", __name__)


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def get(query: GroupsQuery) -> tuple[SearchResult | ErrorResponse, int]:
    """Get a list of groups based on query parameters.

    Args:
        query (GroupsQuery): Query parameters for filtering groups.

    Returns:
        - If succeeded in getting groups, search result and status code 200
        - If query is invalid, error message and status code 400
    """
    try:
        results = groups.search(query)
    except InvalidQueryError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400

    return results, 200


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def post(
    body: GroupDetail,
) -> tuple[GroupDetail, int, dict[str, str]] | tuple[ErrorResponse, int]:
    """Create group endpoint.

    Args:
        body (GroupDetail): Group information to create.

    Returns:
        - If succeeded in creating group, group information
            and status code 201 and location header
        - If form data is invalid, error message and status code 400
        - If logged-in user does not have permission, status code 403
        - If id already exist, status code 409
    """
    # permission will be checked in validation process.
    try:
        created = groups.create(body)
    except InvalidFormError as exc:
        traceback.print_exc()
        if exc.message == E.GROUP_FORBIDDEN_REPOSITORY:
            return ErrorResponse(message=exc.message), 403

        return ErrorResponse(message=exc.message), 400
    except ResourceInvalid as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 409

    header = {
        "Location": url_for("api.groups.id_get", group_id=created.id, _external=True)
    }
    return created, 201, header


@bp.get("/<string:group_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_get(group_id: str) -> tuple[GroupDetail | ErrorResponse, int]:
    """Get information of group endpoint.

    Args:
        group_id (str): Group id to get.

    Returns:
        - If succeeded in getting group information,
          group information and status code 200
        - If logged-in user does not have permission, status code 403
        - If group not found, status code 404
    """
    if not detect_affiliation(group_id):
        # out of this service's scope.
        current_app.logger.error(E.GROUP_UNRECOGNIZED_ID, {"id": group_id})
        return ErrorResponse(message=E.GROUP_NOT_FOUND % {"id": group_id}), 404

    if not has_permission(group_id):
        current_app.logger.error(E.GROUP_FORBIDDEN, {"id": group_id})
        return ErrorResponse(message=E.GROUP_FORBIDDEN % {"id": group_id}), 403

    result = groups.get_by_id(group_id, more_detail=True)

    if result is None:
        current_app.logger.error(E.GROUP_NOT_FOUND, {"id": group_id})
        return ErrorResponse(message=E.GROUP_NOT_FOUND % {"id": group_id}), 404
    return result, 200


@bp.put("/<string:group_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_put(group_id: str, body: GroupDetail) -> tuple[GroupDetail | ErrorResponse, int]:
    """Update group information endpoint.

    Args:
        group_id (str): Group id to update.
        body (GroupDetail): Group information to update.

    Returns:
        - If succeeded in updating group informaion,
          group information and status code 200
        - If logged-in user does not have permission, status code 403
        - If group not found, status code 404
        - If coflicted group information, status code 409
    """
    if not detect_affiliation(group_id):
        # out of this service's scope.
        current_app.logger.error(E.GROUP_UNRECOGNIZED_ID, {"id": group_id})
        return ErrorResponse(message=E.GROUP_NOT_FOUND % {"id": group_id}), 404

    if not has_permission(group_id):
        current_app.logger.error(E.GROUP_FORBIDDEN, {"id": group_id})
        return ErrorResponse(message=E.GROUP_FORBIDDEN % {"id": group_id}), 403

    body.id = group_id
    try:
        result = groups.update(body)
    except InvalidFormError as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 400
    except ResourceNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404
    return result, 200


@bp.patch("/<string:group_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_patch(
    group_id: str, body: GroupPatchRequest
) -> tuple[GroupDetail | ErrorResponse, int]:
    """Update group endpoint.

    It supports adding and removing group members,
    but does not support updating other group information.

    Args:
        group_id(str): Group id to update.
        body(GroupPatchRequest): Group member information to update.

    Returns:
        - If succeeded in updating group member,
          group member and status code 200
        - If logged-in user does not have permission, status code 403
        - If group not found, status code 404
        - If coflicted group member, status code 409
    """
    if not detect_affiliation(group_id):
        # out of this service's scope.
        current_app.logger.error(E.GROUP_UNRECOGNIZED_ID, {"id": group_id})
        return ErrorResponse(message=E.GROUP_NOT_FOUND % {"id": group_id}), 404

    if not has_permission(group_id):
        current_app.logger.error(E.GROUP_FORBIDDEN, {"id": group_id})
        return ErrorResponse(message=E.GROUP_FORBIDDEN % {"id": group_id}), 403

    adding = set()
    removing = set()
    for operation in body.operations:
        if operation.path != "members":
            current_app.logger.error(
                E.GROUP_UNSUPPORTED_PATCH_PATH, {"path": operation.path}
            )
            return ErrorResponse(
                message=E.GROUP_UNSUPPORTED_PATCH_PATH % {"path": operation.path}
            ), 400

        if operation.op == "add":
            adding.update(set(operation.value))
        elif operation.op == "remove":
            removing.update(set(operation.value))

    try:
        result = groups.update_member(group_id, add=adding, remove=removing)
    except RequestConflict as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 409
    except ResourceNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404

    return result, 200


@bp.delete("/<string:group_id>")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def id_delete(group_id: str) -> tuple[t.Literal[""], int] | tuple[ErrorResponse, int]:
    """Single group deletion endpoint.

    Args:
        group_id(str): Group id to delete.

    Returns:
        - If succeeded in delete group, status code 204
        - If group is role-type group, status code 400
        - If logged-in user does not have permission, status code 403
        - If group not found, status code 404
    """
    if not detect_affiliation(group_id):
        # out of this service's scope.
        current_app.logger.error(E.GROUP_UNRECOGNIZED_ID, {"id": group_id})
        return ErrorResponse(message=E.GROUP_NOT_FOUND % {"id": group_id}), 404

    rolegroups, _ = detect_affiliations(list(group_id))
    if rolegroups:
        current_app.logger.error(E.ROLEGROUP_CANNOT_DELETE)
        return ErrorResponse(message=E.ROLEGROUP_CANNOT_DELETE), 400

    if not has_permission(group_id):
        current_app.logger.error(E.GROUP_FORBIDDEN, {"id": group_id})
        return ErrorResponse(message=E.GROUP_FORBIDDEN % {"id": group_id}), 403

    try:
        groups.delete_by_id(group_id)
    except ResourceNotFound as exc:
        traceback.print_exc()
        return ErrorResponse(message=exc.message), 404

    return "", 204


@bp.post("/delete")
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def delete_post(
    body: DeleteGroupsBody,
) -> tuple[t.Literal[""], int] | tuple[ErrorResponse, int]:
    """The multiple group deletion endpoint.

    Args:
        body (DeleteGroupsBody): Group ids to delete.

    Returns:
        - If any of groups failed to delete,
            status code 202 and error message with failed group list
        - If succeeded in delete group, status code 204
        - If any of the groups is role-type group, status code 400
          (In this case, no group will be deleted.)
        - If logged-in user does not have permission, status code 403
    """
    rolegroups, groups_ = detect_affiliations(list(group_ids := body.group_ids))

    if rolegroups:
        current_app.logger.error(E.ROLEGROUP_CANNOT_DELETE)
        return ErrorResponse(message=E.ROLEGROUP_CANNOT_DELETE), 400

    non_detected = {_.group_id for _ in groups_} ^ set(group_ids)
    if non_detected:
        current_app.logger.error(
            E.SOME_GROUP_UNRECOGNIZED, {"ids": ", ".join(non_detected)}
        )
        return ErrorResponse(
            message=E.SOME_GROUP_UNRECOGNIZED % {"ids": ", ".join(non_detected)}
        ), 400

    if not has_permission(*group_ids):
        return ErrorResponse(code="", message=""), 403

    group_list = groups.delete_multiple(group_ids)
    if group_list:
        message = f"{group_list} is failed"
        return ErrorResponse(code="", message=message), 202
    return "", 204


@bp.get("/filter-options")
@validate(response_many=True)
def filter_options() -> list[FilterOption]:
    """Get filter options for groups search.

    Returns:
        list[FilterOption]: List of filter options for group search.
    """
    return search_groups_options()


def has_permission(*group_id: str) -> bool:
    """Check user controll permmision.

    If the logged-in user is a system administrator or
    an administrator of the target group, that user has permission.

    Args:
        group_id (str): Group ID to check permission for.

    Returns:
        bool:
        - True: logged-in user has permission
        - False: logged-in user does not have permission
    """
    if is_current_user_system_admin():
        return True

    return filter_permitted_group_ids(*group_id) == set(group_id)
