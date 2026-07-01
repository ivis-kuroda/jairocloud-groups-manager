import typing as t

import pytest

from server.exc import ProgrammingError
from server.messages import E
from server.services.utils.resolvers import resolve_repository_id, resolve_service_id

from tests.helpers import regex


if t.TYPE_CHECKING:
    from server.config import RuntimeConfig


def test_resolve_repository_id_from_fqdn(config):
    fqdn = "test-resolve.repo.ac.jp"
    expected = "test_resolve_repo_ac_jp"

    result = resolve_repository_id(fqdn=fqdn)

    assert result == expected


def test_resolve_repository_id_from_service_id(config: RuntimeConfig):
    pattern = config.REPOSITORIES.id_patterns.sp_connector
    expected = repository_id = "test_resolve_repo_ac_jp"
    service_id = pattern.format(repository_id=repository_id)

    result = resolve_repository_id(service_id=service_id)

    assert result == expected


def test_resolve_repository_id_from_service_id_invalid(config: RuntimeConfig):
    pattern = config.REPOSITORIES.id_patterns.sp_connector
    _, suffix = pattern.split("{repository_id}")
    repository_id = "test_resolve_repo_ac_jp"
    service_id = f"invalid_{repository_id}{suffix}"

    result = resolve_repository_id(service_id=service_id)

    assert result is None


def test_resolve_repository_id_programming_error(config):
    with pytest.raises(ProgrammingError, match=regex(E.REPOSITORY_REQUIRES_FQDN_OR_SERVICE_ID)):
        resolve_repository_id()  # pyright: ignore[reportCallIssue]


def test_resolve_service_id_from_fqdn(config: RuntimeConfig):
    pattern = config.REPOSITORIES.id_patterns.sp_connector
    prefix, suffix = pattern.split("{repository_id}")
    fqdn = "test-resolve.repo.ac.jp"
    expected = f"{prefix}test_resolve_repo_ac_jp{suffix}"

    result = resolve_service_id(fqdn=fqdn)

    assert result == expected


def test_resolve_service_id_from_repository_id(config: RuntimeConfig):
    pattern = config.REPOSITORIES.id_patterns.sp_connector
    prefix, suffix = pattern.split("{repository_id}")
    repository_id = "test_resolve_repo_ac_jp"
    expected = f"{prefix}{repository_id}{suffix}"

    result = resolve_service_id(repository_id=repository_id)

    assert result == expected


def test_resolve_service_id_error(config):
    with pytest.raises(ProgrammingError, match=regex(E.RESOURCE_REQUIRES_FQDN_OR_REPOSITORY_ID)):
        resolve_service_id()  # pyright: ignore[reportCallIssue]
