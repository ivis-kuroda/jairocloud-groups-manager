#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for User resources of mAP Core API."""

import typing as t

from functools import cache
from http import HTTPStatus

import requests

from pydantic import TypeAdapter
from pydantic.alias_generators import to_camel

from server.config import config
from server.const import MAP_EXIST_EPPN_ENDPOINT, MAP_SELF_ENDPOINT, MAP_USERS_ENDPOINT
from server.entities.map_error import MapError
from server.entities.map_user import MapUser
from server.entities.patch_request import PatchOperation, PatchRequestPayload
from server.entities.search_request import SearchRequestParameter, SearchResponse
from server.signals import user_created, user_deleted, user_updated

from .decorators import cache_resource, default_id_generator
from .utils import compute_signature, get_time_stamp


type GetMapUserResponse = MapUser | MapError
"""Type alias for response of getting a MapUser."""
adapter: TypeAdapter[GetMapUserResponse] = TypeAdapter(GetMapUserResponse)


type UsersSearchResponse = SearchResponse[MapUser] | MapError
"""Type alias for search response containing MapUser resources."""
adapter_search: TypeAdapter[UsersSearchResponse] = TypeAdapter(UsersSearchResponse)


@cache_resource(id_generator=default_id_generator)
def search(
    query: SearchRequestParameter,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> UsersSearchResponse:
    """Search for User resources in mAP API.

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
            The search response containing User resources. If the search fails,
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
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}",
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
    user_id: str,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapUserResponse:
    """Get a User resource by its ID from mAP API.

    Args:
        user_id (str): ID of the User resource.
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapUser | MapError: The User resource if found, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}",
        params=auth_params | attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text, extra="ignore")


@cache_resource
def get_by_eppn(
    eppn: str,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapUserResponse:
    """Get a User resource by its ePPN from mAP API.

    Args:
        eppn (str): ePPN of the User resource.
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapUser | MapError: The User resource if found, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_EXIST_EPPN_ENDPOINT}/{eppn}",
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
    user: MapUser,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapUserResponse:
    """Create a User resource in mAP API.

    Args:
        user (MapUser): The User resource to create.
        include (set[str] | None):
            Attribute names to include in creation. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from creation. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapUser | MapError:
            The created User resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = user.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=_build_user_dump_exclude(exclude),
        by_alias=True,
        exclude_unset=True,
    )

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}",
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
    user: MapUser,
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapUserResponse:
    """Update a User resource by its ID in mAP API.

    Args:
        user (MapUser): The User resource to update.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapUser | MapError:
            The updated User resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    payload = user.model_dump(
        mode="json",
        include=include | {"id"} if include else None,
        exclude=_build_user_dump_exclude(exclude),
        by_alias=True,
        exclude_unset=True,
    )

    response = requests.put(
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user.id}",
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

    if isinstance(resource, MapUser):
        user_updated.send(put_by_id, user=resource)

    return resource


def patch_by_id(
    user_id: str,
    operations: t.Sequence[PatchOperation[MapUser]],
    /,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapUserResponse:
    """Patch a User resource by its ID in mAP API.

    Args:
        user_id (str): ID of the User resource.
        operations (Sequence[PatchOperation]): List of patch operations to apply.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapUser | MapError:
            The updated User resource if successful, otherwise Error response.
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
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}",
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

    if isinstance(resource, MapUser):
        user_updated.send(patch_by_id, user=resource)

    return resource


def get_self(
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    *,
    access_token: str,
    client_secret: str,
) -> GetMapUserResponse:
    """Get a User resource of the access token owner from mAP API.

    Args:
        include (set[str] | None):
            Attribute names to include in the response. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from the response. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Authentication.

    Returns:
        MapUser | MapError: The User resource if found, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    attributes_params = _build_attribute_params(include, exclude)

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_SELF_ENDPOINT}",
        params=auth_params | attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text, extra="ignore")


@cache
def _a(o: str) -> str:
    ag = MapUser.model_config.get("alias_generator")
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


def _build_user_dump_exclude(exclude: set[str] | None) -> dict[str, t.Any]:
    dump_exclude: dict[str, t.Any] = dict.fromkeys(exclude or set(), True)

    if "edu_person_principal_names" not in dump_exclude:
        dump_exclude["edu_person_principal_names"] = {
            # Only include the ePPN values in the dump.
            "__all__": {"idp_entity_id"},
        }

    return dump_exclude


@user_updated.connect
@user_deleted.connect
def handle_user_updated_by_eppn(
    _sender: object = None,
    *_args,  # ruff: ignore[missing-type-args]
    eppns: list[str] | None = None,
    **_kwargs,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Handle user_updated signal to clear cache of the updated user by ePPN.

    Args:
        sender: The sender of the signal.
        eppns (list): The ePPNs of the updated User resources.
    """
    if not eppns:
        return

    get_by_eppn.clear_cache(*eppns)


@user_updated.connect
@user_deleted.connect
def handle_user_updated_by_id(
    _sender: object = None,
    *_args,  # ruff: ignore[missing-type-args]
    user_id: str | None = None,
    **_kwargs,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Handle user_updated signal to clear cache of the updated user by ID.

    Args:
        sender: The sender of the signal.
        user_id (str): The ID of the updated User resource.
    """
    if not user_id:
        return

    get_by_id.clear_cache(user_id)


@user_created.connect
@user_updated.connect
@user_deleted.connect
def handle_reset_search_cache(
    _sender: object = None,
    *_args,  # ruff: ignore[missing-type-args]
    **_kwargs,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Handle users signals to clear cache of the search results.

    Args:
        sender: The sender of the signal.
    """
    search.clear_cache(default_id_generator())
