import typing as t

from types import SimpleNamespace

from flask_login import login_user

import server.services.utils.permissions

from server.const import USER_ROLES
from server.services.utils.permissions import (
    filter_permitted_group_ids,
    get_permitted_repository_ids,
    is_current_user_system_admin,
)


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig
    from server.entities.login_user import LoginUser


def test_is_current_user_system_admin(app: Flask, config: RuntimeConfig, login_users, mocker: MockerFixture):
    user: LoginUser = login_users[USER_ROLES.SYSTEM_ADMIN]
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=True)
    mock_parse = mocker.patch.object(server.services.utils.permissions, "parse_affiliated_group_ids")
    mock_parse.return_value = [config.GROUPS.id_patterns.system_admin]

    with app.test_request_context():
        login_user(user)

        result = is_current_user_system_admin() is True

    assert result is True


def test_is_current_user_system_admin_not_logged_in(mocker: MockerFixture):
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=False)

    assert is_current_user_system_admin() is False


def test_get_permitted_repository_ids(app: Flask, login_users, mocker: MockerFixture):
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    repository_ids = "test_1_repo_ac_jp", "test_2_repo_ac_jp"

    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=True)
    mocker.patch.object(server.services.utils.permissions, "parse_affiliated_group_ids")

    roles = [
        SimpleNamespace(repository_id=repository_ids[0], role=USER_ROLES.REPOSITORY_ADMIN),
        SimpleNamespace(repository_id=repository_ids[1], role=USER_ROLES.CONTRIBUTOR),
    ]
    mock_detect = mocker.patch.object(server.services.utils.permissions, "detect_affiliations")
    mock_detect.return_value = roles, []

    expected = {repository_ids[0]}

    with app.test_request_context("/"):
        login_user(user)

        result = get_permitted_repository_ids()

    assert result == expected


def test_get_permitted_repository_ids_not_logged_in(mocker: MockerFixture):
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=False)

    result = get_permitted_repository_ids()

    assert result == set()


def test_get_permitted_repository_ids_system_admin(app: Flask, login_users, mocker: MockerFixture):
    user: LoginUser = login_users[USER_ROLES.SYSTEM_ADMIN]
    mocker.patch.object(server.services.utils.permissions, "is_current_user_system_admin", return_value=True)
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=True)

    with app.test_request_context("/"):
        login_user(user)

        result = get_permitted_repository_ids()

    assert result == {"*"}


def test_filter_permitted_group_ids(app: Flask, test_config: RuntimeConfig, login_users, mocker: MockerFixture):
    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    patterns = test_config.GROUPS.id_patterns
    repository_ids = "test_1_repo_ac_jp", "test_2_repo_ac_jp"
    group_ids = [
        patterns.user_defined.format(repository_id=repository_ids[0], user_defined_id="permitted1"),
        patterns.user_defined.format(repository_id=repository_ids[1], user_defined_id="permitted2"),
    ]
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=True)
    mock_permitted = mocker.patch.object(server.services.utils.permissions, "get_permitted_repository_ids")
    mock_permitted.return_value = {repository_ids[0]}
    mock_detect = mocker.patch.object(server.services.utils.permissions, "detect_affiliations")
    mock_detect.return_value = (
        [],
        [SimpleNamespace(repository_id=repository_ids[i], group_id=group_ids[i]) for i in range(2)],
    )

    with app.test_request_context():
        login_user(user)

        result = filter_permitted_group_ids()

    assert result == {group_ids[0]}


def test_filter_permitted_group_ids_not_logged_in(test_config: RuntimeConfig, mocker: MockerFixture):
    patterns = test_config.GROUPS.id_patterns
    group_ids = [
        patterns.user_defined.format(repository_id="test_1_repo_ac_jp", user_defined_id="permitted1"),
        patterns.user_defined.format(repository_id="test_2_repo_ac_jp", user_defined_id="permitted2"),
    ]
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=False)

    result = filter_permitted_group_ids(*group_ids)

    assert result == set()


def test_filter_permitted_group_ids_system_admin(
    app: Flask, test_config: RuntimeConfig, login_users, mocker: MockerFixture
):
    user: LoginUser = login_users[USER_ROLES.SYSTEM_ADMIN]
    patterns = test_config.GROUPS.id_patterns
    group_ids = [
        patterns.user_defined.format(repository_id="test_1_repo_ac_jp", user_defined_id="permitted1"),
        patterns.user_defined.format(repository_id="test_2_repo_ac_jp", user_defined_id="permitted2"),
    ]
    mocker.patch.object(server.services.utils.permissions, "is_user_logged_in", return_value=True)
    mocker.patch.object(server.services.utils.permissions, "is_current_user_system_admin", return_value=True)

    with app.test_request_context():
        login_user(user)

        result = filter_permitted_group_ids(*group_ids)

    assert result == set(group_ids)
