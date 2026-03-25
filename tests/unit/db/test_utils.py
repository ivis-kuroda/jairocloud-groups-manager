import typing as t

import pytest


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture

from server.db import utils
from server.exc import DatabaseError


def test_create_db_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests create_db when database already exists."""
    mocker.patch("server.db.utils.database_exists", return_value=True)
    logger_mock = mocker.patch("server.db.utils.current_app.logger.info")

    utils.create_db()

    logger_mock.assert_called_once_with(utils.I.DATABASE_ALREADY_EXISTS)


def test_create_db_not_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests create_db when database does not exist."""
    mocker.patch("server.db.utils.database_exists", return_value=False)
    create_db_mock = mocker.patch("server.db.utils.create_database")
    logger_mock = mocker.patch("server.db.utils.current_app.logger.info")

    utils.create_db()

    create_db_mock.assert_called_once_with(app.config["SQLALCHEMY_DATABASE_URI"])
    logger_mock.assert_called_with(utils.I.DATABASE_CREATED)


def test_destroy_db_not_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests destroy_db when database does not exist."""
    mocker.patch("server.db.utils.database_exists", return_value=False)
    logger_mock = mocker.patch("server.db.utils.current_app.logger.info")

    utils.destroy_db()

    logger_mock.assert_called_once_with(utils.I.DATABASE_NOT_EXIST)


def test_destroy_db_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests destroy_db when database exists."""
    mocker.patch("server.db.utils.database_exists", return_value=True)
    drop_db_mock = mocker.patch("server.db.utils.drop_database")
    logger_mock = mocker.patch("server.db.utils.current_app.logger.info")

    utils.destroy_db()

    drop_db_mock.assert_called_once_with(app.config["SQLALCHEMY_DATABASE_URI"])
    logger_mock.assert_called_with(utils.I.DATABASE_DESTROYED)


def test_create_tables_db_not_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests create_tables raises DatabaseError when DB does not exist."""
    mocker.patch("server.db.utils.database_exists", return_value=False)

    with pytest.raises(DatabaseError, match=str(utils.E.DATABASE_NOT_EXIST)):
        utils.create_tables()


def test_create_tables_db_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests create_tables when DB exists."""
    db_obj = app.extensions["sqlalchemy"]
    logger_obj = app.logger
    db_mock = mocker.patch.object(db_obj, "create_all")
    logger_mock = mocker.patch.object(logger_obj, "info")
    mocker.patch("server.db.utils.database_exists", return_value=True)

    utils.create_tables()

    db_mock.assert_called_once()
    logger_mock.assert_called_with(utils.I.TABLE_CREATED)


def test_drop_tables_db_not_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests drop_tables raises DatabaseError when DB does not exist."""
    mocker.patch("server.db.utils.database_exists", return_value=False)

    with pytest.raises(DatabaseError, match=str(utils.E.DATABASE_NOT_EXIST)):
        utils.drop_tables()


def test_drop_tables_db_exists(app: Flask, mocker: MockerFixture) -> None:
    """Tests drop_tables when DB exists."""
    db_obj = app.extensions["sqlalchemy"]
    logger_obj = app.logger
    db_mock = mocker.patch.object(db_obj, "drop_all")
    logger_mock = mocker.patch.object(logger_obj, "info")
    mocker.patch("server.db.utils.database_exists", return_value=True)

    utils.drop_tables()

    db_mock.assert_called_once()
    logger_mock.assert_called_with(utils.I.TABLE_DROPPED)


def test_load_models_imports_all(mocker: MockerFixture) -> None:
    """Tests load_models imports all modules in the directory."""
    expected_call_count = 2
    mocker.patch("server.db.utils.iter_modules", return_value=[(None, "mod1", None), (None, "mod2", None)])
    import_module_mock = mocker.patch("server.db.utils.import_module")

    utils.load_models()

    import_module_mock.assert_any_call(f"{utils.__package__}.mod1")
    import_module_mock.assert_any_call(f"{utils.__package__}.mod2")
    assert import_module_mock.call_count == expected_call_count
