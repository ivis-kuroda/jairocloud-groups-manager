import typing as t

from server.cli.token import check, issue, refresh, whoami
from server.const import MAP_OAUTH_AUTHORIZE_ENDPOINT, OAUTH_CALLBACK_CHANNEL
from server.entities.user_detail import UserDetail
from server.messages import E, I


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_issue_success(app: Flask, datastore, config, mocker: MockerFixture):
    """Tests token issue command calls prepare_issuing_url and logs info."""
    app_cache, _, _ = datastore
    issued_url = f"{config.MAP_CORE.base_url}{MAP_OAUTH_AUTHORIZE_ENDPOINT}"
    mock_prepare = mocker.patch("server.cli.token.prepare_issuing_url", return_value=issued_url)
    mock_wait = mocker.patch("server.cli.token._wait_for_token_result", return_value=b"issued")
    mock_logger = mocker.patch("server.cli.token.current_app.logger.info")

    issue.main(args=[], standalone_mode=False)

    mock_prepare.assert_called_once()
    mock_wait.assert_called_once_with(mocker.ANY, OAUTH_CALLBACK_CHANNEL)
    app_cache.pubsub.assert_called_once()
    args, _ = mock_logger.call_args_list[0]
    assert args == (I.REQUEST_FOR_AUTH_CODE, {"url": issued_url})
    args, _ = mock_logger.call_args_list[2]
    assert args == (I.SUCCESS_ISSUE_TOKEN,)


def test_issue_failed(app: Flask, datastore, config, mocker: MockerFixture):
    """Tests token issue command calls prepare_issuing_url and logs info."""
    app_cache, _, _ = datastore
    issued_url = f"{config.MAP_CORE.base_url}{MAP_OAUTH_AUTHORIZE_ENDPOINT}"
    mock_prepare = mocker.patch("server.cli.token.prepare_issuing_url", return_value=issued_url)
    mock_wait = mocker.patch("server.cli.token._wait_for_token_result", return_value=b"failed")
    mock_logger = mocker.patch("server.cli.token.current_app.logger.info")

    issue.main(args=[], standalone_mode=False)

    mock_prepare.assert_called_once()
    mock_wait.assert_called_once_with(mocker.ANY, OAUTH_CALLBACK_CHANNEL)
    app_cache.pubsub.assert_called_once()
    args, _ = mock_logger.call_args_list[0]
    assert args == (I.REQUEST_FOR_AUTH_CODE, {"url": issued_url})


def test_token_refresh_calls_refresh_access_token(mocker: MockerFixture):
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
        {"json": dummy_owner.model_dump_json(indent=2, ensure_ascii=False)},
    )
