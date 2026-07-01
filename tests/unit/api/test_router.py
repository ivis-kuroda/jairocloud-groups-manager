import typing as t

from http import HTTPStatus
from types import ModuleType

import pytest

from flask import Blueprint

import server.api.router

from server.api.router import create_api_blueprint
from server.api.schemas import ErrorResponse
from server.exc import (
    ApiRequestError,
    InfrastructureError,
    JAIROCloudGroupsManagerError,
    ServiceSettingsError,
    UnsafeOperationError,
)
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_create_api_blueprint(mocker: MockerFixture):
    target_bp = Blueprint("target_api", __name__)
    mock_module = mocker.MagicMock(spec=ModuleType, bp=target_bp)

    mock_iter = mocker.patch.object(server.api.router, "iter_modules", return_value=[(None, "target_api", None)])
    mock_import = mocker.patch.object(server.api.router, "import_module", return_value=mock_module)
    mock_register = mocker.patch.object(server.api.router.Blueprint, "register_blueprint")

    bp = create_api_blueprint()

    assert bp.name == "api"
    mock_iter.assert_called_once()
    mock_import.assert_called_once_with("server.api.target_api")
    mock_register.assert_called_once_with(target_bp, url_prefix="/target-api")


def test_create_api_blueprint_no_bp(mocker: MockerFixture):
    mock_iter = mocker.patch.object(server.api.router, "iter_modules", return_value=[(None, "no_api", None)])
    mock_import = mocker.patch.object(server.api.router, "import_module", return_value=mocker.MagicMock())
    mock_register = mocker.patch.object(server.api.router.Blueprint, "register_blueprint")

    bp = create_api_blueprint()

    assert bp.name == "api"
    mock_iter.assert_called_once()
    mock_import.assert_called_once_with("server.api.no_api")
    mock_register.assert_not_called()


def test__handle_unexpected_error(mocker: MockerFixture):
    handlers = {}
    mocker.patch.object(server.api.router, "iter_modules", return_value=[])
    mock_decorator = mocker.patch.object(server.api.router.Blueprint, "errorhandler")
    mock_decorator.side_effect = lambda exc: lambda func: handlers.setdefault(exc, func)

    create_api_blueprint()
    handler = handlers[JAIROCloudGroupsManagerError]
    error = JAIROCloudGroupsManagerError(E.DATABASE_NOT_EXIST)

    assert callable(handler)

    res, status = t.cast("tuple", unwrap(handler)(error))

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNEXPECTED_SERVER_ERROR)

    mock_decorator.assert_any_call(JAIROCloudGroupsManagerError)


@pytest.mark.parametrize("error_cls", [InfrastructureError, ServiceSettingsError, UnsafeOperationError])
def test__handle_service_settings_error(mocker: MockerFixture, error_cls):
    handlers = {}
    mocker.patch.object(server.api.router, "iter_modules", return_value=[])
    mock_decorator = mocker.patch.object(server.api.router.Blueprint, "errorhandler")
    mock_decorator.side_effect = lambda exc: lambda func: handlers.setdefault(exc, func)

    create_api_blueprint()
    handler = handlers[error_cls]
    error = error_cls(E.INVALID_SERVER_CONFIG)

    assert callable(handler)
    res, status = t.cast("tuple", unwrap(handler)(error))

    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.SERVER_UNAVAILABLE)
    mock_decorator.assert_any_call(error_cls)


def test__handle_api_request_error(mocker: MockerFixture):
    handlers = {}
    mocker.patch.object(server.api.router, "iter_modules", return_value=[])
    mock_decorator = mocker.patch.object(server.api.router.Blueprint, "errorhandler")
    mock_decorator.side_effect = lambda exc: lambda func: handlers.setdefault(exc, func)

    create_api_blueprint()
    handler = handlers[ApiRequestError]
    error = ApiRequestError(E.REPOSITORY_REQUIRES_SERVICE_NAME)

    assert callable(handler)
    res, status = t.cast("tuple", unwrap(handler)(error))

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_REQUIRES_SERVICE_NAME)
    mock_decorator.assert_any_call(ApiRequestError)


def test__unauthorized(mocker: MockerFixture):
    mock_decorator = mocker.patch.object(server.api.router.login_manager, "unauthorized_handler")

    create_api_blueprint()

    mock_decorator.assert_called_once()
    (handler,), _ = mock_decorator.call_args

    assert callable(handler)
    res, status = t.cast("tuple", unwrap(handler)())

    assert status == HTTPStatus.UNAUTHORIZED
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNAUTHORIZED)
    mock_decorator.assert_called_once()
