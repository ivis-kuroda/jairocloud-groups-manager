#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing repositories."""

import re
import typing as t

from http import HTTPStatus

import requests

from flask import current_app
from pydantic_core import ValidationError

from server.clients import groups, services
from server.config import config
from server.const import (
    MAP_DUPLICATE_ID_PATTERN,
    MAP_NO_RIGHTS_CREATE_PATTERN,
    MAP_NO_RIGHTS_UPDATE_PATTERN,
    MAP_NOT_FOUND_PATTERN,
)
from server.entities.map_error import MapError
from server.entities.repository_detail import RepositoryDetail
from server.entities.search_request import SearchResponse, SearchResult
from server.entities.summaries import RepositorySummary
from server.exc import (
    CredentialsError,
    InvalidFormError,
    InvalidQueryError,
    OAuthTokenError,
    ResourceInvalid,
    ResourceNotFound,
    SystemAdminNotFound,
    UnexpectedResponseError,
)
from server.messages import E, I

from . import users
from .token import get_access_token, get_client_secret
from .utils import (
    RepositoriesCriteria,
    build_patch_operations,
    build_search_query,
    prepare_role_groups,
    prepare_service,
    resolve_repository_id,
    resolve_service_id,
    validate_repository_to_map_service,
)


if t.TYPE_CHECKING:
    from server.clients.services import ServicesSearchResponse
    from server.entities.map_service import MapService
    from server.entities.patch_request import PatchOperation


@t.overload
def search(criteria: RepositoriesCriteria) -> SearchResult[RepositorySummary]: ...
@t.overload
def search(
    criteria: RepositoriesCriteria, *, raw: t.Literal[True]
) -> SearchResponse[MapService]: ...


def search(
    criteria: RepositoriesCriteria, *, raw: bool = False
) -> SearchResult[RepositorySummary] | SearchResponse[MapService]:
    """Search for repositories based on given criteria.

    Args:
        criteria (RepositoriesCriteria): Search criteria for filtering repositories.
        raw (bool):
            If True, return raw search response from mAP Core API. Defaults to False.

    Returns:
        object: Search results. The type depends on the `raw` argument.
        - SearchResult;
            Search result containing Repository summaries. It has members `total`,
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
    default_include = {"id", "service_name", "service_url", "entity_ids"}

    query = build_search_query(criteria)
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        results: ServicesSearchResponse = services.search(
            query,
            include=default_include,
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(results, MapError):
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        current_app.logger.error(
            E.RECEIVE_RESPONSE_MESSAGE, {"message": results.detail}
        )
        error = E.UNSUPPORTED_SEARCH_FILTER
        raise InvalidQueryError(error)

    if raw:
        return results

    repository_summaries = [
        RepositorySummary(
            id=repository_id,
            service_name=result.service_name,
            service_url=result.service_url,
            service_id=result.id,
            entity_ids=[eid.value for eid in result.entity_ids or []],
        )
        for result in results.resources
        if (repository_id := resolve_repository_id(service_id=result.id))
    ]

    return SearchResult(
        total=results.total_results,
        page_size=results.items_per_page,
        offset=results.start_index,
        resources=repository_summaries,
    )


@t.overload
def get_by_id(
    repository_id: str, *, more_detail: bool = False
) -> RepositoryDetail | None: ...
@t.overload
def get_by_id(repository_id: str, *, raw: t.Literal[True]) -> MapService | None: ...


def get_by_id(
    repository_id: str, *, raw: bool = False, more_detail: bool = False
) -> RepositoryDetail | MapService | None:
    """Get a Repository resource by its ID.

    Args:
        repository_id (str): ID of the Repository resource.
        more_detail (bool):
            If True, include more details such as groups and users count.
        raw (bool): If True, return raw MapService object. Defaults to False.

    Returns:
        object: The Repository resource if found, otherwise None. The type depends
            on the `raw` argument.
        - RepositoryDetail: The Repository detail object.
        - MapService: The raw Repository object from mAP Core API.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    service_id = resolve_service_id(repository_id=repository_id)
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapService | MapError = services.get_by_id(
            service_id,
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": service_id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": service_id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": service_id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": service_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        return None

    if raw:
        return result

    return RepositoryDetail.from_map_service(result, more_detail=more_detail)


def create(repository: RepositoryDetail) -> RepositoryDetail:
    """Create a new Repository resource.

    Args:
        repository (RepositoryDetail): The Repository resource to create.

    Returns:
        RepositoryDetail: The created Repository resource.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If failed to validate repository form data for creation.
        ResourceInvalid: If the Repository resource data is invalid.
        SystemAdminNotFound: If no system administrators are found in the system.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    admins = users.get_system_admins()

    try:
        service, repository_id = prepare_service(repository, admins)
        role_groups = prepare_role_groups(
            repository_id, t.cast("str", repository.service_name), admins
        )

        access_token = get_access_token()
        client_secret = get_client_secret()
        for group in role_groups:
            groups.post(group, access_token=access_token, client_secret=client_secret)
        current_app.logger.info(
            I.SUCCESS_CREATE_ROLEGROUPS, {"id": repository.service_id}
        )

        result: MapService | MapError = services.post(
            service,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(
            E.FAILED_CREATE_REPOSITORY, {"id": repository.service_id}
        )
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(
            E.FAILED_CREATE_REPOSITORY, {"id": repository.service_id}
        )
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(
            E.FAILED_CREATE_REPOSITORY, {"id": repository.service_id}
        )
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError, InvalidFormError, SystemAdminNotFound:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(
            E.FAILED_CREATE_REPOSITORY, {"id": repository.service_id}
        )
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_DUPLICATE_ID_PATTERN, result.detail):
            error = E.REPOSITORY_DUPLICATE_ID % {"id": m.group(1)}
            raise ResourceInvalid(error)
        if re.search(MAP_NO_RIGHTS_CREATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_CREATE_REPOSITORY
            raise OAuthTokenError(error)
        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(I.SUCCESS_CREATE_REPOSITORY, {"id": result.id})
    return RepositoryDetail.from_map_service(result)


def update(repository: RepositoryDetail) -> RepositoryDetail:  # noqa: C901
    """Update an existing Repository resource.

    Args:
        repository (RepositoryDetail):
            The Repository data to update. The `id` field is required.

    Returns:
        RepositoryDetail: The updated Repository resource.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If failed to validate repository form data for update.
        ResourceNotFound: If the Repository resource does not exist.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if config.MAP_CORE.update_strategy == "put":
        return update_put(repository)

    validated = validate_repository_to_map_service(repository)

    repository_id = t.cast("str", repository.id)
    service_id = t.cast("str", validated.id)
    current = get_by_id(repository_id)
    if current is None:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        error = E.REPOSITORY_NOT_FOUND % {"id": service_id}
        raise ResourceNotFound(error)

    if validated.service_url and validated.service_url != current.service_url:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        error = E.UNCHANGEABLE_REPOSITORY_URL
        raise InvalidFormError(error)

    operations: list[PatchOperation[MapService]] = build_patch_operations(
        current.to_map_service(),
        validated,
        include={"service_name", "suspended", "entity_ids"},
    )
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapService | MapError = services.patch_by_id(
            service_id,
            operations,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.REPOSITORY_NOT_FOUND % {"id": m.group(1)}
            raise ResourceNotFound(error)
        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_UPDATE_REPOSITORY % {"id": service_id}
            raise OAuthTokenError(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(I.SUCCESS_UPDATE_REPOSITORY, {"id": result.id})
    return RepositoryDetail.from_map_service(result)


def update_put(repository: RepositoryDetail) -> RepositoryDetail:  # noqa: C901
    """Update an existing Repository resource (replace with PUT).

    Args:
        repository (RepositoryDetail):
            The Repository data to update. The `id` field is required.


    Returns:
        RepositoryDetail: The updated Repository resource.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        InvalidFormError: If failed to validate repository form data for update.
        ResourceNotFound: If the Repository resource does not exist.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if config.MAP_CORE.update_strategy == "patch":
        return update(repository)

    validated = validate_repository_to_map_service(repository)

    repository_id = t.cast("str", repository.id)
    service_id = t.cast("str", validated.id)
    current = get_by_id(repository_id)
    if current is None:
        error = E.REPOSITORY_NOT_FOUND % {"id": service_id}
        raise ResourceNotFound(error)

    if validated.service_url and validated.service_url != current.service_url:
        error = E.UNCHANGEABLE_REPOSITORY_URL
        raise InvalidFormError(error)

    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapService | MapError = services.put_by_id(
            validated,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        error = E.FAILED_CONNECT_REDIS
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": service_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.REPOSITORY_NOT_FOUND % {"id": m.group(1)}
            raise ResourceNotFound(error)
        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            error = E.NO_RIGHTS_UPDATE_REPOSITORY % {"id": service_id}
            raise OAuthTokenError(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(I.SUCCESS_UPDATE_REPOSITORY, {"id": result.id})
    return RepositoryDetail.from_map_service(result)


def delete_by_id(repository_id: str, service_name: str) -> None:
    """Delete a Repository resource by its ID.

    Args:
        repository_id (str): ID of the Repository resource to delete.
        service_name (str):
            Name of the service associated with the Repository resource to confirm.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        CredentialsError: If the client credentials are invalid.
        ResourceNotFound: If the Repository resource does not exist.
        InvalidFormError: If the service name to confirm does not match.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if not (repository := get_by_id(repository_id)):
        error = E.REPOSITORY_NOT_FOUND % {"id": repository_id}
        raise ResourceNotFound(error)

    if repository.service_name != service_name:
        error = E.REPOSITORY_NAME_NOT_MATCH % {"id": repository_id}
        raise InvalidFormError(error)

    service_id = resolve_service_id(repository_id=repository_id)
    groups_to_delete = [*(repository._groups or []), *(repository._rolegroups or [])]  # noqa: SLF001
    try:
        access_token = get_access_token()
        client_secret = get_client_secret()
        result: MapError | None = services.delete_by_id(
            service_id,
            access_token=access_token,
            client_secret=client_secret,
        )

    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": service_id})
        code = exc.response.status_code
        if code == HTTPStatus.UNAUTHORIZED:
            error = E.ACCESS_TOKEN_NOT_AVAILABLE
            raise OAuthTokenError(error) from exc

        error = E.UNEXPECTED_SERVER_ERROR
        raise UnexpectedResponseError(error) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": service_id})
        error = E.FAILED_COMMUNICATE_API
        raise UnexpectedResponseError(error) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": service_id})
        error = E.FAILED_PARSE_RESPONSE
        raise UnexpectedResponseError(error) from exc

    except OAuthTokenError, CredentialsError:
        raise

    if result:
        if m := re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            error = E.REPOSITORY_NOT_FOUND % {"id": m.group(1)}
            raise ResourceNotFound(error)

        error = E.RECEIVE_UNEXPECTED_RESPONSE
        raise UnexpectedResponseError(error)

    current_app.logger.info(I.SUCCESS_DELETE_REPOSITORY, {"id": service_id})

    from . import groups  # noqa: PLC0415

    groups.delete_multiple(set(groups_to_delete))
