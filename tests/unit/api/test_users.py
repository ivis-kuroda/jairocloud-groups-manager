import inspect
import typing as t

from flask import Flask
from pytest_mock import MockerFixture

from server.api import users as users_api
from server.api.schemas import ErrorResponse, UsersQuery
from server.const import USER_ROLES
from server.entities.login_user import LoginUser
from server.entities.search_request import SearchResult
from server.entities.user_detail import RepositoryRole, UserDetail
from server.exc import InvalidExportError, InvalidFormError, InvalidQueryError, ResourceInvalid, ResourceNotFound
from server.messages import E


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_get_success(app, mocker):
    expected_status = 200
    query = UsersQuery(q="", r=[], k="display_name", d="asc", p=1, l=30)
    expected_result = SearchResult(total=1, page_size=10, offset=0, resources=[])
    mocke_serch = mocker.patch("server.services.users.search", return_value=expected_result)
    original_func = inspect.unwrap(users_api.get)
    _, status = original_func(query)
    assert status == expected_status
    mocke_serch.assert_called_once_with(query)


def test_get_invalid_query_error(app: Flask, mocker: MockerFixture) -> None:
    """Covers users_api.get: users.search raises InvalidQueryError, returns ErrorResponse and 400."""
    expected_status = 400
    query = mocker.Mock()
    error_message = "invalid query!"
    mocker.patch("server.clients.users.search", side_effect=InvalidQueryError(error_message))
    original_func = inspect.unwrap(users_api.get)
    result, status = original_func(query)
    assert isinstance(result, ErrorResponse)
    assert status == expected_status


def test_post_success(app: Flask, mocker: MockerFixture) -> None:
    """Tests user creation returns UserDetail, 201, and Location header."""

    user = UserDetail(
        id="u1",
        user_name="test user",
        emails=["test@example.com"],
        eppns=["eppn1"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo1", user_role=USER_ROLES.REPOSITORY_ADMIN)],
    )
    expected_status = 201
    expected_headers = {"Location": "https://host/api/users/u1"}
    mocker.patch("server.services.users.create", return_value=user)
    mocker.patch("server.api.users.url_for", return_value=expected_headers["Location"])

    original_func = inspect.unwrap(users_api.post)
    result, status, headers = original_func(user)
    assert result == user
    assert status == expected_status
    assert headers == expected_headers


def test_post_returns_400_on_invalid_form_error(app, mocker):
    expected_status = 400
    error_detail = "id already exist"
    user = UserDetail(
        id="u3",
        user_name="conflict user",
        emails=["conflict@example.com"],
        eppns=["eppn3"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo3", user_role=USER_ROLES.REPOSITORY_ADMIN)],
    )
    mocker.patch("server.services.users.create", side_effect=InvalidFormError(error_detail))

    original_func = inspect.unwrap(users_api.post)
    result, status = original_func(user)

    assert isinstance(result, ErrorResponse)
    assert status == expected_status
    assert error_detail in result.message


def test_post_id_conflict(app: Flask, mocker: MockerFixture) -> None:
    """Tests user creation returns ErrorResponse and 409 when id or eppn already exist."""

    user = UserDetail(
        id="u3",
        user_name="conflict user",
        emails=["conflict@example.com"],
        eppns=["eppn3"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo3", user_role=USER_ROLES.REPOSITORY_ADMIN)],
    )
    error_detail = "id already exist"
    expected_status = 409
    mocker.patch("server.services.users.create", side_effect=ResourceInvalid(error_detail))

    original_func = inspect.unwrap(users_api.post)
    result, status = original_func(user)

    assert isinstance(result, ErrorResponse)
    assert status == expected_status
    assert error_detail in result.message


def test_id_get_success(app: Flask, mocker: MockerFixture) -> None:
    """Tests id_get returns UserDetail and 200 when user exists and has permission."""

    user = UserDetail(
        id="u10",
        user_name="user10",
        emails=["user10@example.com"],
        eppns=["eppn10"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo10", user_role=USER_ROLES.REPOSITORY_ADMIN)],
    )
    expected_status = 200
    mocker.patch("server.services.users.get_by_id", return_value=user)
    mocker.patch("server.api.users.has_permission", return_value=True)

    original_func = inspect.unwrap(users_api.id_get)
    result, status = original_func("u10")
    assert result == user
    assert status == expected_status


def test_id_get_not_found(app: Flask, mocker: MockerFixture) -> None:
    """Tests id_get returns ErrorResponse and 404 when user does not exist."""
    expected_status = 404
    mocker.patch("server.services.users.get_by_id", return_value=None)

    original_func = inspect.unwrap(users_api.id_get)
    result, status = original_func("u12")

    assert isinstance(result, ErrorResponse)
    assert status == expected_status
    assert result.message == "User resource (id: u12) not found."


def test_id_get_no_permission(app: Flask, mocker: MockerFixture) -> None:
    """Tests id_get returns ErrorResponse and 403 when user exists but no permission."""

    user = UserDetail(
        id="u11",
        user_name="user11",
        emails=["user11@example.com"],
        eppns=["eppn11"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo11", user_role=USER_ROLES.GENERAL_USER)],
    )
    expected_status = 403
    mocker.patch("server.services.users.get_by_id", return_value=user)
    mocker.patch("server.api.users.has_permission", return_value=False)

    original_func = inspect.unwrap(users_api.id_get)
    result, status = original_func("u11")

    assert isinstance(result, ErrorResponse)
    assert status == expected_status
    assert "Logged-in user does not have permission to access User (id: u11)." in result.message


def test_id_put_success(app: Flask, mocker: MockerFixture) -> None:
    """Tests id_put returns UserDetail and 200 when update succeeds."""

    user = UserDetail(
        id="dummy",
        user_name="user20",
        emails=["user20@example.com"],
        eppns=["eppn20"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo20", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    expected_status = 200
    mocker.patch("server.services.users.update", return_value=user)

    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="not_u20",
        session_id="dummy",
    )
    mocker.patch("server.api.users.current_user", dummy_user)

    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u20", user)
    assert result == user
    assert status == expected_status


def test_id_put_success_self(app: Flask, mocker: MockerFixture) -> None:
    expected_status = 200

    user = UserDetail(
        id="dummy",
        user_name="user20",
        emails=["user20@example.com"],
        eppns=["eppn20"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo20", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    mocker.patch("server.services.users.update", return_value=user)

    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="u20",
        session_id="dummy",
    )

    mocker.patch("server.api.users.logout", return_value=("", 204))
    mocker.patch("server.api.users.current_user", dummy_user)

    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u20", user)
    assert result == user
    assert status == expected_status


def test_id_put_invalid_form_error_403(app: Flask, mocker: MockerFixture) -> None:
    """Covers id_put except* InvalidFormError: E.USER_NO_UPDATE_SYSTEM_ADMIN (403) branch."""
    expected_status = 403
    expected_result = ErrorResponse(message="")
    user = UserDetail(
        id="u99",
        user_name="user99",
        emails=["user99@example.com"],
        eppns=["eppn99"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo99", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    exc = InvalidFormError(E.USER_NO_UPDATE_SYSTEM_ADMIN)
    mocker.patch("server.services.users.update", side_effect=exc)
    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="u99",
        session_id="dummy",
    )
    mocker.patch("server.api.users.current_user", dummy_user)
    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u99", user)
    assert status == expected_status
    assert result == expected_result


def test_id_put_invalid_form_error_400(app: Flask, mocker: MockerFixture) -> None:
    """Covers id_put except* InvalidFormError: (400) branch."""

    expected_status = 400
    expected_result = ErrorResponse(message="")
    user = UserDetail(
        id="u99",
        user_name="user99",
        emails=["user99@example.com"],
        eppns=["eppn99"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo99", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    exc = InvalidFormError(E.USER_NO_PROMOTE_SYSTEM_ADMIN)
    mocker.patch("server.services.users.update", side_effect=exc)
    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="u99",
        session_id="dummy",
    )
    mocker.patch("server.api.users.current_user", dummy_user)
    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u99", user)
    assert status == expected_status
    assert result == expected_result


def test_id_put_not_found(app: Flask, mocker: MockerFixture) -> None:
    """Tests id_put returns ErrorResponse and 404 when user not found."""

    user = UserDetail(
        id="u24",
        user_name="user24",
        emails=["user24@example.com"],
        eppns=["eppn24"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo24", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    expected_status = 404
    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="u24",
        session_id="dummy",
    )
    mocker.patch("server.api.users.current_user", dummy_user)
    mocker.patch("server.services.users.update", side_effect=ResourceNotFound("not found"))

    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u24", user)

    assert isinstance(result, ErrorResponse)
    assert status == expected_status
    assert not result.message


def test_id_put_resource_invalid(app: Flask, mocker: MockerFixture) -> None:
    """Tests id_put returns ErrorResponse and 409 when resource invalid."""

    user = UserDetail(
        id="u25",
        user_name="user25",
        emails=["user25@example.com"],
        eppns=["eppn25"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo25", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    expected_status = 409
    mocker.patch("server.services.users.update", side_effect=ResourceInvalid("resource invalid"))

    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="u25",
        session_id="dummy",
    )
    mocker.patch("server.api.users.current_user", dummy_user)

    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u25", user)

    assert isinstance(result, ErrorResponse)
    assert status == expected_status
    assert not result.message


def test_id_put_sys_exc_info_branch(app: Flask, mocker: MockerFixture):
    """Covers id_put: sys.exc_info()[0] is not None -> traceback.print_exc() branch (without raising exception)."""
    expected_status = 200
    user = UserDetail(
        id="dummy",
        user_name="user20",
        emails=["user20@example.com"],
        eppns=["eppn20"],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repo20", user_role=USER_ROLES.REPOSITORY_ADMIN)],
        is_system_admin=False,
    )
    dummy_user = LoginUser(
        eppn="dummy",
        is_member_of="",
        user_name="dummy",
        map_id="not_u20",
        session_id="dummy",
    )
    mocker.patch("server.api.users.current_user", dummy_user)
    mocker.patch("server.services.users.update", return_value=user)
    mocker.patch("sys.exc_info", return_value=(Exception, None, None))
    print_exc_mock = mocker.patch("traceback.print_exc")
    original_func = inspect.unwrap(users_api.id_put)
    result, status = original_func("u20", user)
    assert result == user
    assert status == expected_status
    assert print_exc_mock.called


def test_has_permission_system_admin(mocker: MockerFixture) -> None:
    """Tests has_permission returns True for system admin."""
    user = UserDetail(
        id="u1",
        user_name="user1",
        emails=[],
        eppns=[],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repoA", user_role=None)],
        is_system_admin=True,
    )
    mocker.patch("server.api.users.is_current_user_system_admin", return_value=True)
    result = users_api.has_permission(user)
    assert result is True


def test_has_permission_repo_admin(mocker: MockerFixture) -> None:
    """Tests has_permission returns True for permitted repo admin."""
    user = UserDetail(
        id="u2",
        user_name="user2",
        emails=[],
        eppns=[],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repoB", user_role=None)],
        is_system_admin=False,
    )
    mocker.patch("server.api.users.is_current_user_system_admin", return_value=False)
    result = users_api.has_permission(user)
    assert result is True


def test_has_permission_user_is_system_admin(mocker: MockerFixture) -> None:
    """Covers has_permission: user.is_system_admin is True, returns False."""

    mocker.patch("server.api.users.is_current_user_system_admin", return_value=False)
    user = UserDetail(
        id="u1",
        user_name="user1",
        emails=[],
        eppns=[],
        preferred_language="en",
        repository_roles=[RepositoryRole(id="repoA", user_role=None)],
        is_system_admin=True,
    )
    result = users_api.has_permission(user)
    assert result is False


def test_filter_options_returns_search_users_options_unit(mocker: MockerFixture) -> None:
    """Unit test: filter_options returns the mocked search_users_options result."""
    mock_return = [object()]
    mocker.patch("server.api.users.search_users_options", return_value=mock_return)
    original_func = inspect.unwrap(users_api.filter_options)

    result = original_func()
    assert result == mock_return


def test_export_get_success(app, mocker: MockerFixture) -> None:

    query = {"foo": "bar"}
    mock_current_user = mocker.patch("server.api.users.current_user")
    mock_current_user.map_id = "mapid"
    mock_current_user.name = "username"
    mock_file = object()
    mocker.patch("server.api.users.users.make_export_file", return_value=mock_file)
    mock_send_file = mocker.patch("server.api.users.send_file", return_value="sent-file-response")
    original_func = inspect.unwrap(users_api.export_get)
    with app.test_request_context():
        resp = original_func(query)
    mock_send_file.assert_called_once_with(mock_file)
    assert resp == "sent-file-response"


def test_export_get_invalid_export_error(app, mocker: MockerFixture) -> None:
    excepted_status = 403
    query = {"foo": "bar"}
    mock_current_user = mocker.patch("server.api.users.current_user")
    mock_current_user.map_id = "mapid"
    mock_current_user.name = "username"
    mocker.patch("server.api.users.users.make_export_file", side_effect=InvalidExportError("failmsg"))
    original_func = inspect.unwrap(users_api.export_get)
    with app.test_request_context():
        result, state = original_func(query)
    assert state == excepted_status
    assert isinstance(result, ErrorResponse)


def test_export_post_success(app, mocker: MockerFixture) -> None:
    query = {"foo": "bar"}
    mock_current_user = mocker.patch("server.api.users.current_user")
    mock_current_user.map_id = "mapid"
    mock_current_user.name = "username"
    mock_file = object()
    mocker.patch("server.api.users.users.make_export_file", return_value=mock_file)
    mock_send_file = mocker.patch("server.api.users.send_file", return_value="sent-file-response")
    original_func = inspect.unwrap(users_api.export_post)
    with app.test_request_context():
        resp = original_func(query)
    mock_send_file.assert_called_once_with(mock_file)
    assert resp == "sent-file-response"


def test_export_post_invalid_export_error(app, mocker: MockerFixture) -> None:
    excepted_status = 403
    query = {"foo": "bar"}
    mock_current_user = mocker.patch("server.api.users.current_user")
    mock_current_user.map_id = "mapid"
    mock_current_user.name = "username"
    mocker.patch("server.api.users.users.make_export_file", side_effect=InvalidExportError("failmsg"))
    original_func = inspect.unwrap(users_api.export_post)
    with app.test_request_context():
        result, state = original_func(query)
    assert state == excepted_status
    assert isinstance(result, ErrorResponse)
