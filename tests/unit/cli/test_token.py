import typing as t

from server.cli.token import check, issue, refresh, whoami
from server.entities.user_detail import UserDetail
from server.messages import E, I


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_token_issue_calls_prepare_issuing_url(app: Flask, test_config, mocker: MockerFixture) -> None:
    """Tests token issue command calls prepare_issuing_url and logs info."""

    issuing_url = test_config.MAP_CORE.base_url
    prepare_mock = mocker.patch("server.cli.token.prepare_issuing_url", return_value=issuing_url)
    logger_mock = mocker.patch("server.cli.token.current_app.logger.info")

    issue.main(args=[], standalone_mode=False)

    prepare_mock.assert_called_once()
    logger_mock.assert_called_once_with(mocker.ANY, {"url": issuing_url})


def test_token_refresh_calls_refresh_access_token(app: Flask, mocker: MockerFixture) -> None:
    """Tests token refresh command calls refresh_access_token and logs info."""
    refresh_mock = mocker.patch("server.cli.token.refresh_access_token")

    refresh.main(args=[], standalone_mode=False)

    refresh_mock.assert_called_once()


def test_token_check_invalid(app, mocker):
    mocker.patch("server.cli.token.get_access_token", return_value="dummy_token")
    mocker.patch("server.cli.token.check_token_validity", return_value=False)
    logger_mock = mocker.patch("server.cli.token.current_app.logger.info")

    check.main(args=[], standalone_mode=False)
    logger_mock.assert_called_once_with(E.ACCESS_TOKEN_NOT_AVAILABLE)


def test_token_check_valid(app, mocker):
    mocker.patch("server.cli.token.get_access_token", return_value="dummy_token")
    mocker.patch("server.cli.token.check_token_validity", return_value=True)
    logger_mock = mocker.patch("server.cli.token.current_app.logger.info")

    check.main(args=[], standalone_mode=False)
    logger_mock.assert_called_once_with(I.ACCESS_TOKEN_AVAILABLE)


def test_token_whoami_logs_owner_userdetail(app, mocker):
    dummy_owner = UserDetail(id="dummy", user_name="dummy", emails=[], eppns=[])
    mocker.patch("server.cli.token.get_token_owner", return_value=dummy_owner)
    logger_mock = mocker.patch("server.cli.token.current_app.logger.info")

    whoami.main(args=[], standalone_mode=False)
    logger_mock.assert_called_once_with(
        I.SUCCESS_GET_TOKEN_OWNER,
        {"user": dummy_owner.model_dump_json(indent=2, ensure_ascii=False)},
    )
