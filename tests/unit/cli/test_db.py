import typing as t

from server.cli.db import create, destroy, drop, init


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_db_init_calls_create_db(app, mocker: MockerFixture) -> None:
    """Tests db init command calls create_db."""
    create_db_mock = mocker.patch("server.cli.db.create_db")

    init.main(args=[], standalone_mode=False)

    create_db_mock.assert_called_once()


def test_db_create_calls_create_tables(app, mocker: MockerFixture) -> None:
    """Tests db create command calls create_tables."""
    create_tables_mock = mocker.patch("server.cli.db.create_tables")

    create.main(args=[], standalone_mode=False)

    create_tables_mock.assert_called_once()


def test_db_drop_calls_drop_tables(app, mocker: MockerFixture) -> None:
    """Tests db drop command calls drop_tables."""
    drop_tables_mock = mocker.patch("server.cli.db.drop_tables")

    drop.main(args=[], standalone_mode=False)

    drop_tables_mock.assert_called_once()


def test_db_destroy_calls_destroy_db(app, mocker: MockerFixture) -> None:
    """Tests db destroy command calls destroy_db."""
    destroy_db_mock = mocker.patch("server.cli.db.destroy_db")

    destroy.main(args=[], standalone_mode=False)

    destroy_db_mock.assert_called_once()
