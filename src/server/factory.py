#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Factory for creating and configuring the Flask application."""

# ruff: file-ignore[missing-type-function-argument, missing-type-args, missing-type-kwargs]
# ruff: file-ignore[missing-return-type-special-method, missing-return-type-private-function]

import typing as t

from uuid import uuid7

import flask_login

from celery import Celery, Task
from flask import Flask
from flask_login import current_user

from server.auth import get_user_from_store, is_user_logged_in
from server.const import RUNTIME_ROLE
from server.ext import JAIROCloudGroupsManager


if t.TYPE_CHECKING:
    from .config import RuntimeConfig


@t.overload
def create_app(
    import_name: str,
    *,
    runtime_role: RUNTIME_ROLE = RUNTIME_ROLE.SERVER,
) -> Flask: ...
@t.overload
def create_app(
    import_name: str,
    *,
    config_path: str,
    runtime_role: RUNTIME_ROLE = RUNTIME_ROLE.SERVER,
) -> Flask: ...
@t.overload
def create_app(
    import_name: str,
    *,
    config: RuntimeConfig,
    runtime_role: RUNTIME_ROLE = RUNTIME_ROLE.SERVER,
) -> Flask: ...
def create_app(
    import_name: str,
    config_path: str | None = None,
    config: RuntimeConfig | None = None,
    runtime_role: RUNTIME_ROLE = RUNTIME_ROLE.SERVER,
) -> Flask:
    """Factory function to create and configure the Flask application.

    Args:
        import_name (str): The name of the application package.
        config_path (str | None): The path to the configuration TOML file.
        config (RuntimeConfig | None): The runtime configuration instance.
        runtime_role (RUNTIME_ROLE): The role of the application at runtime.

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(import_name)
    app.config["RUNTIME_ROLE"] = runtime_role
    app.config["RUNTIME_CONFIG"] = config or config_path
    JAIROCloudGroupsManager(app)
    celery_init_app(app)

    return app


def celery_init_app(app: Flask) -> Celery:
    """Initialize and configure a Celery application with the Flask app context.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        Celery: The configured Celery application instance.
    """

    class FlaskTask(Task):
        """Task with Flask application context."""

        @t.override
        def __call__(self, *args, **kwargs):
            ploxy = flask_login.current_user
            session_id = kwargs.pop("session_id", None)

            with app.app_context():
                if session_id and (user := get_user_from_store(session_id)):
                    flask_login.current_user = user
                result = self.run(*args, **kwargs)

            flask_login.current_user = ploxy
            return result

        @t.override
        def apply_async(  # pyright: ignore[reportIncompatibleMethodOverride]
            self, args, kwargs=None, session_required=None, **options
        ):
            options.setdefault("task_id", str(uuid7()))
            if session_required and is_user_logged_in(current_user):
                kwargs = kwargs or {}
                kwargs.setdefault("session_id", current_user.session_id)
            return super().apply_async(args, kwargs, **options)

    celery_app: Celery = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app

    return celery_app
