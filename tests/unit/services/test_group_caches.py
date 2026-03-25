import typing as t

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from redis import RedisError
from weko_group_cache_db.config import setup_config as setup_wgcd_config
from weko_group_cache_db.signals import ExecutedData, ProgressData

from server.api.schemas import CacheQuery
from server.config import config
from server.entities.cache import RepositoryCache, TaskDetail
from server.entities.search_request import SearchResult
from server.entities.summaries import RepositorySummary
from server.exc import DatastoreError, GroupCacheError, RequestConflict
from server.messages import E, W
from server.services.group_caches import (
    get_repository_cache,
    get_task_status,
    handle_excuted,
    handle_progress,
    is_update_task_running,
    update,
    update_task,
)


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def setup_config(app):
    setup_wgcd_config(config.CACHE_GROUPS)


def test_get_repository_cache(app, mocker: MockerFixture, gen_summaries, cache_keys, cached_data, datastore):
    num_repo = 20
    query = CacheQuery(l=20, p=1)
    repositories = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)

    keys = cache_keys([repo.service_url.host for repo in repositories.resources[::2]])
    now = datetime.now(UTC)
    caches = cached_data(repositories.resources, now, every_other=True)

    _, _, group_cache = datastore
    group_cache.hget.side_effect = lambda key, _: now.isoformat() if key.encode() in keys else None
    expect = SearchResult(total=20, resources=caches, page_size=20, offset=1)

    result = get_repository_cache(query)

    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_multi_scan(mocker: MockerFixture, app, gen_summaries, cache_keys, cached_data, datastore):
    num_repo = 20
    query = CacheQuery(l=20, p=1)
    repositories = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    keys = cache_keys([repo.service_url.host for repo in repositories.resources[::2]])
    now = datetime.now(UTC)
    caches = cached_data(repositories.resources, now, every_other=True)

    _, _, group_cache = datastore
    group_cache.hget.side_effect = lambda key, _: now.isoformat() if key.encode() in keys else None

    expect = SearchResult(total=20, resources=caches, page_size=20, offset=1)

    result = get_repository_cache(query)

    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_all_cache_not_exceeding_page_size(
    app, mocker: MockerFixture, gen_summaries, cache_keys, cached_data, datastore
):
    num = 20
    query = CacheQuery(f=["e"], l=20, p=1)
    repositories: SearchResult[RepositorySummary] = gen_summaries(num)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    now = datetime.now(UTC)
    caches = cached_data(repositories.resources, now, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.return_value = now.isoformat()

    result = get_repository_cache(query)
    expect = SearchResult(
        total=num,
        resources=caches,
        page_size=20,
        offset=1,
    )
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num

    mocker.stopall()


def test_get_repository_cache_all_cache_exceeding_page_size(
    app, mocker: MockerFixture, gen_summaries, cache_keys, cached_data, datastore
):
    num = 30
    query = CacheQuery(f=["e"], l=20, p=1)
    repositories = gen_summaries(num)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)

    now = datetime.now(UTC)
    caches = cached_data(repositories.resources[:20], now, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.return_value = now.isoformat()

    expect = SearchResult(total=num, resources=caches, page_size=20, offset=1)
    result = get_repository_cache(query)

    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num

    mocker.stopall()


def test_get_repository_cache_all_cache_exceeding_page_size_next_page(
    mocker: MockerFixture, app, gen_summaries, cache_keys, cached_data, datastore
):
    num = 30
    query = CacheQuery(f=["e"], l=20, p=2)
    repositories = gen_summaries(num)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    now = datetime.now(UTC)
    caches = cached_data(repositories.resources[20:30], now, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.return_value = now.isoformat()
    result = get_repository_cache(query)
    expect = SearchResult(total=30, resources=caches, page_size=20, offset=21)

    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num

    mocker.stopall()


def test_get_repository_cache_empty_cache(app, mocker: MockerFixture, gen_summaries, datastore):
    num_repo = 20
    query = CacheQuery(f=["e"], l=20, p=1)
    repositories = gen_summaries(20)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    _, _, group_cache = datastore
    group_cache.hget.return_value = None

    result = get_repository_cache(query)
    expect = SearchResult(
        total=0,
        resources=[],
        page_size=20,
        offset=1,
    )
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_half_cache(app, mocker: MockerFixture, gen_summaries, cache_keys, cached_data, datastore):
    num_repo = 20
    query = CacheQuery(f=["e"], l=20, p=1)
    repositories = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    keys = cache_keys([repo.service_url.host for repo in repositories.resources[::2]])
    now = datetime.now(UTC)
    caches = cached_data(repositories.resources[::2], now, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.side_effect = lambda key, _: now.isoformat() if key.encode() in keys else None

    result = get_repository_cache(query)
    expect = SearchResult(
        total=10,
        resources=caches,
        page_size=20,
        offset=1,
    )
    mock_search.assert_called_once()
    assert result == expect

    assert group_cache.hget.call_count == num_repo
    mocker.stopall()


def test_get_repository_cache_no_cache_not_exceeding_page_size(
    app, mocker: MockerFixture, gen_summaries, cache_keys, cached_data, datastore
):
    num_repo = 20
    query = CacheQuery(f=["n"], l=20, p=1)
    repositories = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    caches = cached_data(repositories.resources, None, every_other=False)
    _, _, group_cache = datastore
    group_cache.hget.return_value = None

    expect = SearchResult(total=num_repo, resources=caches, page_size=20, offset=1)

    result = get_repository_cache(query)
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_no_cache_exceeding_page_size(
    app, mocker: MockerFixture, gen_summaries, cache_keys, cached_data, datastore
):
    num_repo = 30
    query = CacheQuery(f=["n"], l=20, p=1)
    repositories = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    caches = cached_data(repositories.resources[:20], None, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.return_value = None
    result = get_repository_cache(query)
    expect = SearchResult(
        total=30,
        resources=caches,
        page_size=20,
        offset=1,
    )
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_no_cache_exceeding_page_size_next_page(
    mocker: MockerFixture, app, gen_summaries, cache_keys, cached_data, datastore
):
    num_repo = 30
    query = CacheQuery(f=["n"], l=20, p=2)
    repositories = gen_summaries(30)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    caches = cached_data(repositories.resources[20:30], None, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.return_value = None

    result = get_repository_cache(query)
    expect = SearchResult(
        total=30,
        resources=caches,
        page_size=20,
        offset=21,
    )
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_no_cache_all_cache(mocker: MockerFixture, app, gen_summaries, cache_keys, datastore):
    num_repo = 20
    query = CacheQuery(f=["n"], l=20, p=1)
    now = datetime.now(UTC)
    repositories: SearchResult = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)

    _, _, group_cache = datastore
    group_cache.hget.return_value = now.isoformat()

    result = get_repository_cache(query)
    expect = SearchResult(
        total=0,
        resources=[],
        page_size=20,
        offset=1,
    )
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_get_repository_cache_no_cache_half_cache(
    mocker: MockerFixture, app, gen_summaries, cache_keys, cached_data, datastore
):
    num_repo = 20
    query = CacheQuery(f=["n"], l=20, p=1)
    repositories = gen_summaries(num_repo)
    mock_search = mocker.patch("server.services.group_caches.repositories.search", return_value=repositories)
    keys = cache_keys([repo.service_url.host for repo in repositories.resources[::2]])
    now = datetime.now(UTC)
    caches = cached_data(repositories.resources[1::2], None, every_other=False)

    _, _, group_cache = datastore
    group_cache.hget.side_effect = lambda key, _: now.isoformat() if key.encode() in keys else None

    result = get_repository_cache(query)
    expect = SearchResult(
        total=10,
        resources=caches,
        page_size=20,
        offset=1,
    )
    assert result == expect
    mock_search.assert_called_once()
    assert group_cache.hget.call_count == num_repo

    mocker.stopall()


def test_update_all(app, mocker: MockerFixture, datastore, gen_summaries):

    mock_check = mocker.patch("server.services.group_caches.is_update_task_running")
    mock_check.return_value = False
    mock_search = mocker.patch("server.services.group_caches.repositories.search")
    repositories = SearchResult(
        resources=[gen_summaries(1).resources[0]],
        total=1,
        page_size=1,
        offset=1,
    )
    mock_search.return_value = repositories
    mock_update_task = mocker.patch("server.services.group_caches.update_task.apply_async")

    query = SimpleNamespace(q=None, i=[], p=None, l=-1, k="id", d="asc")

    app_cache, _, _ = datastore

    ids = [repositories.resources[0].id]
    fqdn_list = [repositories.resources[0].service_url.host]
    op = "all"

    update(op, ids)

    mock_check.assert_called_once()
    mock_search.assert_called_once_with(query)
    mock_update_task.assert_called_once_with((fqdn_list,))
    app_cache.delete.assert_called_once_with("jcgroups-test-weko-group-cache-db")
    app_cache.hset.assert_called_once_with("jcgroups-test-weko-group-cache-db", mapping={"status": "pending"})
    mocker.stopall()


def test_update_id_specified(app, mocker: MockerFixture, datastore, gen_summaries):

    mock_check = mocker.patch("server.services.group_caches.is_update_task_running")
    mock_check.return_value = False
    mock_search = mocker.patch("server.services.group_caches.repositories.search")
    repositories = SearchResult(
        resources=[gen_summaries(1).resources[0]],
        total=1,
        page_size=1,
        offset=1,
    )
    mock_search.return_value = repositories
    mock_update_task = mocker.patch("server.services.group_caches.update_task.apply_async")

    ids = [repositories.resources[0].id]
    fqdn_list = [repositories.resources[0].service_url.host]
    op = "id-specified"
    query = SimpleNamespace(q=None, i=ids, p=None, l=-1, k="id", d="asc")

    app_cache, _, _ = datastore

    update(op, ids)

    mock_check.assert_called_once()
    mock_search.assert_called_once_with(query)
    mock_update_task.assert_called_once_with((fqdn_list,))
    app_cache.delete.assert_called_once_with("jcgroups-test-weko-group-cache-db")
    app_cache.hset.assert_called_once_with("jcgroups-test-weko-group-cache-db", mapping={"status": "pending"})
    mocker.stopall()


def test_update_raises_task_running(app, mocker: MockerFixture):
    mock_check = mocker.patch("server.services.group_caches.is_update_task_running")
    mock_check.return_value = True
    mock_update_task = mocker.patch("server.services.group_caches.update_task.apply_async")

    fqdn_list = ["example.com"]
    op = "all"

    with pytest.raises(RequestConflict, match=str(E.GROUP_CACHE_UPDATE_CONFLICT)):
        update(op, fqdn_list)

    mock_check.assert_called_once()
    mock_update_task.assert_not_called()

    mocker.stopall()


def test_update_raises_failed_task_running(app, mocker: MockerFixture, datastore, gen_summaries):
    mock_check = mocker.patch("server.services.group_caches.is_update_task_running")
    mock_check.return_value = False
    mock_update_task = mocker.patch("server.services.group_caches.update_task.apply_async")
    mock_update_task.side_effect = RedisError("Failed to connect to Redis.")

    mock_search = mocker.patch("server.services.group_caches.repositories.search")
    repositories = SearchResult(
        resources=[gen_summaries(1).resources[0]],
        total=1,
        page_size=1,
        offset=1,
    )
    mock_search.return_value = repositories

    app_cache, _, _ = datastore

    ids = [repositories.resources[0].id]
    fqdn_list = [repositories.resources[0].service_url.host]
    op = "all"

    with pytest.raises(DatastoreError, match=str(E.FAILED_ENQUEUE_CACHE_UPDATE_TASK)):
        update(op, ids)

    mock_check.assert_called_once()
    app_cache.hset.assert_called_once_with("jcgroups-test-weko-group-cache-db", mapping={"status": "pending"})

    mock_update_task.assert_called_once_with((fqdn_list,))

    mocker.stopall()


def test_update_task_all(app, mocker: MockerFixture, gen_summaries, unwrap):
    repositories = gen_summaries(1).resources
    mock_fetch_all = mocker.patch("server.services.group_caches.wgcd.fetch_all")

    fqdn_list = [repositories[0].service_url.host]

    unwrap(update_task)(fqdn_list)
    mock_fetch_all.assert_called_once_with(
        directory_path=config.CACHE_GROUPS.directory_path,
        fqdn_list=fqdn_list,
    )
    mocker.stopall()


def test_is_update_task_running_pending(app, datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = "pending"

    result = is_update_task_running()
    assert result is True
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_is_update_task_running_started(app, datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = "started"

    result = is_update_task_running()
    assert result is True
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_is_update_task_running_in_progress(app, datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = "in_progress"

    result = is_update_task_running()
    assert result is True
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_is_update_task_running_completed(app, datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = "completed"

    result = is_update_task_running()
    assert result is False
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_is_update_task_running_not_exists(app, datastore):
    app_cache, _, _ = datastore
    app_cache.hget.return_value = None

    result = is_update_task_running()
    assert result is False
    app_cache.hget.assert_called_once_with("jcgroups-test-weko-group-cache-db", "status")


def test_handle_progress(app, mocker: MockerFixture, unwrap, datastore):
    data = ProgressData(status="in_progress", total=10, done=5, current="example.com")
    app_cache, _, _ = datastore

    unwrap(handle_progress)(None, data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    app_cache.hset.assert_called_once_with(cache_key, mapping=data.model_dump(mode="json"))


def test_handle_progress_redis_error(app, mocker: MockerFixture, unwrap, datastore, caplog):
    data = ProgressData(status="in_progress", total=10, done=5, current="example.com")
    app_cache, _, _ = datastore
    app_cache.hset.side_effect = RedisError("Redis error")

    unwrap(handle_progress)(None, data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    app_cache.hset.assert_called_once_with(cache_key, mapping=data.model_dump(mode="json"))

    assert str(W.FAILED_UPDATE_TASK_PROGRESS % {"done": 5, "total": 10}) in caplog.text


def test_handle_excuted(app, mocker: MockerFixture, unwrap, datastore):
    data = ExecutedData(
        fqdn="example.com",
        status="success",
        retries=0,
        error_type=None,
        error_message=None,
        updated_at=datetime.now(UTC),
    )
    app_cache, _, _ = datastore

    unwrap(handle_excuted)(None, data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    field_name = "example_com_0"
    app_cache.hset.assert_called_once_with(cache_key, mapping={field_name: data.model_dump_json()})


def test_handle_excuted_redis_error(app, mocker: MockerFixture, unwrap, datastore, caplog):
    data = ExecutedData(
        fqdn="example.com",
        status="success",
        retries=0,
        error_type=None,
        error_message=None,
        updated_at=datetime.now(UTC),
    )
    app_cache, _, _ = datastore
    app_cache.hset.side_effect = RedisError("Redis error")

    unwrap(handle_excuted)(None, data)

    cache_key = "jcgroups-test-weko-group-cache-db"
    field_name = "example_com_0"
    app_cache.hset.assert_called_once_with(cache_key, mapping={field_name: data.model_dump_json()})

    assert (
        str(W.FAILED_UPDATE_TASK_EXECUT_STATUS % {"rid": "example_com", "status": "success", "retries": 0})
        in caplog.text
    )


def test_get_task_status(app, mocker: MockerFixture, unwrap, datastore):
    task_data = {
        b"current": b"example.com",
        b"status": b"in_progress",
        b"done": b"5",
        b"total": b"10",
        b"example_com_0": b'{"fqdn": "example.com", "status": "success", "updated_at": "2026-01-01T00:00:00Z"}',
    }
    ids = ["example_com"]

    app_cache, _, _ = datastore
    app_cache.hgetall.return_value = task_data
    mocker.patch("server.services.group_caches.make_criteria_object")
    mock_query = MagicMock()
    mock_query.i = ids
    mock_search = mocker.patch("server.services.group_caches.repositories.search")
    mock_search.return_value = SearchResult(
        resources=[RepositorySummary(id="example_com", service_name="Example Repository")],
        total=1,
        page_size=1,
        offset=1,
    )

    result = unwrap(get_task_status)()

    expect_result = [
        RepositoryCache(
            id="example_com",
            service_name="Example Repository",
            updated=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            status="success",
        )
    ]

    assert result == TaskDetail(results=expect_result, status="in_progress", current="example_com", total=10, done=5)

    app_cache.hgetall.assert_called_once_with("jcgroups-test-weko-group-cache-db")
    app_cache.delete.assert_not_called()


def test_get_task_status_not_running(app, unwrap, datastore):
    app_cache, _, _ = datastore
    app_cache.hgetall.return_value = {}
    app_cache.hget.return_value = "completed"

    result = unwrap(get_task_status)()

    assert result is None


def test_get_task_status_no_task(app, unwrap, datastore):
    app_cache, _, _ = datastore
    app_cache.hgetall.return_value = {}

    result = unwrap(get_task_status)()

    assert result is None


def test_get_task_status_redis_error(app, unwrap, datastore):
    app_cache, _, _ = datastore
    app_cache.hgetall.side_effect = RedisError("Redis error")

    with pytest.raises(DatastoreError, match=str(E.FAILED_FETCH_UPDATE_TASK_STATUS)):
        unwrap(get_task_status)()


def test_get_task_status_parse_error(app, unwrap, datastore):
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
