#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Extension for the server application."""

import typing as t

from functools import cached_property
from pathlib import Path

from sqlalchemy_utils import database_exists
from weko_group_cache_db.config import setup_config as setup_weko_group_cache_db_config

from server.api.router import create_api_blueprint
from server.auth import login_manager
from server.cli.base import register_cli_commands
from server.config import RuntimeConfig, load_config
from server.const import DEFAULT_CONFIG_PATH
from server.datastore import setup_datastore
from server.db.base import db
from server.db.utils import load_models
from server.exc import JAIROCloudGroupsManagerError
from server.logger import setup_logger
from server.messages import E, W


if t.TYPE_CHECKING:
    from flask import Flask
    from redis import Redis


class JAIROCloudGroupsManager:
    """Flask extension for JAIRO Cloud Groups management."""

    def __init__(self, app: Flask | None = None) -> None:
        """Initialize this extension instance.

        Args:
            app (:class:`~flask.Flask` | None): The Flask application instance.

        """
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize a Flask application for use with this extension instance.

        Args:
            app (:class:`~flask.Flask`): The Flask application instance.

        """
        self.state = _JAIROCloudGroupsManagerState(app)
        self.init_config(app)
        self.setup_extension(app)

        self.init_db_app(app)
        self.init_storage()

        if app.debug and app.config.get("ENV") == "development":
            self.setup_dev_contrib(app)

        app.extensions["jairocloud-groups-manager"] = self

    def init_config(self, app: Flask) -> None:
        """Initialize the configuration for the Flask extensions.

        Args:
            app (:class:`~flask.Flask`): The Flask application instance.
        """
        app.config.from_mapping(self.config.FLASK)
        app.config.from_prefixed_env()
        app.config.from_prefixed_env("JCGROUPS_")

        setup_weko_group_cache_db_config(self.config.for_group_caches)

    def setup_extension(self, app: Flask) -> None:
        """Set up this extension with the Flask application.

        Args:
            app (:class:`~flask.Flask`): The Flask application instance.
        """
        setup_logger(app, self.config)
        login_manager.init_app(app)

        app.register_blueprint(create_api_blueprint(), url_prefix="/api")
        register_cli_commands(app)

    def init_db_app(self, app: Flask) -> None:  # ruff:ignore[no-self-use]
        """Initialize the database for the this extension.

        Loads all model modules to register them with SQLAlchemy.

        Args:
            app (:class:`~flask.Flask`): The Flask application instance.
        """
        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if not database_exists(db_uri):
            app.logger.warning(W.DATABASE_NOT_EXIST)

        db.init_app(app)
        load_models()

    def setup_dev_contrib(self, app: Flask) -> None:
        """Provide development contribution utilities."""
        with app.app_context():
            from contrib import setup_contrib  # ruff: ignore[import-outside-top-level]

            setup_contrib(app, self.config)

    if t.TYPE_CHECKING:
        config: RuntimeConfig
        datastore: dict[str, Redis]
        temporary_storage: Path
        storage: Path

    def __getattr__(self, name: str):  # ruff: ignore[missing-return-type-special-method, undocumented-magic-method]
        try:
            state = object.__getattribute__(self, "state")
        except AttributeError:
            raise JAIROCloudGroupsManagerError(E.EXTENSION_NOT_INITIALIZED)  # ruff: ignore[raise-without-from-inside-except]
        return getattr(state, name)


class _JAIROCloudGroupsManagerState:
    """JAIRO Cloud Groups Manager extension state object."""

    def __init__(self, app: Flask) -> None:
        self.app = app

        config = app.config.get("RUNTIME_CONFIG") or DEFAULT_CONFIG_PATH
        if isinstance(config, str):
            app.logger.info("Loading runtime configuration from: %s", config)
        else:
            app.logger.info("Using provided runtime configuration object.")
        self.config = (
            config if isinstance(config, RuntimeConfig) else load_config(config)
        )

        self.init_storage()

    @cached_property
    def datastore(self) -> dict[str, Redis]:
        return setup_datastore(self.app, self.config)

    @property
    def temporary_storage(self) -> Path:
        return Path(self.config.STORAGE.local.temporary)

    @property
    def storage(self) -> Path:
        return Path(self.config.STORAGE.local.storage)

    def init_storage(self) -> None:
        """Initialize the storage for this extension."""
        if self.config.STORAGE.type == "local":
            self.temporary_storage.mkdir(parents=True, exist_ok=True)
            self.storage.mkdir(parents=True, exist_ok=True)
