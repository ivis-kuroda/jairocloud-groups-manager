import typing as t

from flask import Blueprint

from server.api.router import create_api_blueprint


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_create_api_blueprint(mocker: MockerFixture):
    mock_iter_modules = mocker.patch(
        "server.api.router.iter_modules",
        return_value=[
            (None, "test", None),
        ],
    )
    mock_import_module = mocker.patch(
        "server.api.router.import_module",
    )
    mock_register_blueprint = mocker.patch(
        "server.api.router.Blueprint.register_blueprint",
    )
    mock_blueprint = mocker.MagicMock(Blueprint)
    mock_module = mocker.MagicMock()
    mock_module.bp = mock_blueprint
    mock_import_module.return_value = mock_module

    bp = create_api_blueprint()

    assert bp.name == "api"
    mock_iter_modules.assert_called_once()
    mock_import_module.assert_called_once_with("server.api.test")
    mock_register_blueprint.assert_called_once_with(
        mock_blueprint,
        url_prefix="/test",
    )


def test_create_api_blueprint_multiple_words(mocker: MockerFixture):
    mock_iter_modules = mocker.patch(
        "server.api.router.iter_modules",
        return_value=[
            (None, "cache_groups", None),
        ],
    )
    mock_import_module = mocker.patch(
        "server.api.router.import_module",
    )
    mock_register_blueprint = mocker.patch(
        "server.api.router.Blueprint.register_blueprint",
    )
    mock_blueprint = mocker.MagicMock(Blueprint)
    mock_module = mocker.MagicMock()
    mock_module.bp = mock_blueprint
    mock_import_module.return_value = mock_module

    bp = create_api_blueprint()

    assert bp.name == "api"
    mock_iter_modules.assert_called_once()
    mock_import_module.assert_called_once_with("server.api.cache_groups")
    mock_register_blueprint.assert_called_once_with(
        mock_blueprint,
        url_prefix="/cache-groups",
    )


def test_create_api_blueprint_no_bp(mocker: MockerFixture):
    mock_iter_modules = mocker.patch(
        "server.api.router.iter_modules",
        return_value=[
            (None, "no_bp_module", None),
        ],
    )
    mock_import_module = mocker.patch(
        "server.api.router.import_module",
    )
    mock_register_blueprint = mocker.patch(
        "server.api.router.Blueprint.register_blueprint",
    )
    mock_module = mocker.MagicMock()
    mock_import_module.return_value = mock_module

    bp = create_api_blueprint()

    assert bp.name == "api"
    mock_iter_modules.assert_called_once()
    mock_import_module.assert_called_once_with("server.api.no_bp_module")
    mock_register_blueprint.assert_not_called()


def test_create_api_blueprint_no_modules(mocker: MockerFixture):
    mock_iter_modules = mocker.patch(
        "server.api.router.iter_modules",
        return_value=[],
    )
    mock_import_module = mocker.patch(
        "server.api.router.import_module",
    )
    mock_register_blueprint = mocker.patch(
        "server.api.router.Blueprint.register_blueprint",
    )

    bp = create_api_blueprint()

    assert bp.name == "api"
    mock_iter_modules.assert_called_once()
    mock_import_module.assert_not_called()
    mock_register_blueprint.assert_not_called()
