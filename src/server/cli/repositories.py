#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Command-line interface for repository management."""

import typing as t

import click

from flask import current_app
from pydantic import HttpUrl

from server.entities.repository_detail import RepositoryDetail
from server.messages import E, I
from server.services.resources import RepositoryService
from server.services.utils import resolve_repository_id


@click.group()
def repositories() -> None:
    """Manage repositories."""


@repositories.command()
@click.argument("fqdn")
def get(fqdn: str) -> None:
    """Get Service resource of the Repository."""
    repository_id = resolve_repository_id(fqdn=fqdn)
    obj = RepositoryService.get_by_id(repository_id, raw=True)
    if obj is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"rid": repository_id})
        return

    json = obj.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_REPOSITORY, {"json": json})


@repositories.command()
@click.argument("fqdn")
@click.option("--more-detail", is_flag=True, help="Show more detailed information.")
def detail(fqdn: str, *, more_detail: bool) -> None:
    """Get Repository details."""
    repository_id = resolve_repository_id(fqdn=fqdn)
    detail = RepositoryService.get_by_id(repository_id, more_detail=more_detail)
    if detail is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"rid": repository_id})
        return

    json = detail.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_REPOSITORY, {"json": json})


@repositories.command()
@click.option("-n", "--name", required=True, help="Name of the Repository.")
@click.option("-d", "--fqdn", required=True, help="FQDN of the Repository.")
@click.option(
    "-e",
    "--entity-id",
    multiple=True,
    help="Entity ID of the SP linked to the Repository. [multiple]",
)
def create(name: str, fqdn: str, entity_id: tuple[str] | str | None = None) -> None:
    """Create a new Repository.

    If no entity ID is provided, a default one will be generated using the FQDN.
    default: https://<fqdn>/shibboleth-sp
    """
    service_url = HttpUrl.build(scheme="https", host=fqdn)
    if not entity_id:
        default_path = "shibboleth-sp"
        entity_id = (str(HttpUrl.build(scheme="https", host=fqdn, path=default_path)),)

    detail = RepositoryDetail(
        service_name=name,
        service_url=service_url,
        entity_ids=list(entity_id),
    )
    RepositoryService.create(detail)


@repositories.command()
@click.argument("fqdn")
@click.option("-f", is_flag=True, help="Skip confirmation.")
def delete(fqdn: str, *, yes: bool) -> None:
    """Delete a Repository."""
    repository_id = resolve_repository_id(fqdn=fqdn)
    if not yes:
        service_name: str = click.prompt(
            "To confirm, type the name of the Repository to delete",
            type=str,
            default="",
        )
    else:
        detail = RepositoryService.get_by_id(repository_id)
        service_name = t.cast("str", detail.service_name) if detail else ""

    RepositoryService.delete_by_id(repository_id, service_name)
