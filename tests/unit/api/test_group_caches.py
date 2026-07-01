import typing as t

from http import HTTPStatus

import server.api.group_caches

from server.api import group_caches
from server.api.schemas import CacheQuery, CacheRequest, ErrorResponse
from server.entities.cache import TaskDetail
from server.entities.search_request import SearchResult
from server.exc import InvalidQueryError, RequestConflict
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


def test_init_settings(config: RuntimeConfig, mocker: MockerFixture):
    mock_setup_config = mocker.patch.object(server.api.group_caches, "setup_weko_group_cache_db_config")

    unwrap(group_caches.init_settings)()

    mock_setup_config.assert_called_once_with(config.for_group_caches)


def test_get(repository_summaries, cached_data, mocker: MockerFixture):
    page, length, total = 1, 20, 20
    query = CacheQuery(q=None, p=page, l=length)
    summaries = repository_summaries * 2
    cache_result = SearchResult(resources=cached_data(summaries), total=total, page_size=length, offset=page)
    mock_get_cache = mocker.patch.object(server.api.group_caches.group_caches, "get_repository_cache")
    mock_get_cache.return_value = cache_result

    res, status = unwrap(group_caches.get)(query)

    assert res == cache_result
    assert status == HTTPStatus.OK
    mock_get_cache.assert_called_once_with(query)


def test_get_invalid_query(mocker: MockerFixture):
    page, length = 1, 20
    query = CacheQuery(q=None, p=page, l=length)
    mock_search = mocker.patch.object(server.api.group_caches.group_caches, "get_repository_cache")
    mock_search.side_effect = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)

    res, status = unwrap(group_caches.get)(query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNSUPPORTED_SEARCH_FILTER)
    mock_search.assert_called_once_with(query)


def test_post(mocker: MockerFixture):
    mock_update = mocker.patch.object(server.api.group_caches.group_caches, "update")
    body = CacheRequest(op=(operation := "all"), ids=(ids := ["test_1_repo_ac_jp", "test_2_repo_ac_jp"]))

    res, status = unwrap(group_caches.post)(body)

    assert status == HTTPStatus.ACCEPTED
    assert not res
    mock_update.assert_called_once_with(operation, ids)


def test_post_conflict(mocker: MockerFixture):
    mock_update = mocker.patch.object(server.api.group_caches.group_caches, "update")
    mock_update.side_effect = RequestConflict(E.GROUP_CACHE_UPDATE_CONFLICT)
    body = CacheRequest(op=(operation := "all"), ids=(ids := ["test_1_repo_ac_jp", "test_2_repo_ac_jp"]))

    res, status = unwrap(group_caches.post)(body)

    assert status == HTTPStatus.CONFLICT
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_CACHE_UPDATE_CONFLICT)
    mock_update.assert_called_once_with(operation, ids)


def test_status(repository_summaries, cached_data, mocker: MockerFixture):
    done, total = 10, 20
    repository_cache = cached_data(repository_summaries[:1])[0]
    expected = TaskDetail(
        results=[repository_cache], status="in_progress", current="test_1_repo_ac_jp", done=done, total=total
    )

    mock_status = mocker.patch.object(server.api.group_caches.group_caches, "get_task_status")
    mock_status.return_value = expected

    res, status = unwrap(group_caches.status)()

    assert status == HTTPStatus.OK
    assert res == expected
    mock_status.assert_called_once_with()


def test_status_no_task(app, mocker: MockerFixture):
    mock_status = mocker.patch.object(server.api.group_caches.group_caches, "get_task_status")
    mock_status.return_value = None

    res, status = unwrap(group_caches.status)()

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UPDATE_TASK_NOT_RUNNING)
    mock_status.assert_called_once_with()
