from click.testing import CliRunner

from server.cli.app import version


def test_version_logs_version_(app, mocker):
    fake_version = "9.9.9"
    fake_pyproject = {"project": {"version": fake_version}}
    mocker.patch("tomllib.load", return_value=fake_pyproject)
    mocker_log = mocker.patch("flask.current_app.logger.info")

    runner = CliRunner()
    runner.invoke(version, [])

    mocker_log.assert_called_once_with(fake_version)
