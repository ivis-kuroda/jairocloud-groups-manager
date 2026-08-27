#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing users."""

import re
import typing as t

from contextlib import suppress
from http import HTTPStatus

import requests

from flask import current_app
from pydantic_core import ValidationError

from server.clients import users
from server.const import (
    MAP_ALREADY_TIED_PATTERN,
    MAP_DUPLICATE_ID_PATTERN,
    MAP_ILLEGAL_EPPN_PATTERN,
    MAP_NO_RIGHTS_UPDATE_PATTERN,
    MAP_NOT_FOUND_PATTERN,
)
from server.entities.map_error import MapError
from server.entities.search_request import SearchResponse, SearchResult
from server.exc import (
    ApiClientError,
    ApiRequestError,
    CredentialsError,
    InvalidFormError,
    InvalidQueryError,
    JAIROCloudGroupsManagerError,
    OAuthTokenError,
    ResourceInvalid,
    ResourceNotFound,
    UnexpectedResponseError,
)
from server.messages import E, I
from server.services.utils import (
    UsersCriteria,
    build_patch_operations,
    build_search_query,
    is_current_user_system_admin,
    make_map_user,
    make_user_detail,
    make_user_summary,
    prepare_user,
    validate_user_to_map_user,
)
from server.signals import user_created, user_updated

from .token import get_access_token, get_client_secret


if t.TYPE_CHECKING:
    from server.clients.users import UsersSearchResponse
    from server.entities.map_user import Group, MapUser
    from server.entities.patch_request import PatchOperation
    from server.entities.summaries import UserSummary
    from server.entities.user_detail import UserDetail


@t.overload
def search(criteria: UsersCriteria) -> SearchResult[UserSummary]: ...
@t.overload
def search(
    criteria: UsersCriteria, *, raw: t.Literal[True]
) -> SearchResponse[MapUser]: ...
def search(
    criteria: UsersCriteria, *, raw: bool = False
) -> SearchResult[UserSummary] | SearchResponse[MapUser]:
    """Search for users based on given criteria.

    Args:
        criteria (UsersCriteria): Search criteria for filtering users.
        raw (bool):
            If True, return raw search response from mAP Core API. Defaults to False.

    Returns:
        object: Search results. The type depends on the `raw` argument.
        - SearchResult;
            Search result containing User summaries. It has members `total`,
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
        "user_name",
        "meta",
        "edu_person_principal_names",
        "emails",
        "groups",
    }

    query = build_search_query(criteria)
    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        results: UsersSearchResponse = users.search(
            query,
            include=default_include,
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_SEARCH_USERS, {"filter": query.filter})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_SEARCH_USERS, {"filter": query.filter})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_SEARCH_USERS, {"filter": query.filter})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(results, MapError):
        current_app.logger.error(E.FAILED_SEARCH_USERS, {"filter": query.filter})
        current_app.logger.error(
            E.RECEIVE_RESPONSE_MESSAGE, {"message": results.detail}
        )
        raise InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)

    if raw:
        return results

    return SearchResult(
        total=results.total_results,
        page_size=results.items_per_page,
        offset=results.start_index,
        resources=[make_user_summary(result) for result in results.resources],
    )


@t.overload
def get_by_id(user_id: str, *, more_detail: bool = False) -> UserDetail | None: ...
@t.overload
def get_by_id(user_id: str, *, raw: t.Literal[True]) -> MapUser | None: ...
def get_by_id(
    user_id: str, *, raw: bool = False, more_detail: bool = False
) -> UserDetail | MapUser | None:
    """Get a User detail by its ID.

    Args:
        user_id (str): ID of the User detail.
        more_detail (bool):
            If True, include more detail such as groups and repositories name.
        raw (bool): If True, return raw MapUser object. Defaults to False.

    Returns:
        object: The User object if found, otherwise None. The type depends
            on the `raw` argument.
        - UserDetail: The User detail object.
        - MapUser: The raw User object from mAP Core API.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapUser | MapError = users.get_by_id(
            user_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_USER, {"id": user_id})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_USER, {"id": user_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_USER, {"id": user_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_USER, {"id": user_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        return None

    if raw:
        return result

    return make_user_detail(result, more_detail=more_detail)


@t.overload
def get_by_eppn(eppn: str, *, more_detail: bool = False) -> UserDetail | None: ...
@t.overload
def get_by_eppn(eppn: str, *, raw: t.Literal[True]) -> MapUser | None: ...
def get_by_eppn(
    eppn: str, *, raw: bool = False, more_detail: bool = False
) -> UserDetail | MapUser | None:
    """Get a User detail by its eduPersonPrincipalName.

    Args:
        eppn (str): eduPersonPrincipalName of the User detail.
        more_detail (bool):
            If True, include more detail such as groups and repositories name.
        raw (bool): If True, return raw MapUser object. Defaults to False.

    Returns:
        object: The User object if found, otherwise None. The type depends
            on the `raw` argument.
        - UserDetail: The User detail object.
        - MapUser: The raw User object from mAP Core API.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapUser | MapError = users.get_by_eppn(
            eppn, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_USER_BY_EPPN, {"eppn": eppn})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_USER_BY_EPPN, {"eppn": eppn})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_USER_BY_EPPN, {"eppn": eppn})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_USER_BY_EPPN, {"eppn": eppn})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        return None

    if raw:
        return result

    return make_user_detail(result, more_detail=more_detail)


def create(user: UserDetail) -> UserDetail:
    """Create a User detail.

    Args:
       user (UserDetail): The User detail to create.

    Returns:
        UserDetail: The created User detail.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If the form data to create is invalid.
        ResourceInvalid: If the User resource is invalid despite passing validation.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    primary_eppn = user.eppns[0] if user.eppns else "N/A"
    try:
        map_user = prepare_user(user)

        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapUser | MapError = users.post(
            map_user,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_CREATE_USER, {"eppn": primary_eppn})
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.FAILED_CREATE_USER) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_CREATE_USER, {"eppn": primary_eppn})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_CREATE_USER, {"eppn": primary_eppn})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError, CredentialsError, InvalidFormError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_CREATE_USER, {"eppn": primary_eppn})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_DUPLICATE_ID_PATTERN, result.detail):
            raise ResourceInvalid(E.USER_DUPLICATE_ID % {"id": m.group(1)})

        if m := re.search(MAP_ALREADY_TIED_PATTERN, result.detail):
            raise ResourceInvalid(E.USER_ALREADY_TIED_EPPN % {"eppn": m.group(1)})

        if m := re.search(MAP_ILLEGAL_EPPN_PATTERN, result.detail):
            raise ResourceInvalid(E.USER_EPPN_ILLEGAL % {"eppn": m.group(1)})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(
        I.SUCCESS_CREATE_USER, {"id": result.id, "eppn": primary_eppn}
    )

    with suppress(JAIROCloudGroupsManagerError):
        user_created.send(create, user_id=result.id, eppn=primary_eppn)

    return make_user_detail(result)


def update(user: UserDetail) -> UserDetail:  # ruff:ignore[complex-structure]
    """Update a User resource.

    Args:
        user (UserDetail): The User resource to update.

    Returns:
        UserDetail: The updated User resource.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If the form data to update is invalid.
        ResourceNotFound: If the User resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(user_id := t.cast("str", user.id))) is None:
        current_app.logger.error(E.FAILED_UPDATE_USER, {"id": user_id})
        raise ResourceNotFound(E.USER_NOT_FOUND % {"id": user_id})

    if not is_current_user_system_admin() and current.is_system_admin:
        raise InvalidFormError(E.USER_NO_UPDATE_SYSTEM_ADMIN)
    # promotion permission will be checked in validation process.

    primary_eppn = user.eppns[0] if user.eppns else "N/A"
    validated = validate_user_to_map_user(user, mode="update")
    operations = build_patch_operations(
        make_map_user(current),
        validated,
        exclude={"schemas", "external_id", "meta"},
    )

    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapUser | MapError = users.patch_by_id(
            user_id,
            operations,
            exclude={"external_id", "meta"},
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
        )
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.FAILED_UPDATE_USER) from exc

    except requests.RequestException as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
        )
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
        )
        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
        )
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.USER_NOT_FOUND % {"id": m.group(1)})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_USER % {"id": user_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(
        I.SUCCESS_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
    )

    with suppress(JAIROCloudGroupsManagerError):
        user_updated.send(update, user_id=user_id, eppn=primary_eppn)

    return make_user_detail(result)


def update_put(user: UserDetail) -> UserDetail:  # ruff:ignore[complex-structure]
    """Update a User resource using PUT method.

    Args:
        user (UserDetail): The User resource to update.

    Returns:
        UserDetail: The updated User resource.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If the form data to update is invalid.
        ResourceNotFound: If the User resource is not found.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(user_id := t.cast("str", user.id))) is None:
        current_app.logger.error(E.FAILED_UPDATE_USER, {"id": user_id})
        raise ResourceNotFound(E.USER_NOT_FOUND % {"id": user_id})

    if not is_current_user_system_admin() and current.is_system_admin:
        raise InvalidFormError(E.USER_NO_UPDATE_SYSTEM_ADMIN)

    primary_eppn = user.eppns[0] if user.eppns else "N/A"
    validated = validate_user_to_map_user(user, mode="update")

    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapUser | MapError = users.put_by_id(
            validated,
            exclude={"external_id", "meta"},
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user.id, "eppn": primary_eppn}
        )
        if exc.response and exc.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.FAILED_UPDATE_USER) from exc

    except requests.RequestException as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user.id, "eppn": primary_eppn}
        )
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user.id, "eppn": primary_eppn}
        )
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(
            E.FAILED_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
        )
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.USER_NOT_FOUND % {"id": m.group(1)})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_USER % {"id": user_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(
        I.SUCCESS_UPDATE_USER, {"id": user_id, "eppn": primary_eppn}
    )

    with suppress(JAIROCloudGroupsManagerError):
        user_updated.send(update, user_id=user_id, eppn=primary_eppn)

    return make_user_detail(result)


def update_affiliations(user: UserDetail) -> UserDetail:
    """Update a User's affiliations with groups and repositories.

    Args:
        user (UserDetail): The User resource to update.

    Returns:
        UserDetail: The updated User detail.

    Raises:
        ResourceNotFound: If the User resource is not found.
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        ExceptionGroup: If there are multiple errors while updating affiliations.
    """
    user_id = t.cast("str", user.id)
    current: UserDetail | None = get_by_id(user_id)
    if current is None:
        error = E.USER_NOT_FOUND % {"id": user_id}
        raise ResourceNotFound(error)

    validated = validate_user_to_map_user(user, mode="update")
    operations: list[PatchOperation[MapUser]] = build_patch_operations(
        make_map_user(current),
        validated,
        include={"groups"},
    )

    from . import groups  # ruff:ignore[import-outside-top-level]

    primary_eppn = user.eppns[0] if user.eppns else "N/A"
    errors: list[Exception] = []
    for op in operations:
        if op.op == "replace":
            continue
        if op.op == "add":
            group_id = t.cast("Group", op.value).value
        elif match := re.search(r'groups\[value eq "(.*?)"\]', op.path):
            group_id = match.group(1)
        else:
            continue

        try:
            groups.update_members(group_id, **{op.op: {user_id}})

        except OAuthTokenError, CredentialsError:
            raise
        except (ApiClientError, ApiRequestError) as exc:
            errors.append(exc)

    user_updated.send(None, user=user)

    if errors:
        error = E.FAILED_UPDATE_USER_AFFILIATIONS % {
            "id": user_id,
            "eppn": primary_eppn,
        }
        raise ExceptionGroup(error, errors)

    current_app.logger.info(
        I.SUCCESS_UPDATE_USER_AFFILIATIONS, {"id": user_id, "eppn": primary_eppn}
    )
    return t.cast("UserDetail", get_by_id(user_id))
