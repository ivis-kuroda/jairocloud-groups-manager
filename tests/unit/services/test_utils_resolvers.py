import typing as t

import pytest

from server.services.utils.resolvers import resolve_repository_id, resolve_service_id


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_resolve_repository_id_with_fqdn(app: Flask, mocker: MockerFixture):
    """Tests resolve_repository_id returns correct id from fqdn."""

    fqdn = "repo.example-domain.com"
    expected = "repo_example_domain_com"

    result = resolve_repository_id(fqdn=fqdn)

    assert result == expected


def test_resolve_repository_id_with_invalid_service_id_prefix(app: Flask, mocker: MockerFixture):
    """Tests resolve_repository_id returns None if service_id does not start with prefix."""
    pattern = "sp_{repository_id}_suffix"
    suffix = pattern.split("{repository_id}")[1]
    repository_id = "repo123"
    service_id = f"WRONG{repository_id}{suffix}"
    mocker.patch("server.config.config.REPOSITORIES.id_patterns.sp_connector", pattern)

    result = resolve_repository_id(service_id=service_id)

    assert result is None


def test_resolve_repository_id_with_valid_service_id(app: Flask, mocker: MockerFixture):
    """Tests resolve_repository_id returns correct id from valid service_id."""
    pattern = "sp_{repository_id}_suffix"
    prefix = pattern.split("{repository_id}", maxsplit=1)[0]
    suffix = pattern.split("{repository_id}")[1]
    repository_id = "repo123"
    service_id = f"{prefix}{repository_id}{suffix}"
    mocker.patch("server.config.config.REPOSITORIES.id_patterns.sp_connector", pattern)

    result = resolve_repository_id(service_id=service_id)

    assert result == repository_id


def test_resolve_repository_id_error(app: Flask, mocker: MockerFixture):
    """Tests resolve_repository_id raises ValueError if neither fqdn nor service_id is provided."""

    error_msg = "E151 | Either 'fqdn' or 'service_id' must be provided."

    with pytest.raises(ValueError, match=error_msg):
        resolve_repository_id()


def test_resolve_repository_id_removeprefix_removesuffix_branch(app: Flask, mocker: MockerFixture):
    """Tests that resolve_repository_id returns correct id when service_id matches prefix and suffix."""
    pattern = "sp_{repository_id}_suffix"
    prefix = pattern.split("{repository_id}", maxsplit=1)[0]
    suffix = pattern.split("{repository_id}")[1]
    repository_id = "repo123"
    service_id = f"{prefix}{repository_id}{suffix}"
    mocker.patch("server.config.config.REPOSITORIES.id_patterns.sp_connector", pattern)

    result = resolve_repository_id(service_id=service_id)

    assert result == repository_id


def test_resolve_service_id_with_fqdn(app: Flask, mocker: MockerFixture):
    """Tests resolve_service_id returns correct service_id from fqdn."""
    fqdn = "repo.example-domain.com"
    expected_service_id = "jc_repo_example_domain_com_test"

    result = resolve_service_id(fqdn=fqdn)

    assert result == expected_service_id


def test_resolve_service_id_with_repository_id(app: Flask, mocker: MockerFixture):
    """Tests resolve_service_id returns correct service_id from repository_id."""

    repository_id = "myrepo"
    expected_service_id = "jc_myrepo_test"

    result = resolve_service_id(repository_id=repository_id)

    assert result == expected_service_id


def test_resolve_service_id_error(app: Flask, mocker: MockerFixture):
    """Tests resolve_service_id raises ValueError if neither fqdn nor repository_id is provided."""

    error_msg = "Either 'fqdn' or 'repository_id' must be provided."

    with pytest.raises(ValueError, match=error_msg):
        resolve_service_id()
