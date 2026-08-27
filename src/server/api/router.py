#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API router for the server application."""

import traceback

from http import HTTPStatus
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from flask import Blueprint
from flask_pydantic import validate
from werkzeug.exceptions import Forbidden, Unauthorized

from server.auth import login_manager
from server.exc import (
    ApiRequestError,
    InfrastructureError,
    JAIROCloudGroupsManagerError,
    ServiceSettingsError,
    UnsafeOperationError,
)
from server.messages import E
from server.signals import before_request

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

        if not (bp := getattr(module, "bp", None)) or not isinstance(bp, Blueprint):
            continue

        bp_api.register_blueprint(bp, url_prefix=url_prefix)

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
        return ErrorResponse(
            code=error.code, message=E.UNEXPECTED_SERVER_ERROR
        ), HTTPStatus.INTERNAL_SERVER_ERROR

    @bp_api.errorhandler(InfrastructureError)
    @bp_api.errorhandler(ServiceSettingsError)
    @bp_api.errorhandler(UnsafeOperationError)
    @validate()
    def handle_service_settings_error(
        error: ServiceSettingsError | UnsafeOperationError | InfrastructureError,
    ) -> tuple[ErrorResponse, int]:
        """Handle service settings errors for the API.

        Args:
            error: The error object.

        Returns:
            tuple: Response body and 503 status code.
        """
        traceback.print_exc()
        # override error message to avoid exposing sensitive information
        return ErrorResponse(
            code=error.code, message=E.SERVER_UNAVAILABLE
        ), HTTPStatus.SERVICE_UNAVAILABLE

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
        return ErrorResponse(message=error.message), HTTPStatus.BAD_REQUEST

    @bp_api.before_request
    def emit_before_request_signal() -> None:
        """Emit signal at API before-request timing."""
        before_request.send(bp_api)  # pragma: no cover

    @login_manager.unauthorized_handler
    @bp_api.errorhandler(HTTPStatus.UNAUTHORIZED)
    @bp_api.errorhandler(Unauthorized)
    @validate()
    def unauthorized(_error: Exception | None = None) -> tuple[ErrorResponse, int]:
        """Handle unauthorized access attempts.

        Returns:
            tuple: Response body and 401 status code.
        """
        return ErrorResponse(message=E.UNAUTHORIZED), HTTPStatus.UNAUTHORIZED

    @bp_api.errorhandler(HTTPStatus.FORBIDDEN)
    @bp_api.errorhandler(Forbidden)
    @validate()
    def forbidden(_error: Exception | None = None) -> tuple[ErrorResponse, int]:
        """Handle forbidden access attempts.

        Returns:
            tuple: Response body and 403 status code.
        """
        return ErrorResponse(message=E.FORBIDDEN), HTTPStatus.FORBIDDEN

    return bp_api
