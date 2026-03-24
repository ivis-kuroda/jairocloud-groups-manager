#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Command-line interface for database management."""

import click

from server.db.utils import create_db, create_tables, destroy_db, drop_tables


@click.group()
def db() -> None:
    """Manage database."""


@db.command()
def init() -> None:
    """Initialize database."""
    create_db()


@db.command()
def create() -> None:
    """Create database tables."""
    create_tables()


@db.command()
def drop() -> None:
    """Drop database tables."""
    drop_tables()


@db.command()
def destroy() -> None:
    """Destroy database."""
    destroy_db()
