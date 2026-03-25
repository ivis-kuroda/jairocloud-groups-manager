#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Service module for managing cache groups."""

import traceback
import typing as t

from datetime import datetime
from functools import cache

from celery import shared_task
from flask import current_app
from pydantic_core import PydanticSerializationError, ValidationError
from redis import RedisError
from weko_group_cache_db import groups as wgcd
from weko_group_cache_db.signals import (
    ExecutedData,
    ProgressData as ProgressDataBase,
    executed_signal,
    progress_signal,
)

from server.config import config
from server.const import GROUP_CACHE_KEY_PATTERN
from server.datastore import app_cache, group_cache
from server.entities.cache import RepositoryCache, TaskDetail
from server.entities.search_request import SearchResult
from server.exc import (
    DatastoreError,
    GroupCacheError,
    RequestConflict,
    TaskExecutionError,
)
from server.messages import E, I, W
from server.services import repositories

from .utils import make_criteria_object, resolve_repository_id


if t.TYPE_CHECKING:
    from server.entities.summaries import RepositorySummary

    from .utils.search_queries import (
        GroupCacheCriteria,
        GroupCacheFilter,
        GroupCacheOperation,
    )


def get_repository_cache(query: GroupCacheCriteria) -> SearchResult[RepositoryCache]:
    """Retrieve repository cache entries based on the provided query.

    Args:
        query (GroupCacheCriteria): Query parameters for filtering and pagination.

    Returns:
        SearchResult[RepositoryCache]: List of repository cache entries.
    """
    repository_query = make_criteria_object(
        "repositories",
        q=query.q,
        k="id",
        d="asc",
        # when filtering by cache status,
        # get all repositories to apply pagination in this app.
        p=query.p if not query.f else -1,
        l=query.l,
    )
    searched = repositories.search(repository_query)

    page_size = searched.page_size
    start = (query.p - 1) * page_size if query.p else 0
    end = min(start + page_size, len(searched.resources))

    results = check_cache_exists(
        repositories=searched.resources,
        status_filter=query.f,
    )

    resources = results
    total = searched.total
    if query.f:
        # If filtering by status, apply pagination in this app.
        resources = results[start:end]
        total = len(results)

    return SearchResult(
        resources=resources,
        total=total,
        page_size=page_size,
        offset=start + 1,
    )


def check_cache_exists(
    repositories: list[RepositorySummary],
    status_filter: list[GroupCacheFilter] | None = None,
) -> list[RepositoryCache]:
    """Check if cache exists for the given list of repositories.

    Args:
        repositories (list[RepositorySummary]): List of repository summaries.
        status_filter (list | None): List of status filters, e.g., ["e", "n"].

    Returns:
        list[RepositoryCache]: List of repository caches that exist.
    """
    result_repositories: list[RepositoryCache] = []
    for repository in repositories:
        if not repository.service_url or not repository.service_name:
            # service URL and name should exist.
            continue  # pragma: no cover

        fqdn = t.cast("str", repository.service_url.host)
        cache_key = wgcd.cache_key(fqdn)
        # when cache exists, `updated_at` is always present.
        updated: str | None = group_cache.hget(cache_key, "updated_at")  # pyright: ignore[reportAssignmentType]

        repo_cache = RepositoryCache(
            id=repository.id,
            service_name=repository.service_name,
            service_url=repository.service_url,
            updated=datetime.fromisoformat(updated) if updated else None,
        )

        if (
            not status_filter
            or (updated and "e" in status_filter)
            or (not updated and "n" in status_filter)
        ):
            result_repositories.append(repo_cache)

    return result_repositories


@cache
def _unique_progress_key() -> str:
    """Generate a unique key for tracking progress in Redis.

    Returns:
        str: A unique key for progress tracking.
    """
    return config.REDIS.key_prefix + GROUP_CACHE_KEY_PATTERN


def update(op: GroupCacheOperation, repository_ids: list[str] | None = None) -> None:
    """Update cache groups based on the operation type.

    Args:
        op (str): Operation type, either 'all' or 'id-specified'.
        repository_ids (list[str]): List of repository IDs.

    Raises:
        RequestConflict: If the cache update task is already running.
        TaskExecutionError: If there is an error connecting to Redis.
    """
    if is_update_task_running():
        raise RequestConflict(E.GROUP_CACHE_UPDATE_CONFLICT)

    repository_ids = repository_ids if op == "id-specified" else []
    query = make_criteria_object(
        "repositories", i=repository_ids, l=-1, k="id", d="asc"
    )
    repositories_result = repositories.search(query)
    fqdn_list = [
        t.cast("str", repo.service_url.host)
        for repo in repositories_result.resources
        if repo.service_url
    ]

    cache_key = _unique_progress_key()
    try:
        app_cache.delete(cache_key)
        app_cache.hset(cache_key, mapping={"status": "pending"})
        task = update_task.apply_async((fqdn_list,))
    except RedisError as exc:
        error = E.FAILED_ENQUEUE_CACHE_UPDATE_TASK
        raise TaskExecutionError(error) from exc

    current_app.logger.info(
        I.GROUP_CACHE_UPDATE_STARTED, {"op": op, "task_id": task.id}
    )


@shared_task()
def update_task(fqdn_list: list[str]) -> None:
    """Celery task to update cache groups.

    Args:
        fqdn_list (list[str]): List of fully qualified domain names.
    """
    wgcd.fetch_all(
        directory_path=config.CACHE_GROUPS.directory_path, fqdn_list=fqdn_list
    )


def is_update_task_running() -> bool:
    """Check if a cache update task is currently running.

    Returns:
        bool: True if a cache update task is running, False otherwise.
    """
    cache_key = _unique_progress_key()
    progress_status: str | None = app_cache.hget(cache_key, "status")  # pyright: ignore[reportAssignmentType]

    return progress_status in {"pending", "started", "in_progress"}


@progress_signal.connect
def handle_progress(_: object, data: ProgressDataBase, **kwargs: object) -> None:  # noqa: ARG001
    """Receive progress update signal and update task progress in Redis.

    Args:
        _: The sender of the signal.
        data (ProgressData): Data containing progress information.
        **kwargs: Additional keyword arguments containing task details.
    """
    cache_key = _unique_progress_key()
    try:
        update_dict = data.model_dump(mode="json")
        app_cache.hset(cache_key, mapping=update_dict)
    except RedisError, PydanticSerializationError:
        current_app.logger.warning(
            W.FAILED_UPDATE_TASK_PROGRESS, {"done": data.done, "total": data.total}
        )
        traceback.print_exc()


@executed_signal.connect
def handle_excuted(_: object, data: ExecutedData, **kwargs: object) -> None:  # noqa: ARG001
    """Receive executed signal and update task execution status in Redis.

    Args:
        _: The sender of the signal.
        data (ExecutedData): Data containing executed information.
        **kwargs: Additional keyword arguments containing task details.
    """
    cache_key = _unique_progress_key()
    repository_id = resolve_repository_id(fqdn=data.fqdn)
    field_name = f"{repository_id}_{data.retries}"
    try:
        app_cache.hset(cache_key, mapping={field_name: data.model_dump_json()})
    except RedisError, PydanticSerializationError:
        current_app.logger.warning(
            W.FAILED_UPDATE_TASK_EXECUT_STATUS,
            {"rid": repository_id, "status": data.status, "retries": data.retries},
        )
        traceback.print_exc()


def get_task_status() -> TaskDetail | None:
    """Get the status of the cache update task.

    Returns:
        TaskDetail:
            Details of the cache update task. if no task is running, returns None.

    Raises:
        GroupCacheError: If there is an error connecting to Redis.
        DatastoreError: If there is an error parsing task status data.
    """
    cache_key = _unique_progress_key()
    try:
        raw = app_cache.hgetall(cache_key)
        if not raw:
            return None
    except RedisError as exc:
        raise DatastoreError(E.FAILED_FETCH_UPDATE_TASK_STATUS) from exc

    task_data = {
        k.decode("utf-8"): v.decode("utf-8")
        for k, v in t.cast("dict[bytes, bytes]", raw).items()
    }

    try:
        progress = ProgressData.model_validate(task_data, extra="ignore")

        results: list[ExecutedData] = [
            ExecutedData.model_validate_json(value)
            for key, value in task_data.items()
            if key not in {"status", "current", "done", "total"}
        ]
        repository_ids = [resolve_repository_id(fqdn=result.fqdn) for result in results]
        repository_query = make_criteria_object(
            "repositories", i=repository_ids, l=len(repository_ids)
        )
        searchd = repositories.search(repository_query)
        repository_map = {repo.id: repo for repo in searchd.resources}
        detail_results = [
            RepositoryCache(
                id=r.id,
                service_name=r.service_name,
                service_url=r.service_url,
                updated=result.updated_at,
                status=result.status,
            )
            for result in results
            if (r := repository_map.get(resolve_repository_id(fqdn=result.fqdn)))
        ]

        task_status = TaskDetail(
            results=detail_results,
            status=progress.status,
            current=resolve_repository_id(fqdn=progress.current),
            done=progress.done,
            total=progress.total,
        )
    except ValidationError as exc:
        raise GroupCacheError(E.FAILED_PARSE_UPDATE_TASK_STATUS) from exc

    return task_status


class ProgressData(ProgressDataBase):
    """Model for progress data entity."""

    status: t.Literal["pending", "started", "in_progress", "completed"]  # pyright: ignore[reportIncompatibleVariableOverride]
    """The status of the cache update task."""
