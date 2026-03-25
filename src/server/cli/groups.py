#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Command-line interface for group management."""

import click

from flask import current_app

from server.entities.group_detail import GroupDetail, Repository
from server.messages import E, I, W
from server.services import groups as group_services


@click.group()
def groups() -> None:
    """Manage groups."""


@groups.command()
@click.argument("group_id")
def get(group_id: str) -> None:
    """Get Service resource of the Group."""
    obj = group_services.get_by_id(group_id, raw=True)
    if obj is None:
        current_app.logger.error(E.GROUP_NOT_FOUND, {"gid": group_id})
        return

    json = obj.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_GROUP, {"json": json})


@groups.command()
@click.argument("group_id")
@click.option("--more-detail", is_flag=True, help="Show more detailed information.")
def detail(group_id: str, *, more_detail: bool) -> None:
    """Get Group details."""
    detail = group_services.get_by_id(group_id, more_detail=more_detail)
    if detail is None:
        current_app.logger.error(E.GROUP_NOT_FOUND, {"gid": group_id})
        return

    json = detail.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
    current_app.logger.info(I.SUCCESS_GET_GROUP, {"json": json})


@groups.command()
@click.option("-i", "--id", "group_id", required=True, help="ID of the Group.")
@click.option("-n", "--name", required=True, help="Name of the Group.")
@click.option(
    "-r",
    "--repository",
    "repository_id",
    required=True,
    help="ID of the Repository to which the Group belongs.",
)
@click.option("-d", "--description", help="Description of the Group.")
def create(group_id: str, name: str, repository_id: str, description: str) -> None:
    """Create a new Group."""
    detail = GroupDetail(
        user_defined_id=group_id,
        display_name=name,
        repository=Repository(id=repository_id),
        description=description,
    )
    group_services.create(detail)


@groups.command()
@click.argument("group_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
def delete(group_id: str, *, yes: bool) -> None:
    """Delete a Group."""
    if not yes:
        click.confirm((W.CONFIRM_DELETE_GROUP % {"gid": group_id}).data, abort=True)  # pyright: ignore[reportAttributeAccessIssue]

    group_services.delete_by_id(group_id)
