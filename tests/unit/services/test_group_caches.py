import typing as t

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid7

import pytest

from redis import RedisError
from weko_group_cache_db.config import setup_config as setup_wgcd_config
from weko_group_cache_db.signals import ExecutedData, ProgressData

import server.services.group_caches

from server.api.schemas import CacheQuery
from server.entities.cache import RepositoryCache, TaskDetail
from server.entities.search_request import SearchResult
from server.exc import DatastoreError, GroupCacheError, RequestConflict
from server.messages import E, I, W
from server.services.group_caches import (
    get_repository_cache,
    get_task_status,
    handle_excuted,
    handle_progress,
    is_update_task_running,
    update,
    update_task,
)

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def _wgcd_config(config):
    setup_wgcd_config(config.CACHE_GROUPS)


@pytest.mark.parametrize("page", range(1, 4), ids=(f"page {p}" for p in range(1, 4)))
def test_get_repository_cache_no_filter(page, repository_summaries, repository_caches, mocker: MockerFixture):
    num_repo, q_length, offset = 10, 4, (page - 1) * 4 + 1
    query = CacheQuery(q="Test", l=q_length, p=page)

    searched = repository_summaries[q_length * (page - 1) : q_length * page]
    search_result = SearchResult(resources=searched, total=num_repo, page_size=q_length, offset=offset)
    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    mock_search.return_value = search_result
    checked_caches = repository_caches[q_length * (page - 1) : q_length * page]
    mock_check = mocker.patch.object(server.services.group_caches, "check_cache_exists", return_value=checked_caches)

    expected = SearchResult(resources=checked_caches, total=num_repo, page_size=q_length, offset=offset)
    threshold = int(num_repo / q_length)
    expected_length = q_length if page <= threshold else num_repo - q_length * threshold

    result = get_repository_cache(query)

    assert result == expected
    assert len(result.resources) == expected_length
    mock_search.assert_called_once()
    (criteria,), _ = mock_search.call_args
    assert criteria.q == query.q
    assert criteria.k == "id"
    assert criteria.d == "asc"
    assert criteria.p == page
    assert criteria.l == q_length
    mock_check.assert_called_once_with(search_result.resources, status_filter=None)


@pytest.mark.parametrize("page", range(1, 3), ids=(f"page {p}" for p in range(1, 3)))
def test_get_repository_cache_with_filter(page, repository_summaries, repository_caches, mocker: MockerFixture):
    num_repo, q_length, offset = 10, 4, (page - 1) * 4 + 1
    query = CacheQuery(q="Test", f=["e"], l=q_length, p=page)

    non_existent = [3, 4, 8]
    checked_caches = [c for i, c in enumerate(repository_caches) if i not in non_existent]

    search_result = SearchResult(resources=repository_summaries, total=num_repo, page_size=q_length, offset=offset)
    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    mock_search.return_value = search_result
    mock_check = mocker.patch.object(server.services.group_caches, "check_cache_exists", return_value=checked_caches)

    expected_caches = checked_caches[(page - 1) * q_length : page * q_length]
    expected = SearchResult(
        resources=expected_caches, total=num_repo - len(non_existent), page_size=q_length, offset=offset
    )
    threshold = int((num_repo - len(non_existent)) / q_length)
    expected_length = q_length if page <= threshold else num_repo - len(non_existent) - q_length * threshold

    result = get_repository_cache(query)

    assert result == expected
    assert len(result.resources) == expected_length
    mock_search.assert_called_once()
    (criteria,), _ = mock_search.call_args
    assert criteria.q == query.q
    assert criteria.k == "id"
    assert criteria.d == "asc"
    assert criteria.p == -1
    assert criteria.l == q_length
    mock_check.assert_called_once_with(search_result.resources, status_filter=query.f)


def test_get_repository_cache_no_size(repository_summaries, repository_caches, mocker: MockerFixture):
    num_repo, page, offset = 10, 1, 1
    query = CacheQuery(q="Test", f=["n"], p=page)

    non_existent = [3, 4, 8]
    checked_caches = [c for i, c in enumerate(repository_caches) if i in non_existent]

    search_result = SearchResult(resources=repository_summaries, total=num_repo, page_size=num_repo, offset=offset)
    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    mock_search.return_value = search_result
    mock_check = mocker.patch.object(server.services.group_caches, "check_cache_exists", return_value=checked_caches)

    expected_caches = checked_caches[(page - 1) * num_repo : page * num_repo]
    expect = SearchResult(
        resources=expected_caches, total=len(non_existent), page_size=len(non_existent), offset=offset
    )

    result = get_repository_cache(query)

    assert result == expect
    mock_search.assert_called_once()
    (criteria,), _ = mock_search.call_args
    assert criteria.q == query.q
    assert criteria.k == "id"
    assert criteria.d == "asc"
    assert criteria.p == -1
    assert criteria.l is None
    mock_check.assert_called_once_with(search_result.resources, status_filter=query.f)


def test_update_all(app, mocker: MockerFixture, datastore, repository_summaries, caplog):

    mock_check = mocker.patch.object(server.services.group_caches, "is_update_task_running")
    mock_check.return_value = False
    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    repository = repository_summaries[0]
    repositories = SearchResult(resources=[repository], total=1, page_size=1, offset=1)
    mock_search.return_value = repositories
    mock_task = mocker.MagicMock(id=(task_id := str(uuid7())))
    mock_update_task = mocker.patch.object(server.services.group_caches.update_task, "delay", return_value=mock_task)

    query = SimpleNamespace(q=None, i=[], p=None, l=-1, k="id", d="asc")

    app_cache, _, _ = datastore

    ids = [repository.id]
    fqdn_list = [repository.service_url.host]
    op = "all"

    update(op, ids)

    mock_check.assert_called_once()
    mock_search.assert_called_once_with(query)
    mock_update_task.assert_called_once_with(fqdn_list)
    app_cache.delete.assert_called_once_with("jcgroups-test-weko-group-cache-db")
    app_cache.hset.assert_called_once_with("jcgroups-test-weko-group-cache-db", mapping={"status": "pending"})
    assert_message(caplog.records[0], I.GROUP_CACHE_UPDATE_STARTED, {"op": op, "task_id": task_id})


def test_update_id_specified(app, mocker: MockerFixture, datastore, repository_summaries, caplog):

    mock_check = mocker.patch.object(server.services.group_caches, "is_update_task_running")
    mock_check.return_value = False
    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    repository = repository_summaries[0]
    repositories = SearchResult(resources=[repository], total=1, page_size=1, offset=1)
    mock_search.return_value = repositories
    mock_update_task = mocker.patch.object(server.services.group_caches.update_task, "delay")

    ids = [repository.id]
    fqdn_list = [repository.service_url.host]
    op = "id-specified"
    query = SimpleNamespace(q=None, i=ids, p=None, l=-1, k="id", d="asc")

    app_cache, _, _ = datastore

    update(op, ids)

    mock_check.assert_called_once()
    mock_search.assert_called_once_with(query)
    mock_update_task.assert_called_once_with(fqdn_list)
    app_cache.delete.assert_called_once_with("jcgroups-test-weko-group-cache-db")
    app_cache.hset.assert_called_once_with("jcgroups-test-weko-group-cache-db", mapping={"status": "pending"})


def test_update_task_conflict(repository_summaries, mocker: MockerFixture):
    mock_check = mocker.patch.object(server.services.group_caches, "is_update_task_running")
    mock_check.return_value = True
    mock_update_task = mocker.patch.object(server.services.group_caches.update_task, "delay")

    fqdn_list = [repository_summaries[0].service_url.host]
    op = "all"

    with pytest.raises(RequestConflict, match=str(E.GROUP_CACHE_UPDATE_CONFLICT)):
        update(op, fqdn_list)

    mock_check.assert_called_once()
    mock_update_task.assert_not_called()


def test_update_redis_error(app, mocker: MockerFixture, datastore, repository_summaries, caplog):
    mock_check = mocker.patch.object(server.services.group_caches, "is_update_task_running")
    mock_check.return_value = False
    mock_update_task = mocker.patch.object(server.services.group_caches.update_task, "delay")
    mock_update_task.side_effect = RedisError("Failed to connect to Redis.")

    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    repository = repository_summaries[0]
    repositories = SearchResult(
        resources=[repository],
        total=1,
        page_size=1,
        offset=1,
    )
    mock_search.return_value = repositories

    app_cache, _, _ = datastore

    ids = [repository.id]
    fqdn_list = [repository.service_url.host]
    op = "all"

    with pytest.raises(DatastoreError, match=str(E.FAILED_ENQUEUE_CACHE_UPDATE_TASK)):
        update(op, ids)

    mock_check.assert_called_once()
    app_cache.hset.assert_called_once_with("jcgroups-test-weko-group-cache-db", mapping={"status": "pending"})
    mock_update_task.assert_called_once_with(fqdn_list)
    assert_message(caplog.records[0], E.FAILED_ENQUEUE_CACHE_UPDATE_TASK)


def test_update_task(config, mocker: MockerFixture, repository_caches):
    repository = repository_caches[0]
    mock_fetch_all = mocker.patch.object(server.services.group_caches.wgcd, "fetch_all")

    fqdn_list = [repository.service_url.host]

    unwrap(update_task)(fqdn_list)
    mock_fetch_all.assert_called_once_with(
        directory_path=config.CACHE_GROUPS.directory_path,
        fqdn_list=fqdn_list,
    )


@pytest.mark.parametrize("status", ["pending", "started", "in_progress"])
def test_is_update_task_running(datastore, status):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = status

    result = is_update_task_running()
    assert result is True
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_is_update_task_running_completed(datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = "completed"

    result = is_update_task_running()
    assert result is False
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_is_update_task_running_not_exists(datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = None

    result = is_update_task_running()
    assert result is False
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_handle_progress(datastore, repository_summaries):
    data = ProgressData(status="in_progress", total=10, done=5, current=repository_summaries[0].service_url.host)
    app_cache, _, _ = datastore

    unwrap(handle_progress)(data=data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    app_cache.hset.assert_called_once_with(cache_key, mapping=data.model_dump(mode="json"))


def test_handle_progress_redis_error(app, datastore, repository_summaries, caplog):
    fqdn = repository_summaries[0].service_url.host
    data = ProgressData(status="in_progress", total=10, done=5, current=fqdn)
    app_cache, _, _ = datastore
    app_cache.hset.side_effect = RedisError("Failed to connect to Redis.")

    unwrap(handle_progress)(data=data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    app_cache.hset.assert_called_once_with(cache_key, mapping=data.model_dump(mode="json"))

    assert str(W.FAILED_UPDATE_TASK_PROGRESS % {"done": 5, "total": 10}) in caplog.text


def test_handle_excuted(datastore, repository_summaries):
    fqdn = repository_summaries[0].service_url.host
    data = ExecutedData(fqdn=fqdn, status="success", updated_at=datetime.now(UTC))
    app_cache, _, _ = datastore

    unwrap(handle_excuted)(None, data=data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    rid = fqdn.replace(".", "_").replace("-", "_")
    field_name = f"{rid}_0"
    app_cache.hset.assert_called_once_with(cache_key, mapping={field_name: data.model_dump_json()})


def test_handle_excuted_redis_error(app, datastore, repository_summaries, caplog):
    fqdn = repository_summaries[0].service_url.host
    data = ExecutedData(fqdn=fqdn, status="success", updated_at=datetime.now(UTC))
    app_cache, _, _ = datastore
    app_cache.hset.side_effect = RedisError("Failed to connect to Redis.")

    unwrap(handle_excuted)(None, data=data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    rid = fqdn.replace(".", "_").replace("-", "_")
    field_name = f"{rid}_0"
    app_cache.hset.assert_called_once_with(cache_key, mapping={field_name: data.model_dump_json()})

    assert_message(
        caplog.records[0],
        W.FAILED_UPDATE_TASK_EXECUT_STATUS,
        {"rid": rid, "status": "success", "retries": 0},
    )


def test_get_task_status(config, datastore, repository_summaries, repository_caches, mocker: MockerFixture):
    cached_data: RepositoryCache = repository_caches[0]
    assert cached_data.service_url
    assert cached_data.service_url.host
    assert cached_data.updated
    fqdn = cached_data.service_url.host
    rid = fqdn.replace(".", "_").replace("-", "_")
    ex_data = ExecutedData(fqdn=fqdn, status=(status := "success"), updated_at=cached_data.updated)
    cached_data.status = status
    task_data = {
        b"current": fqdn.encode(),
        b"status": b"in_progress",
        b"done": b"5",
        b"total": b"10",
        f"{rid}_0".encode(): ex_data.model_dump_json().encode(),
    }

    assert ex_data == ExecutedData.model_validate_json(task_data[f"{rid}_0".encode()])

    app_cache, _, _ = datastore
    app_cache.hgetall.return_value = task_data
    mocker.patch.object(server.services.group_caches, "make_criteria_object")
    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")
    mock_search.return_value = SearchResult(resources=[repository_summaries[0]], total=1, page_size=1, offset=1)

    expect = TaskDetail(results=[cached_data], status="in_progress", current=rid, total=10, done=5)

    result = get_task_status()

    assert result == expect

    app_cache.hgetall.assert_called_once_with("jcgroups-test-weko-group-cache-db")
    app_cache.delete.assert_not_called()


def test_get_task_status_not_running(app, datastore):
    app_cache, _, _ = datastore
    app_cache.hgetall.return_value = {}
    app_cache.hget.return_value = "completed"

    result = get_task_status()

    assert result is None


def test_get_task_status_no_task(datastore, mocker: MockerFixture):
    app_cache, _, _ = datastore
    app_cache.hgetall.return_value = {}

    mock_search = mocker.patch.object(server.services.group_caches.RepositoryService, "search")

    result = get_task_status()

    assert result is None
    mock_search.assert_not_called()


def test_get_task_status_redis_error(app, datastore, caplog):
    app_cache, _, _ = datastore
    app_cache.hgetall.side_effect = RedisError("Redis error")

    with pytest.raises(DatastoreError, match=str(E.FAILED_FETCH_UPDATE_TASK_STATUS)):
        unwrap(get_task_status)()

    assert_message(caplog.records[0], E.FAILED_FETCH_UPDATE_TASK_STATUS)


def test_get_task_status_parse_error(app, datastore, caplog):
    app_cache, _, _ = datastore

    cache_data = {
        b"current": b"example.com",
        b"done": b"5",
        b"total": b"10",
        b"example_com_0": b"invalid_json",
    }
    app_cache.hgetall.return_value = cache_data

    error = str(E.FAILED_PARSE_UPDATE_TASK_STATUS)
    with pytest.raises(GroupCacheError, match=error):
        unwrap(get_task_status)()

    assert_message(caplog.records[0], E.FAILED_PARSE_UPDATE_TASK_STATUS)
