import typing as t

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import uuid7

from celery.result import AsyncResult
from flask_login import login_user
from werkzeug.datastructures import FileStorage

import server.api.bulk

from server.api import bulk
from server.api.schemas import (
    BulkBody,
    BulkFileForm,
    BulkResultQuery,
    ErrorResponse,
    ExcuteRequest,
    TargetRepositoryForm,
)
from server.const import USER_ROLES
from server.entities.bulk import ExecuteResults, ResultSummary, ValidateResults
from server.entities.login_user import LoginUser
from server.exc import FileValidationError, RecordNotFound
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_upload_file(app, login_users, mocker: MockerFixture):
    task_id, tmp_id = str(uuid7()), uuid7()
    operator_id, operator_name = (user := login_users[USER_ROLES.REPOSITORY_ADMIN]).map_id, user.user_name

    form = TargetRepositoryForm(repository_id=(rid := "test_repo_ac_jp"))
    form_file = BulkFileForm(bulk_file=FileStorage(filename="test.tsv"))
    mock_task = mocker.Mock(id=task_id, spec=AsyncResult)

    mocker.patch.object(server.api.bulk.repositories, "get_by_id", return_value=mocker.Mock())
    mocker.patch.object(server.api.bulk, "get_permitted_repository_ids", return_value=[rid])
    mock_upload = mocker.patch.object(server.api.bulk.bulks, "upload_file", return_value=tmp_id)
    mock_delay = mocker.patch.object(server.api.bulk.bulks.validate_upload_data, "delay")
    mock_delay.return_value = mock_task

    expected = BulkBody(task_id=task_id, tmp_file_id=tmp_id)

    with app.test_request_context():
        login_user(user)
        res, status = unwrap(bulk.upload_file)(form, form_file)

    assert status == HTTPStatus.OK
    assert res == expected

    mock_upload.assert_called_once_with(rid, form_file.bulk_file)
    mock_delay.assert_called_once_with(operator_id, operator_name, tmp_id)


def test_upload_file_repository_not_found(app, mocker: MockerFixture, caplog):
    form = TargetRepositoryForm(repository_id=(rid := "test_repo_ac_jp"))
    form_file = BulkFileForm(bulk_file=FileStorage(filename="test.tsv"))

    mocker.patch.object(server.api.bulk.repositories, "get_by_id", return_value=None)

    res, status = unwrap(bulk.upload_file)(form, form_file)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_NOT_FOUND, {"id": rid})
    assert_message(caplog.records[0], E.REPOSITORY_NOT_FOUND, {"id": rid})


def test_upload_file_repository_forbidden(app, login_users, mocker: MockerFixture, caplog):
    mocker.patch.object(server.api.bulk.repositories, "get_by_id", return_value=mocker.Mock())

    form = TargetRepositoryForm(repository_id=(rid := "test_repo_ac_jp"))
    form_file = BulkFileForm(bulk_file=FileStorage(filename="test.tsv"))

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(bulk.upload_file)(form, form_file)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.REPOSITORY_FORBIDDEN, {"id": rid})
    assert_message(caplog.records[0], E.REPOSITORY_FORBIDDEN, {"id": rid})


def test_validate_status(mocker: MockerFixture):
    task_id = uuid7()
    mock_task = mocker.Mock(state=(status := "SUCCESS"), spec=AsyncResult)
    mocker.patch.object(server.api.bulk.bulks, "get_validate_task_result", return_value=mock_task)
    expected = BulkBody(status=status)

    res = unwrap(bulk.validate_status)(task_id)

    assert res == expected


def test_validate_result(app, login_users, mocker: MockerFixture):
    task_id, history_id = uuid7(), uuid7()
    mock_task = mocker.MagicMock(spec=AsyncResult)
    mock_task.get.return_value = history_id
    mocker.patch.object(server.api.bulk.bulks, "get_validate_task_result", return_value=mock_task)
    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_operation", return_value=True)

    offset, page, size = 1, 1, 20
    query = BulkResultQuery(f=[0], p=page, l=size)
    expected = ValidateResults(results=[], summary=ResultSummary(), offset=offset, page_size=size)
    mock_validate_result = mocker.patch.object(server.api.bulk.bulks, "get_validate_result", return_value=expected)

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(bulk.validate_result)(query, task_id)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_validate_result.assert_called_once_with(history_id, query)


def test_validate_result_not_permission(app, login_users, mocker: MockerFixture):
    task_id, history_id = uuid7(), uuid7()

    mock_task = mocker.MagicMock(spec=AsyncResult)
    mock_task.get.return_value = history_id
    mocker.patch.object(server.api.bulk.bulks, "get_validate_task_result", return_value=mock_task)
    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_operation", return_value=False)

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(bulk.validate_result)(query=BulkResultQuery(), task_id=task_id)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.OPERATION_FORBIDDEN)


def test_validate_result_record_not_found(config, mocker: MockerFixture):
    task_id, file_id = uuid7(), uuid7()

    mock_task = mocker.MagicMock(spec=AsyncResult)
    mock_task.get.side_effect = RecordNotFound(E.FAILED_GET_FILE_RECORD % {"file_id": file_id})
    mocker.patch.object(server.api.bulk.bulks, "get_validate_task_result", return_value=mock_task)

    res, status = unwrap(bulk.validate_result)(query=BulkResultQuery(), task_id=task_id)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FAILED_GET_FILE_RECORD, {"file_id": file_id})


def test_validate_result_operation_error(config, mocker: MockerFixture):
    task_id = uuid7()

    mock_task = mocker.MagicMock(spec=AsyncResult)
    mock_task.get.side_effect = FileValidationError(E.INVALID_FILE_STRUCTURE)
    mocker.patch.object(server.api.bulk.bulks, "get_validate_task_result", return_value=mock_task)

    res, status = unwrap(bulk.validate_result)(query=BulkResultQuery(), task_id=task_id)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.INVALID_FILE_STRUCTURE)


def test_execute(app, login_users, mocker: MockerFixture):
    tmp_id, history_id = uuid7(), uuid7()
    repository_id = "test_repo_ac_jp"
    task_id = str(uuid7())
    body = ExcuteRequest(tmp_file_id=tmp_id, repository_id=repository_id, delete_users=["user1", "user2"])

    mock_history = mocker.patch.object(server.api.bulk.history_table, "get_history_by_file_id")
    mock_history.return_value.id = history_id

    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_operation", return_value=True)
    mock_task = mocker.Mock(id=task_id, spec=AsyncResult)
    mock_apply = mocker.patch.object(server.api.bulk.bulks.update_users, "delay", return_value=mock_task)

    expected = BulkBody(task_id=task_id, history_id=history_id)

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(bulk.execute)(body)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_history.assert_called_once_with(tmp_id)
    mock_apply.assert_called_once_with(history_id, body.tmp_file_id, body.delete_users)


def test_execute_history_not_found(mocker: MockerFixture):
    tmp_id = uuid7()
    repository_id = "test_repo_ac_jp"
    body = ExcuteRequest(tmp_file_id=tmp_id, repository_id=repository_id)

    mock_history = mocker.patch.object(server.api.bulk.history_table, "get_history_by_file_id")
    mock_history.side_effect = RecordNotFound(E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": tmp_id})

    res, status = unwrap(bulk.execute)(body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UPLOAD_HISTORY_RECORD_NOT_FOUND, {"id": tmp_id})


def test_execute_no_permission(app, login_users, mocker: MockerFixture):
    tmp_id, history_id = uuid7(), uuid7()
    repository_id = "test_repo_ac_jp"
    body = ExcuteRequest(tmp_file_id=tmp_id, repository_id=repository_id)

    mock_history = mocker.patch.object(server.api.bulk.history_table, "get_history_by_file_id")
    mock_history.return_value.id = history_id

    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_operation", return_value=False)

    with app.test_request_context():
        login_user(login_users[USER_ROLES.REPOSITORY_ADMIN])
        res, status = unwrap(bulk.execute)(body)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.OPERATION_FORBIDDEN)


def test_execute_status(mocker: MockerFixture):
    task_id = uuid7()
    mock_task = mocker.Mock(state=(status := "SUCCESS"), spec=AsyncResult)
    mocker.patch.object(server.api.bulk.bulks.update_users, "AsyncResult", return_value=mock_task)

    expected = BulkBody(status=status)

    res = unwrap(bulk.execute_status)(task_id)

    assert res == expected


def test_result(login_users, mocker: MockerFixture):
    history_id, file_id = uuid7(), uuid7()
    total, offset, page_size = 0, 2, 20
    query = BulkResultQuery(f=[0, 1], p=offset, l=page_size)

    user: LoginUser = login_users[USER_ROLES.REPOSITORY_ADMIN]
    expected = ExecuteResults(
        items=[],
        summary=ResultSummary(),
        file_id=file_id,
        file_name=f"{str(file_id)[:7]}.csv",
        operator=user.user_name,
        start_timestamp=datetime.now(UTC),
        total=total,
        offset=offset,
        page_size=page_size,
    )
    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_view", return_value=True)
    mock_get_result = mocker.patch.object(server.api.bulk.bulks, "get_upload_result", return_value=expected)

    res, status = unwrap(bulk.result)(history_id, query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_get_result.assert_called_once_with(history_id, query)


def test_result_not_found(mocker: MockerFixture):
    history_id = uuid7()
    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_view", return_value=True)
    mock_get_result = mocker.patch.object(server.api.bulk.bulks, "get_upload_result")
    mock_get_result.side_effect = RecordNotFound(E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": history_id})

    res, status = unwrap(bulk.result)(history_id, BulkResultQuery())

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UPLOAD_HISTORY_RECORD_NOT_FOUND, {"id": history_id})


def test_result_not_permission(app, mocker: MockerFixture, caplog):
    history_id = uuid7()
    mocker.patch.object(server.api.bulk.bulks, "chack_permission_to_view", return_value=False)

    res, status = unwrap(bulk.result)(history_id, BulkResultQuery())

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.OPERATION_FORBIDDEN)
