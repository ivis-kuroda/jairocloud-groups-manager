#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Entry point for the server application."""

from server.factory import create_app


app = create_app(__name__)
"""Entry point for the server application."""


def cli() -> None:
    """Entry point for the command-line interface."""
    with app.app_context():
        app.cli()
