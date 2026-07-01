#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Providers of decorators for client functions."""

# ruff: noqa: ANN002, ANN003

import hashlib
import inspect
import traceback
import typing as t

from functools import partial, wraps
from typing import get_type_hints

from flask import current_app
from flask_login import current_user
from pydantic import BaseModel, TypeAdapter
from pydantic_core import ValidationError
from redis.exceptions import RedisError

from server.auth import is_user_logged_in
from server.config import config
from server.datastore import app_cache
from server.entities.map_error import MapError
from server.messages import E, I, W


class Cacheable[**P, R: BaseModel](t.Protocol):
    """Callable protocol for cached resources with cache control methods."""

    __name__: str

    _cache_namespace: str

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call wrapped function with cache behavior."""
        ...

    def clear_cache(self, *identifier: str) -> None:
        """Delete cached responses for the given function and resource id.

        Args:
            identifier (str): The identifier(s) to delete cache for.
        """
        ...


@t.overload
def cache_resource[**P, R: BaseModel](f: t.Callable[P, R]) -> Cacheable[P, R]: ...
@t.overload
def cache_resource[**P, R: BaseModel](
    *,
    id_generator: t.Callable[..., str] | None = None,
    timeout: int | None = None,
) -> t.Callable[[t.Callable[P, R]], Cacheable[P, R]]: ...


def cache_resource[**P, R: BaseModel](  # noqa: C901
    f: t.Callable[P, R] | None = None,
    *,
    id_generator: t.Callable[..., str] | None = None,
    timeout: int | None = None,
) -> Cacheable[P, R] | t.Callable[[t.Callable[P, R]], Cacheable[P, R]]:
    """Cache the response of the API client function using Redis.

    This decorator attaches cache metadata and provides a method to clear the cache
    for the decorated function.

    Args:
        f (Callable | None): The function to decorate.
        id_generator (Callable[..., str]):
            Function to generate a unique identifier string to cache key.
            If not provided, the first argument of the decorated function will be used.
        timeout (int):
            Timeout for the cache entry in seconds, overrides the default from config.

    Returns:
        Callable: Decorated function with caching.
    """

    def decorator(func: t.Callable[P, R]) -> Cacheable[P, R]:

        hints = get_type_hints(func)
        return_type: type[R] | None = hints.get("return")
        original_func = inspect.unwrap(func)
        namespace = f"{original_func.__module__}.{original_func.__qualname__}"

        @wraps(func)
        def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal timeout
            ttl = timeout or config.REDIS.cache_timeout

            if not ttl:
                # specifed 0, do not cache
                return func(*args, **kwargs)

            if not args:
                return func(*args, **kwargs)

            identifier = str(args[0])
            if id_generator:
                identifier = id_generator(*args, **kwargs)

            relevant_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in {"access_token", "client_secret"}
            }

            hash_input = f"{args}-{sorted(relevant_kwargs.items())!s}"
            args_hash = hashlib.md5(
                hash_input.encode(), usedforsecurity=False
            ).hexdigest()

            prefix = config.REDIS.key_prefix
            cache_key = f"{prefix}{namespace}-{identifier}-{args_hash}"

            try:
                cached_data: str | None = app_cache.get(cache_key)  # pyright: ignore[reportAssignmentType]
                if cached_data and return_type:
                    adapter = TypeAdapter(return_type)
                    cached_result: R = adapter.validate_json(cached_data)
                    current_app.logger.info(
                        I.RESOURCE_CACHE_HIT, {"func": namespace, "id": identifier}
                    )
                    return cached_result
            except RedisError:
                current_app.logger.warning(
                    W.FAILED_GET_CACHE, {"func": namespace, "id": identifier}
                )
                traceback.print_exc()
            except ValidationError:
                current_app.logger.warning(
                    W.FAILED_PARSE_CACHE, {"func": namespace, "id": identifier}
                )
                traceback.print_exc()

            result: R = func(*args, **kwargs)

            if isinstance(result, MapError):
                ttl = int(ttl / 100)

            try:
                app_cache.set(
                    cache_key,
                    result.model_dump_json(exclude_none=True),
                    ex=ttl if ttl > 0 else None,
                )
                current_app.logger.info(
                    I.RESOURCE_CACHE_CREATED,
                    {"func": namespace, "id": identifier},
                )
            except RedisError:
                current_app.logger.warning(
                    W.FAILED_SET_CACHE, {"func": namespace, "id": identifier}
                )
                traceback.print_exc()
            return result

        wrapper = t.cast("Cacheable[P, R]", _wrapper)
        wrapper._cache_namespace = namespace  # noqa: SLF001
        wrapper.clear_cache = partial(_clear_cache, wrapper)
        return wrapper

    if f is not None:
        return decorator(f)

    return decorator


def default_id_generator(*_, **__) -> str:
    """Function of default identifier generator.

    It generates an identifier string based on current user's permissions.

    Returns:
        str: The generated identifier string.
    """
    if not is_user_logged_in(current_user):
        return "by_anonymous"
    if current_user.is_system_admin:
        return "by_system_admin"

    permitted = sorted(current_user.permitted_repositories)

    return ",".join(permitted)


def _clear_cache(func: Cacheable, *identifier: str) -> None:
    """Delete cached responses for the given function and resource id.

    Args:
        func (Cacheable): The decorated function whose cache to delete.
        identifier (str): The identifier(s) to delete cache for.

    Raises:
        NotImplementedError: If the function is not decorated with @response_cache.
    """
    prefix = config.REDIS.key_prefix
    try:
        namespace = func._cache_namespace  # noqa: SLF001
    except AttributeError as exc:
        raise NotImplementedError(
            E.UNINIT_RESOURCE_CACHE % {"name": func.__name__}
        ) from exc

    for cid in identifier:
        match = f"{prefix}{namespace}-{cid}-*"
        try:
            cursor: str | int = "0"  # start with "0", exit with int 0
            while cursor != 0:
                cursor, keys = app_cache.scan(int(cursor), match, count=100)  # pyright: ignore[reportGeneralTypeIssues]

                if keys:
                    app_cache.delete(*keys)
        except RedisError:
            current_app.logger.warning(
                W.FAILED_DELETE_CACHE, {"func": namespace, "id": cid}
            )
            traceback.print_exc()
            continue

        current_app.logger.info(
            I.RESOURCE_CACHE_DELETED, {"func": namespace, "id": cid}
        )
