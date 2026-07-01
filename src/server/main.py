#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Entry point for the command-line interface."""

from flask.cli import FlaskGroup

from server.const import RUNTIME_ROLE
from server.factory import create_app


app = create_app(__name__, runtime_role=RUNTIME_ROLE.CLI)
cli = FlaskGroup(create_app=lambda: app)

if __name__ == "__main__":
    cli()
