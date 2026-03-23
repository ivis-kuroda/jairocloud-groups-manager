#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for Group resources of mAP Core API."""

import typing as t

from http import HTTPStatus

import requests

from flask_login import current_user
from pydantic import TypeAdapter

from server.auth import is_user_logged_in
from server.config import config
from server.const import MAP_GROUPS_ENDPOINT
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup
from server.entities.patch_request import PatchOperation, PatchRequestPayload
from server.entities.search_request import SearchRequestParameter, SearchResponse
from server.signals import group_created, group_deleted, group_updated

from .decoraters import cache_resource
from .utils import compute_signature, get_time_stamp


type GetMapGroupResponse = MapGroup | MapError
"""Type alias for response of getting a MapGroup."""
adapter: TypeAdapter[GetMapGroupResponse] = TypeAdapter(GetMapGroupResponse)


type GroupsSearchResponse = SearchResponse[MapGroup] | MapError
"""Type alias for search response containing MapGroup resources."""
adapter_search: TypeAdapter[GroupsSearchResponse] = TypeAdapter(GroupsSearchResponse)


def _search_cache_identifier(*args, **kwargs) -> str:  # noqa: ANN002, ANN003, ARG001
    if not is_user_logged_in(current_user):
        return "by_anonymous"
    if current_user.is_system_admin:
        return "by_system_admin"
    permitted = sorted(current_user.permitted_repositories)
    return ",".join(permitted)


@cache_resource(identifier_generator=_search_cache_identifier)
def search(
    query: SearchRequestParameter,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GroupsSearchResponse:
    """Search for Group resources in mAP API.

    Args:
        query (SearchRequestParameter): The search query parameters.
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Basic Authentication.

    Returns:
        GroupsSearchResponse: The search response containing Group resources.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    attributes_params: dict[str, str] = {}
    if include:
        attributes_params[alias_generator("attributes")] = ",".join([
            alias_generator(name) for name in include | {"id"}
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

    query_params = query.model_dump(
        mode="json",
        by_alias=True,
    )

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}",
        params=auth_params | attributes_params | query_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter_search.validate_json(response.text, extra="ignore")


@cache_resource
def get_by_id(
    group_id: str,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapGroupResponse:
    """Get a Group resource by its ID from mAP API.

    Args:
        group_id (str): ID of the Group resource.
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        GetMapGroupResponse: The Group resource if found, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    attributes_params: dict[str, str] = {}
    if include:
        attributes_params[alias_generator("attributes")] = ",".join([
            alias_generator(name) for name in include | {"id"}
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}",
        params=auth_params | attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text)


def post(
    group: MapGroup,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapGroupResponse:
    """Create a Group resource in mAP API.

    Args:
        group (MapGroup): The Group resource to create.
        include (set[str] | None):
            Attribute names to include in creation. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from creation. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        GetMapGroupResponse:
            The created Group resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = group.model_dump(
        mode="json",
        exclude=set(exclude or ()),
        by_alias=True,
        exclude_unset=True,
    )

    attributes_params: dict[str, str] = {}
    if include:
        attributes_params[alias_generator("attributes")] = ",".join([
            alias_generator(name) for name in include
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}",
        params=attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text)


def put_by_id(
    group: MapGroup,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapGroupResponse:
    """Update a Group resource by its ID in mAP API.

    Args:
        group (MapGroup): The Group resource to update.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        GetMapGroupResponse:
            The updated Group resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = group.model_dump(
        mode="json",
        exclude=set(exclude or ()),
        by_alias=True,
        exclude_unset=True,
    )

    attributes_params: dict[str, str] = {}
    if include:
        attributes_params[alias_generator("attributes")] = ",".join([
            alias_generator(name) for name in include
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

    response = requests.put(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group.id}",
        params=attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    resource = adapter.validate_json(response.text)

    if isinstance(resource, MapGroup):
        group_updated.send(None, group=resource)

    return resource


def patch_by_id(
    group_id: str,
    operations: list[PatchOperation[MapGroup]],
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapGroupResponse:
    """Patch a Group resource by its ID in mAP API.

    Args:
        group_id (str): ID of the Group resource.
        operations (list[PatchOperation]): List of patch operations to apply.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Basic Authentication.

    Returns:
        GetMapGroupResponse:
            The updated Group resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = PatchRequestPayload(operations=operations).model_dump(
        mode="json",
        by_alias=True,
        exclude_unset=False,
    )

    attributes_params: dict[str, str] = {}
    if include:
        attributes_params[alias_generator("attributes")] = ",".join([
            alias_generator(name) for name in include
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

    response = requests.patch(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}",
        params=attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    resource = adapter.validate_json(response.text)

    if isinstance(resource, MapGroup):
        group_updated.send(None, group=resource)

    return resource


def delete_by_id(
    group_id: str,
    *,
    access_token: str,
    client_secret: str,
) -> MapError | None:
    """Delete a Group resource by its ID in mAP API.

    Args:
        group_id (str): ID of the Group resource.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Basic Authentication.

    Returns:
        MapError:
            The None if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    response = requests.delete(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}",
        params=auth_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    if not response.text:
        group_updated.send(None, group=MapGroup(id=group_id))
        return None

    return MapError.model_validate_json(response.text)


def _get_alias_generator() -> t.Callable[[str], str]:
    generator = MapGroup.model_config.get("alias_generator")
    if generator and not callable(generator):
        generator = generator.serialization_alias
    if generator is None:
        generator = lambda x: x  # noqa: E731

    return generator


alias_generator: t.Callable[[str], str] = _get_alias_generator()
del _get_alias_generator


@group_updated.connect
@group_deleted.connect
def handle_group_updated(
    _sender: object,
    group: MapGroup | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle group_updated signal to clear cache of the updated group.

    Args:
        group (MapGroup): The updated Group resource.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if group:
        get_by_id.clear_cache(group.id)  # pyright: ignore[reportFunctionMemberAccess]


@group_updated.connect
@group_deleted.connect
def handle_group_updated_by_id(
    _sender: object,
    group_id: str | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle group_updated signal to clear cache of the updated group by ID.

    Args:
        sender: The sender of the signal.
        group_id (str): ID of the updated Group resource.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if group_id:
        get_by_id.clear_cache(group_id)  # pyright: ignore[reportFunctionMemberAccess]


@group_updated.connect
@group_deleted.connect
def handle_group_updated_by_ids(
    _sender: object,
    group_ids: list[str] | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle group_updated signal to clear cache of the updated groups by IDs.

    Args:
        sender: The sender of the signal.
        group_ids (list): IDs of the updated Group resources.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if group_ids:
        get_by_id.clear_cache(*group_ids)  # pyright: ignore[reportFunctionMemberAccess]


@group_created.connect
@group_updated.connect
@group_deleted.connect
def handle_reset_search_cache(
    _sender: object,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle users signals to clear cache of the search results.

    Args:
        sender: The sender of the signal.
        **kwargs: Other keyword arguments passed with the signal.
    """
    search.clear_cache(_search_cache_identifier())  # pyright: ignore[reportFunctionMemberAccess]
