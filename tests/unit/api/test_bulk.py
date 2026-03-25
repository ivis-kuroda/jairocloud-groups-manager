import inspect
import typing as t

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import uuid7

from flask_login import login_user

from server.api import bulk
from server.api.schemas import BulkBody, ErrorResponse, ExcuteRequest, TargetRepositoryForm, UploadQuery
from server.entities.bulk import ExecuteResults, ResultSummary, ValidateResults
from server.entities.login_user import LoginUser
from server.exc import FileNotFound, FileValidationError, RecordNotFound, TaskExecutionError
from server.messages import E


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_upload_file(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.upload_file)
    repository_id = "repo1"
    operator_id = "user1"
    operator_name = "test_user"
    temp_file_id = uuid7()
    mock_user = LoginUser(eppn="test_eppn", is_member_of="", user_name=operator_name, map_id=operator_id, session_id="")
    form = TargetRepositoryForm(repository_id=repository_id)
    dummy_file = mocker.Mock(bulk_file=mocker.Mock(filename="test.csv", save=mocker.Mock()))
    mock_task = mocker.Mock(id="task_id")
    mocker.patch("server.services.repositories.get_by_id", return_value=mocker.Mock())
    mocker.patch("server.api.bulk.get_permitted_repository_ids", return_value=[repository_id])
    mock_upload_file = mocker.patch("server.services.bulks.upload_file", return_value=temp_file_id)
    mock_validate_upload_data = mocker.patch(
        "server.services.bulks.validate_upload_data.apply_async", return_value=mock_task
    )
    with app.test_request_context():
        login_user(mock_user)
        result = test_func(form=form, files=dummy_file)
        assert result[0].task_id == mock_task.id
        assert isinstance(result[0], BulkBody)
        assert result[1] == HTTPStatus.OK
        args, _ = mock_upload_file.call_args
        assert args[0] == form.repository_id
        assert args[1] == dummy_file.bulk_file
        args, _ = mock_validate_upload_data.call_args
        assert args[0][0] == operator_id
        assert args[0][1] == operator_name
        assert args[0][2] == temp_file_id


def test_upload_file_repository_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.upload_file)
    mocker.patch("server.services.repositories.get_by_id", return_value=None)
    repository_id = "repo1"
    form = TargetRepositoryForm(repository_id=repository_id)
    dummy_file = mocker.Mock(bulk_file=mocker.Mock(filename="test.csv", save=mocker.Mock()))
    expected_message = E.REPOSITORY_NOT_FOUND % {"id": form.repository_id}
    result = test_func(form=form, files=dummy_file)
    assert result[0] == ErrorResponse(message=expected_message)
    assert result[1] == HTTPStatus.NOT_FOUND


def test_upload_file_repository_forbidden(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.upload_file)
    mocker.patch("server.services.repositories.get_by_id", return_value=mocker.Mock())
    repository_id = "repo1"
    form = TargetRepositoryForm(repository_id=repository_id)
    dummy_file = mocker.Mock(bulk_file=mocker.Mock(filename="test.csv", save=mocker.Mock()))
    expected_message = E.REPOSITORY_FORBIDDEN % {"id": form.repository_id}
    with app.test_request_context():
        login_user(LoginUser(eppn="test_eppn", is_member_of="", user_name="test_user", map_id="test_id", session_id=""))
        result = test_func(form=form, files=dummy_file)
    assert result[0] == ErrorResponse(message=expected_message)
    assert result[1] == HTTPStatus.FORBIDDEN


def test_validate_status(app, mocker: MockerFixture):
    task_id = "task_id"
    test_func = inspect.unwrap(bulk.validate_status)
    mocker.patch("server.services.bulks.get_validate_task_result", return_value=mocker.Mock(state="SUCCESS"))
    expected = BulkBody(status="SUCCESS")
    with app.test_request_context():
        result = test_func(task_id)
        assert result[0] == expected
        assert result[1] == HTTPStatus.OK


def test_validate_status_not_found(app, mocker: MockerFixture):
    task_id = "task_id"
    test_func = inspect.unwrap(bulk.validate_status)
    expected_message = E.TASK_NOT_FOUND % {"task_id": task_id}
    mocker.patch("server.services.bulks.get_validate_task_result", side_effect=TaskExecutionError(expected_message))
    expected = ErrorResponse(message=expected_message)
    with app.test_request_context():
        result = test_func(task_id)
        assert result[0] == expected
        assert result[1] == HTTPStatus.NOT_FOUND


def test_validate_result(app, mocker: MockerFixture):
    task_id = "task_id"
    history_id = uuid7()
    test_func = inspect.unwrap(bulk.validate_result)
    mocker.patch("server.services.bulks.get_validate_task_result", return_value=mocker.Mock(result=history_id))
    mocker.patch("server.api.bulk.is_user_logged_in", return_value=True)
    mocker.patch("server.services.bulks.chack_permission_to_operation", return_value=True)
    expected = ValidateResults(
        results=[],
        summary=ResultSummary(create=0, delete=0, error=0, skip=0, update=0),
        missing_user=[],
        offset=1,
        page_size=50,
    )
    mock_validate_result = mocker.patch("server.services.bulks.get_validate_result", return_value=expected)
    with app.test_request_context():
        login_user(LoginUser(eppn="test_eppn", is_member_of="", user_name="test_user", map_id="test_id", session_id=""))
        result = test_func(query=UploadQuery(f=[3], p=2, l=50), task_id=task_id)
        assert result[0] == expected
        assert result[1] == HTTPStatus.OK
        mock_validate_result.assert_called_once_with(history_id=history_id, status_filter=["skip"], offset=2, size=50)


def test_validate_result_not_permission(app, mocker: MockerFixture):
    task_id = "task_id"
    history_id = uuid7()
    test_func = inspect.unwrap(bulk.validate_result)
    mocker.patch("server.services.bulks.get_validate_task_result", return_value=mocker.Mock(result=history_id))
    mocker.patch("server.api.bulk.is_user_logged_in", return_value=False)
    expected = ErrorResponse(message=E.OPERATION_FORBIDDEN)
    with app.test_request_context():
        result = test_func(query=UploadQuery(), task_id=task_id)
        assert result[0] == expected
        assert result[1] == HTTPStatus.FORBIDDEN


def test_validate_result_failed(app, mocker: MockerFixture):
    task_id = "task_id"
    test_func = inspect.unwrap(bulk.validate_result)
    mocker.patch("server.services.bulks.get_validate_task_result", return_value=mocker.Mock(successful=False))
    expected_message = E.UNEXPECTED_SERVER_ERROR
    with app.test_request_context():
        result = test_func(query=UploadQuery(), task_id=task_id)
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.INTERNAL_SERVER_ERROR


def test_validate_result_with_exception(app, mocker: MockerFixture):
    task_id = "task_id"
    test_func = inspect.unwrap(bulk.validate_result)
    history_id = uuid7()
    mocker.patch("server.services.bulks.get_validate_task_result", return_value=mocker.Mock(result=history_id))
    mocker.patch("server.api.bulk.is_user_logged_in", return_value=True)
    mocker.patch(
        "server.services.bulks.chack_permission_to_operation",
        side_effect=RecordNotFound(E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": history_id}),
    )
    with app.test_request_context():
        login_user(LoginUser(eppn="test_eppn", is_member_of="", user_name="test_user", map_id="test_id", session_id=""))
        result = test_func(query=UploadQuery(), task_id=task_id)
        assert result[0] == ErrorResponse(message=E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": history_id})
        assert result[1] == HTTPStatus.NOT_FOUND


def test_validate_result_not_found(app, mocker: MockerFixture):
    task_id = "task_id"
    test_func = inspect.unwrap(bulk.validate_result)
    expected_message = E.FILE_EXPIRED % {"path": "file_path"}
    mocker.patch(
        "server.services.bulks.get_validate_task_result",
        return_value=mocker.Mock(result=FileNotFound(expected_message)),
    )
    with app.test_request_context():
        result = test_func(query=UploadQuery(), task_id=task_id)
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.NOT_FOUND


def test_validate_result_file_error(app, mocker: MockerFixture):
    task_id = "task_id"
    test_func = inspect.unwrap(bulk.validate_result)
    expected_message = E.INVALID_FILE_STRUCTURE
    mock_return_value = FileValidationError(expected_message)
    mocker.patch("server.services.bulks.get_validate_task_result", return_value=mocker.Mock(result=mock_return_value))
    with app.test_request_context():
        result = test_func(query=UploadQuery(), task_id=task_id)
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.BAD_REQUEST


def test_execute(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.execute)
    temp_id = uuid7()
    repository_id = "repo1"
    task_id = "task_id"
    body = ExcuteRequest(
        temp_file_id=temp_id,
        repository_id=repository_id,
        delete_users=["user1", "user2"],
    )
    history_id = uuid7()
    mocker.patch("server.api.bulk.is_user_logged_in", return_value=True)
    mocker.patch("server.services.bulks.chack_permission_to_operation", return_value=True)
    mock_get_history_by_file_id = mocker.patch(
        "server.services.history_table.get_history_by_file_id", return_value=mocker.Mock(id=history_id)
    )
    mock_execute_bulk_upload = mocker.patch(
        "server.services.bulks.update_users.apply_async", return_value=mocker.Mock(id=task_id)
    )
    expected = BulkBody(task_id=task_id, history_id=history_id)
    with app.test_request_context():
        login_user(LoginUser(eppn="test_eppn", is_member_of="", user_name="test_user", map_id="test_id", session_id=""))
        result = test_func(body)
        assert result[0] == expected
        assert result[1] == HTTPStatus.OK
        mock_get_history_by_file_id.assert_called_once_with(temp_id)
        mock_execute_bulk_upload.assert_called_once_with(
            kwargs={"history_id": history_id, "temp_file_id": body.temp_file_id, "delete_users": body.delete_users}
        )


def test_execute_history_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.execute)
    temp_id = uuid7()
    body = ExcuteRequest(temp_file_id=temp_id)
    mocker.patch(
        "server.services.history_table.get_history_by_file_id",
        side_effect=RecordNotFound(E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": temp_id}),
    )
    expected_message = E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": temp_id}
    with app.test_request_context():
        result = test_func(body)
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.NOT_FOUND


def test_execute_not_permission(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.execute)
    temp_id = uuid7()
    repository_id = "repo1"
    body = ExcuteRequest(temp_file_id=temp_id, repository_id=repository_id)
    expected_message = E.OPERATION_FORBIDDEN
    mocker.patch(
        "server.services.history_table.get_history_by_file_id",
        return_value=mocker.Mock(id=uuid7()),
    )
    mocker.patch("server.api.bulk.is_user_logged_in", return_value=True)
    mocker.patch("server.services.bulks.chack_permission_to_operation", return_value=False)
    with app.test_request_context():
        login_user(LoginUser(eppn="test_eppn", is_member_of="", user_name="test_user", map_id="test_id", session_id=""))
        result = test_func(body)
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.FORBIDDEN


def test_execute_status(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.execute_status)
    task_id = "task_id"
    mocker.patch("server.services.bulks.update_users.AsyncResult", return_value=mocker.Mock(state="SUCCESS"))
    expected = BulkBody(status="SUCCESS")
    with app.test_request_context():
        result = test_func(task_id)
        assert result[0] == expected
        assert result[1] == HTTPStatus.OK


def test_execute_status_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.execute_status)
    task_id = "task_id"
    expected_message = E.TASK_NOT_FOUND % {"task_id": task_id}
    mocker.patch("server.services.bulks.get_execute_task_result", side_effect=TaskExecutionError(expected_message))
    with app.test_request_context():
        result = test_func(task_id)
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.NOT_FOUND


def test_result(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.result)
    history_id = uuid7()
    expected_summary = ExecuteResults(
        items=[],
        summary=ResultSummary(create=0, delete=0, error=0, skip=0, update=0),
        file_id=uuid7(),
        file_name="",
        operator="",
        start_timestamp=datetime.now(UTC),
        end_timestamp=None,
        total=0,
        offset=2,
        page_size=50,
    )
    mocker.patch("server.services.bulks.chack_permission_to_view", return_value=True)
    mock_get_upload_result = mocker.patch("server.services.bulks.get_upload_result", return_value=expected_summary)
    with app.test_request_context():
        result = test_func(history_id, UploadQuery(f=[0, 1], p=2, l=50))
        assert result[0] == expected_summary
        assert result[1] == HTTPStatus.OK
        mock_get_upload_result.assert_called_once_with(
            history_id=history_id, status_filter=["create", "update"], offset=2, size=50
        )


def test_result_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.result)
    history_id = uuid7()
    expected_message = E.UPDATE_HISTORY_RECORD_NOT_FOUND % {"id": history_id}
    mocker.patch("server.services.bulks.chack_permission_to_view", return_value=True)
    mocker.patch(
        "server.services.bulks.get_upload_result",
        side_effect=RecordNotFound(expected_message),
    )
    with app.test_request_context():
        result = test_func(history_id, UploadQuery())
        assert result[0] == ErrorResponse(message=expected_message)
        assert result[1] == HTTPStatus.NOT_FOUND


def test_result_not_permission(app, mocker: MockerFixture):
    test_func = inspect.unwrap(bulk.result)
    history_id = uuid7()
    expected_message = E.OPERATION_FORBIDDEN
    mocker.patch("server.services.bulks.chack_permission_to_view", return_value=False)
    result = test_func(history_id, UploadQuery())
    assert result[0] == ErrorResponse(message=expected_message)
    assert result[1] == HTTPStatus.FORBIDDEN
