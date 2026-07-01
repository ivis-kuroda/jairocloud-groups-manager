import typing as t

import pytest

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import server.db.utils

from server.db.utils import create_db, create_tables, destroy_db, drop_tables
from server.exc import DatabaseError
from server.messages import E, I

from tests.helpers import assert_message


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from werkzeug.local import LocalProxy

    from server.config import RuntimeConfig


@pytest.fixture(autouse=True)
def _app(test_config: RuntimeConfig, mocker: MockerFixture):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = test_config.SQLALCHEMY_DATABASE_URI
    SQLAlchemy(app)

    with app.app_context():
        yield app


@pytest.mark.sqlalchemy_enabled
def test_create_db(test_config: RuntimeConfig, mocker: MockerFixture, caplog):
    mocker.patch.object(server.db.utils, "database_exists", return_value=False)
    mock_create = mocker.patch.object(server.db.utils, "create_database")

    create_db()

    mock_create.assert_called_once_with(test_config.SQLALCHEMY_DATABASE_URI)
    assert_message(caplog.records[0], I.DATABASE_CREATED)


@pytest.mark.sqlalchemy_enabled
def test_create_db_already_exists(mocker: MockerFixture, caplog):
    mocker.patch.object(server.db.utils, "database_exists", return_value=True)

    create_db()

    assert_message(caplog.records[0], I.DATABASE_ALREADY_EXISTS)


@pytest.mark.sqlalchemy_enabled
def test_destroy_db(test_config: RuntimeConfig, mocker: MockerFixture, caplog):
    mocker.patch.object(server.db.utils, "database_exists", return_value=True)
    mock_drop = mocker.patch.object(server.db.utils, "drop_database")

    destroy_db()

    mock_drop.assert_called_once_with(test_config.SQLALCHEMY_DATABASE_URI)
    assert_message(caplog.records[0], I.DATABASE_DESTROYED)


@pytest.mark.sqlalchemy_enabled
def test_destroy_db_not_exists(mocker: MockerFixture, caplog):
    mocker.patch.object(server.db.utils, "database_exists", return_value=False)

    destroy_db()

    assert_message(caplog.records[0], I.DATABASE_NOT_EXIST)


@pytest.mark.sqlalchemy_enabled
def test_create_tables(db, mocker: MockerFixture, caplog):
    mocker.patch.object(server.db.utils, "database_exists", return_value=True)

    create_tables()

    db.create_all.assert_called_once()
    assert_message(caplog.records[0], I.TABLE_CREATED)


@pytest.mark.sqlalchemy_enabled
def test_create_tables_not_exists(mocker: MockerFixture):
    mocker.patch.object(server.db.utils, "database_exists", return_value=False)

    with pytest.raises(DatabaseError, match=str(E.DATABASE_NOT_EXIST)):
        create_tables()


@pytest.mark.sqlalchemy_enabled
def test_drop_tables(db, mocker: MockerFixture, caplog):
    mocker.patch.object(server.db.utils, "database_exists", return_value=True)

    drop_tables()

    db.drop_all.assert_called_once()
    assert_message(caplog.records[0], I.TABLE_DROPPED)


@pytest.mark.sqlalchemy_enabled
def test_drop_tables_not_exists(mocker: MockerFixture):
    mocker.patch.object(server.db.utils, "database_exists", return_value=False)

    with pytest.raises(DatabaseError, match=str(E.DATABASE_NOT_EXIST)):
        drop_tables()


@pytest.mark.sqlalchemy_enabled
def test_load_models(mocker: MockerFixture):
    mocker.patch.object(server.db.utils, "iter_modules", return_value=[(None, "target_model", None)])
    mock_import = mocker.patch.object(server.db.utils, "import_module")

    server.db.utils.load_models()

    mock_import.assert_called_once_with("server.db.target_model")


@pytest.mark.sqlalchemy_enabled
def test_proxy(test_config: RuntimeConfig, mocker: MockerFixture):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = test_config.SQLALCHEMY_DATABASE_URI
    expected = SQLAlchemy(app)

    proxy = t.cast("LocalProxy[SQLAlchemy]", server.db.utils.db)
    with app.app_context():
        assert proxy == expected
        assert proxy._get_current_object() == expected
