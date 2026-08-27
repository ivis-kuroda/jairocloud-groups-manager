import typing as t

from http import HTTPStatus

from flask import Flask, Response
from flask_login import login_user

import server.api.users

from server.api import users
from server.api.schemas import ErrorResponse, ExportUsersQuery, UsersQuery
from server.const import USER_ROLES
from server.entities.search_request import FilterOption, SearchResult
from server.exc import (
    InvalidExportError,
    InvalidFormError,
    InvalidQueryError,
    RequestConflict,
    ResourceInvalid,
    ResourceNotFound,
)
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get(user_details, mocker: MockerFixture):
    total, page_size, offset = len(user_details), len(user_details), 0
    searched = expected = SearchResult(total=total, page_size=page_size, offset=offset, resources=user_details.values())
    mock_search = mocker.patch.object(server.api.users.users, "search", return_value=searched)
    query = UsersQuery()

    res, status = unwrap(users.get)(query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_search.assert_called_once_with(query)


def test_get_invalid_query_error(mocker: MockerFixture):
    mock_search = mocker.patch.object(server.api.users.users, "search")
    mock_search.side_effect = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)
    query = UsersQuery()

    res, status = unwrap(users.get)(query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNSUPPORTED_SEARCH_FILTER)


def test_post(use_blueprint, app, user_details, mocker: MockerFixture):
    body = expected = user_details[USER_ROLES.CONTRIBUTOR]
    mock_create = mocker.patch.object(server.api.users.users, "create", return_value=expected)

    res, status, headers = unwrap(users.post)(body)

    assert status == HTTPStatus.CREATED
    assert res == expected
    assert headers["Location"] == f"https://localhost/api/users/{expected.id}"
    mock_create.assert_called_once_with(body)


def test_post_invalid_form_error(user_details, mocker: MockerFixture):
    body = user_details[USER_ROLES.CONTRIBUTOR]
    mock_create = mocker.patch.object(server.api.users.users, "create")
    mock_create.side_effect = InvalidFormError(E.USER_REQUIRES_EPPN)

    original_func = unwrap(users.post)
    res, status, *_ = original_func(body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_REQUIRES_EPPN)
    assert not _


def test_post_conflict(user_details, mocker: MockerFixture):
    body = user_details[USER_ROLES.CONTRIBUTOR]
    mock_create = mocker.patch.object(server.api.users.users, "create")
    mock_create.side_effect = ResourceInvalid(E.USER_DUPLICATE_ID % {"id": body.id})

    res, status, *_ = unwrap(users.post)(body)

    assert status == HTTPStatus.CONFLICT
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_DUPLICATE_ID, {"id": body.id})
    assert not _


def test_id_get(user_details, mocker: MockerFixture):
    target = expected = user_details[USER_ROLES.CONTRIBUTOR]
    mock_get = mocker.patch.object(server.api.users.users, "get_by_id", return_value=target)
    mocker.patch.object(server.api.users, "has_permission", return_value=True)

    res, status = unwrap(users.id_get)(target.id)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_get.assert_called_once_with(target.id, more_detail=True)


def test_id_get_not_found(app, user_details, mocker: MockerFixture, caplog):
    uid = "non-existent-user"
    mocker.patch.object(server.api.users.users, "get_by_id", return_value=None)
    mock_permission = mocker.patch.object(server.api.users, "has_permission")

    res, status = unwrap(users.id_get)(uid)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_NOT_FOUND, {"id": uid})
    assert_message(caplog.records[0].message, E.USER_NOT_FOUND, {"id": uid})
    mock_permission.assert_not_called()


def test_id_get_forbidden(app, user_details, mocker: MockerFixture, caplog):
    target = user_details[USER_ROLES.CONTRIBUTOR]
    mocker.patch.object(server.api.users.users, "get_by_id", return_value=target)
    mock_permission = mocker.patch.object(server.api.users, "has_permission", return_value=False)

    res, status = unwrap(users.id_get)(target.id)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_FORBIDDEN, {"id": target.id})
    assert_message(caplog.records[0].message, E.USER_FORBIDDEN, {"id": target.id})
    mock_permission.assert_called_once_with(target)


def test_id_put(app: Flask, login_users, user_details, mocker: MockerFixture):
    body = expected = user_details[USER_ROLES.CONTRIBUTOR]
    uid, body.id = body.id, None
    mock_update = mocker.patch.object(server.api.users.users, "update", return_value=body)
    mock_permission = mocker.patch.object(server.api.users, "has_permission")

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(users.id_put)(uid, body)

    assert status == HTTPStatus.OK
    assert res == expected
    assert body.id == uid
    mock_update.assert_called_once_with(body)
    mock_permission.assert_not_called()  # not to check (implemented in service layer)


def test_id_put_self(app: Flask, login_users, user_details, mocker: MockerFixture):
    body = expected = user_details[USER_ROLES.REPOSITORY_ADMIN]
    mock_update = mocker.patch.object(server.api.users.users, "update", return_value=body)
    spy_logout = mocker.spy(server.api.users, "logout")

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(users.id_put)(body.id, body)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_update.assert_called_once_with(body)
    spy_logout.assert_called_once()  # to logout after updating own information


def test_id_put_forbidden(user_details, mocker: MockerFixture):
    body = user_details[USER_ROLES.CONTRIBUTOR]
    mock_update = mocker.patch.object(server.api.users.users, "update")
    mock_update.side_effect = InvalidFormError(E.USER_NO_UPDATE_SYSTEM_ADMIN)

    res, status = unwrap(users.id_put)(body.id, body)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_NO_UPDATE_SYSTEM_ADMIN)


def test_id_put_invalid_form_error(user_details, mocker: MockerFixture):
    body = user_details[USER_ROLES.CONTRIBUTOR]
    mock_update = mocker.patch.object(server.api.users.users, "update")
    mock_update.side_effect = InvalidFormError(E.USER_REQUIRES_NO_REPOSITORY)

    res, status = unwrap(users.id_put)(body.id, body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_REQUIRES_NO_REPOSITORY)


def test_id_put_not_found(user_details, mocker: MockerFixture):
    body = user_details[USER_ROLES.CONTRIBUTOR]
    mock_update = mocker.patch.object(server.api.users.users, "update")
    mock_update.side_effect = ResourceNotFound(E.USER_NOT_FOUND % {"id": body.id})

    res, status = unwrap(users.id_put)(body.id, body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_NOT_FOUND, {"id": body.id})


def test_id_put_exception_group(user_details, mocker: MockerFixture):
    body = user_details[USER_ROLES.CONTRIBUTOR]
    errors = [ResourceNotFound(E.USER_NOT_FOUND % {"id": body.id}), RequestConflict(E.CONFLICT_MEMBER_OPERATION)]
    mock_update = mocker.patch.object(server.api.users.users, "update")
    mock_update.side_effect = ExceptionGroup(E.FAILED_UPDATE_USER_AFFILIATIONS, errors)

    res, status = unwrap(users.id_put)(body.id, body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FAILED_UPDATE_USER_AFFILIATIONS)


def test_has_permission_system_admin(user_details, mocker: MockerFixture):
    user = user_details[USER_ROLES.CONTRIBUTOR]
    mocker.patch.object(server.api.users, "is_current_user_system_admin", return_value=True)

    assert users.has_permission(user) is True


def test_has_permission_permitted(user_details, mocker: MockerFixture):
    user = user_details[USER_ROLES.CONTRIBUTOR]
    mocker.patch.object(server.api.users, "is_current_user_system_admin", return_value=False)

    assert users.has_permission(user) is True


def test_has_permission_user_is_system_admin(user_details, mocker: MockerFixture):
    user = user_details[USER_ROLES.SYSTEM_ADMIN]
    mocker.patch.object(server.api.users, "is_current_user_system_admin", return_value=False)

    assert users.has_permission(user) is False


def test_filter_options(mocker: MockerFixture):
    options = expected = [FilterOption(key="t", description="test opttion", type="string", multiple=False)]
    mocker.patch.object(server.api.users, "search_users_options", return_value=options)

    result = unwrap(users.filter_options)()

    assert result == expected


def test_export_get(app: Flask, login_users, mocker: MockerFixture, tmp_path):
    operator = login_users[USER_ROLES.REPOSITORY_ADMIN]
    query = ExportUsersQuery(f="tsv")

    file_path = tmp_path / "export.tsv"
    file_path.write_text("test file content")
    mock_export = mocker.patch.object(server.api.users.users, "make_export_file", return_value=file_path)

    with app.test_request_context():
        login_user(operator)
        res, status = unwrap(users.export_get)(query)

    assert status == HTTPStatus.OK
    assert isinstance(res, Response)
    assert next(iter(res.response)) == b"test file content"
    mock_export.assert_called_once_with(operator.map_id, operator.user_name, query)


def test_export_post(app: Flask, login_users, mocker: MockerFixture, tmp_path):
    operator = login_users[USER_ROLES.REPOSITORY_ADMIN]
    query = ExportUsersQuery(f="tsv")

    file_path = tmp_path / "export.tsv"
    file_path.write_text("test file content")
    mock_export = mocker.patch.object(server.api.users.users, "make_export_file", return_value=file_path)

    with app.test_request_context():
        login_user(operator)
        res, status = unwrap(users.export_post)(query)

    assert status == HTTPStatus.OK
    assert isinstance(res, Response)
    assert next(iter(res.response)) == b"test file content"
    mock_export.assert_called_once_with(operator.map_id, operator.user_name, query)


def test_export_forbidden(app: Flask, login_users, mocker: MockerFixture):
    operator = login_users[USER_ROLES.REPOSITORY_ADMIN]
    query = ExportUsersQuery(f="tsv")

    mock_export = mocker.patch.object(server.api.users.users, "make_export_file")
    mock_export.side_effect = InvalidExportError(E.USER_FORBIDDEN_EXPORT)

    with app.test_request_context():
        login_user(operator)
        res, state = unwrap(users.export_get)(query)

    assert state == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.USER_FORBIDDEN_EXPORT)


def test_export_invalid_query_error(app: Flask, login_users, mocker: MockerFixture):
    operator = login_users[USER_ROLES.REPOSITORY_ADMIN]
    body = ExportUsersQuery(f="tsv")

    mock_export = mocker.patch.object(server.api.users.users, "make_export_file")
    mock_export.side_effect = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)

    with app.test_request_context():
        login_user(operator)
        res, state = unwrap(users.export_post)(body)

    assert state == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNSUPPORTED_SEARCH_FILTER)
