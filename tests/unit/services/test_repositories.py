import typing as t

from http import HTTPStatus

import pytest
import requests

from pydantic import HttpUrl
from pydantic_core import ValidationError
from requests import Response

from server import const
from server.entities.map_error import MapError
from server.entities.map_service import MapService, ServiceEntityID
from server.entities.repository_detail import RepositoryDetail
from server.entities.search_request import SearchRequestParameter, SearchResponse, SearchResult
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
from server.services import repositories
from server.services.utils import make_criteria_object


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_search_success(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests successful search for repositories and validates the returned SearchResult."""

    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    map_service = MapService(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        schemas=[const.MAP_SERVICE_SCHEMA],
        entity_ids=[],
    )
    expected_result = SearchResponse[MapService](
        total_results=1,
        items_per_page=1,
        start_index=1,
        resources=[map_service],
    )
    expected = expected_result.resources[0]
    mocker.patch("server.services.repositories.build_search_query", return_value=criteria)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", return_value=expected_result)
    mocker.patch("server.services.repositories.resolve_repository_id", return_value="repo1")

    result = repositories.search(criteria)

    actual = result.resources[0]
    assert isinstance(result, SearchResult)
    assert result.total == expected_result.total_results
    assert result.page_size == expected_result.items_per_page
    assert result.offset == expected_result.start_index
    assert len(result.resources) == len(expected_result.resources)
    assert isinstance(result.resources[0], RepositorySummary)
    assert actual.id == expected.id
    assert actual.service_name == expected.service_name
    assert actual.service_url == expected.service_url
    assert actual.entity_ids == [eid.value for eid in (expected.entity_ids or [])]


def test_search_returns_raw_response(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests that the raw SearchResponse is returned when raw=True is specified."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id="repo1")
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/repo1")
    service_schema = const.MAP_SERVICE_SCHEMA
    map_service = MapService(
        id=service_id,
        service_name=service_name,
        service_url=service_url,
        schemas=[service_schema],
        entity_ids=[],
    )
    expected_result = SearchResponse[MapService](
        total_results=1,
        items_per_page=1,
        start_index=1,
        resources=[map_service],
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=criteria)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", return_value=expected_result)

    result = repositories.search(criteria, raw=True)

    assert result is expected_result


def test_search_raises_oauth_token_error_on_unauthorized(app: Flask, mocker: MockerFixture) -> None:
    """Tests that OAuthTokenError is raised when search receives an unauthorized response."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.UNAUTHORIZED
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.search", side_effect=http_error)

    msg = "Access token is invalid or expired"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.search(criteria)


def test_search_raises_unexpected_response_error_on_internal_server_error(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on internal server error during search."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.search", side_effect=http_error)

    msg = "E031 | Received unexpected response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.search(criteria)


def test_search_raises_unexpected_response_error_on_request_exception(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on request exception during search."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", side_effect=requests.RequestException("fail"))

    msg = "Failed to communicate with mAP Core API"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.search(criteria)


def test_search_raises_unexpected_response_error_on_validation_error(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on validation error during search."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", side_effect=ValidationError("fail", []))

    msg = "E034 | Failed to parse response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.search(criteria)


def test_search_raises_oauth_token_error_directly(mocker: MockerFixture) -> None:
    """Test: search() re-raises OAuthTokenError from build_search_query (except block coverage)"""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", side_effect=OAuthTokenError("token error"))

    with pytest.raises(OAuthTokenError, match="token error"):
        repositories.search(criteria)


def test_search_raises_credentials_error_directly(mocker: MockerFixture) -> None:
    """Test: search() re-raises CredentialsError from build_search_query (except block coverage)"""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    mocker.patch("server.services.repositories.build_search_query", return_value=criteria)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", side_effect=CredentialsError("cred error"))

    with pytest.raises(CredentialsError, match="cred error"):
        repositories.search(criteria)


def test_search_raises_invalid_query_error_direct(mocker: MockerFixture) -> None:
    """Tests that InvalidQueryError is raised directly from build_search_query."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_search_query", side_effect=InvalidQueryError("criteria error"))

    msg = "criteria error"
    with pytest.raises(InvalidQueryError, match=msg):
        repositories.search(criteria)


def test_search_raises_oauth_token_error_direct(mocker: MockerFixture) -> None:
    """Tests that OAuthTokenError is raised directly from build_search_query."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_search_query", side_effect=OAuthTokenError("token error"))

    msg = "token error"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.search(criteria)


def test_search_raises_credentials_error_direct(mocker: MockerFixture) -> None:
    """Tests that CredentialsError is raised directly from build_search_query."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_search_query", side_effect=CredentialsError("cred error"))

    msg = "cred error"
    with pytest.raises(CredentialsError, match=msg):
        repositories.search(criteria)


def test_search_raises_invalid_query_error_on_map_error(app, mocker: MockerFixture) -> None:
    """Tests that InvalidQueryError is raised when MapError is returned from search."""
    criteria = make_criteria_object("repositories", q="test", i=["repo1"])
    build_search_query = SearchRequestParameter(
        filter='(serviceName co "test") or (entity_ids.value co "repo1")',
        start_index=1,
        count=10,
        sort_by="serviceName",
        sort_order="ascending",
    )
    map_error = MapError(detail="invalid query", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.build_search_query", return_value=build_search_query)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.search", return_value=map_error)

    msg = "E050 | Unsupported search filter or combination of filters."
    with pytest.raises(InvalidQueryError, match=msg):
        repositories.search(criteria)


def test_get_by_id_success(app, mocker: MockerFixture, test_config) -> None:
    """Tests successful retrieval of a repository by ID with raw response."""

    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id="repo1")
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/repo1")
    service_schema = const.MAP_SERVICE_SCHEMA
    map_service = MapService(
        id=service_id,
        service_name=service_name,
        service_url=service_url,
        schemas=[service_schema],
        entity_ids=[],
    )
    mocker.patch("server.services.repositories.resolve_service_id", return_value=service_id)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", return_value=map_service)

    result = repositories.get_by_id("repo1", raw=True)

    assert result is map_service


def test_get_by_id_success_false(app, mocker: MockerFixture, test_config) -> None:
    """Tests that get_by_id returns RepositoryDetail when raw is False (default)."""
    repository_id = "repo1"
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id="repo1")
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/repo1")
    service_schema = const.MAP_SERVICE_SCHEMA
    map_service = MapService(
        id=service_id,
        service_name=service_name,
        service_url=service_url,
        schemas=[service_schema],
        entity_ids=[ServiceEntityID(value="e1"), ServiceEntityID(value="e2")],
    )
    mocker.patch("server.services.repositories.resolve_service_id", return_value=service_id)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", return_value=map_service)

    result = repositories.get_by_id("repo1")

    assert isinstance(result, RepositoryDetail)
    assert result.id == repository_id
    assert result.service_name == service_name
    assert str(result.service_url) == str(service_url)
    assert result.entity_ids == ["e1", "e2"]


def test_get_by_id_more_detail(app, mocker: MockerFixture, test_config) -> None:
    """Tests that get_by_id returns RepositoryDetail with more_detail=True."""
    repository_id = "repo1"
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id=repository_id)
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/repo1")
    service_schema = const.MAP_SERVICE_SCHEMA
    map_service = MapService(
        id=service_id,
        service_name=service_name,
        service_url=service_url,
        schemas=[service_schema],
        entity_ids=[],
    )
    mocker.patch("server.services.repositories.resolve_service_id", return_value=service_id)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", return_value=map_service)

    result = repositories.get_by_id("repo1", more_detail=True)

    assert isinstance(result, RepositoryDetail)
    assert result.id == repository_id
    assert result.service_name == service_name
    assert str(result.service_url) == str(service_url)


def test_get_by_id_returns_none_on_map_error(app, mocker: MockerFixture, test_config) -> None:
    """Tests that get_by_id returns None when MapError is returned."""
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id="repo1")
    map_error = MapError(detail="not found", status="404", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.resolve_service_id", return_value=service_id)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", return_value=map_error)

    result = repositories.get_by_id("repo1")

    assert result is None


def test_get_by_id_raises_oauth_token_error_on_unauthorized(app: Flask, mocker: MockerFixture) -> None:
    """Tests that OAuthTokenError is raised when get_by_id receives an unauthorized response."""
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.UNAUTHORIZED
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.get_by_id", side_effect=http_error)

    msg = "E027 | Access token is invalid or expired."
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.get_by_id("repo1")


def test_get_by_id_raises_unexpected_response_error_on_internal_server_error(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on internal server error during get_by_id."""
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.get_by_id", side_effect=http_error)

    msg: str = "E031 | Received unexpected response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.get_by_id("repo1")


def test_get_by_id_raises_unexpected_response_error_on_request_exception(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on request exception during get_by_id."""
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", side_effect=requests.RequestException("fail"))

    msg: str = "E033 | Failed to communicate with mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.get_by_id("repo1")


def test_get_by_id_raises_unexpected_response_error_on_validation_error(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on validation error during get_by_id."""
    msg: str = "Failed to parse response from mAP Core API"
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", side_effect=ValidationError("fail", []))

    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.get_by_id("repo1")


def test_get_by_id_raises_oauth_token_error_direct(mocker: MockerFixture) -> None:
    """Tests that OAuthTokenError is raised directly from get_by_id."""
    msg: str = "token error"
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", side_effect=OAuthTokenError("token error"))

    with pytest.raises(OAuthTokenError, match=msg):
        repositories.get_by_id("repo1")


def test_get_by_id_raises_credentials_error_direct(mocker: MockerFixture) -> None:
    """Tests that CredentialsError is raised directly from get_by_id."""
    msg: str = "cred error"
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.get_by_id", side_effect=CredentialsError("cred error"))

    with pytest.raises(CredentialsError, match=msg):
        repositories.get_by_id("repo1")


def test_get_by_id_raises_unexpected_response_error_on_other_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Tests that UnexpectedResponseError is raised on non-401/500 HTTP errors during get_by_id."""
    msg: str = "E031 | Received unexpected response from mAP Core API."
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.BAD_REQUEST
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.get_by_id", side_effect=http_error)

    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.get_by_id("repo1")


def test_create_success(app, mocker: MockerFixture, test_config) -> None:
    """Tests successful creation of a repository and validates the returned RepositoryDetail."""

    repository_id = "repo1"
    role_groups: list = [["group1"], ["group2"]]
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id=repository_id)
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/repo1")
    service_schema = const.MAP_SERVICE_SCHEMA
    repo = RepositoryDetail(id=service_id, service_name=service_name, service_url=service_url, entity_ids=[])
    map_service = MapService(
        id=service_id, service_name=service_name, service_url=service_url, schemas=[service_schema], entity_ids=[]
    )
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_service", return_value=(map_service, service_id))
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=role_groups)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", return_value=map_service)
    mocker.patch("server.services.repositories.current_app")

    result = repositories.create(repo)

    assert isinstance(result, RepositoryDetail)
    assert result.id == repository_id
    assert result.service_name == service_name
    assert str(result.service_url) == str(service_url)


def test_create_raises_oauth_token_error_on_unauthorized(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests that OAuthTokenError is raised when create receives an unauthorized response."""
    msg: str = "Access token is invalid or expired"
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.services.repositories.current_app")
    response = Response()
    response.status_code = HTTPStatus.UNAUTHORIZED
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.post", side_effect=http_error)

    with pytest.raises(OAuthTokenError, match=msg):
        repositories.create(repo)


def test_create_raises_unexpected_response_error_on_internal_server_error(
    app: Flask, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on internal server error during create."""
    msg: str = "E031 | Received unexpected response from mAP Core API."
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.services.repositories.current_app")
    response = Response()
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.post", side_effect=http_error)

    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.create(repo)


def test_create_raises_unexpected_response_error_on_request_exception(
    app: Flask, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on request exception during create."""
    msg: str = "E033 | Failed to communicate with mAP Core API."
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", side_effect=requests.RequestException("fail"))
    mocker.patch("server.services.repositories.current_app")

    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.create(repo)


def test_create_raises_unexpected_response_error_on_validation_error(
    app: Flask, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on validation error during create."""
    msg: str = "Failed to parse response from mAP Core API"
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", side_effect=ValidationError("fail", []))
    mocker.patch("server.services.repositories.current_app")

    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.create(repo)


def test_create_raises_oauth_token_error_direct(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests that OAuthTokenError is raised directly from create."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", side_effect=OAuthTokenError("token error"))
    mocker.patch("server.services.repositories.current_app")

    msg: str = "token error"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.create(repo)


def test_create_raises_credentials_error_direct(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests that CredentialsError is raised directly from create."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", side_effect=CredentialsError("cred error"))
    mocker.patch("server.services.repositories.current_app")

    msg: str = "cred error"
    with pytest.raises(CredentialsError, match=msg):
        repositories.create(repo)


def test_create_raises_invalid_form_error_direct(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests that InvalidFormError is raised directly from create."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", side_effect=InvalidFormError("form error"))
    mocker.patch("server.services.repositories.current_app")

    msg: str = "form error"
    with pytest.raises(InvalidFormError, match=msg):
        repositories.create(repo)


def test_create_raises_system_admin_not_found_direct(app: Flask, mocker: MockerFixture, test_config) -> None:
    """Tests that SystemAdminNotFound is raised directly from create."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", side_effect=SystemAdminNotFound("admin not found"))
    mocker.patch("server.services.repositories.current_app")

    msg: str = "admin not found"
    with pytest.raises(SystemAdminNotFound, match=msg):
        repositories.create(repo)


def test_create_raises_resource_invalid_on_map_error(app, mocker: MockerFixture, test_config) -> None:
    """Tests that ResourceInvalid is raised when MapError is returned from create."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail=r"Duplicate id '(.*)'", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "E111 | A Service resource for Repository (id: %(id)s) already exists."
    with pytest.raises(ResourceInvalid, match=msg):
        repositories.create(repo)


def test_create_map_error_no_rights_create(app, mocker: MockerFixture, test_config) -> None:
    """Test create raises OAuthTokenError when MapError.detail matches MAP_NO_RIGHTS_CREATE_PATTERN."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail=r"You do not have creation right of '(.*)'", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "E113 | No creation rights for Repository with current access token."
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.create(repo)


def test_create_map_error_unexpected_response(app, mocker: MockerFixture, test_config) -> None:
    """Test create raises UnexpectedResponseError when MapError.detail does not match known patterns."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail="some unknown error", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.users.get_system_admins", return_value=["admin"])
    mocker.patch("server.services.repositories.prepare_role_groups", return_value=[])
    mocker.patch("server.services.repositories.prepare_service", return_value=(mocker.MagicMock(), "repo1"))
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.groups.post")
    mocker.patch("server.clients.services.post", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "Received unexpected response from mAP Core API"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.create(repo)


def test_update_success(app, mocker: MockerFixture, test_config) -> None:
    """Tests successful update of a repository and validates the returned RepositoryDetail."""

    repository_id = "repo1"
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id=repository_id)
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/repo1")
    service_schema = const.MAP_SERVICE_SCHEMA
    repo = RepositoryDetail(id=service_id, service_name=service_name, service_url=service_url, entity_ids=[])
    map_service = MapService(
        id=service_id, service_name=service_name, service_url=service_url, schemas=[service_schema], entity_ids=[]
    )
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=map_service)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.patch_by_id", return_value=map_service)
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.services.repositories.current_app")
    result = repositories.update(repo)
    assert isinstance(result, RepositoryDetail)
    assert result.id == repository_id
    assert result.service_name == service_name
    assert str(result.service_url) == str(service_url)


def test_update_calls_update_put_when_strategy_put(app, mocker: MockerFixture, test_config) -> None:
    """Tests that update delegates to update_put when config.MAP_CORE.update_strategy == 'put'."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")
    mock_update_put = mocker.patch("server.services.repositories.update_put", return_value="called")

    result = repositories.update(repo)

    assert result == "called"
    assert mock_update_put.called


def test_update_raises_resource_not_found_on_none(app, mocker: MockerFixture, test_config) -> None:
    """Tests that ResourceNotFound is raised when get_by_id returns None during update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=None)

    msg: str = "E104 | Service resource for Repository (id: repo1) not found."
    with pytest.raises(ResourceNotFound, match=msg):
        repositories.update(repo)


def test_update_raises_invalid_form_error_on_service_url_update(app, mocker: MockerFixture, test_config) -> None:
    """Tests that InvalidFormError is raised when service_url is updated during update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    current_url: HttpUrl = HttpUrl("https://other.com")
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    current = RepositoryDetail(id="repo1", service_name="s", service_url=current_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=current)

    msg: str = "E150 | Service URL of Repository cannot be updated."
    with pytest.raises(InvalidFormError, match=msg):
        repositories.update(repo)


def test_update_raises_oauth_token_error_on_unauthorized(app, mocker: MockerFixture, test_config) -> None:
    """Tests that OAuthTokenError is raised when update receives an unauthorized response."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    response = Response()
    response.status_code = HTTPStatus.UNAUTHORIZED
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.patch_by_id", side_effect=http_error)

    msg: str = "Access token is invalid or expired"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.update(repo)


def test_update_raises_unexpected_response_error_on_internal_server_error(
    app, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on internal server error during update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    response = Response()
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.patch_by_id", side_effect=http_error)

    msg: str = "E500 | An unexpected error occurred in the server application."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update(repo)


def test_update_raises_unexpected_response_error_on_request_exception(app, mocker: MockerFixture, test_config) -> None:
    """Tests that UnexpectedResponseError is raised on request exception during update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.clients.services.patch_by_id", side_effect=requests.RequestException("fail"))

    msg: str = "E033 | Failed to communicate with mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update(repo)


def test_update_raises_unexpected_response_error_on_validation_error(app, mocker: MockerFixture, test_config) -> None:
    """Tests that UnexpectedResponseError is raised on validation error during update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.clients.services.patch_by_id", side_effect=ValidationError("fail", []))

    msg: str = "Failed to parse response from mAP Core API"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update(repo)


def test_update_raises_oauth_token_error_direct(app, mocker: MockerFixture, test_config) -> None:
    """Tests that OAuthTokenError is raised directly from update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.clients.services.patch_by_id", side_effect=OAuthTokenError("token error"))

    msg: str = "token error"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.update(repo)


def test_update_raises_credentials_error_direct(app, mocker: MockerFixture, test_config) -> None:
    """Tests that CredentialsError is raised directly from update."""

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.clients.services.patch_by_id", side_effect=CredentialsError("cred error"))

    msg: str = "cred error"
    with pytest.raises(CredentialsError, match=msg):
        repositories.update(repo)


def test_update_raises_resource_not_found_on_map_error(app, mocker: MockerFixture, test_config) -> None:
    """Tests that ResourceNotFound is raised when MapError.detail matches MAP_NOT_FOUND_PATTERN during update."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    map_error = MapError(detail="Repository 'repo1' Not Found", status="404", scim_type="invalidSyntax")
    mocker.patch("server.clients.services.patch_by_id", return_value=map_error)

    msg: str = "not found"
    with pytest.raises(ResourceNotFound, match=msg):
        repositories.update(repo)


def test_update_map_error_no_rights_update(app, mocker: MockerFixture, test_config) -> None:
    """Test update raises OAuthTokenError when MapError.detail matches MAP_NO_RIGHTS_UPDATE_PATTERN."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail="No update rights for 'repo1'", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.clients.services.patch_by_id", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "E123 | No update rights for Repository (id: repo1) with current access token."
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.update(repo)


def test_update_map_error_unexpected_response(app, mocker: MockerFixture, test_config) -> None:
    """Test update raises UnexpectedResponseError when MapError.detail does not match known patterns."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail="some unknown update error", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.build_patch_operations", return_value=[])
    mocker.patch("server.clients.services.patch_by_id", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "Received unexpected response from mAP Core API"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update(repo)


def test_update_put_success(app, mocker: MockerFixture, test_config) -> None:
    """Tests successful update (PUT) of a repository and validates the returned RepositoryDetail."""

    repository_id = "repo1"
    service_id = test_config.REPOSITORIES.id_patterns.sp_connector.format(repository_id=repository_id)
    service_name = test_config.SP.entity_id
    service_url: HttpUrl = HttpUrl(f"https://{test_config.POSTGRES.host}/{repository_id}")
    service_schema = const.MAP_SERVICE_SCHEMA
    repo = RepositoryDetail(id=service_id, service_name=service_name, service_url=service_url, entity_ids=[])
    map_service = MapService(
        id=service_id, service_name=service_name, service_url=service_url, schemas=[service_schema], entity_ids=[]
    )
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=map_service)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", return_value=map_service)
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")
    mocker.patch("server.services.repositories.current_app")
    result = repositories.update_put(repo)
    assert isinstance(result, RepositoryDetail)
    assert result.id == repository_id
    assert result.service_name == service_name
    assert str(result.service_url) == str(service_url)


def test_update_put_calls_update_when_strategy_patch(app, mocker: MockerFixture, test_config) -> None:
    """Tests that update_put delegates to update when config.MAP_CORE.update_strategy == 'patch'."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "patch")
    mock_update = mocker.patch("server.services.repositories.update", return_value="called")

    result = repositories.update_put(repo)

    assert result == "called"
    assert mock_update.called


def test_update_put_raises_resource_not_found_on_none(app, mocker: MockerFixture, test_config) -> None:
    """Tests that ResourceNotFound is raised when get_by_id returns None during update_put."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=None)

    msg: str = "E104 | Service resource for Repository (id: repo1) not found."
    with pytest.raises(ResourceNotFound, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_invalid_form_error_on_service_url_update(app, mocker: MockerFixture, test_config) -> None:
    """Tests that InvalidFormError is raised when service_url is updated during update_put."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    current_url: HttpUrl = HttpUrl("https://other.com")
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    current = RepositoryDetail(id="repo1", service_name="s", service_url=current_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=current)

    msg: str = "E150 | Service URL of Repository cannot be updated."
    with pytest.raises(InvalidFormError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_oauth_token_error_on_unauthorized(app, mocker: MockerFixture, test_config) -> None:
    """Tests that OAuthTokenError is raised when update_put receives an unauthorized response."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.UNAUTHORIZED
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.put_by_id", side_effect=http_error)

    msg: str = "Access token is invalid or expired"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_unexpected_response_error_on_internal_server_error(
    app, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on internal server error during update_put."""

    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    response = Response()
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.put_by_id", side_effect=http_error)

    msg: str = "E500 | An unexpected error occurred in the server application."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_unexpected_response_error_on_request_exception(
    app, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on request exception during update_put."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", side_effect=requests.RequestException("fail"))

    msg: str = "E021 | Failed to connect to Redis: %(error)s"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_unexpected_response_error_on_validation_error(
    app, mocker: MockerFixture, test_config
) -> None:
    """Tests that UnexpectedResponseError is raised on validation error during update_put."""

    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", side_effect=ValidationError("fail", []))

    msg: str = "Failed to parse response from mAP Core API"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_oauth_token_error_direct(app, mocker: MockerFixture, test_config) -> None:
    """Tests that OAuthTokenError is raised directly from update_put."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", side_effect=OAuthTokenError("token error"))

    msg: str = "token error"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_credentials_error_direct(app, mocker: MockerFixture, test_config) -> None:
    """Tests that CredentialsError is raised directly from update_put."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")

    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", side_effect=CredentialsError("cred error"))

    msg: str = "cred error"
    with pytest.raises(CredentialsError, match=msg):
        repositories.update_put(repo)


def test_update_put_raises_resource_not_found_on_map_error(app, mocker: MockerFixture, test_config) -> None:
    """Tests that ResourceNotFound is raised when MapError.detail matches MAP_NOT_FOUND_PATTERN during update_put."""
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    map_error = MapError(detail="Repository 'repo1' Not Found", status="404", scim_type="invalidSyntax")
    mocker.patch("server.clients.services.put_by_id", return_value=map_error)

    msg: str = "E104 | Service resource for Repository (id: repo1) not found."
    with pytest.raises(ResourceNotFound, match=msg):
        repositories.update_put(repo)


def test_update_put_map_error_no_rights_update_true(app, mocker: MockerFixture, test_config) -> None:
    """Test update_put raises Error when MapError.detail matches MAP_NO_RIGHTS_UPDATE_PATTERN (True branch)."""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail="No update rights for 'repo1'", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "E123 | No update rights for Repository (id: repo1) with current access token."
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.update_put(repo)


def test_update_put_map_error_no_rights_update_false(app, mocker: MockerFixture, test_config) -> None:
    """Test update_put raises Error when MapError.detail does NOT match MAP_NO_RIGHTS_UPDATE_PATTERN"""
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    repo = RepositoryDetail(id="repo1", service_name="s", service_url=service_url, entity_ids=[])
    map_error = MapError(detail="Some unknown update error", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.validate_repository_to_map_service", return_value=repo)
    mocker.patch("server.config.config.MAP_CORE.update_strategy", "put")
    mocker.patch("server.services.repositories.get_by_id", return_value=repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.put_by_id", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")

    msg: str = "Received unexpected response from mAP Core API"
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.update_put(repo)


def test_delete_by_id_success(app, test_config, mocker: MockerFixture) -> None:
    """Tests successful deletion of a repository by ID and verifies the correct call arguments."""

    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)

    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.services.repositories.current_app")
    mock_delete = mocker.patch("server.clients.services.delete_by_id", return_value=None)
    mocker.patch("server.services.groups.delete_multiple")

    repositories.delete_by_id("repo1", test_config.SP.entity_id)

    mock_delete.assert_called_once_with("repo1", access_token="token", client_secret="secret")


def test_delete_by_id_raises_resource_not_found_if_repo_missing(app, test_config, mocker: MockerFixture) -> None:
    """Tests that ResourceNotFound is raised if get_by_id returns None in delete_by_id."""
    mocker.patch("server.services.repositories.get_by_id", return_value=None)

    msg: str = "E104 | Service resource for Repository (id: missing_repo) not found."
    with pytest.raises(ResourceNotFound, match=msg):
        repositories.delete_by_id("missing_repo", test_config.SP.entity_id)


def test_delete_by_id_raises_invalid_form_error_if_service_name_mismatch(app, mocker: MockerFixture) -> None:
    """Tests that InvalidFormError is raised if service_name does not match in delete_by_id."""
    dummy_map_service = MapService(
        id="repo1",
        service_name="actual_service",
    )
    mocker.patch("server.services.repositories.get_by_id", return_value=dummy_map_service)

    msg: str = "does not match"
    with pytest.raises(InvalidFormError, match=msg):
        repositories.delete_by_id("repo1", "wrong_service")


def test_delete_by_id_raises_oauth_token_error_on_unauthorized(app, test_config, mocker: MockerFixture) -> None:
    """Tests that OAuthTokenError is raised when delete_by_id receives an unauthorized response."""
    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    response = Response()
    response.status_code = HTTPStatus.UNAUTHORIZED
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.delete_by_id", side_effect=http_error)

    msg: str = "Access token is invalid or expired"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_raises_unexpected_response_error_on_internal_server_error(
    app, test_config, mocker: MockerFixture
) -> None:
    """Tests that UnexpectedResponseError is raised on internal server error during delete_by_id."""
    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    response = Response()
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    http_error = requests.HTTPError(response=response)
    mocker.patch("server.clients.services.delete_by_id", side_effect=http_error)

    msg: str = "E500 | An unexpected error occurred in the server application."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_raises_unexpected_response_error_on_request_exception(
    app, test_config, mocker: MockerFixture
) -> None:
    """Tests that UnexpectedResponseError is raised on request exception during delete_by_id."""
    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.clients.services.delete_by_id", side_effect=requests.RequestException("fail"))

    msg: str = "E033 | Failed to communicate with mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_raises_unexpected_response_error_on_validation_error_(
    app, test_config, mocker: MockerFixture
) -> None:
    """Tests that UnexpectedResponseError is raised on ValidationError during delete_by_id."""
    dummy_repo = RepositoryDetail(id="repo1", service_name=test_config.SP.entity_id)
    dummy_repo._groups = []  # noqa: SLF001
    dummy_repo._rolegroups = []  # noqa: SLF001
    mocker.patch("server.services.repositories.get_by_id", return_value=dummy_repo)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.clients.services.delete_by_id", side_effect=ValidationError("fail", []))

    msg: str = "Failed to parse response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_raises_oauth_token_error_direct(app, test_config, mocker: MockerFixture) -> None:
    """Tests that OAuthTokenError is raised directly from delete_by_id."""
    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.clients.services.delete_by_id", side_effect=OAuthTokenError("token error"))

    msg: str = "token error"
    with pytest.raises(OAuthTokenError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_raises_credentials_error_direct(app, test_config, mocker: MockerFixture) -> None:
    """Tests that CredentialsError is raised directly from delete_by_id."""
    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    mocker.patch("server.clients.services.delete_by_id", side_effect=CredentialsError("cred error"))

    msg: str = "cred error"
    with pytest.raises(CredentialsError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_raises_resource_not_found_on_map_error(app, test_config, mocker: MockerFixture) -> None:
    """Tests that ResourceNotFound is raised when MapError indicates not found during delete_by_id."""
    dummy_map_service = MapService(
        id="repo1",
        service_name=test_config.SP.entity_id,
    )
    mocker.patch("server.clients.services.get_by_id", return_value=dummy_map_service)
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")
    map_error = MapError(detail="Repository 'repo1' Not Found", status="404", scim_type="invalidSyntax")
    mocker.patch("server.clients.services.delete_by_id", return_value=map_error)

    msg: str = "not found"
    with pytest.raises(ResourceNotFound, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)


def test_delete_by_id_map_error_e031(app, test_config, mocker: MockerFixture) -> None:
    """Test delete_by_id raises UnexpectedResponseErrorwhen MapError.detail does not match MAP_NOT_FOUND_PATTERN."""
    map_error = MapError(detail="unexpected error", status="400", scim_type="invalidSyntax")
    mocker.patch("server.services.repositories.get_access_token", return_value="token")
    mocker.patch("server.services.repositories.get_client_secret", return_value="secret")
    mocker.patch("server.clients.services.delete_by_id", return_value=map_error)
    mocker.patch("server.services.repositories.current_app")
    dummy_repo = RepositoryDetail(id="repo1", service_name=test_config.SP.entity_id)
    dummy_repo._groups = []  # noqa: SLF001
    dummy_repo._rolegroups = []  # noqa: SLF001
    mocker.patch("server.services.repositories.get_by_id", return_value=dummy_repo)
    mocker.patch("server.services.repositories.resolve_service_id", return_value="repo1")

    msg: str = "E031 | Received unexpected response from mAP Core API."
    with pytest.raises(UnexpectedResponseError, match=msg):
        repositories.delete_by_id("repo1", test_config.SP.entity_id)
