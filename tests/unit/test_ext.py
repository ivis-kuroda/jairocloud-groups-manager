import typing as t

from pathlib import Path

import pytest

from flask import Blueprint, Flask

import server.ext

from server.exc import JAIROCloudGroupsManagerError
from server.ext import JAIROCloudGroupsManager
from server.messages import E, W

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


class TestJAIROCloudGroupsManager:
    def test__init__(self):
        ext = JAIROCloudGroupsManager()

        assert ext
        with pytest.raises(JAIROCloudGroupsManagerError, match=regex(E.EXTENSION_NOT_INITIALIZED)):
            _ = ext.config

    def test__init__with_app(self, mocker: MockerFixture):
        app = Flask(__name__)
        mock_init_app = mocker.patch.object(JAIROCloudGroupsManager, "init_app")

        JAIROCloudGroupsManager(app=app)

        mock_init_app.assert_called_once_with(app)

    def test_init_app_state(self, test_config: RuntimeConfig, mocker: MockerFixture):
        app = Flask(__name__)
        app.config["RUNTIME_CONFIG"] = test_config

        mock_blueprint = mocker.patch.object(server.ext, "create_api_blueprint")
        mock_blueprint.return_value = mocker.MagicMock(spec=Blueprint)
        mocker.patch.object(server.ext, "register_cli_commands")
        mocker.patch.object(JAIROCloudGroupsManager, "init_db_app")

        ext = JAIROCloudGroupsManager()
        ext.init_app(app)

        assert ext.config == test_config
        assert ext.datastore
        assert ext.temporary_storage == Path(test_config.STORAGE.local.temporary)
        assert ext.storage == Path(test_config.STORAGE.local.storage)

    def test_init_app_config(self, test_config: RuntimeConfig, mocker: MockerFixture):
        app = Flask(__name__)
        app.config["RUNTIME_CONFIG"] = test_config

        mock_blueprint = mocker.patch.object(server.ext, "create_api_blueprint")
        mock_blueprint.return_value = mocker.MagicMock(spec=Blueprint)
        mocker.patch.object(server.ext, "register_cli_commands")
        mocker.patch.object(JAIROCloudGroupsManager, "init_db_app")

        ext = JAIROCloudGroupsManager()
        ext.init_app(app)

        assert app.config["SERVER_NAME"] == test_config.SERVER_NAME
        assert app.config["SECRET_KEY"] == test_config.SECRET_KEY
        assert app.config["SQLALCHEMY_DATABASE_URI"] == test_config.SQLALCHEMY_DATABASE_URI

    def test_init_app_setup(self, test_config: RuntimeConfig, mocker: MockerFixture):
        app = Flask(__name__)
        app.config["RUNTIME_CONFIG"] = test_config

        mock_setup_cache = mocker.patch.object(server.ext, "setup_weko_group_cache_db_config")
        mock_setup_logger = mocker.patch.object(server.ext, "setup_logger")
        mock_blueprint = mocker.patch.object(server.ext, "create_api_blueprint")
        mock_blueprint.return_value = mocker.MagicMock(spec=Blueprint)
        mock_cli = mocker.patch.object(server.ext, "register_cli_commands")
        mock_init_db_app = mocker.patch.object(JAIROCloudGroupsManager, "init_db_app")

        ext = JAIROCloudGroupsManager()
        ext.init_app(app)

        mock_setup_cache.assert_called_once_with(test_config.for_group_caches)

        mock_setup_logger.assert_called_once_with(app, test_config)
        mock_blueprint.assert_called_once()
        mock_cli.assert_called_once_with(app)
        mock_init_db_app.assert_called_once_with(app)

    def test_init_db_app(self, test_config: RuntimeConfig, mocker: MockerFixture, caplog):
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = test_config.SQLALCHEMY_DATABASE_URI

        mocker.patch.object(server.ext, "database_exists", return_value=True)
        mock_db_init = mocker.patch.object(server.ext.db, "init_app")
        mock_load_models = mocker.patch.object(server.ext, "load_models")

        ext = JAIROCloudGroupsManager()

        ext.init_db_app(app)
        mock_load_models.assert_called_once()
        mock_db_init.assert_called_once_with(app)

        assert len(caplog.records) == 0

    def test_init_db_app_db_not_exists(self, test_config: RuntimeConfig, mocker: MockerFixture, caplog):
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = test_config.SQLALCHEMY_DATABASE_URI

        mocker.patch.object(server.ext, "database_exists", return_value=False)
        mock_db_init = mocker.patch.object(server.ext.db, "init_app")
        mock_load_models = mocker.patch.object(server.ext, "load_models")

        ext = JAIROCloudGroupsManager()

        ext.init_db_app(app)
        mock_load_models.assert_called_once()
        mock_db_init.assert_called_once_with(app)

        assert_message(caplog.records[0], W.DATABASE_NOT_EXIST)

    def test_init_storage_local(self, test_config: RuntimeConfig, mocker: MockerFixture):
        app = Flask(__name__)
        app.config["RUNTIME_CONFIG"] = test_config

        mock_blueprint = mocker.patch.object(server.ext, "create_api_blueprint")
        mock_blueprint.return_value = mocker.MagicMock(spec=Blueprint)
        mocker.patch.object(server.ext, "register_cli_commands")
        mocker.patch.object(JAIROCloudGroupsManager, "init_db_app")

        ext = JAIROCloudGroupsManager()

        temporary = Path(test_config.STORAGE.local.temporary)
        storage = Path(test_config.STORAGE.local.storage)
        assert not temporary.exists()
        assert not storage.exists()

        ext.init_app(app)

        assert ext.temporary_storage.exists()
        assert ext.storage.exists()

    def test_config_property(self, test_config: RuntimeConfig, mocker: MockerFixture):
        ext = JAIROCloudGroupsManager()
        ext.state = mocker.MagicMock(config=test_config)

        assert ext.config == test_config
