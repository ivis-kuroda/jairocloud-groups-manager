#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for Service resources of mAP Core API."""

import typing as t

from http import HTTPStatus

import requests

from flask import current_app
from flask_login import current_user
from pydantic import TypeAdapter

from server.auth import is_user_logged_in
from server.config import config
from server.const import MAP_SERVICES_ENDPOINT
from server.entities.map_error import MapError
from server.entities.map_service import MapService
from server.entities.patch_request import PatchOperation, PatchRequestPayload
from server.entities.search_request import SearchRequestParameter, SearchResponse
from server.signals import repository_created, repository_deleted, repository_updated

from .decoraters import cache_resource
from .utils import compute_signature, get_time_stamp


type GetMapServiceResponse = MapService | MapError
"""Type alias for response of getting a MapService."""
adapter: TypeAdapter[GetMapServiceResponse] = TypeAdapter(GetMapServiceResponse)


type ServicesSearchResponse = SearchResponse[MapService] | MapError
"""Type alias for search response containing MapService resources."""
adapter_search: TypeAdapter[ServicesSearchResponse] = TypeAdapter(
    ServicesSearchResponse
)


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
) -> ServicesSearchResponse:
    """Search for Service resources in mAP API.

    Args:
        query (SearchRequestPayload): The search filter criteria.
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        list[GetMapUserResponse]: List of User resources matching the search criteria.
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
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}",
        params=auth_params | attributes_params | query_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter_search.validate_json(response.text)


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
        GetMapServiceResponse: The Service resource if found, otherwise Error response.
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
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",
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
        service (MapService): Service resource to create.
        include (set[str] | None):
            Attribute names to include in creation. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from creation. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        GetMapServiceResponse:
            The created Service resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = service.model_dump(
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

    return adapter.validate_json(response.text)


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
        service (MapService): Service resource to update.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        GetMapServiceResponse:
            The updated Service resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = service.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=exclude,
        by_alias=True,
        exclude_unset=True,
    )

    attributes_params: dict[str, str] = {}
    if include:
        attributes_params[alias_generator("attributes")] = ",".join([
            alias_generator(name) for name in include | {"id"}
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

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

    resource = adapter.validate_json(response.text)

    if isinstance(resource, MapService):
        repository_updated.send(None, service=resource)

    return resource


def patch_by_id(
    service_id: str,
    operations: list[PatchOperation[MapService]],
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapServiceResponse:
    """Patch a Service resource by its ID in mAP API.

    Args:
        service_id (str): ID of the Service resource to patch.
        operations (list[PatchOperation]): List of patch operations to apply.
        include (set[str] | None):
            Attribute names to include in patch. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from patch. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        GetMapServiceResponse:
            The patched Service resource if successful, otherwise Error response.
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
            alias_generator(name) for name in include | {"id"}
        ])
    if exclude:
        attributes_params[alias_generator("excluded_attributes")] = ",".join([
            alias_generator(name) for name in exclude
        ])

    response = requests.patch(
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",
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

    if isinstance(resource, MapService):
        repository_updated.send(None, service=resource)

    return resource


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
        f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",
        params=auth_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    current_app.logger.info(
        "status_code: %s, response: %s",
        response.status_code,
        response.text,
    )

    if response.ok:
        repository_deleted.send(None, service_id=service_id)
        return None

    response.raise_for_status()

    if not response.text:
        repository_updated.send(None, service=MapService(id=service_id))
        return None

    return MapError.model_validate_json(response.text)


def _get_alias_generator() -> t.Callable[[str], str]:
    generator = MapService.model_config.get("alias_generator")
    if generator and not callable(generator):
        generator = generator.serialization_alias
    if generator is None:
        generator = lambda x: x  # noqa: E731

    return generator


alias_generator: t.Callable[[str], str] = _get_alias_generator()
del _get_alias_generator


@repository_updated.connect
@repository_deleted.connect
def handle_repository_updated(
    _sender: object,
    service: MapService | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle repository updated signal to clear cache for the updated service.

    Args:
        sender: The sender of the signal.
        service (MapService): The updated Service resource.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if service and service.id:
        get_by_id.clear_cache(service.id)  # pyright: ignore[reportFunctionMemberAccess]


@repository_updated.connect
@repository_deleted.connect
def handle_repository_updated_by_id(
    _sender: object,
    service_id: str | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle repository updated signal to clear cache for the updated service by ID.

    Args:
        sender: The sender of the signal.
        service_id (str): The ID of the updated Service resource.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if service_id:
        get_by_id.clear_cache(service_id)  # pyright: ignore[reportFunctionMemberAccess]


@repository_created.connect
@repository_updated.connect
@repository_deleted.connect
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
