#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Extension for the server application."""

import typing as t

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
from server.exc import ConfigurationError
from server.logger import setup_logger
from server.messages import E, W


if t.TYPE_CHECKING:
    from flask import Flask
    from redis import Redis


class JAIROCloudGroupsManager:
    """Flask extension for JAIRO Cloud Groups management."""

    def __init__(
        self, app: Flask | None = None, config: RuntimeConfig | str | None = None
    ) -> None:
        """Initialize this extension instance.

        Args:
            app (Flask | None): The Flask application instance.
            config (RuntimeConfig | str | None): The runtime configuration
                instance or path to the configuration file.

        """
        self._config = config or DEFAULT_CONFIG_PATH
        self.datastore: dict[str, Redis] = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize a Flask application for use with this extension instance.

        Args:
            app (Flask): The Flask application instance.

        """
        self.init_config(app)
        setup_logger(app, self.config)

        self.init_db_app(app)
        login_manager.init_app(app)

        self.datastore = setup_datastore(app, self.config)
        app.register_blueprint(create_api_blueprint(), url_prefix="/api")
        register_cli_commands(app)
        self.init_storage()

        if app.debug and app.config.get("ENV") == "development":
            self.dev_contrib(app)

        app.extensions["jairocloud-groups-manager"] = self

    def init_config(self, app: Flask | None) -> None:
        """Initialize the configuration for this extension.

        Args:
            app (Flask | None): The Flask application instance.

        """
        if isinstance(self._config, str):
            self._config = load_config(self._config)

        if app is not None:
            app.config.from_mapping(self.config.FLASK)
            app.config.from_prefixed_env()

        setup_weko_group_cache_db_config(self.config.for_group_caches)

    def init_db_app(self, app: Flask) -> None:  # noqa: PLR6301
        """Initialize the database for the this extension.

        Loads all model modules to register them with SQLAlchemy.

        Args:
            app (Flask): The Flask application instance.
        """
        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if not database_exists(db_uri):
            app.logger.warning(W.DATABASE_NOT_EXIST)

        db.init_app(app)
        load_models()

    def init_storage(self) -> None:
        """Initialize the storage for this extension."""
        if self.config.STORAGE.type == "local":
            tmp_dir = Path(self.config.STORAGE.local.temporary)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            storage_dir = Path(self.config.STORAGE.local.storage)
            storage_dir.mkdir(parents=True, exist_ok=True)

    def dev_contrib(self, app: Flask) -> None:
        """Provide development contribution utilities."""
        with app.app_context():
            from contrib import developers, messages  # noqa: PLC0415

            messages.generate_type_stub()
            app.register_blueprint(
                developers.create_developer_blueprint(self.config),
                url_prefix="/api/dev",
            )

    @property
    def config(self) -> RuntimeConfig:
        """Runtime configuration instance.

        Returns:
            RuntimeConfig: The runtime configuration instance.

        Raises:
            ConfigurationError: If the configuration has not been initialized.
        """
        if isinstance(self._config, str):
            raise ConfigurationError(E.UNINIT_SERVER_CONFIG)

        return self._config
