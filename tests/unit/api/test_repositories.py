import typing as t

from http import HTTPStatus

import server.api.repositories

from server.api import repositories
from server.api.schemas import ErrorResponse, RepositoriesQuery, RepositoryDeleteQuery, SearchResult
from server.entities.search_request import FilterOption
from server.exc import InvalidFormError, InvalidQueryError, ResourceInvalid, ResourceNotFound
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get(repository_summaries, mocker: MockerFixture):
    total, page_size, offset = len(repository_summaries), len(repository_summaries), 0
    searched = expected = SearchResult(total=total, page_size=page_size, offset=offset, resources=repository_summaries)
    mock_search = mocker.patch.object(server.api.repositories.RepositoryService, "search", return_value=searched)
    query = RepositoriesQuery()

    res, status = unwrap(repositories.get)(query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_search.assert_called_once_with(query)


def test_get_invalid_query_error(mocker: MockerFixture):
    mock_search = mocker.patch.object(server.api.repositories.RepositoryService, "search")
    mock_search.side_effect = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)
    query = RepositoriesQuery()

    res, status = unwrap(repositories.get)(query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNSUPPORTED_SEARCH_FILTER)


def test_post(use_blueprint, app, test_config, repository_details, mocker: MockerFixture):
    server_name = test_config.SERVER_NAME
    body = expected = repository_details[0]
    mock_create = mocker.patch.object(server.api.repositories.RepositoryService, "create", return_value=expected)

    res, status, header = unwrap(repositories.post)(body)

    assert status == HTTPStatus.CREATED
    assert res == expected
    assert header["Location"] == f"https://{server_name}/api/repositories/{expected.id}"
    mock_create.assert_called_once_with(body)


def test_post_invalid_form_error(repository_details, mocker: MockerFixture):
    body = repository_details[0]
    mock_create = mocker.patch.object(server.api.repositories.RepositoryService, "create")
    mock_create.side_effect = InvalidFormError(E.REPOSITORY_REQUIRES_ENTITY_ID)

    res, status, *_ = unwrap(repositories.post)(body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_REQUIRES_ENTITY_ID)
    assert not _


def test_post_conflict(repository_details, mocker: MockerFixture):
    body = repository_details[0]
    mock_create = mocker.patch.object(server.api.repositories.RepositoryService, "create")
    mock_create.side_effect = ResourceInvalid(E.REPOSITORY_DUPLICATE_ID % {"id": body.id})

    res, status, *_ = unwrap(repositories.post)(body)

    assert status == HTTPStatus.CONFLICT
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_DUPLICATE_ID, {"id": body.id})
    assert not _


def test_id_get(repository_details, mocker: MockerFixture):
    target = expected = repository_details[0]
    mock_get = mocker.patch.object(server.api.repositories.RepositoryService, "get_by_id", return_value=target)
    mocker.patch.object(server.api.repositories, "has_permission", return_value=True)

    res, status = unwrap(repositories.id_get)(target.id)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_get.assert_called_once_with(target.id, more_detail=True)


def test_id_get_not_found(app, mocker: MockerFixture, caplog):
    rid = "non-existent-repo"
    mocker.patch.object(server.api.repositories.RepositoryService, "get_by_id", return_value=None)
    mock_permission = mocker.patch.object(server.api.repositories, "has_permission")

    res, status = unwrap(repositories.id_get)(rid)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_NOT_FOUND, {"id": rid})
    assert_message(caplog.records[0].message, E.REPOSITORY_NOT_FOUND, {"id": rid})
    mock_permission.assert_not_called()


def test_id_get_forbidden(app, repository_details, mocker: MockerFixture, caplog):
    target = repository_details[0]
    mocker.patch.object(server.api.repositories.RepositoryService, "get_by_id", return_value=target)
    mock_permission = mocker.patch.object(server.api.repositories, "has_permission", return_value=False)

    res, status = unwrap(repositories.id_get)(target.id)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_FORBIDDEN, {"id": target.id})
    assert_message(caplog.records[0].message, E.REPOSITORY_FORBIDDEN, {"id": target.id})
    mock_permission.assert_called_once_with(target.id)


def test_id_put(repository_details, mocker: MockerFixture):
    body = expected = repository_details[0]
    rid, body.id = body.id, None
    mock_update = mocker.patch.object(server.api.repositories.RepositoryService, "update", return_value=body)
    mock_permission = mocker.patch.object(server.api.repositories, "has_permission")

    res, status = unwrap(repositories.id_put)(rid, body)

    assert status == HTTPStatus.OK
    assert res == expected
    assert body.id == rid
    mock_update.assert_called_once_with(body)
    mock_permission.assert_not_called()  # not to check (system admin only)


def test_id_put_invalid_form_error(repository_details, mocker: MockerFixture):
    body = repository_details[0]
    mock_update = mocker.patch.object(server.api.repositories.RepositoryService, "update")
    mock_update.side_effect = InvalidFormError(E.REPOSITORY_REQUIRES_ENTITY_ID)

    res, status = unwrap(repositories.id_put)(body.id, body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_REQUIRES_ENTITY_ID)


def test_id_put_not_found(repository_details, mocker: MockerFixture):
    body = repository_details[0]
    mock_update = mocker.patch.object(server.api.repositories.RepositoryService, "update")
    mock_update.side_effect = ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": body.id})

    res, status = unwrap(repositories.id_put)(body.id, body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_NOT_FOUND, {"id": body.id})


def test_id_delete(repository_details, mocker: MockerFixture):
    target = repository_details[0]
    mock_delete = mocker.patch.object(server.api.repositories.RepositoryService, "delete_by_id")
    query = RepositoryDeleteQuery(confirmation=target.service_name)

    res, status = unwrap(repositories.id_delete)(target.id, query)

    assert status == HTTPStatus.NO_CONTENT
    assert not res
    mock_delete.assert_called_once_with(target.id, query.confirmation)


def test_id_delete_invalid_form_error(repository_details, mocker: MockerFixture):
    target = repository_details[0]
    query = RepositoryDeleteQuery(confirmation="invalid-confirmation")
    mock_delete = mocker.patch.object(server.api.repositories.RepositoryService, "delete_by_id")
    mock_delete.side_effect = InvalidFormError(E.REPOSITORY_NAME_NOT_MATCH % {"id": target.id})

    res, status = unwrap(repositories.id_delete)(target.id, query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_NAME_NOT_MATCH, {"id": target.id})


def test_id_delete_not_found(repository_details, mocker: MockerFixture):
    target = repository_details[0]
    query = RepositoryDeleteQuery(confirmation=target.service_name)
    mock_delete = mocker.patch.object(server.api.repositories.RepositoryService, "delete_by_id")
    mock_delete.side_effect = ResourceNotFound(E.REPOSITORY_NOT_FOUND % {"id": target.id})

    res, status = unwrap(repositories.id_delete)(target.id, query)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_NOT_FOUND, {"id": target.id})


def test_has_permission_system_admin(mocker: MockerFixture):
    mocker.patch.object(server.api.repositories, "is_current_user_system_admin", return_value=True)

    assert repositories.has_permission("test_repo_ac_jp") is True


def test_has_permission_permitted(mocker: MockerFixture):
    mocker.patch.object(server.api.repositories, "is_current_user_system_admin", return_value=False)
    mock_get_permitted = mocker.patch.object(server.api.repositories, "get_permitted_repository_ids")
    mock_get_permitted.return_value = ["test_1_repo_ac_jp", "test_2_repo_ac_jp"]

    assert repositories.has_permission("test_1_repo_ac_jp") is True


def test_has_permission_not_permitted(mocker: MockerFixture):
    """Test: has_permission returns False for not permitted repository."""
    mocker.patch.object(server.api.repositories, "is_current_user_system_admin", return_value=False)
    mock_get_permitted = mocker.patch.object(server.api.repositories, "get_permitted_repository_ids")
    mock_get_permitted.return_value = ["test_2_repo_ac_jp", "test_3_repo_ac_jp"]

    assert repositories.has_permission("test_1_repo_ac_jp") is False


def test_filter_options(mocker: MockerFixture):
    options = expected = [FilterOption(key="t", description="test opttion", type="string", multiple=False)]
    mock_options = mocker.patch.object(server.api.repositories, "search_repositories_options", return_value=options)

    result = unwrap(repositories.filter_options)()

    assert result == expected
    mock_options.assert_called_once_with()
