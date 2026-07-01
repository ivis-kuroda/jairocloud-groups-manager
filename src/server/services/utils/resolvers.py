#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities for resolvers in the application."""

import typing as t

from server.config import config
from server.exc import ProgrammingError
from server.messages import E


@t.overload
def resolve_repository_id(*, fqdn: str) -> str: ...
@t.overload
def resolve_repository_id(*, service_id: str) -> str | None: ...
def resolve_repository_id(
    *, fqdn: str | None = None, service_id: str | None = None
) -> str | None:
    """Resolve the repository ID from either FQDN or service ID.

    Args:
        fqdn (str): The fully qualified domain name.
        service_id (str): The service ID.

    Returns:
        str: The corresponding repository ID, or None if it cannot be resolved.

    Raises:
        ProgrammingError: If neither `fqdn` nor `service_id` is provided.
    """
    pattern = config.REPOSITORIES.id_patterns.sp_connector
    prefix, suffix = pattern.split("{repository_id}")

    if fqdn is not None:
        return fqdn.replace(".", "_").replace("-", "_")
    if service_id is not None:
        if not service_id.startswith(prefix) or not service_id.endswith(suffix):
            return None
        return service_id.removeprefix(prefix).removesuffix(suffix)

    raise ProgrammingError(E.REPOSITORY_REQUIRES_FQDN_OR_SERVICE_ID)


@t.overload
def resolve_service_id(*, fqdn: str) -> str: ...
@t.overload
def resolve_service_id(*, repository_id: str) -> str: ...
def resolve_service_id(
    *, fqdn: str | None = None, repository_id: str | None = None
) -> str:
    """Resolve the service ID from either FQDN or repository ID.

    Args:
        repository_id (str): The repository ID.
        fqdn (str): The fully qualified domain name.

    Returns:
        str: The corresponding service ID.

    Raises:
        ProgrammingError: If neither `fqdn` nor `repository_id` is provided.
    """
    pattern = config.REPOSITORIES.id_patterns.sp_connector

    if fqdn is not None:
        repository_id = resolve_repository_id(fqdn=fqdn)
    if repository_id is not None:
        return pattern.format(repository_id=repository_id)

    raise ProgrammingError(E.RESOURCE_REQUIRES_FQDN_OR_REPOSITORY_ID)
