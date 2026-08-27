import typing as t

from http import HTTPStatus
from uuid import uuid4

import pytest
import requests

from pydantic_core import ValidationError
from requests import Response

import server.services.core.repositories

from server.const import (
    MAP_DUPLICATE_ID_PATTERN,
    MAP_NO_RIGHTS_CREATE_PATTERN,
    MAP_NO_RIGHTS_UPDATE_PATTERN,
    MAP_NOT_FOUND_PATTERN,
    USER_ROLES,
)
from server.entities.map_error import MapError
from server.entities.map_service import MapService
from server.entities.patch_request import ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse, SearchResult
from server.entities.summaries import RepositorySummary
from server.exc import (
    InvalidFormError,
    InvalidQueryError,
    OAuthTokenError,
    ResourceInvalid,
    ResourceNotFound,
    UnexpectedResponseError,
)
from server.messages import E, I
from server.services.core import repositories
from server.services.utils import RepositoriesCriteria

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.entities.repository_detail import RepositoryDetail


@pytest.fixture
def token_and_secret(mocker: MockerFixture):
    """Return a tuple of (token, secret) for testing purposes."""
    mock_get_token = mocker.patch.object(server.services.core.repositories, "get_access_token", autospec=True)
    mock_get_token.return_value = (access_token := uuid4().hex[:8])
    mock_get_secret = mocker.patch.object(server.services.core.repositories, "get_client_secret", autospec=True)
    mock_get_secret.return_value = (client_secret := uuid4().hex[:16])

    return access_token, client_secret


def test_search(repository_summaries, map_services, token_and_secret, mocker: MockerFixture):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter)
    repository_id = repository_summaries[0].id

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)

    total, size, index = 1, 1, 1
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search", autospec=True)
    mock_search.return_value = SearchResponse[MapService](
        total_results=total, items_per_page=size, start_index=index, resources=map_services[:1]
    )
    mocker.patch.object(server.services.core.repositories, "resolve_repository_id", return_value=repository_id)
    mock_make_summary = mocker.patch.object(
        server.services.core.repositories, "make_repository_summary", return_value=repository_summaries[0]
    )
    expected = SearchResult[RepositorySummary](
        total=total, page_size=size, offset=index, resources=repository_summaries[:1]
    )

    result = repositories.search(criteria)

    assert result == expected
    mock_search.assert_called_once_with(query, include=mocker.ANY, access_token=token, client_secret=secret)
    mock_make_summary.assert_called_once_with(map_services[0], repository_id)


def test_search_with_raw(map_services, token_and_secret, mocker: MockerFixture):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter)

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)

    total, size, index = 1, 1, 1
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search", autospec=True)
    mock_search.return_value = expected = SearchResponse[MapService](
        total_results=total, items_per_page=size, start_index=index, resources=map_services[:1]
    )

    result = repositories.search(criteria, raw=True)

    assert result == expected
    mock_search.assert_called_once_with(query, include=mocker.ANY, access_token=token, client_secret=secret)


def test_search_map_error(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "test_repo_ac_jp"'))

    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search")
    map_error = MapError(detail="eq is not supported.", status="400", scim_type="invalidSyntax")
    mock_search.return_value = map_error

    with pytest.raises(InvalidQueryError, match=regex(E.UNSUPPORTED_SEARCH_FILTER)):
        repositories.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_REPOSITORIES, {"filter": filter_str})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_search_unauthorized(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "test_repo_ac_jp"'))

    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search")
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_search.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        repositories.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_REPOSITORIES, {"filter": filter_str})


def test_search_unexpected_response(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "test_repo_ac_jp"'))

    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search")
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_search.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        repositories.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_REPOSITORIES, {"filter": filter_str})


def test_search_request_exception(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "test_repo_ac_jp"'))

    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search")
    mock_search.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        repositories.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_REPOSITORIES, {"filter": filter_str})


def test_search_validation_error(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=RepositoriesCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "test_repo_ac_jp"'))

    mocker.patch.object(server.services.core.repositories, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.repositories.services, "search")
    mock_search.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        repositories.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_REPOSITORIES, {"filter": filter_str})


def test_get_by_id(repository_details, map_services, token_and_secret, mocker: MockerFixture):
    repository = expected = repository_details[0]
    service_id = (map_service := map_services[0]).id

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id", autospec=True)
    mock_get.return_value = map_service
    mock_make_detail = mocker.patch.object(
        server.services.core.repositories, "make_repository_detail", return_value=repository
    )

    result = repositories.get_by_id(repository.id)

    assert result is expected
    mock_get.assert_called_once_with(service_id, access_token=token, client_secret=secret)
    mock_make_detail.assert_called_once_with(map_service, more_detail=False)


def test_get_by_id_with_more_detail(repository_details, map_services, token_and_secret, mocker: MockerFixture):
    repository = expected = repository_details[0]
    repository.groups_count = 5
    repository.users_count = 10
    service_id = (map_service := map_services[0]).id

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id", autospec=True)
    mock_get.return_value = map_service
    mock_make_detail = mocker.patch.object(
        server.services.core.repositories, "make_repository_detail", return_value=repository
    )

    result = repositories.get_by_id(repository.id, more_detail=True)

    assert result is expected
    mock_get.assert_called_once_with(service_id, access_token=token, client_secret=secret)
    mock_make_detail.assert_called_once_with(map_service, more_detail=True)


def test_get_by_id_with_raw(repository_details, map_services, token_and_secret, mocker: MockerFixture):
    repository = repository_details[0]
    service_id = (map_service := map_services[0]).id

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id", autospec=True)
    mock_get.return_value = map_service

    result = repositories.get_by_id(repository.id, raw=True)

    assert result is map_service
    mock_get.assert_called_once_with(service_id, access_token=token, client_secret=secret)


def test_get_by_id_map_error(app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog):
    repository = repository_details[0]
    service_id = map_services[0].id

    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    map_error = MapError(detail="Service not found.", status="404", scim_type="invalidValue")
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id", return_value=map_error)

    result = repositories.get_by_id(repository.id)

    assert result is None
    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_get_by_id_unauthorized(app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog):
    repository = repository_details[0]
    service_id = map_services[0].id

    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id")
    mock_get.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        repositories.get_by_id(repository.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_REPOSITORY, {"id": repository.id})


def test_get_by_id_unexpected_response(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_details[0]
    service_id = map_services[0].id

    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id")
    mock_get.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        repositories.get_by_id(repository.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_REPOSITORY, {"id": repository.id})


def test_get_by_id_request_exception(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_details[0]
    service_id = map_services[0].id

    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id")
    mock_get.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        repositories.get_by_id(repository.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_REPOSITORY, {"id": repository.id})


def test_get_by_id_validation_error(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_details[0]
    service_id = map_services[0].id

    mocker.patch.object(server.services.core.repositories, "resolve_service_id", return_value=service_id)
    mock_get = mocker.patch.object(server.services.core.repositories.services, "get_by_id")
    mock_get.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        repositories.get_by_id(repository.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_REPOSITORY, {"id": repository.id})


def test_create(
    app, user_summaries, repository_details, map_services, token_and_secret, signal_send, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = expected = repository_details[0]
    map_service = map_services[0]
    prepared = map_service.model_copy(update={"id": None})

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post", autospec=True)
    mock_post.return_value = map_service
    mocker.patch.object(server.services.core.repositories, "make_repository_detail", return_value=repository)

    result = repositories.create(repository, admins)

    assert result == expected
    mock_post.assert_called_once_with(prepared, exclude=mocker.ANY, access_token=token, client_secret=secret)
    assert_message(caplog.records[0], I.SUCCESS_CREATE_REPOSITORY, {"id": repository.id})
    signal_send["repository_created"].assert_called_once()


def test_create_already_exists(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    service_id = (map_service := map_services[0]).id
    prepared = map_service.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    map_error = MapError(
        detail=MAP_DUPLICATE_ID_PATTERN.replace("(.*)", service_id), status="400", scim_type="uniqueness"
    )
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post", return_value=map_error)

    with pytest.raises(ResourceInvalid, match=regex(E.REPOSITORY_DUPLICATE_ID)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_create_no_rights(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    prepared = map_services[0].model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    map_error = MapError(
        detail=MAP_NO_RIGHTS_CREATE_PATTERN.replace("(.*)", "Service"), status="400", scim_type="invalidSyntax"
    )
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post", return_value=map_error)

    with pytest.raises(OAuthTokenError, match=regex(E.NO_RIGHTS_CREATE_REPOSITORY)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_create_unexpected_map_error(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    prepared = map_services[0].model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    map_error = MapError(detail="Unexpected error.", status="400", scim_type="invalidValue")
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post", return_value=map_error)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_create_unauthorized(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    prepared = map_services[0].model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post")
    mock_post.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})


def test_create_unexpected_response(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    prepared = map_services[0].model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post")
    mock_post.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})


def test_create_request_exception(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    prepared = map_services[0].model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post")
    mock_post.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})


def test_create_validation_error(
    app, user_summaries, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository = repository_details[0]
    prepared = map_services[0].model_copy(update={"id": None})

    mocker.patch.object(server.services.core.repositories, "prepare_service", return_value=(prepared, repository.id))
    mock_post = mocker.patch.object(server.services.core.repositories.services, "post")
    mock_post.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        repositories.create(repository, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_REPOSITORY, {"id": repository.id})


def test_update(
    app,
    repository_details,
    map_services,
    token_and_secret,
    signal_send,
    mocker: MockerFixture,
    caplog,
):
    current_detail: RepositoryDetail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    updated_detail = expected = repository.model_copy()
    current_service: MapService = map_services[0]
    validated = current_service.model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]
    include_fields = {"service_name", "suspended", "entity_ids"}

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "make_map_service", return_value=current_service)
    mock_build_ops = mocker.patch.object(server.services.core.repositories, "build_patch_operations", autospec=True)
    mock_build_ops.return_value = operations
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id", autospec=True)
    mock_patch.return_value = validated
    mocker.patch.object(server.services.core.repositories, "make_repository_detail", return_value=updated_detail)

    result = repositories.update(repository)

    assert result is expected
    mock_build_ops.assert_called_once_with(current_service, validated, include=include_fields)
    mock_patch.assert_called_once_with(
        validated.id, operations, exclude={"meta"}, access_token=token, client_secret=secret
    )
    signal_send["repository_updated"].assert_called_once()
    assert_message(caplog.records[0], I.SUCCESS_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_not_found(app, repository_details, mocker: MockerFixture, caplog):
    repository = repository_details[0]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=None)

    with pytest.raises(ResourceNotFound, match=regex(E.REPOSITORY_NOT_FOUND)):
        repositories.update(repository)

    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_unchangeable_service_url(app, repository_details, map_services, mocker: MockerFixture, caplog):
    current_detail = repository_details[0]
    repository = current_detail.model_copy()
    repository.service_url = str(repository.service_url) + "/new"
    validated = map_services[0].model_copy(update={"service_url": repository.service_url})

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)

    with pytest.raises(InvalidFormError, match=regex(E.UNCHANGEABLE_REPOSITORY_URL)):
        repositories.update(repository)

    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_unauthorized(app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    validated = map_services[0]
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id")
    mock_patch.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_unexpected_response(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    validated = map_services[0].model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id")
    mock_patch.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_request_exception(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    current_service = map_services[0]
    validated = map_services[0].model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "make_map_service", return_value=current_service)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id")
    mock_patch.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_validation_error(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    validated = map_services[0].model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id")
    mock_patch.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})


def test_update_map_error_not_found(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    current_service = map_services[0]
    validated = map_services[0].model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "make_map_service", return_value=current_service)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    map_error = MapError(
        detail=MAP_NOT_FOUND_PATTERN.replace("(.*)", validated.id), status="400", scim_type="invalidValue"
    )
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id", return_value=map_error)

    with pytest.raises(ResourceNotFound, match=regex(E.REPOSITORY_NOT_FOUND)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_update_map_error_no_rights(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    validated = map_services[0].model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    map_error = MapError(
        detail=MAP_NO_RIGHTS_UPDATE_PATTERN.replace("(.*)", t.cast("str", validated.id)),
        status="403",
        scim_type="invalidSyntax",
    )
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id", return_value=map_error)

    with pytest.raises(OAuthTokenError, match=regex(E.NO_RIGHTS_UPDATE_REPOSITORY)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_update_map_error_unexpected(
    app, repository_details, map_services, token_and_secret, mocker: MockerFixture, caplog
):
    current_detail = repository_details[0]
    repository = current_detail.model_copy(
        update={"service_name": (updated_name := f"Updated {current_detail.service_name}")}
    )
    validated = map_services[0].model_copy(update={"service_name": updated_name})
    operations = [ReplaceOperation(path="service_name", value=updated_name)]

    mocker.patch.object(server.services.core.repositories, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.repositories, "validate_repository_to_map_service", return_value=validated)
    mocker.patch.object(server.services.core.repositories, "build_patch_operations", return_value=operations)
    map_error = MapError(detail="Unexpected error.", status="400", scim_type="invalidValue")
    mock_patch = mocker.patch.object(server.services.core.repositories.services, "patch_by_id", return_value=map_error)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        repositories.update(repository)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_REPOSITORY, {"id": repository.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})
