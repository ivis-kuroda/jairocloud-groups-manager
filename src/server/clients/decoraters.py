#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Providers of decorators for client functions."""

# ruff: noqa: ANN002, ANN003, ANN202, SLF001

import hashlib
import inspect
import traceback
import typing as t

from functools import wraps

from flask import current_app
from pydantic import BaseModel, TypeAdapter
from pydantic_core import ValidationError
from redis.exceptions import RedisError

from server.config import config
from server.datastore import app_cache
from server.entities.map_error import MapError
from server.messages import E, I, W


@t.overload
def cache_resource[T: t.Callable[..., BaseModel]](f: T) -> T: ...
@t.overload
def cache_resource[T: t.Callable[..., BaseModel]](
    *,
    identifier_generator: t.Callable[..., str] | None = None,
    timeout: int | None = None,
) -> t.Callable[[T], T]: ...


def cache_resource[T: t.Callable[..., BaseModel]](  # noqa: C901
    f: T | None = None,
    *,
    identifier_generator: t.Callable[..., str] | None = None,
    timeout: int | None = None,
) -> T | t.Callable:
    """Cache the response of the API client function using Redis.

    Args:
        f (Callable | None): The function to decorate.
        identifier_generator (Callable[..., str]):
            Function to generate a unique identifier string to cache key.
            If not provided, the first argument of the decorated function will be used.
        timeout (int):
            Timeout for the cache entry in seconds, overrides the default from config.

    Returns:
        Callable: Decorated function with caching.
    """

    def decorator(func: t.Callable):  # noqa: C901

        hints = t.get_type_hints(func)
        return_type: type[BaseModel] | None = hints.get("return")
        original_func = inspect.unwrap(func)
        import_name = f"{original_func.__module__}.{original_func.__qualname__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal timeout
            ttl = timeout or config.REDIS.cache_timeout

            if not ttl:
                # specifed 0, do not cache
                return func(*args, **kwargs)

            if not args:
                return func(*args, **kwargs)
            identifier = str(args[0])
            if identifier_generator:
                identifier = identifier_generator(*args, **kwargs)

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
            cache_key = f"{prefix}{import_name}-{identifier}-{args_hash}"

            result = None
            try:
                cached_data: str | None = app_cache.get(cache_key)  # pyright: ignore[reportAssignmentType]
                if cached_data and return_type:
                    adapter = TypeAdapter(return_type)
                    result = adapter.validate_json(cached_data)
            except RedisError:
                current_app.logger.warning(
                    W.FAILED_GET_CACHE, {"func": import_name, "id": identifier}
                )
                traceback.print_exc()
                cached_data = None
            except ValidationError:
                current_app.logger.warning(
                    W.FAILED_PARSE_CACHE, {"func": import_name, "id": identifier}
                )
                traceback.print_exc()

            if result:
                current_app.logger.info(
                    I.RESOURCE_CACHE_HIT, {"func": import_name, "id": identifier}
                )
                return result

            result = func(*args, **kwargs)

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
                    {"func": import_name, "id": identifier},
                )
            except RedisError:
                current_app.logger.warning(
                    W.FAILED_SET_CACHE, {"func": import_name, "id": identifier}
                )
                traceback.print_exc()
            return result

        wrapper._import_name = import_name  # pyright: ignore[reportAttributeAccessIssue]
        wrapper.clear_cache = lambda *identifier: clear_cache(  # pyright: ignore[reportAttributeAccessIssue]
            wrapper, *identifier
        )
        return wrapper

    if f is not None:
        return decorator(f)

    return decorator


def clear_cache(func: t.Callable, *identifier: str) -> None:
    """Delete cached responses for the given function and resource id.

    Args:
        func (Callable): The decorated function whose cache to delete.
        identifier (str): The identifier(s) to delete cache for.

    Raises:
        NotImplementedError: If the function is not decorated with @response_cache.
    """
    prefix = config.REDIS.key_prefix
    import_name = getattr(func, "_import_name", None)
    if not import_name:
        error = E.UNINIT_RESOURCE_CACHE % {"name": func.__name__}
        raise NotImplementedError(error)

    try:
        for cid in identifier:
            match = f"{prefix}{import_name}-{cid}-*"

            cursor: str | int = "0"  # start with "0", exit with int 0
            while cursor != 0:
                cursor, keys = app_cache.scan(  # pyright: ignore[reportGeneralTypeIssues]
                    cursor=int(cursor),
                    match=match,
                    count=100,
                )
                if not keys:
                    continue
                app_cache.delete(*keys)
        current_app.logger.info(
            I.RESOURCE_CACHE_DELETED, {"func": import_name, "id": identifier}
        )
    except RedisError:
        current_app.logger.warning(
            W.FAILED_DELETE_CACHE, {"func": import_name, "id": identifier}
        )
        traceback.print_exc()
