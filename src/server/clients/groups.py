#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for Group resources of mAP Core API."""

import typing as t

from functools import cache
from http import HTTPStatus

import requests

from pydantic import TypeAdapter
from pydantic.alias_generators import to_camel

from server.config import config
from server.const import MAP_GROUPS_ENDPOINT
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup
from server.entities.patch_request import PatchOperation, PatchRequestPayload
from server.entities.search_request import SearchRequestParameter, SearchResponse
from server.signals import group_created, group_deleted, group_updated

from .decorators import cache_resource, default_id_generator
from .utils import compute_signature, get_time_stamp


type GetMapGroupResponse = MapGroup | MapError
"""Type alias for response of getting a MapGroup."""
adapter: TypeAdapter[GetMapGroupResponse] = TypeAdapter(GetMapGroupResponse)


type GroupsSearchResponse = SearchResponse[MapGroup] | MapError
"""Type alias for search response containing MapGroup resources."""
adapter_search: TypeAdapter[GroupsSearchResponse] = TypeAdapter(GroupsSearchResponse)


@cache_resource(id_generator=default_id_generator)
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
        client_secret (str): Client secret for Authentication.

    Returns:
        SearchResponse | MapError:
            The search response containing Group resources. If the search fails,
            returns an Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)
    query_params = query.model_dump(mode="json", by_alias=True)

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
        MapGroup | MapError: The Group resource if found, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

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

    return adapter.validate_json(response.text, extra="ignore")


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
        MapGroup | MapError:
            The created Group resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = group.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=exclude,
        by_alias=True,
        exclude_unset=True,
    )

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}",
        params=attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    status_code = response.status_code
    if status_code not in {HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT}:
        response.raise_for_status()

    return adapter.validate_json(response.text, extra="ignore")


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
        MapGroup | MapError:
            The updated Group resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = group.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=exclude,
        by_alias=True,
        exclude_unset=True,
    )

    response = requests.put(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group.id}",
        params=attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    status_code = response.status_code
    if status_code not in {HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT}:
        response.raise_for_status()

    resource = adapter.validate_json(response.text, extra="ignore")

    if isinstance(resource, MapGroup):
        group_updated.send(put_by_id, group=resource)

    return resource


def patch_by_id(
    group_id: str,
    operations: t.Sequence[PatchOperation[MapGroup]],
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapGroupResponse:
    """Patch a Group resource by its ID in mAP API.

    Args:
        group_id (str): ID of the Group resource to update.
        operations (Sequence[PatchOperation]): List of patch operations to apply.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapGroup | MapError:
            The updated Group resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = PatchRequestPayload(operations=operations).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    response = requests.patch(
        f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}",
        params=attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    status_code = response.status_code
    if status_code not in {HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT}:
        response.raise_for_status()

    resource = adapter.validate_json(response.text, extra="ignore")

    if isinstance(resource, MapGroup):
        group_updated.send(patch_by_id, group=resource)

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
        client_secret (str): Client secret for Authentication.

    Returns:
        MapError | None:
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
        group_deleted.send(delete_by_id, group_id=group_id)
        return None

    return MapError.model_validate_json(response.text, extra="ignore")


@cache
def _a(o: str) -> str:
    ag = MapGroup.model_config.get("alias_generator")
    fnc = ag if callable(ag) else ag.serialization_alias if ag else None
    return fnc(o) if fnc else o


def _build_attribute_params(
    include: set[str] | None, exclude: set[str] | None
) -> dict[str, str]:
    attributes_params = {}
    if include:
        attributes_params[to_camel("attributes")] = ",".join([
            _a(name) for name in include | {"id"}
        ])
    if exclude:
        attributes_params[to_camel("excluded_attributes")] = ",".join([
            _a(name) for name in exclude
        ])
    return attributes_params


@group_updated.connect
@group_deleted.connect
def handle_group_updated_by_id(
    _sender: object = None,
    *_args,  # ruff: ignore[missing-type-args]
    group_id: str | None = None,
    **_kwargs,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Handle group_updated signal to clear cache of the updated group by ID.

    Args:
        sender: The sender of the signal.
        group_id (str): ID of the updated Group resource.
    """
    if not group_id:
        return

    get_by_id.clear_cache(group_id)


@group_updated.connect
@group_deleted.connect
def handle_group_updated_by_ids(
    _sender: object = None,
    *_args,  # ruff: ignore[missing-type-args]
    group_ids: list[str] | None = None,
    **_kwargs,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Handle group updated signal to clear cache of the updated groups by IDs.

    Args:
        sender: The sender of the signal.
        group_ids (list): IDs of the updated Group resources.
    """
    if not group_ids:
        return

    get_by_id.clear_cache(*group_ids)


@group_created.connect
@group_updated.connect
@group_deleted.connect
def handle_reset_search_cache(
    _sender: object = None,
    *_args,  # ruff: ignore[missing-type-args]
    **_kwargs,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Handle groups signals to clear cache of the search results.

    Args:
        sender: The sender of the signal.
    """
    search.clear_cache(default_id_generator())
