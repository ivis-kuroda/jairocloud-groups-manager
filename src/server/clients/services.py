#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for Service resources of mAP Core API."""

import typing as t

from functools import cache
from http import HTTPStatus

import requests

from pydantic import TypeAdapter
from pydantic.alias_generators import to_camel

from server.config import config
from server.const import MAP_SERVICES_ENDPOINT
from server.entities.map_error import MapError
from server.entities.map_service import MapService
from server.entities.patch_request import PatchOperation, PatchRequestPayload
from server.entities.search_request import SearchRequestParameter, SearchResponse
from server.signals import repository_created, repository_deleted, repository_updated

from .decorators import cache_resource, default_id_generator
from .utils import compute_signature, get_time_stamp


type GetMapServiceResponse = MapService | MapError
"""Type alias for response of getting a MapService."""
adapter: TypeAdapter[GetMapServiceResponse] = TypeAdapter(GetMapServiceResponse)


type ServicesSearchResponse = SearchResponse[MapService] | MapError
"""Type alias for search response containing MapService resources."""
adapter_search: TypeAdapter[ServicesSearchResponse] = TypeAdapter(
    ServicesSearchResponse
)


@cache_resource(id_generator=default_id_generator)
def search(
    query: SearchRequestParameter,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> ServicesSearchResponse:
    """Search for Service resources in mAP API.

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
            The search response containing Service resources. If the search fails,
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
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}",
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
    service_id: str,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapServiceResponse:
    """Get a Service resource by its ID from mAP API.

    Args:
        service_id (str): ID of the Service resource.
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapService | MapError: The Service resource if found, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",
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
    service: MapService,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapServiceResponse:
    """Create a Service resource in mAP API.

    Args:
        service (MapService): The Service resource to create.
        include (set[str] | None):
            Attribute names to include in creation. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from creation. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapService | MapError:
            The created Service resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = service.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=exclude,
        by_alias=True,
        exclude_unset=True,
    )

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}",
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
    service: MapService,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapServiceResponse:
    """Update a Service resource by its ID in mAP API.

    Args:
        service (MapService): The Service resource to update.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapService | MapError:
            The updated Service resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = service.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=exclude,
        by_alias=True,
        exclude_unset=True,
    )

    response = requests.put(
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service.id}",
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


def patch_by_id(
    service_id: str,
    operations: t.Sequence[PatchOperation[MapService]],
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapServiceResponse:
    """Patch a Service resource by its ID in mAP API.

    Args:
        service_id (str): ID of the Service resource to update.
        operations (Sequence[PatchOperation]): List of patch operations to apply.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapService | MapError:
            The patched Service resource if successful, otherwise Error response.
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
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",
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


def delete_by_id(
    service_id: str,
    *,
    access_token: str,
    client_secret: str,
) -> MapError | None:
    """Delete a Service resource by its ID in mAP API.

    Args:
        service_id (str): ID of the Service resource to delete.
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
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",
        params=auth_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    if not response.text:
        return None

    return MapError.model_validate_json(response.text, extra="ignore")


@cache
def _a(o: str) -> str:
    ag = MapService.model_config.get("alias_generator")
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


@repository_updated.connect
@repository_deleted.connect
def handle_repository_updated_by_id(
    _sender: object = None,
    *_args,  # ruff:ignore[missing-type-args]
    service_id: str | None = None,
    **_kwargs,  # ruff:ignore[missing-type-kwargs]
) -> None:
    """Handle repository updated signal to clear cache of the updated service by ID.

    Args:
        sender: The sender of the signal.
        service_id (str): The ID of the updated Service resource.
    """
    if not service_id:
        return

    get_by_id.clear_cache(service_id)


@repository_created.connect
@repository_updated.connect
@repository_deleted.connect
def handle_reset_search_cache(
    _sender: object = None,
    *_args,  # ruff:ignore[missing-type-args]
    **_kwargs,  # ruff:ignore[missing-type-kwargs]
) -> None:
    """Handle services signals to clear cache of the search results.

    Args:
        sender: The sender of the signal.
    """
    search.clear_cache(default_id_generator())
