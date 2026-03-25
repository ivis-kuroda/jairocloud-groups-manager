#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API router for the server application."""

import traceback

from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from flask import Blueprint
from flask_pydantic import validate

from server.auth import login_manager, refresh_session
from server.exc import (
    ApiRequestError,
    InfrastructureError,
    JAIROCloudGroupsManagerError,
    ServiceSettingsError,
    SystemAdminNotFound,
)
from server.messages import E

from .schemas import ErrorResponse


def create_api_blueprint() -> Blueprint:
    """Register blueprints for API routers.

    Returns:
        Blueprint: Blueprint instance for API routers.
    """
    bp_api = Blueprint("api", __name__)

    for _, module_name, _ in iter_modules([str(Path(__file__).parent)]):
        module = import_module(f"{__package__}.{module_name}")
        url_prefix = f"/{module_name}".replace("_", "-")
        if hasattr(module, "bp") and isinstance(module.bp, Blueprint):
            bp_api.register_blueprint(module.bp, url_prefix=url_prefix)

    @bp_api.errorhandler(JAIROCloudGroupsManagerError)
    @validate()
    def handle_unexpected_error(
        error: JAIROCloudGroupsManagerError,
    ) -> tuple[ErrorResponse, int]:
        """Handle unexpected errors for the API.

        Args:
            error: The error object.

        Returns:
            tuple: Response body and 500 status code.
        """
        traceback.print_exc()
        # override error message to avoid exposing sensitive information
        return ErrorResponse(code=error.code, message=E.UNEXPECTED_SERVER_ERROR), 500

    @bp_api.errorhandler(InfrastructureError)
    @bp_api.errorhandler(ServiceSettingsError)
    @bp_api.errorhandler(SystemAdminNotFound)
    @validate()
    def handle_service_settings_error(
        error: ServiceSettingsError | SystemAdminNotFound | InfrastructureError,
    ) -> tuple[ErrorResponse, int]:
        """Handle service settings errors for the API.

        Args:
            error: The error object.

        Returns:
            tuple: Response body and 503 status code.
        """
        traceback.print_exc()
        # override error message to avoid exposing sensitive information
        return ErrorResponse(code=error.code, message=E.SERVER_UNAVAILABLE), 503

    @bp_api.errorhandler(ApiRequestError)
    @validate()
    def handle_api_request_error(error: ApiRequestError) -> tuple[ErrorResponse, int]:
        """Handle API request errors for the API.

        Args:
            error: The error object.

        Returns:
            tuple: Response body and 400 status code.
        """
        traceback.print_exc()
        return ErrorResponse(message=error.message), 400

    bp_api.before_request(refresh_session)

    @login_manager.unauthorized_handler
    @validate()
    def unauthorized() -> tuple[ErrorResponse, int]:
        """Handle unauthorized access attempts.

        Returns:
            tuple: Response body and 401 status code.
        """
        return ErrorResponse(message=E.UNAUTHORIZED), 401

    return bp_api
