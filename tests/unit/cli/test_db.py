import typing as t

from server.cli.db import create, destroy, drop, init


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_init(app, mocker: MockerFixture):
    mock_create = mocker.patch("server.cli.db.create_db")

    init.main(args=[], standalone_mode=False)

    mock_create.assert_called_once()


def test_create(app, mocker: MockerFixture):
    mock_create = mocker.patch("server.cli.db.create_tables")

    create.main(args=[], standalone_mode=False)

    mock_create.assert_called_once()


def test_drop(app, mocker: MockerFixture):
    mock_drop = mocker.patch("server.cli.db.drop_tables")

    drop.main(args=[], standalone_mode=False)

    mock_drop.assert_called_once()


def test_destroy(app, mocker: MockerFixture):
    mock_destroy = mocker.patch("server.cli.db.destroy_db")

    destroy.main(args=[], standalone_mode=False)

    mock_destroy.assert_called_once()
