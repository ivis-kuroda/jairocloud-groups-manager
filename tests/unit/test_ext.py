import typing as t

from server.ext import JAIROCloudGroupsManager


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_init_config(mocker: MockerFixture):
    mock_setup_config = mocker.patch(
        "server.ext.setup_config",
    )
    mock_cache_db_setup_config = mocker.patch(
        "server.ext.setup_weko_group_cache_db_config",
    )
    mock_app = mocker.MagicMock()

    ext = JAIROCloudGroupsManager()
    ext.init_config(mock_app)
    mock_setup_config.assert_called_once()
    mock_cache_db_setup_config.assert_called_once_with(ext.config.CACHE_DB)
