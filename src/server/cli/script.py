#
# Copyright (C) 2026 National Institute of Informatics.
#

"""Command-line interface for token management."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import click

from flask import current_app


@click.command()
@click.argument("script", type=click.Path(exists=True))
def script(script: str) -> None:
    """Run a custom script."""
    script_path = Path(script).resolve()

    spec = spec_from_file_location("__main__", script_path)
    if spec is None or spec.loader is None:
        current_app.logger.error("Failed to load script: %s", script)
        return

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
