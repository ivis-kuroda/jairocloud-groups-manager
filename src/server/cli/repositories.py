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
from server.services import repositories as repository_services


@click.group()
def repositories() -> None:
    """Manage repositories."""


@repositories.command()
@click.argument("repository_id")
def get(repository_id: str) -> None:
    """Get Service resource of the Repository."""
    obj = repository_services.get_by_id(repository_id, raw=True)
    if obj is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"rid": repository_id})
        return

    json = obj.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_REPOSITORY, {"json": json})


@repositories.command()
@click.argument("repository_id")
@click.option("--more-detail", is_flag=True, help="Show more detailed information.")
def detail(repository_id: str, *, more_detail: bool) -> None:
    """Get Repository details."""
    detail = repository_services.get_by_id(repository_id, more_detail=more_detail)
    if detail is None:
        current_app.logger.error(E.REPOSITORY_NOT_FOUND, {"rid": repository_id})
        return

    json = detail.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_REPOSITORY, {"json": json})


@repositories.command()
@click.option("-n", "--name", required=True, help="Name of the Repository.")
@click.option("-u", "--url", required=True, help="URL of the Repository.")
@click.option(
    "-e",
    "--entity-id",
    multiple=True,
    help="Entity ID of the SP linked to the Repository. [multiple]",
)
def create(name: str, url: str, entity_id: tuple[str] | None = None) -> None:
    """Create a new Repository.

    If no entity ID is provided, a default one will be generated using the URL.
    """
    service_url = HttpUrl(url)
    if not entity_id:
        entity_id = (f"{service_url.encoded_string()}shibboleth-sp",)

    detail = RepositoryDetail(
        service_name=name,
        service_url=service_url,
        entity_ids=list(entity_id),
    )
    repository_services.create(detail)


@repositories.command()
@click.argument("repository_id")
@click.option("-f", is_flag=True, help="Skip confirmation.")
def delete(repository_id: str, *, yes: bool) -> None:
    """Delete a Repository."""
    if not yes:
        service_name: str = click.prompt(
            "To confirm, type the name of the Repository to delete",
            type=str,
            default="",
        )
    else:
        detail = repository_services.get_by_id(repository_id)
        service_name = t.cast("str", detail.service_name) if detail else ""

    repository_services.delete_by_id(repository_id, service_name)
