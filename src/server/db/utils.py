#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Database utilities for the server application."""

import typing as t

from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules
from typing import cast

from flask import current_app
from sqlalchemy_utils import create_database, database_exists, drop_database
from werkzeug.local import LocalProxy

from server.exc import DatabaseError
from server.messages import E, I


if t.TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def create_db() -> None:
    """Create the database if it does not already exist."""
    db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]

    if database_exists(db_uri):
        current_app.logger.info(I.DATABASE_ALREADY_EXISTS)
        return

    create_database(db_uri)
    current_app.logger.info(I.DATABASE_CREATED)


def destroy_db() -> None:
    """Drop the database if it exists."""
    db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]

    if not database_exists(db_uri):
        current_app.logger.info(I.DATABASE_NOT_EXIST)
        return

    drop_database(db_uri)
    current_app.logger.info(I.DATABASE_DESTROYED)


def create_tables() -> None:
    """Create all tables defined in the models.

    Raises:
        DatabaseError: If the database does not exist.
    """
    db_url = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not database_exists(db_url):
        raise DatabaseError(E.DATABASE_NOT_EXIST)

    db.create_all()
    current_app.logger.info(I.TABLE_CREATED)


def drop_tables() -> None:
    """Drop all tables in the database.

    Raises:
        DatabaseError: If the database does not exist.
    """
    db_url = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not database_exists(db_url):
        raise DatabaseError(E.DATABASE_NOT_EXIST)

    db.drop_all()
    current_app.logger.info(I.TABLE_DROPPED)


def load_models() -> None:
    """Dynamically import all model modules to register them with SQLAlchemy."""
    for _, name, _ in iter_modules([Path(__file__).parent]):
        import_module(f"{__package__}.{name}")


db = cast("SQLAlchemy", LocalProxy(lambda: current_app.extensions["sqlalchemy"]))
"""Database instance proxy."""
