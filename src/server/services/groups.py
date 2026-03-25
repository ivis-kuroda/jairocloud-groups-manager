#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing groups."""

import re
import typing as t

from http import HTTPStatus

import requests

from flask import current_app
from pydantic_core import ValidationError

from server.clients import bulks, groups
from server.config import config
from server.const import (
    MAP_DUPLICATE_ID_PATTERN,
    MAP_NO_RIGHTS_UPDATE_PATTERN,
    MAP_NOT_FOUND_PATTERN,
)
from server.entities.bulk_request import BulkOperation
from server.entities.group_detail import GroupDetail, Repository
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup, MemberUser
from server.entities.search_request import SearchResponse, SearchResult
from server.entities.summaries import GroupSummary
from server.exc import (
    CredentialsError,
    InvalidFormError,
    InvalidQueryError,
    OAuthTokenError,
    RequestConflict,
    ResourceInvalid,
    ResourceNotFound,
    UnexpectedResponseError,
)
from server.messages import E, I

from . import users
from .token import get_access_token, get_client_secret
from .utils import (
    GroupsCriteria,
    build_patch_operations,
    build_search_query,
    build_update_member_operations,
    detect_repository,
    prepare_group,
    validate_group_to_map_group,
)


if t.TYPE_CHECKING:
    from server.clients.groups import GroupsSearchResponse
    from server.entities.patch_request import PatchOperation


@t.overload
def search(criteria: GroupsCriteria) -> SearchResult[GroupSummary]: ...
@t.overload
def search(
    criteria: GroupsCriteria, *, raw: t.Literal[True]
) -> SearchResponse[MapGroup]: ...


def search(
    criteria: GroupsCriteria, *, raw: bool = False
) -> SearchResult[GroupSummary] | SearchResponse[MapGroup]:
    """Search for groups based on given criteria.

    Args:
        criteria (GroupsCriteria): Search criteria for filtering groups.
        raw (bool):
            If True, return raw search response from mAP Core API. Defaults to False.

    Returns:
        object: Search results. The type depends on the `raw` argument.
        - SearchResult;
            Search result containing Group summaries. It has members `total`,
            `page_size`, `offset`, and `resources`.
        - SearchResponse;
            Raw search response from mAP Core API. It has members `schemas`,
            `total_results`, `start_index`, `items_per_page`, and `resources`.

    Raises:
        InvalidQueryError: If the query construction is invalid.
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    default_include = {
        "id",
        "display_name",
        "public",
        "member_list_visibility",
        "members",
        "services",
    }
    query = build_search_query(criteria)
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        results: GroupsSearchResponse = groups.search(
            query,
            include=default_include,
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except InvalidQueryError, OAuthTokenError, CredentialsError:
        raise

    if isinstance(results, MapError):
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        current_app.logger.error(
            E.RECEIVE_RESPONSE_MESSAGE, {"message": results.detail}
        )
        error = E.UNSUPPORTED_SEARCH_FILTER
        raise InvalidQueryError(error)

    if raw:
        return results

    group_summaries = [
        GroupSummary(
            id=t.cast("str", group.id),
            display_name=group.display_name,
            repository_name=repository.display,
            public=group.public,
            member_list_visibility=group.member_list_visibility,
            users_count=len(group.members) if group.members else 0,
        )
        for group in results.resources
        if (repository := detect_repository(group.services or []))
    ]

    return SearchResult[GroupSummary](
        total=results.total_results,
        page_size=results.items_per_page,
        offset=results.start_index,
        resources=group_summaries,
    )


@t.overload
def get_by_id(group_id: str, *, more_detail: bool = False) -> GroupDetail | None: ...
@t.overload
def get_by_id(group_id: str, *, raw: t.Literal[True]) -> MapGroup | None: ...


def get_by_id(
    group_id: str, *, raw: bool = False, more_detail: bool = False
) -> GroupDetail | MapGroup | None:
    """Get group from mAP Core API by group_id.

    Args:
        group_id (str): ID of the Group resource.
        more_detail (bool): If True, include more detail sach as repository name.
        raw (bool): If True, return raw MapGroup object. Defaults to False.

    Returns:
        object: The Group resource if found, otherwise None. The type depends
            on the `raw` argument.
        - GroupDetail: The Group detail object.
        - MapGroup: The raw Group object from mAP Core API.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapGroup | MapError = groups.get_by_id(
            group_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        return None

    if raw:
        return result

    return GroupDetail.from_map_group(result, more_detail=more_detail)


def create(group: GroupDetail) -> GroupDetail:
    """Create group to mAP Core API.

    Args:
        group (GroupDetail):
            Detail information about the group created from the input data.

    Returns:
        GroupDetail: The created Group detail object.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        ResourceInvalid: If the Group resource data is invalid.
        InvalidFormError: If failed to validate group form data for creation.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    admins = users.get_system_admins()

    try:
        map_group = prepare_group(group, administrators=admins)

        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapGroup | MapError = groups.post(
            map_group,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError, InvalidFormError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_DUPLICATE_ID_PATTERN, result.detail):
            error = E.GROUP_DUPLICATE_ID % {"id": m.group(1)}
            raise ResourceInvalid(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(
        I.SUCCESS_CREATE_GROUP,
        {"id": group.id, "rid": t.cast("Repository", group.repository).id},
    )
    return GroupDetail.from_map_group(result)


def update(group: GroupDetail) -> GroupDetail:  # noqa: C901
    """Update group from mAP Core API by group_id.

    Args:
        group (GroupDetail): The Group data to update. The `id` field is required.

    Returns:
        GroupDetail: The updated Group detail object.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If failed to validate group form data for update.
        ResourceNotFound: If the Group resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if config.MAP_CORE.update_strategy == "put":
        return update_put(group)

    try:
        validated = validate_group_to_map_group(group, mode="update")

        group_id = t.cast("str", group.id)
        current: GroupDetail | None = get_by_id(group_id)
        if current is None:
            error = E.GROUP_NOT_FOUND % {"id": group_id}
            raise ResourceNotFound(error)

        operations: list[PatchOperation[MapGroup]] = build_patch_operations(
            current.to_map_group(),
            validated,
            include={"display_name", "description"},
        )
        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapGroup | MapError = groups.patch_by_id(
            group_id,
            operations,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError, InvalidFormError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.REPOSITORY_NOT_FOUND % {"id": m.group(1)}
            raise ResourceNotFound(error)
        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_UPDATE_GROUP % {"id": group.id}
            raise OAuthTokenError(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(
        I.SUCCESS_UPDATE_GROUP,
        {"id": group.id, "rid": group.repository.id if group.repository else "N/A"},
    )
    return GroupDetail.from_map_group(result)


def update_put(group: GroupDetail) -> GroupDetail:
    """Update group from mAP Core API by group_id (replace with PUT).

    Args:
        group (GroupDetail): The Group data to update. The `id` field is required.

    Returns:
        GroupDetail: The updated Group detail object.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If failed to validate group form data for update.
        ResourceNotFound: If the Group resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if config.MAP_CORE.update_strategy == "patch":
        return update(group)

    try:
        validated = validate_group_to_map_group(group, mode="update")

        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapGroup | MapError = groups.put_by_id(
            validated,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError, InvalidFormError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.REPOSITORY_NOT_FOUND % {"id": m.group(1)}
            raise ResourceNotFound(error)
        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_UPDATE_GROUP % {"id": group.id}
            raise OAuthTokenError(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(
        I.SUCCESS_UPDATE_GROUP,
        {"id": group.id, "rid": group.repository.id if group.repository else "N/A"},
    )
    return GroupDetail.from_map_group(result)


def delete_multiple(group_ids: set[str]) -> set[str] | None:
    """Delete groups from mAP Core API by group_ids.

    Args:
        group_ids (list[str]): ID of the Group resource.

    Returns:
        list[str]: group id list of failed.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if not config.FEATURES.enable_bulk_operation:
        return delete_multiple_sequentially(group_ids)
    operations = [
        BulkOperation(method="DELETE", path=f"/Groups/{group_id}")
        for group_id in group_ids
    ]
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result = bulks.post(operations, access_token, client_secret)
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    failed_list = {
        o.path.removeprefix("Groups/")
        for o in result.operations
        if type(o.response) is MapError
    }
    if failed_list:
        current_app.logger.error(
            E.FAILED_DELETE_GROUPS, {"ids": ", ".join(failed_list)}
        )
    current_app.logger.info(
        I.SUCCESS_DELETE_GROUPS,
        {"ids": ", ".join(group_ids - failed_list)},
    )
    return failed_list if failed_list != set() else None


def delete_multiple_sequentially(group_ids: set[str]) -> set[str] | None:
    """Delete groups from mAP Core API by group_ids asynchronously.

    Args:
        group_ids (list[str]): ID of the Group resource.

    Returns:
        list[str]: group id list of failed.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
    """
    if config.FEATURES.enable_bulk_operation:
        return delete_multiple(group_ids)
    failed_list: set[str] = set()
    for group_id in group_ids:
        try:
            delete_by_id(group_id)
        except OAuthTokenError, CredentialsError:
            raise
        except (
            ResourceNotFound,
            ResourceInvalid,
            UnexpectedResponseError,
        ):
            failed_list.add(group_id)

    return failed_list if failed_list != set() else None


def delete_by_id(group_id: str) -> None:
    """Delete group from mAP Core API by group_id.

    Args:
        group_id (str): ID of the Group resource.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        ResourceNotFound: If the Group resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result = groups.delete_by_id(
            group_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if result is None:
        return

    current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
    current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
    if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
        error = E.GROUP_NOT_FOUND % {"id": group_id}
        raise ResourceNotFound(error)

    error = E.FAILED_PARSE_RESPONSE
    raise UnexpectedResponseError(error)


def update_member(  # noqa: C901
    group_id: str, add: set[str] | None = None, remove: set[str] | None = None
) -> GroupDetail:
    """Update group members by group_id in mAP Core API .

    Args:
        group_id (str): ID of the Group resource.
        add (list[str]): List of user IDs to add .
        remove (list[str]): List of user IDs to remove.

    Returns:
        GroupDetail: updated group detail

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        ResourceNotFound: If the Group resource is not found.
        RequestConflict: If the User id exists in both "add" and "remove".
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if config.MAP_CORE.update_strategy == "put":
        return update_member_put(group_id, add, remove)

    add = add or set()
    remove = remove or set()

    if add & remove:
        error = E.CONFLICT_MEMBER_OPERATION % {
            "id": group_id,
            "uids": ", ".join(add & remove),
        }
        raise RequestConflict(error)

    current = get_by_id(group_id, raw=True)
    if current is None:
        error = E.GROUP_NOT_FOUND % {"id": group_id}
        raise ResourceNotFound(error)

    logging_params = {
        "id": group_id,
        "add": ", ".join(add) or "N/A",
        "remove": ", ".join(remove) or "N/A",
    }
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()

        user_list: set[str] = {
            u.value for u in (current.members or []) if u.type == "User"
        }
        system_admins = users.get_system_admins()
        operations = build_update_member_operations(
            add=add, remove=remove, user_list=user_list, system_admins=system_admins
        )

        result: MapGroup | MapError = groups.patch_by_id(
            group_id,
            operations,
            include=({"members"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.GROUP_NOT_FOUND % {"id": group_id}
            raise ResourceNotFound(error)
        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_UPDATE_GROUP % {"id": group_id}
            raise OAuthTokenError(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(I.SUCCESS_UPDATE_GROUP_MEMBERS, logging_params)
    return GroupDetail.from_map_group(result)


def update_member_put(  # noqa: C901
    group_id: str, add: set[str] | None = None, remove: set[str] | None = None
) -> GroupDetail:
    """Update group members by group_id in mAP Core API (replace with PUT).

    Args:
        group_id (str): ID of the Group resource.
        add (list[str]): List of user IDs to add .
        remove (list[str]): List of user IDs to remove.

    Returns:
        GroupDetail: updated group detail

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        ResourceNotFound: If the Group resource is not found.
        RequestConflict: If the User id exists in both "add" and "remove".
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if config.MAP_CORE.update_strategy == "patch":
        return update_member(group_id, add, remove)

    add = add or set()
    remove = remove or set()

    if add & remove:
        error = E.CONFLICT_MEMBER_OPERATION % {
            "id": group_id,
            "uids": ", ".join(add & remove),
        }
        raise RequestConflict(error)

    current = get_by_id(group_id, raw=True)
    if current is None:
        error = E.GROUP_NOT_FOUND % {"id": group_id}
        raise ResourceNotFound(error)

    existing = {m.value for m in current.members or [] if m.type == "User"}
    current.members = [
        m for m in (current.members or []) if m.type == "Group" or m.value not in remove
    ]
    current.members.extend(
        MemberUser(type="User", value=uid) for uid in add if uid not in existing
    )

    logging_params = {
        "id": group_id,
        "add": ", ".join(add) or "N/A",
        "remove": ", ".join(remove) or "N/A",
    }
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()

        result: MapGroup | MapError = groups.put_by_id(
            current,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.GROUP_NOT_FOUND % {"id": group_id}
            raise ResourceNotFound(error)
        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_UPDATE_GROUP % {"id": group_id}
            raise OAuthTokenError(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(I.SUCCESS_UPDATE_GROUP_MEMBERS, logging_params)
    return GroupDetail.from_map_group(result)
