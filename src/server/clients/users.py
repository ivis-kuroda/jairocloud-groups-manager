#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for User resources of mAP Core API."""

import typing as t

from http import HTTPStatus

import requests

from flask_login import current_user
from pydantic import TypeAdapter

from server.auth import is_user_logged_in
from server.config import config
from server.const import MAP_EXIST_EPPN_ENDPOINT, MAP_SELF_ENDPOINT, MAP_USERS_ENDPOINT
from server.entities.map_error import MapError
from server.entities.map_user import MapUser
from server.entities.patch_request import PatchOperation, PatchRequestPayload
from server.entities.search_request import SearchRequestParameter, SearchResponse
from server.signals import user_created, user_deleted, user_updated

from .decoraters import cache_resource
from .utils import compute_signature, get_time_stamp


type GetMapUserResponse = MapUser | MapError
"""Type alias for Get MapUser response."""
adapter: TypeAdapter[GetMapUserResponse] = TypeAdapter(GetMapUserResponse)


type UsersSearchResponse = SearchResponse[MapUser] | MapError
"""Type alias for search response containing MapUser resources."""
adapter_search: TypeAdapter[UsersSearchResponse] = TypeAdapter(UsersSearchResponse)


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
) -> UsersSearchResponse:
    """Search for User resources in mAP API.

    Args:
        query (SearchRequestParameter): The search filter criteria.
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
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}",
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
        GetMapUserResponse: The User resource if found, otherwise Error response.
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
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}",
        params=auth_params | attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text)


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
        GetMapUserResponse: The User resource if found, otherwise Error response.
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
        f"{config.MAP_CORE.base_url}{MAP_EXIST_EPPN_ENDPOINT}/{eppn}",
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
        GetMapUserResponse:
            The created User resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = user.model_dump(
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

    return adapter.validate_json(response.text)


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
        GetMapUserResponse:
            The updated User resource if successful, otherwise Error response.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = user.model_dump(
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
        f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user.id}",
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

    if isinstance(resource, MapUser):
        user_updated.send(None, user=resource)

    return resource


def patch_by_id(
    user_id: str,
    operations: list[PatchOperation[MapUser]],
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
        operations (list[PatchOperation]): List of patch operations to apply.
        include (set[str] | None):
            Attribute names to include in update. Optional.
        exclude (set[str] | None):
            Attribute names to exclude from update. Optional.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Basic Authentication.

    Returns:
        GetMapUserResponse:
            The updated User resource if successful, otherwise Error response.
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

    resource = adapter.validate_json(response.text)

    if isinstance(resource, MapUser):
        user_updated.send(None, user=resource)

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
        GetMapUserResponse: The User resource if found, otherwise Error response.
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
        f"{config.MAP_CORE.base_url}{MAP_SELF_ENDPOINT}",
        params=auth_params | attributes_params,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text)


def _get_alias_generator() -> t.Callable[[str], str]:
    generator = MapUser.model_config.get("alias_generator")
    if generator and not callable(generator):
        generator = generator.serialization_alias
    if generator is None:
        generator = lambda x: x  # noqa: E731

    return generator


alias_generator: t.Callable[[str], str] = _get_alias_generator()
del _get_alias_generator


@user_updated.connect
@user_deleted.connect
def handle_user_updated(_sender: object, user: MapUser | None = None, **kwargs) -> None:  # noqa: ANN003, ARG001
    """Handle user_updated signal to clear cache of the updated user.

    Args:
        sender: The sender of the signal.
        user (MapUser): The updated User resource.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if not isinstance(user, MapUser):
        return
    get_by_id.clear_cache(user.id)  # pyright: ignore[reportFunctionMemberAccess]
    get_by_eppn.clear_cache(  # pyright: ignore[reportFunctionMemberAccess]
        *[eppn.value for eppn in user.edu_person_principal_names or []]
    )


@user_updated.connect
@user_deleted.connect
def handle_user_updated_by_eppn(
    _sender: object,
    eppns: list[str] | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle user_updated signal to clear cache of the updated user by ePPN.

    Args:
        sender: The sender of the signal.
        eppns (list): The ePPNs of the updated User resources.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if eppns:
        get_by_eppn.clear_cache(*eppns)  # pyright: ignore[reportFunctionMemberAccess]


@user_updated.connect
@user_deleted.connect
def handle_user_updated_by_id(
    _sender: object,
    user_id: str | None = None,
    **kwargs,  # noqa: ANN003, ARG001
) -> None:
    """Handle user_updated signal to clear cache of the updated user by ID.

    Args:
        sender: The sender of the signal.
        user_id (str): The ID of the updated User resource.
        **kwargs: Other keyword arguments passed with the signal.
    """
    if user_id:
        get_by_id.clear_cache(user_id)  # pyright: ignore[reportFunctionMemberAccess]


@user_created.connect
@user_updated.connect
@user_deleted.connect
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
