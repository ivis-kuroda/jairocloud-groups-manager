import typing as t

from flask import Flask

from server.api import group_caches
from server.api.schemas import CacheQuery, CacheRequest, ErrorResponse
from server.entities.cache import RepositoryCache, TaskDetail
from server.entities.search_request import SearchResult
from server.exc import InvalidQueryError
from server.messages import E


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get(app, mocker: MockerFixture, gen_summaries, cached_data, unwrap):
    query = CacheQuery(q=None, p=1, l=20, f=[])
    repositories: SearchResult = gen_summaries(20)
    search_result = SearchResult(
        resources=cached_data(repositories.resources, None, every_other=False),
        total=20,
        page_size=20,
        offset=1,
    )
    mock_get_cache = mocker.patch("server.api.group_caches.group_caches.get_repository_cache")
    mock_get_cache.return_value = search_result
    success = 200

    result, status = unwrap(group_caches.get)(query)

    assert result == search_result
    assert status == success
    mock_get_cache.assert_called_once_with(query)


def test_get_invalid_query(mocker: MockerFixture, unwrap):
    query = CacheQuery(q=None, p=1, l=20, f=[])
    messege = "Invalid query"
    mock_search = mocker.patch("server.api.group_caches.group_caches.get_repository_cache")
    mock_search.side_effect = InvalidQueryError(messege)
    bad_request = 400

    result, status = unwrap(group_caches.get)(query)

    assert isinstance(result, ErrorResponse)
    assert result.message == messege
    assert status == bad_request
    mock_search.assert_called_once_with(query)


def test_post(app: Flask, mocker: MockerFixture, unwrap):
    mock_update = mocker.patch("server.api.group_caches.group_caches.update")
    ids = ["repo1_example_jp", "repo2_example_jp"]
    operation = "all"
    accepted = 202

    result, status = unwrap(group_caches.post)(body=CacheRequest(ids=ids, op=operation))

    assert not result
    assert status == accepted
    mock_update.assert_called_once_with(operation, ids)


def test_post_conflict(app: Flask, mocker: MockerFixture, unwrap):
    mock_update = mocker.patch("server.api.group_caches.group_caches.update")
    mock_update.side_effect = group_caches.RequestConflict(E.GROUP_CACHE_UPDATE_CONFLICT)
    ids = ["repo1_example_jp", "repo2_example_jp"]
    operation = "all"
    conflict = 409

    result, status = unwrap(group_caches.post)(body=CacheRequest(ids=ids, op=operation))

    assert isinstance(result, ErrorResponse)
    assert result.message in str(E.GROUP_CACHE_UPDATE_CONFLICT)
    assert status == conflict
    mock_update.assert_called_once_with(operation, ids)


def test_status(app: Flask, mocker: MockerFixture, unwrap, gen_summaries):
    repository = gen_summaries(1).resources[0]
    repository_cache = RepositoryCache(
        id=repository.id,
        service_name=repository.service_name,  # pyright: ignore[reportArgumentType],
        service_url=repository.service_url,
        updated=None,
    )
    task_detail = TaskDetail(
        results=[repository_cache],
        status="in_progress",
        current="repo1_example_jp",
        done=10,
        total=20,
    )

    mock_status = mocker.patch("server.api.group_caches.group_caches.get_task_status")
    mock_status.return_value = task_detail
    success = 200

    result, status = unwrap(group_caches.status)()

    assert result == task_detail
    assert status == success
    mock_status.assert_called_once_with()


def test_status_no_task(app: Flask, mocker: MockerFixture, unwrap):
    mock_status = mocker.patch("server.api.group_caches.group_caches.get_task_status")
    mock_status.return_value = None
    bad_request = 400

    result, status = unwrap(group_caches.status)()

    assert isinstance(result, ErrorResponse)
    assert result.message in str(E.UPDATE_TASK_NOT_RUNNING)
    assert status == bad_request
    mock_status.assert_called_once_with()
