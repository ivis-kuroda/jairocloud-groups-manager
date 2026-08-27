#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing groups."""

import re
import typing as t

from contextlib import suppress
from http import HTTPStatus

import requests

from flask import current_app
from pydantic_core import ValidationError

from server.clients import bulks, groups
from server.const import (
    MAP_DUPLICATE_ID_PATTERN,
    MAP_NO_RIGHTS_UPDATE_PATTERN,
    MAP_NOT_FOUND_PATTERN,
)
from server.entities.bulk_request import BulkOperation
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup, Member, MemberUser
from server.entities.search_request import SearchResponse, SearchResult
from server.entities.summaries import GroupSummary
from server.exc import (
    CredentialsError,
    InvalidFormError,
    InvalidQueryError,
    JAIROCloudGroupsManagerError,
    OAuthTokenError,
    RequestConflict,
    ResourceInvalid,
    ResourceNotFound,
    SystemAdminNotFound,
    UnexpectedResponseError,
)
from server.messages import E, I, W
from server.services.utils import (
    GroupsCriteria,
    build_patch_operations,
    build_search_query,
    build_update_member_operations,
    detect_affiliated_repository,
    make_group_detail,
    make_group_summary,
    make_map_group,
    prepare_group,
    prepare_role_groups,
    validate_group_to_map_group,
)
from server.signals import group_created, group_updated

from .token import get_access_token, get_client_secret


if t.TYPE_CHECKING:
    from server.clients.groups import GroupsSearchResponse
    from server.entities.group_detail import GroupDetail, Repository


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
        Search results. The type depends on the `raw` argument.
        - SearchResult[GroupSummary]:
            Search result containing Group summaries. It has members `total`,
            `page_size`, `offset`, and `resources`.
        - SearchResponse[MapGroup]:
            Raw search response from mAP Core API. It has members `schemas`,
            `total_results`, `start_index`, `items_per_page`, and `resources`.

    Raises:
        InvalidQueryError: If the query construction is invalid.
        OAuthTokenError: If the access token is invalid or expired.
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
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        results: GroupsSearchResponse = groups.search(
            query,
            include=default_include,
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(results, MapError):
        current_app.logger.error(E.FAILED_SEARCH_GROUPS, {"filter": query.filter})
        current_app.logger.error(
            E.RECEIVE_RESPONSE_MESSAGE, {"message": results.detail}
        )
        raise InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)

    if raw:
        return results

    group_summaries = [
        make_group_summary(group, t.cast("str", repository.display))
        for group in results.resources
        if (repository := detect_affiliated_repository(group.services or []))
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
        The Group resource if found, otherwise None. The type depends
            on the `raw` argument.
        - GroupDetail: The Group detail object.
        - MapGroup: The raw Group object from mAP Core API.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result: MapGroup | MapError = groups.get_by_id(
            group_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_GROUP, {"id": group_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        return None

    if raw:
        return result

    return make_group_detail(result, more_detail=more_detail)


def create(group: GroupDetail, system_admins: set[str]) -> GroupDetail:
    """Create group to mAP Core API.

    Args:
        group (GroupDetail):
            Detail information about the group created from the input data.
        system_admins (set[str]): Set of user IDs who are system administrators.

    Returns:
        GroupDetail: The created Group detail object.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        ResourceInvalid: If the Group resource data is invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    map_group = prepare_group(group, administrators=system_admins)
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result: MapGroup | MapError = groups.post(
            map_group,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_CREATE_GROUP, {"id": group.id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_DUPLICATE_ID_PATTERN, result.detail):
            raise ResourceInvalid(E.GROUP_DUPLICATE_ID % {"id": m.group(1)})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(
        I.SUCCESS_CREATE_GROUP,
        {"id": group.id, "rid": t.cast("Repository", group.repository).id},
    )

    with suppress(JAIROCloudGroupsManagerError):
        group_created.send(create, group_id=result.id)

    return make_group_detail(result)


def create_role_groups(
    repository_id: str, service_name: str, system_admins: set[str]
) -> None:
    """Create role groups for a Repository resource.

    Args:
        repository_id (str): ID of the Repository resource.
        service_name (str): Service name of the Repository resource.
        system_admins (set[str]): Set of user IDs who are system administrators.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If the access token is invalid or expired.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    role_groups = prepare_role_groups(repository_id, service_name, system_admins)
    access_token, client_secret = get_access_token(), get_client_secret()

    for group in role_groups:
        try:
            groups.post(group, access_token=access_token, client_secret=client_secret)
        except requests.HTTPError as exc:
            code = t.cast("requests.Response", exc.response).status_code
            if code == HTTPStatus.CONFLICT:
                current_app.logger.warning(
                    W.ROLE_GROUP_ALREADY_EXISTS, {"rid": repository_id, "gid": group.id}
                )
                continue  # Skip to the next group if it already exists

            current_app.logger.error(
                E.FAILED_CREATE_ROLEGROUP, {"rid": repository_id, "gid": group.id}
            )

            if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
                raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

            raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

        except requests.RequestException as exc:
            current_app.logger.error(
                E.FAILED_CREATE_ROLEGROUP, {"rid": repository_id, "gid": group.id}
            )
            raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

        except ValidationError as exc:
            current_app.logger.error(
                E.FAILED_CREATE_ROLEGROUP, {"rid": repository_id, "gid": group.id}
            )
            raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

        except CredentialsError, OAuthTokenError:
            raise

        else:
            with suppress(JAIROCloudGroupsManagerError):
                group_created.send(create_role_groups, group_id=group.id)

    current_app.logger.info(I.SUCCESS_CREATE_ROLEGROUPS, {"id": repository_id})


def update(group: GroupDetail) -> GroupDetail:
    """Update group from mAP Core API by group_id.

    Args:
        group (GroupDetail): The Group data to update. The `id` field is required.

    Returns:
        GroupDetail: The updated Group detail object.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        InvalidFormError: If failed to validate group form data for update.
        ResourceNotFound: If the Group resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(group_id := t.cast("str", group.id))) is None:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group_id})
        raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        validated = validate_group_to_map_group(group, mode="update")
        operations = build_patch_operations(
            make_map_group(current),
            validated,
            include={"display_name", "description"},
        )

        result: MapGroup | MapError = groups.patch_by_id(
            group_id,
            operations,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError, InvalidFormError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": m.group(1)})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_GROUP % {"id": group.id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(
        I.SUCCESS_UPDATE_GROUP,
        {"id": group.id, "rid": group.repository.id if group.repository else "N/A"},
    )

    with suppress(JAIROCloudGroupsManagerError):
        group_updated.send(update, group_id=result.id)

    return make_group_detail(result)


def update_put(group: GroupDetail) -> GroupDetail:
    """Update group from mAP Core API by group_id (replace with PUT).

    Args:
        group (GroupDetail): The Group data to update. The `id` field is required.

    Returns:
        GroupDetail: The updated Group detail object.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        InvalidFormError: If failed to validate group form data for update.
        ResourceNotFound: If the Group resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        validated = validate_group_to_map_group(group, mode="update")

        result: MapGroup | MapError = groups.put_by_id(
            validated,
            exclude=({"external_id", "meta"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except InvalidFormError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP, {"id": group.id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": m.group(1)})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_GROUP % {"id": group.id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(
        I.SUCCESS_UPDATE_GROUP,
        {"id": group.id, "rid": group.repository.id if group.repository else "N/A"},
    )

    with suppress(JAIROCloudGroupsManagerError):
        group_updated.send(update_put, group_id=result.id)

    return make_group_detail(result)


def delete_multiple(group_ids: set[str]) -> set[str] | None:
    """Delete groups from mAP Core API by group_ids.

    Args:
        group_ids (set[str]): ID of the Group resource.

    Returns:
        set[str]: group id list of failed.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    operations = [
        BulkOperation(method="DELETE", path=f"/Groups/{group_id}")
        for group_id in group_ids
    ]
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result = bulks.post(operations, access_token, client_secret)
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_DELETE_GROUPS, {"ids": ", ".join(group_ids)})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

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

    with suppress(JAIROCloudGroupsManagerError):
        for group_id in group_ids - failed_list:
            group_updated.send(delete_multiple, group_id=group_id)

    return failed_list or None


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
    failed_list: set[str] = set()
    for group_id in group_ids:
        try:
            delete_by_id(group_id)
        except OAuthTokenError, CredentialsError:
            raise
        except ResourceNotFound, ResourceInvalid, UnexpectedResponseError:
            failed_list.add(group_id)

    return failed_list or None


def delete_by_id(group_id: str) -> GroupDetail:
    """Delete group from mAP Core API by group_id.

    Args:
        group_id (str): ID of the Group resource.

    Returns:
        GroupDetail: The deleted Group.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        ResourceNotFound: If the Group resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(group_id, raw=True)) is None:
        raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result = groups.delete_by_id(
            group_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError:
        raise

    if result:
        current_app.logger.error(E.FAILED_DELETE_GROUP, {"id": group_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE)

    repository_id = "N/A"
    if repository := detect_affiliated_repository(current.services or []):
        repository_id = repository.value

    current_app.logger.info(
        I.SUCCESS_DELETE_GROUP, {"id": group_id, "rid": repository_id}
    )
    return make_group_detail(current)


def update_members(
    group_id: str,
    /,
    add: set[str] | None = None,
    remove: set[str] | None = None,
    *,
    system_admins: set[str],
) -> GroupDetail:
    """Update group members by group ID in mAP Core API .

    Args:
        group_id (str): ID of the Group resource.
        add (set[str]): Set of user IDs to add.
        remove (set[str]): Set of user IDs to remove.
        system_admins (set[str]): Set of user IDs who are system administrators.

    Returns:
        GroupDetail: updated group detail

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        ResourceNotFound: If the Group resource is not found.
        RequestConflict: If the User id exists in both "add" and "remove".
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (add := add or set()) & (remove := remove or set()):
        raise RequestConflict(
            E.CONFLICT_MEMBER_OPERATION
            % {"id": group_id, "uids": ", ".join(add & remove)}
        )

    if (current := get_by_id(group_id, raw=True)) is None:
        raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

    current_users = {u.value for u in (current.members or []) if u.type == "User"}
    operations = build_update_member_operations(
        add, remove, current_users, system_admins
    )

    logging_params = {
        "id": group_id,
        "add": ", ".join(add) or "N/A",
        "remove": ", ".join(remove) or "N/A",
    }
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result: MapGroup | MapError = groups.patch_by_id(
            group_id,
            operations,
            include={"members"},
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_GROUP % {"id": group_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(I.SUCCESS_UPDATE_GROUP_MEMBERS, logging_params)

    with suppress(JAIROCloudGroupsManagerError):
        group_updated.send(update_members, group_id=result.id)

    return make_group_detail(result)


def update_member_put(
    group_id: str,
    /,
    add: set[str] | None = None,
    remove: set[str] | None = None,
    *,
    system_admins: set[str],
) -> GroupDetail:
    """Update group members by group_id in mAP Core API (replace with PUT).

    Args:
        group_id (str): ID of the Group resource.
        add (set[str]): Set of user IDs to add.
        remove (set[str]): Set of user IDs to remove.
        system_admins (set[str]): Set of user IDs who are system administrators.

    Returns:
        GroupDetail: updated group detail

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        ResourceNotFound: If the Group resource is not found.
        RequestConflict: If the User id exists in both "add" and "remove".
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (add := add or set()) & (remove := remove or set()):
        raise RequestConflict(
            E.CONFLICT_MEMBER_OPERATION
            % {"id": group_id, "uids": ", ".join(add & remove)}
        )

    if (current := get_by_id(group_id, raw=True)) is None:
        raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

    current.members = _updated_members(
        add, remove, current.members or [], system_admins
    )

    logging_params = {
        "id": group_id,
        "add": ", ".join(add) or "N/A",
        "remove": ", ".join(remove) or "N/A",
    }
    access_token, client_secret = get_access_token(), get_client_secret()
    try:
        result: MapGroup | MapError = groups.put_by_id(
            current,
            include=({"members"}),
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_GROUP_MEMBERS, logging_params)
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.GROUP_NOT_FOUND % {"id": group_id})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_GROUP % {"id": group_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(I.SUCCESS_UPDATE_GROUP_MEMBERS, logging_params)

    with suppress(JAIROCloudGroupsManagerError):
        group_updated.send(update_members, group_id=result.id)

    return make_group_detail(result)


def _updated_members(
    add: set[str],
    remove: set[str],
    current: list[Member],
    system_admins: set[str],
) -> list[Member]:
    """Calculate the updated members after adding and removing users.

    Args:
        add (set[str]): Set of user IDs to add.
        remove (set[str]): Set of user IDs to remove.
        current (list[Member]): List of current members in the group.
        system_admins (set[str]): Set of user IDs who are system administrators.

    Returns:
        list[Member]: Updated list of members after applying add and remove operations.

    Raises:
        SystemAdminNotFound: If no administrators are provided.
    """
    if not system_admins:
        raise SystemAdminNotFound(E.GROUP_REQUIRES_SYSTEM_ADMIN)

    current_users = {m.value for m in current if m.type == "User"}

    # Avoid adding users already in the group
    users_to_add = add - current_users
    # Avoid removing system admins, removing users not in the group
    users_to_remove = (remove - system_admins) & current_users

    if not (current_users - users_to_remove) | users_to_add:
        # If this would leave the group with no members, add system admins instead.
        # This situation is highly unlikely.
        users_to_add |= system_admins

    return [
        m for m in current if m.type == "Group" or m.value not in users_to_remove
    ] + [MemberUser(type="User", value=uid) for uid in users_to_add]
