import typing as t

from copy import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from sqlalchemy.exc import SQLAlchemyError

import server.services.history_table

from server.db.history import Files, UploadHistory
from server.entities.bulk import FileContent, ValidateResults
from server.exc import DatabaseError, InvalidQueryError, RecordNotFound
from server.messages import E
from server.services import history_table
from server.services.history_table import get_upload_by_id, get_upload_results, get_upload_results_with_pagination

from tests.helpers import assert_message, load_json_data, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def validate_results():
    json_data = load_json_data("data/validate_results.json")
    validate_results = ValidateResults.model_validate(json_data, by_alias=True)

    return json_data, validate_results


def test_get_upload_by_id(db, mocker: MockerFixture):
    history_id = uuid7()
    expected = history = UploadHistory()
    db.session.get.return_value = history

    obj = get_upload_by_id(history_id)

    assert obj == expected
    db.session.get.assert_called_once_with(UploadHistory, history_id, options=mocker.ANY)


def test_get_upload_by_id_sqlalchemy_error(app, db, caplog):
    history_id = uuid7()
    db.session.get.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_UPLOAD_HISTORY_RECORD)):
        get_upload_by_id(history_id)

    assert_message(caplog.records[0], E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id})


def test_get_upload_results(db):
    history_id = uuid7()

    expected = json = {"create": 1, "update": 2, "delete": 3, "skip": 4, "error": 5}
    mock_execute = db.session.execute
    mock_execute.return_value.one_or_none.return_value = (json,)

    obj = get_upload_results(history_id, "summary")

    assert obj == expected


def test_get_upload_results_sqlalchemy_error(app, db, caplog):
    history_id = uuid7()
    db.session.execute.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_UPLOAD_HISTORY_RECORD)):
        get_upload_results(history_id, "summary")

    db.session.execute.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id})


def test_get_upload_results_not_found(app, db, caplog):
    history_id = uuid7()
    db.session.execute.return_value.one_or_none.return_value = None

    with pytest.raises(RecordNotFound, match=regex(E.UPLOAD_HISTORY_RECORD_NOT_FOUND)):
        get_upload_results(history_id, "summary")

    assert_message(caplog.records[0], E.UPLOAD_HISTORY_RECORD_NOT_FOUND, {"id": history_id})


def test_get_upload_results_with_pagination(db, mocker: MockerFixture):
    history_id = uuid7()
    page, size = 2, 10

    mocker.patch.object(server.services.history_table, "is_upload_history_exists", return_value=True)
    expected = json = [
        {"id": "test_user_id_1", "status": "create"},
        {"id": "test_user_id_2", "status": "update"},
        {"id": "test_user_id_3", "status": "skip"},
    ]
    mock_execute = db.session.execute
    mock_execute.return_value.scalars.return_value.all.return_value = json

    result = get_upload_results_with_pagination(history_id, page, size)

    assert result == expected
    mock_execute.assert_called_once()


def test_get_upload_results_with_pagination_with_filter(db, mocker: MockerFixture):
    history_id = uuid7()
    page, size = 2, 10

    mocker.patch.object(server.services.history_table, "is_upload_history_exists", return_value=True)
    expected = json = [
        {"id": "test_user_id_1", "status": "create"},
        {"id": "test_user_id_2", "status": "update"},
    ]
    mock_execute = db.session.execute
    mock_execute.return_value.scalars.return_value.all.return_value = json

    result = get_upload_results_with_pagination(history_id, page, size, ["create", "update"])

    assert result == expected
    mock_execute.assert_called_once()


def test_get_upload_results_with_pagination_invalid_query(app, db, caplog):
    history_id = uuid7()
    page, size = 0, 10

    with pytest.raises(InvalidQueryError, match=regex(E.INVALID_QUERY)):
        get_upload_results_with_pagination(history_id, page, size)

    assert_message(caplog.records[0], E.INVALID_QUERY, {"page": page, "size": size})


def test_get_upload_results_with_pagination_sqlalchemy_error(app, db, caplog):
    history_id = uuid7()
    page, size = 2, 10
    db.session.execute.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_UPLOAD_HISTORY_RECORD)):
        get_upload_results_with_pagination(history_id, page, size)

    db.session.execute.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id})


def test_create_upload(app, db, validate_results, mocker: MockerFixture):
    file_id = uuid7()
    results_data = validate_results.model_dump(mode="json")

    results_column = copy(results_data)
    results_column["items"] = results_data["results"]
    del results_column["results"]
    del results_column["offset"]
    del results_column["page_size"]

    operator_id = "test_operator_id"
    operator_name = "Test Operator"

    mock_add = db.session.add
    mock_commit = db.session.commit
    mock_history = mocker.patch("server.services.history_table.UploadHistory", autospec=True)

    ret = history_table.create_upload(file_id, validate_results, operator_id, operator_name)

    mock_add.assert_called_once_with(mock_history.return_value)
    mock_commit.assert_called_once()
    assert ret.file_id == file_id
    assert ret.results == results_column
    assert ret.operator_id == operator_id
    assert ret.operator_name == operator_name


def test_create_upload_with_exception(app, db, validate_results, caplog):
    file_id = uuid7()
    operator_id = "test_operator_id"
    operator_name = "Test Operator"
    mock_add = db.session.add
    db.session.add.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_CREATE_UPLOAD_HISTORY_RECORD)):
        history_table.create_upload(file_id, validate_results, operator_id, operator_name)

    mock_add.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_UPLOAD_HISTORY_RECORD, {"file_id": file_id})


def test_update_upload_status(app, db, validate_results, mocker: MockerFixture):
    history_id = uuid7()
    status = "S"
    file_id = uuid7()

    mock_get = db.session.get
    mock_history = mocker.MagicMock(spec=UploadHistory)
    mock_history.end_timestamp = None
    mock_get.return_value = mock_history

    history_table.update_upload_status(history_id, status, validate_results, file_id)

    mock_get.assert_called_once_with(UploadHistory, history_id)
    assert mock_history.status == status
    assert mock_history.file_id == file_id
    assert mock_history.results["summary"] == validate_results.summary.model_dump(mode="json")
    assert mock_history.end_timestamp is not None


def test_update_upload_status_record_not_found(app, db, validate_results):
    history_id = uuid7()
    status = "S"
    file_id = uuid7()
    mock_get = db.session.get
    mock_get.return_value = None

    history_table.update_upload_status(history_id, status, validate_results, file_id)

    mock_get.assert_called_once_with(UploadHistory, history_id)


def test_update_upload_status_no_new_results(app, db, mocker: MockerFixture):
    history_id = uuid7()
    status = "P"
    now = datetime.now(UTC) - timedelta(minutes=1)
    file_id = uuid7()
    mock_get = db.session.get
    mock_history = mocker.MagicMock(spec=UploadHistory)
    mock_history.timestamp = now
    mock_get.return_value = mock_history

    history_table.update_upload_status(history_id, status, None, file_id)

    mock_get.assert_called_once_with(UploadHistory, history_id)
    assert mock_history.status == status
    assert mock_history.file_id == file_id
    assert mock_history.timestamp is not None


def test_update_upload_status_no_file_id(app, db, mocker: MockerFixture):
    history_id = uuid7()
    status = "S"
    new_results = None

    mock_get = db.session.get
    mock_history = mocker.MagicMock(spec=UploadHistory)
    mock_history.file_id = None
    mock_get.return_value = mock_history

    history_table.update_upload_status(history_id, status, new_results, None)

    mock_get.assert_called_once_with(UploadHistory, history_id)
    assert mock_history.status == status
    assert mock_history.file_id is None


def test_update_upload_status_with_exception(app, db, validate_results, caplog):
    history_id = uuid7()
    status = "S"

    file_id = uuid7()
    db.session.get.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_UPDATE_HISTORY_RECORD_STATUS)):
        history_table.update_upload_status(history_id, status, validate_results, file_id)

    assert_message(caplog.records[0], E.FAILED_UPDATE_HISTORY_RECORD_STATUS, {"history_id": history_id})


def test_get_history_by_file_id(app, db, mocker: MockerFixture):
    file_id = uuid7()
    mock_query = db.session.query
    mock_filter_by = mock_query.return_value.filter_by
    mock_history = mocker.MagicMock(spec=UploadHistory)
    mock_history.file_id = file_id
    mock_one = mock_filter_by.return_value.one_or_none
    mock_one.return_value = mock_history

    ret = history_table.get_history_by_file_id(file_id)

    mock_query.assert_called_once()
    mock_filter_by.assert_called_once_with(file_id=file_id)
    mock_one.assert_called_once()
    assert ret.file_id == file_id


def test_get_history_by_file_id_not_found(app, db, caplog):
    file_id = uuid7()
    mock_query = db.session.query
    mock_filter_by = mock_query.return_value.filter_by
    mock_filter_by.return_value.one_or_none.return_value = None

    with pytest.raises(RecordNotFound, match=regex(E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID)):
        history_table.get_history_by_file_id(file_id)

    mock_query.assert_called_once()
    mock_filter_by.assert_called_once_with(file_id=file_id)
    assert_message(caplog.records[0], E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID, {"file_id": file_id})


def test_get_history_by_file_id_with_exception(app, db, caplog):
    file_id = uuid7()
    db.session.query.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID)):
        history_table.get_history_by_file_id(file_id)

    assert_message(caplog.records[0], E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID, {"file_id": file_id})


def test_get_file_by_id(app, db, mocker: MockerFixture):
    file_id = uuid7()
    mock_query = db.session.query
    mock_filter_by = mock_query.return_value.filter_by
    mock_record = mocker.MagicMock(spec=Files)
    mock_filter_by.return_value.one_or_none.return_value = mock_record

    ret = history_table.get_file_by_id(file_id)

    mock_query.assert_called_once()
    mock_filter_by.assert_called_once_with(id=file_id)
    assert ret == mock_record


def test_get_file_by_id_not_found(app, db, caplog):
    file_id = uuid7()
    mock_query = db.session.query
    mock_filter_by = mock_query.return_value.filter_by
    mock_filter_by.return_value.one_or_none.return_value = None

    with pytest.raises(RecordNotFound, match=regex(E.FAILED_GET_FILE_RECORD)):
        history_table.get_file_by_id(file_id)

    assert_message(caplog.records[0], E.FAILED_GET_FILE_RECORD, {"file_id": file_id})


def test_get_file_by_id_with_exception(app, db, caplog) -> None:
    file_id = uuid7()
    db.session.query.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_GET_FILE_RECORD)):
        history_table.get_file_by_id(file_id)

    assert_message(caplog.records[0], E.FAILED_GET_FILE_RECORD, {"file_id": file_id})


def test_delete_file_by_id(app, db):
    file_id = uuid7()
    mock_query = db.session.query
    mock_filter_by = mock_query.return_value.filter_by
    mock_filter_by.return_value.delete.return_value = 1

    ret = history_table.delete_file_by_id(file_id)

    assert ret == 1
    mock_query.assert_called_once()
    mock_filter_by.assert_called_once_with(id=file_id)
    mock_filter_by.return_value.delete.assert_called_once()


def test_delete_file_by_id_with_exception(app, db, caplog) -> None:
    file_id = uuid7()
    db.session.query.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_DELETE_FILE_RECORD)):
        history_table.delete_file_by_id(file_id)
    assert_message(caplog.records[0], E.FAILED_DELETE_FILE_RECORD, {"file_id": file_id})


def test_create_file_record(app, db, mocker: MockerFixture):
    file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    file_content = FileContent()
    file_id = uuid7()

    mock_files = mocker.patch("server.services.history_table.Files", autospec=True)
    mock_add = db.session.add

    result = history_table.create_file_record(file_path, file_content, file_id)

    mock_add.assert_called_once_with(mock_files.return_value)
    assert result.id == file_id
    assert result.file_path == file_path
    assert result.file_content == file_content.model_dump(mode="json", by_alias=True)


def test_create_file_record_without_id(app, db, mocker: MockerFixture):
    file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    file_content = FileContent()

    mock_add = db.session.add
    mock_files = mocker.patch("server.services.history_table.Files", autospec=True)
    mock_files.return_value.id = None

    result = history_table.create_file_record(file_path, file_content, None)

    mock_add.assert_called_once_with(mock_files.return_value)
    assert result.id is None
    assert result.file_path == file_path
    assert result.file_content == file_content.model_dump(mode="json", by_alias=True)


def test_create_file_record_with_exception(app, db, mocker: MockerFixture, caplog):
    file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    file_content = FileContent()
    file_id = uuid7()

    db.session.add.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_CREATE_FILE_RECORD)):
        history_table.create_file_record(file_path, file_content, file_id)

    assert_message(caplog.records[0], E.FAILED_CREATE_FILE_RECORD, {"file_path": file_path})


def test_create_download_history(app, db, mocker: MockerFixture):
    file_id = uuid7()
    file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    file_content = FileContent()
    operator_id = "test_operator_id"
    operator_name = "Test Operator"

    mock_create = mocker.patch("server.services.history_table.create_file_record")
    mock_add = db.session.add

    result = history_table.create_download_history(file_id, file_path, file_content, operator_id, operator_name)

    assert result.file_id == file_id
    assert result.operator_id == operator_id
    assert result.operator_name == operator_name
    mock_create.assert_called_once_with(file_path, file_content, file_id)
    mock_add.assert_called_once()


def test_create_download_history_with_exception(app, db, mocker: MockerFixture, caplog):
    file_id = uuid7()
    file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    file_content = FileContent()
    operator_id = "test_operator_id"
    operator_name = "Test Operator"
    mock_create = mocker.patch("server.services.history_table.create_file_record")

    db.session.add.side_effect = SQLAlchemyError

    with pytest.raises(DatabaseError, match=regex(E.FAILED_CREATE_DOWNLOAD_HISTORY_RECORD)):
        history_table.create_download_history(file_id, file_path, file_content, operator_id, operator_name)

    assert_message(caplog.records[0], E.FAILED_CREATE_DOWNLOAD_HISTORY_RECORD, {"file_id": file_id})
    mock_create.assert_called_once_with(file_path, file_content, file_id)
