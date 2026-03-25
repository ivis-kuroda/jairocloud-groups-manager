import inspect
import typing as t

from pydantic import HttpUrl

from server.api import repositories
from server.api.schemas import ErrorResponse, RepositoriesQuery, RepositoryDeleteQuery, SearchResult
from server.entities.repository_detail import RepositoryDetail
from server.exc import InvalidFormError, InvalidQueryError, ResourceInvalid, ResourceNotFound


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_success(app, mocker: MockerFixture) -> None:
    """Test: /repositories GET returns repository list successfully."""
    expected_status = 200

    expected = SearchResult(total=1, page_size=1, offset=0, resources=[])
    mocker.patch("server.services.repositories.search", return_value=expected)

    original_func = inspect.unwrap(repositories.get)

    response = original_func(RepositoriesQuery(q=None, i=None, k=None, d=None, p=None))
    data, status, *_ = response
    assert status == expected_status
    assert isinstance(data, SearchResult)
    assert data.total == expected.total
    assert data.page_size == expected.page_size
    assert data.offset == expected.offset
    assert data.resources == expected.resources


def test_get_invalid_query_error(app, mocker: MockerFixture) -> None:
    """Test: /repositories GET returns 400 error for invalid query."""
    expected_status = 400

    mocker.patch("server.services.repositories.search", side_effect=InvalidQueryError("Invalid query"))

    original_func = inspect.unwrap(repositories.get)

    response = original_func(RepositoriesQuery(q="search", i=["repo1"], k="created", d="desc", p=3, l=20))
    data, status, *_ = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert "Invalid query" in data.message


def test_post_success(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories POST creates a repository successfully."""
    expected_status = 201
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    mocker.patch("server.services.repositories.create", return_value=expected)
    original_func = inspect.unwrap(repositories.post)

    response = original_func(expected)
    data, status, *_ = response
    assert status == expected_status
    assert isinstance(data, RepositoryDetail)
    assert data.id == "repo1"
    assert data.service_name == "TestRepo"


def test_post_invalid_form_error(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories POST returns 400 error for invalid form."""
    expected_status = 400
    mocker.patch("server.services.repositories.create", side_effect=InvalidFormError("invalid form"))
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    original_func = inspect.unwrap(repositories.post)

    response = original_func(expected)
    data, status, *_ = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "invalid form"
    assert not data.code


def test_post_resource_invalid_error(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories POST returns 409 error for resource invalid."""
    expected_status = 409
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    mocker.patch("server.services.repositories.create", side_effect=ResourceInvalid("resource invalid"))
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    original_func = inspect.unwrap(repositories.post)

    response = original_func(expected)
    data, status, *_ = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "resource invalid"
    assert not data.code


def test_id_get_success(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> GET returns repository detail successfully."""
    expected_status = 200
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    mocker.patch("server.api.repositories.has_permission", return_value=True)
    mocker.patch("server.services.repositories.get_by_id", return_value=expected)
    original_func = inspect.unwrap(repositories.id_get)
    response = original_func("repo1")
    data, status = response
    assert status == expected_status
    assert isinstance(data, RepositoryDetail)
    assert data.id == "repo1"
    assert data.service_name == "TestRepo"


def test_id_get_not_found_error(app, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> GET returns 404 error for not found."""
    expected_status = 404
    mocker.patch("server.api.repositories.has_permission", return_value=True)
    mocker.patch("server.services.repositories.get_by_id", return_value=None)
    original_func = inspect.unwrap(repositories.id_get)
    response = original_func("repo1")
    data, status = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "Service resource for Repository (id: repo1) not found."
    assert data.code == "E104"


def test_id_get_permission_error(app, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> GET returns 403 error for permission denied."""
    expected_status = 403

    dummy_repo = RepositoryDetail(
        id="repo1",
        service_name="repo1",
    )
    mocker.patch("server.services.repositories.get_by_id", return_value=dummy_repo)
    mocker.patch("server.api.repositories.has_permission", return_value=False)
    original_func = inspect.unwrap(repositories.id_get)
    response = original_func("repo1")
    data, status = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "Logged-in user does not have permission to access this Repository (id: repo1)."
    assert data.code == "E103"


def test_id_put_success(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> PUT updates repository successfully."""
    expected_status = 200
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    mocker.patch("server.api.repositories.has_permission", return_value=True)
    mocker.patch("server.services.repositories.update", return_value=expected)
    original_func = inspect.unwrap(repositories.id_put)
    response = original_func("repo1", expected)
    data, status = response
    assert status == expected_status
    assert isinstance(data, RepositoryDetail)
    assert data.id == "repo1"
    assert data.service_name == "TestRepo"


def test_id_put_invalid_form_error(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> PUT returns 400 error for invalid form."""

    expected_status = 400
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    mocker.patch("server.api.repositories.has_permission", return_value=True)
    mocker.patch("server.services.repositories.update", side_effect=InvalidFormError("invalid form"))
    original_func = inspect.unwrap(repositories.id_put)
    response = original_func("repo1", expected)
    data, status = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "invalid form"
    assert not data.code


def test_id_put_not_found_error(app, test_config, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> PUT returns 404 error for not found."""

    expected_status = 404
    service_url: HttpUrl = HttpUrl(test_config.MAP_CORE.base_url)
    expected = RepositoryDetail(
        id="repo1",
        service_name="TestRepo",
        service_url=service_url,
        entity_ids=[],
        active=True,
        service_id="svc1",
        created=None,
        users_count=None,
        groups_count=None,
    )
    mocker.patch("server.api.repositories.has_permission", return_value=True)
    mocker.patch("server.services.repositories.update", side_effect=ResourceNotFound("not found"))
    original_func = inspect.unwrap(repositories.id_put)
    response = original_func("repo1", expected)
    data, status = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "not found"
    assert not data.code


def test_id_delete_success(app, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> DELETE deletes repository successfully."""
    expected_status = 204
    query = RepositoryDeleteQuery(confirmation="delete")
    mocker.patch("server.services.repositories.delete_by_id", return_value=None)
    original_func = inspect.unwrap(repositories.id_delete)
    response = original_func("repo1", query)
    data, status = response
    assert status == expected_status
    assert not data


def test_id_delete_invalid_form_error(app, mocker: MockerFixture) -> None:
    expected_status = 400
    query = RepositoryDeleteQuery(confirmation="delete")
    mocker.patch("server.services.repositories.delete_by_id", side_effect=InvalidFormError("invalid form"))
    original_func = inspect.unwrap(repositories.id_delete)
    response, status = original_func("repo1", query)
    assert status == expected_status
    assert isinstance(response, ErrorResponse)
    assert response.message == "invalid form"
    assert not response.code


def test_id_delete_not_found_error(app, mocker: MockerFixture) -> None:
    """Test: /repositories/<id> DELETE returns 404 error for not found."""
    expected_status = 404
    query = RepositoryDeleteQuery(confirmation="delete")
    mocker.patch("server.services.repositories.delete_by_id", side_effect=ResourceNotFound("not found"))
    original_func = inspect.unwrap(repositories.id_delete)
    response = original_func("repo1", query)
    data, status = response
    assert status == expected_status
    assert isinstance(data, ErrorResponse)
    assert data.message == "not found"
    assert not data.code


def test_has_permission_system_admin(mocker: MockerFixture) -> None:
    """Test: has_permission returns True for system admin."""

    mocker.patch("server.api.repositories.is_current_user_system_admin", return_value=True)
    result = repositories.has_permission("repo1")
    assert result is True


def test_has_permission_permitted_repo(mocker: MockerFixture) -> None:
    """Test: has_permission returns True for permitted repository."""
    mocker.patch("server.api.repositories.is_current_user_system_admin", return_value=False)
    mocker.patch("server.api.repositories.get_permitted_repository_ids", return_value=["repo1", "repo2"])

    result = repositories.has_permission("repo1")
    assert result is True


def test_has_permission_not_permitted(mocker: MockerFixture) -> None:
    """Test: has_permission returns False for not permitted repository."""
    mocker.patch("server.api.repositories.is_current_user_system_admin", return_value=False)
    mocker.patch("server.api.repositories.get_permitted_repository_ids", return_value=["repo2", "repo3"])

    result = repositories.has_permission("repo1")
    assert result is False


def test_filter_options_calls_search_repositories_options(app, mocker: MockerFixture) -> None:
    dummy = ["dummy_option"]
    mock = mocker.patch("server.api.repositories.search_repositories_options", return_value=dummy)
    original_func = inspect.unwrap(repositories.filter_options)
    result = original_func()
    assert result == dummy
    mock.assert_called_once_with()
