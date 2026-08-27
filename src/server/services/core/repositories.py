#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Core services for managing repositories."""

import re
import typing as t

from contextlib import suppress
from http import HTTPStatus

import requests

from flask import current_app
from pydantic_core import ValidationError

from server.clients import services
from server.const import (
    MAP_DUPLICATE_ID_PATTERN,
    MAP_NO_RIGHTS_CREATE_PATTERN,
    MAP_NO_RIGHTS_UPDATE_PATTERN,
    MAP_NOT_FOUND_PATTERN,
)
from server.entities.map_error import MapError
from server.entities.search_request import SearchResponse, SearchResult
from server.entities.summaries import RepositorySummary
from server.exc import (
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
    RepositoriesCriteria,
    build_patch_operations,
    build_search_query,
    make_repository_detail,
    make_repository_summary,
    prepare_service,
    resolve_repository_id,
    resolve_service_id,
    validate_repository_to_map_service,
)
from server.signals import (
    repository_created,
    repository_deleted,
    repository_updated,
)

from .token import get_access_token, get_client_secret


if t.TYPE_CHECKING:
    from server.entities.map_service import MapService
    from server.entities.repository_detail import RepositoryDetail


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
        Search results. The type depends on the `raw` argument.
        - SearchResult[RepositorySummary]:
            Search result containing Repository summaries. It has members `total`,
            `page_size`, `offset`, and `resources`.
        - SearchResponse[MapService]:
            Raw search response from mAP Core API. It has members `schemas`,
            `total_results`, `start_index`, `items_per_page`, and `resources`.

    Raises:
        InvalidQueryError: If the query construction is invalid.
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If the access token is invalid or expired.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    default_include = {"id", "service_name", "service_url", "entity_ids"}
    query = build_search_query(criteria)
    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        results: SearchResponse[MapService] | MapError = services.search(
            query,
            include=default_include,
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        code = t.cast("requests.Response", exc.response).status_code
        if code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except CredentialsError, OAuthTokenError, InvalidQueryError:
        raise

    if isinstance(results, MapError):
        current_app.logger.error(E.FAILED_SEARCH_REPOSITORIES, {"filter": query.filter})
        current_app.logger.error(
            E.RECEIVE_RESPONSE_MESSAGE, {"message": results.detail}
        )
        raise InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)

    if raw:
        return results

    repository_summaries = [
        make_repository_summary(result, repository_id)
        for result in results.resources
        if (repository_id := resolve_repository_id(service_id=result.id))
    ]

    return SearchResult[RepositorySummary](
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
    """Get a Repository by its ID.

    Args:
        repository_id (str): ID of the Repository.
        more_detail (bool):
            If True, include more details such as groups and users count.
        raw (bool): If True, return raw MapService object. Defaults to False.

    Returns:
        The Repository if found, otherwise None. The type depends
            on the `raw` argument.
        - RepositoryDetail: The Repository detail object.
        - MapService: The raw Repository object from mAP Core API.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If the access token is invalid or expired.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    service_id = resolve_service_id(repository_id=repository_id)
    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapService | MapError = services.get_by_id(
            service_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": repository_id})
        code = t.cast("requests.Response", exc.response).status_code
        if code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc
    except CredentialsError, OAuthTokenError:
        raise
    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_GET_REPOSITORY, {"id": repository_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        return None

    if raw:
        return result

    return make_repository_detail(result, more_detail=more_detail)


def create(repository: RepositoryDetail, admins: set[str]) -> RepositoryDetail:
    """Create a new Repository.

    Args:
        repository (RepositoryDetail): The Repository to create.
        admins (set[str]): Set of user IDs who are system administrators.

    Returns:
        RepositoryDetail: The created Repository.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If the access token is invalid or expired.
        ResourceInvalid: If the Repository data is invalid.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    service, repository_id = prepare_service(repository, admins)
    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapService | MapError = services.post(
            service,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_CREATE_REPOSITORY, {"id": repository_id})
        code = t.cast("requests.Response", exc.response).status_code
        if code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_CREATE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_CREATE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except CredentialsError, OAuthTokenError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_CREATE_REPOSITORY, {"id": repository_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_DUPLICATE_ID_PATTERN, result.detail):
            raise ResourceInvalid(E.REPOSITORY_DUPLICATE_ID % {"id": repository_id})

        if re.search(MAP_NO_RIGHTS_CREATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_CREATE_REPOSITORY)

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(I.SUCCESS_CREATE_REPOSITORY, {"id": repository_id})

    with suppress(JAIROCloudGroupsManagerError):
        repository_created.send(
            create, repository_id=repository_id, service_id=result.id
        )

    return make_repository_detail(result)


def update(repository: RepositoryDetail) -> RepositoryDetail:  # ruff:ignore[complex-structure]
    """Update an existing Repository.

    Args:
        repository (RepositoryDetail):
            The Repository data to update. The `id` field is required.

    Returns:
        RepositoryDetail: The updated Repository.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If the access token is invalid or expired.
        InvalidFormError: If failed to validate repository form data for update.
        ResourceNotFound: If the Repository does not exist.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(repository_id := t.cast("str", repository.id))) is None:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": repository_id})

    validated = validate_repository_to_map_service(repository)
    if validated.service_url and validated.service_url != current.service_url:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise InvalidFormError(E.UNCHANGEABLE_REPOSITORY_URL)

    operations = build_patch_operations(
        current.to_map_service(),
        validated,
        include={"service_name", "suspended", "entity_ids"},
    )

    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapService | MapError = services.patch_by_id(
            validated.id,
            operations,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        code = t.cast("requests.Response", exc.response).status_code
        if code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.UNEXPECTED_SERVER_ERROR) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except CredentialsError, OAuthTokenError:
        raise

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": repository_id})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_REPOSITORY % {"id": repository_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(I.SUCCESS_UPDATE_REPOSITORY, {"id": repository_id})

    with suppress(JAIROCloudGroupsManagerError):
        repository_updated.send(
            update, repository_id=repository_id, service_id=result.id
        )

    return make_repository_detail(result)


def update_put(repository: RepositoryDetail) -> RepositoryDetail:
    """Update an existing Repository (replace with PUT).

    Args:
        repository (RepositoryDetail):
            The Repository data to update. The `id` field is required.


    Returns:
        RepositoryDetail: The updated Repository.

    Raises:
        OAuthTokenError: If the access token is invalid or expired.
        InvalidFormError: If failed to validate repository form data for update.
        ResourceNotFound: If the Repository does not exist.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(repository_id := t.cast("str", repository.id))) is None:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": repository_id})

    validated = validate_repository_to_map_service(repository)
    if validated.service_url and validated.service_url != current.service_url:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise InvalidFormError(E.UNCHANGEABLE_REPOSITORY_URL)

    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapService | MapError = services.put_by_id(
            validated,
            exclude={"meta"},
            access_token=access_token,
            client_secret=client_secret,
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        code = t.cast("requests.Response", exc.response).status_code
        if code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.UNEXPECTED_SERVER_ERROR) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_CONNECT_REDIS) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    if isinstance(result, MapError):
        current_app.logger.error(E.FAILED_UPDATE_REPOSITORY, {"id": repository_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": repository_id})

        if re.search(MAP_NO_RIGHTS_UPDATE_PATTERN, result.detail):
            raise OAuthTokenError(E.NO_RIGHTS_UPDATE_REPOSITORY % {"id": repository_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(I.SUCCESS_UPDATE_REPOSITORY, {"id": repository_id})

    with suppress(JAIROCloudGroupsManagerError):
        repository_updated.send(
            update, repository_id=repository_id, service_id=result.id
        )

    return make_repository_detail(result)


def delete_by_id(repository_id: str, service_name: str) -> RepositoryDetail:
    """Delete a Repository by its ID.

    Args:
        repository_id (str): ID of the Repository to delete.
        service_name (str):
            Name of the service associated with the Repository to confirm.

    Returns:
        RepositoryDetail: The deleted Repository.

    Raises:
        CredentialsError: If client credentials are not available.
        OAuthTokenError: If the access token is invalid or expired.
        ResourceNotFound: If the Repository does not exist.
        InvalidFormError: If the service name to confirm does not match.
        UnexpectedResponseError: If response from mAP Core API is unexpected.
    """
    if (current := get_by_id(repository_id, more_detail=True)) is None:
        raise ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": repository_id})

    if current.service_name != service_name:
        raise InvalidFormError(E.REPOSITORY_NAME_NOT_MATCH % {"id": repository_id})

    service_id = resolve_service_id(repository_id=repository_id)

    try:
        access_token, client_secret = get_access_token(), get_client_secret()
        result: MapError | None = services.delete_by_id(
            service_id, access_token=access_token, client_secret=client_secret
        )
    except requests.HTTPError as exc:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": repository_id})
        code = t.cast("requests.Response", exc.response).status_code
        if code == HTTPStatus.UNAUTHORIZED:
            raise OAuthTokenError(E.ACCESS_TOKEN_NOT_AVAILABLE) from exc

        raise UnexpectedResponseError(E.UNEXPECTED_SERVER_ERROR) from exc

    except requests.RequestException as exc:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_COMMUNICATE_API) from exc

    except ValidationError as exc:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": repository_id})
        raise UnexpectedResponseError(E.FAILED_PARSE_RESPONSE) from exc

    except CredentialsError, OAuthTokenError:
        raise

    if result:
        current_app.logger.error(E.FAILED_DELETE_REPOSITORY, {"id": repository_id})
        current_app.logger.error(E.RECEIVE_RESPONSE_MESSAGE, {"message": result.detail})
        if re.search(MAP_NOT_FOUND_PATTERN, result.detail):
            raise ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": repository_id})

        raise UnexpectedResponseError(E.RECEIVE_UNEXPECTED_RESPONSE)

    current_app.logger.info(I.SUCCESS_DELETE_REPOSITORY, {"id": repository_id})

    with suppress(JAIROCloudGroupsManagerError):
        repository_deleted.send(
            delete_by_id,
            service_id=service_id,
            repository_id=repository_id,
            repository=current,
        )

    return current
