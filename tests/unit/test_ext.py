import typing as t

from pathlib import Path

import pytest

from flask import Flask

import server.ext

from server.const import DEFAULT_CONFIG_PATH
from server.exc import ConfigurationError
from server.ext import JAIROCloudGroupsManager
from server.messages import E, W

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


class TestJAIROCloudGroupsManager:
    def test__init__(self):
        ext = JAIROCloudGroupsManager()

        assert ext._config == DEFAULT_CONFIG_PATH
        assert ext.datastore == {}

    def test__init__with_config_obj(self, test_config):
        ext = JAIROCloudGroupsManager(config=test_config)

        assert ext._config == test_config
        assert ext.datastore == {}

    def test__init__with_app(self, mocker: MockerFixture):
        app = Flask(__name__)
        mock_init = mocker.patch.object(JAIROCloudGroupsManager, "init_app")

        JAIROCloudGroupsManager(app=app)

        mock_init.assert_called_once_with(app)

    def test_init_config(self, test_config: RuntimeConfig, mocker: MockerFixture):
        app = Flask(__name__)
        mock_setup = mocker.patch.object(server.ext, "setup_config", return_value=test_config)
        mock_setup_cache = mocker.patch.object(server.ext, "setup_weko_group_cache_db_config")

        ext = JAIROCloudGroupsManager()

        ext.init_config(app)
        mock_setup.assert_called_once()
        mock_setup_cache.assert_called_once_with(test_config.for_group_caches)

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

    def test_init_storage_local(self, test_config: RuntimeConfig):
        ext = JAIROCloudGroupsManager()
        ext._config = test_config

        local = Path(test_config.STORAGE.local.temporary)
        storage = Path(test_config.STORAGE.local.storage)
        assert not local.exists()
        assert not storage.exists()

        ext.init_storage()

        assert local.exists()
        assert storage.exists()

    def test_config_property(self, test_config: RuntimeConfig):
        ext = JAIROCloudGroupsManager()
        ext._config = test_config

        assert ext.config == test_config

    def test_config_property_not_set(self):
        ext = JAIROCloudGroupsManager()

        with pytest.raises(ConfigurationError, match=regex(E.UNINIT_SERVER_CONFIG)):
            _ = ext.config
