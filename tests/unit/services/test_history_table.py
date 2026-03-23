import typing as t

from uuid import uuid7

import pytest

from sqlalchemy.exc import SQLAlchemyError

from server.db.history import UploadHistory
from server.exc import DatabaseError, InvalidQueryError, InvalidRecordError, RecordNotFound
from server.messages import E
from server.services import history_table


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_upload_by_id(app, mocker: MockerFixture):
    history_id = uuid7()
    result_fnc = mocker.patch("server.db.db.session.get", return_value=mocker.MagicMock())
    history_table.get_upload_by_id(history_id)
    result_fnc.assert_called_once()
    assert result_fnc.call_args[0][1] == history_id


def test_get_upload_by_id_with_exception(app, mocker: MockerFixture):
    history_id = uuid7()
    result_fnc = mocker.patch("server.db.db.session.get", side_effect=SQLAlchemyError)
    with pytest.raises(DatabaseError) as exc:
        history_table.get_upload_by_id(history_id)
    result_fnc.assert_called_once()
    assert str(exc.value) == str(E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id})


def test_get_upload_results(app, mocker: MockerFixture):
    history_id = uuid7()
    attribute = "results"
    result_fnc = mocker.patch(
        "server.db.db.session.query",
        return_value=mocker.MagicMock(filter=mocker.MagicMock(first=None)),
    )
    history_table.get_upload_results(history_id, attribute)
    result_fnc.assert_called_once()


def test_get_upload_results_with_exception(app, mocker: MockerFixture):
    history_id = uuid7()
    attribute = "results"
    result_fnc = mocker.patch(
        "server.db.db.session.query",
        return_value=mocker.MagicMock(filter=mocker.MagicMock(first=None)),
        side_effect=SQLAlchemyError,
    )
    with pytest.raises(DatabaseError) as exc:
        history_table.get_upload_results(history_id, attribute)
    result_fnc.assert_called_once()
    assert str(exc.value) == str(E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id})


@pytest.mark.parametrize(
    ("status_filter"),
    [(["S", "F"]), ([])],
)
def test_get_paginated_upload_results(app, mocker: MockerFixture, status_filter):
    history_id = uuid7()
    offset = 2
    size = 10

    mock_db = mocker.patch(
        "server.db.db.session.query", return_value=mocker.MagicMock(filter=mocker.MagicMock(first=None))
    )
    history_table.get_paginated_upload_results(history_id, offset, size, status_filter)
    mock_db.assert_called_once()


def test_get_paginated_upload_results_invalid_query(app, mocker: MockerFixture):
    history_id = uuid7()
    offset = 0
    size = 10
    status_filter = ["S", "F"]
    with pytest.raises(InvalidQueryError) as exc:
        history_table.get_paginated_upload_results(history_id, offset, size, status_filter)
    assert str(exc.value) == str(E.INVALID_QUERY % {"offset": offset, "size": size})


def test_get_paginated_upload_results_with_exception(app, mocker: MockerFixture):
    history_id = uuid7()
    offset = 2
    size = 10
    status_filter = ["S", "F"]
    mock_db = mocker.patch(
        "server.db.db.session.query",
        return_value=mocker.MagicMock(filter=mocker.MagicMock(first=None)),
        side_effect=SQLAlchemyError,
    )
    with pytest.raises(DatabaseError) as exc:
        history_table.get_paginated_upload_results(history_id, offset, size, status_filter)
    mock_db.assert_called_once()
    assert str(exc.value) == str(E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id})


def test_create_upload(app, mocker: MockerFixture):
    file_id = uuid7()
    results = {"summary": {"a": 1}, "results": [1, 2], "missing_users": ["x"]}
    operator_id = "opid"
    operator_name = "opname"
    mock_add = mocker.patch("server.db.db.session.add")
    mock_commit = mocker.patch("server.db.db.session.commit")
    mock_upload = mocker.patch("server.services.history_table.UploadHistory", autospec=True)
    ret = history_table.create_upload(file_id, results, operator_id, operator_name)
    mock_add.assert_called_once_with(mock_upload.return_value)
    mock_commit.assert_called_once()
    assert isinstance(ret, UploadHistory)


def test_create_upload_not_summary(app):
    file_id = uuid7()
    results = {"results": [1, 2], "missing_users": ["x"]}
    operator_id = "opid"
    operator_name = "opname"
    with pytest.raises(InvalidRecordError) as exc:
        history_table.create_upload(file_id, results, operator_id, operator_name)
    assert str(exc.value) == str(E.INVALID_UPLOAD_HISTORY_RECORD_ATTRIBUTES)


def test_create_upload_with_exception(app, mocker: MockerFixture):
    file_id = uuid7()
    results = {"summary": {"a": 1}, "results": [1, 2], "missing_users": ["x"]}
    operator_id = "opid"
    operator_name = "opname"
    mock_add = mocker.patch("server.db.db.session.add", side_effect=SQLAlchemyError)
    with pytest.raises(DatabaseError) as exc:
        history_table.create_upload(file_id, results, operator_id, operator_name)
    mock_add.assert_called_once()
    assert str(exc.value) == str(E.FAILED_CREATE_UPLOAD_HISTORY_RECORD % {"file_id": file_id})


def test_update_upload_status(app, mocker: MockerFixture):
    history_id = uuid7()
    status = "S"
    new_results = {"summary": {}, "results": [], "missing_users": []}
    file_id = uuid7()
    mock_get = mocker.patch("server.db.db.session.get")
    obj = UploadHistory()
    mock_get.return_value = obj
    history_table.update_upload_status(history_id, status, new_results, file_id)
    mock_get.assert_called_once_with(history_table.UploadHistory, history_id)
    assert obj.status == status
    assert obj.file_id == file_id
    assert obj.results["summary"] == {}


def test_update_upload_status_object_not_found(app, mocker: MockerFixture):
    history_id = uuid7()
    status = "S"
    new_results = {"summary": {}, "results": [], "missing_users": []}
    file_id = uuid7()
    mock_get = mocker.patch("server.db.db.session.get", return_value=None)
    history_table.update_upload_status(history_id, status, new_results, file_id)
    mock_get.assert_called_once_with(history_table.UploadHistory, history_id)


def test_update_upload_status_no_new_results(app, mocker: MockerFixture):
    history_id = uuid7()
    status = "P"
    new_results = None
    file_id = uuid7()
    mock_get = mocker.patch("server.db.db.session.get")
    obj = UploadHistory()
    mock_get.return_value = obj
    history_table.update_upload_status(history_id, status, new_results, file_id)
    mock_get.assert_called_once_with(history_table.UploadHistory, history_id)
    assert obj.status == status
    assert obj.file_id == file_id


def test_update_upload_status_no_file_id(app, mocker: MockerFixture):
    history_id = uuid7()
    status = "S"
    new_results = None
    file_id = None
    mock_get = mocker.patch("server.db.db.session.get")
    obj = UploadHistory()
    mock_get.return_value = obj
    history_table.update_upload_status(history_id, status, new_results, file_id)
    mock_get.assert_called_once_with(history_table.UploadHistory, history_id)
    assert obj.status == status


def test_get_history_by_file_id(app, mocker: MockerFixture):
    file_id = uuid7()
    mock_query = mocker.MagicMock()
    mock_filter_by = mocker.MagicMock()
    mock_query.filter_by.return_value = mock_filter_by
    mock_filter_by.one_or_none.return_value = "history_obj"
    mocker.patch("server.db.db.session.query", return_value=mock_query)
    ret = history_table.get_history_by_file_id(file_id)
    mock_query.filter_by.assert_called_once_with(file_id=file_id)
    mock_filter_by.one_or_none.assert_called_once()
    assert ret == "history_obj"


def test_get_history_by_file_id_not_found(app, mocker: MockerFixture):
    file_id = uuid7()
    mock_query = mocker.MagicMock()
    mock_filter_by = mocker.MagicMock()
    mock_query.filter_by.return_value = mock_filter_by
    mock_filter_by.one_or_none.return_value = None
    mocker.patch("server.db.db.session.query", return_value=mock_query)
    with pytest.raises(RecordNotFound) as exc:
        history_table.get_history_by_file_id(file_id)
    assert str(exc.value) == str(E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID % {"file_id": file_id})


def test_get_file_by_id(app, mocker):
    file_id = uuid7()
    mock_query = mocker.MagicMock()
    mock_filter_by = mocker.MagicMock()
    mock_query.filter_by.return_value = mock_filter_by
    mock_filter_by.one_or_none.return_value = "file_obj"
    mocker.patch("server.db.db.session.query", return_value=mock_query)
    ret = history_table.get_file_by_id(file_id)
    mock_query.filter_by.assert_called_once_with(id=file_id)
    mock_filter_by.one_or_none.assert_called_once()
    assert ret == "file_obj"


def test_get_file_by_id_not_found(app, mocker):
    file_id = uuid7()
    mock_query = mocker.MagicMock()
    mock_filter_by = mocker.MagicMock()
    mock_query.filter_by.return_value = mock_filter_by
    mock_filter_by.one_or_none.return_value = None
    mocker.patch("server.db.db.session.query", return_value=mock_query)
    with pytest.raises(RecordNotFound) as exc:
        history_table.get_file_by_id(file_id)
    assert str(exc.value) == str(E.FAILED_GET_FILE_RECORD % {"file_id": file_id})


def test_delete_file_by_id(app, mocker: MockerFixture):
    file_id = uuid7()
    mock_files = mocker.patch(
        "server.services.history_table.Files",
        return_value=mocker.MagicMock(query=mocker.MagicMock(filter=mocker.MagicMock(delete=mocker.MagicMock()))),
    )
    history_table.delete_file_by_id(file_id)
    mock_files.query.filter.assert_called_once()


def test_create_file(app, mocker: MockerFixture):
    file_path = "/var/tmp/test_file.csv"  # noqa: S108
    file_content = {"repositories": [], "groups": [], "users": []}
    file_id = uuid7()
    mock_files = mocker.patch("server.services.history_table.Files", autospec=True)
    instance = mock_files.return_value
    instance.id = file_id
    mock_add = mocker.patch("server.db.db.session.add")
    result = history_table.create_file(file_path, file_content, file_id)
    mock_add.assert_called_once_with(instance)
    assert result.id == file_id
    assert result.file_path == file_path
    assert result.file_content == file_content


def test_create_file_without_id(app, mocker: MockerFixture):
    file_path = "/var/tmp/test_file.csv"  # noqa: S108
    file_content = {"repositories": [], "groups": [], "users": []}
    file_id = None
    mock_files = mocker.patch("server.services.history_table.Files", autospec=True)
    instance = mock_files.return_value
    instance.id = file_id
    mock_add = mocker.patch("server.db.db.session.add")
    result = history_table.create_file(file_path, file_content, file_id)
    mock_add.assert_called_once_with(instance)
    assert result.id == file_id
    assert result.file_path == file_path
    assert result.file_content == file_content


def test_create_download_history(app, mocker: MockerFixture):
    file_id = uuid7()
    file_path = "test/path"
    file_content = {}
    operator_id = "test_user_1"
    operator_name = "Test user"
    mocker.patch("server.services.history_table.create_file", return_value=None)
    mock_add = mocker.patch("server.db.db.session.add")
    result = history_table.create_download_history(file_id, file_path, file_content, operator_id, operator_name)
    assert result.file_id == file_id
    assert result.operator_id == operator_id
    assert result.operator_name == operator_name
    mock_add.assert_called_once()


def test_create_download_history_with_exception(app, mocker: MockerFixture):
    file_id = uuid7()
    file_path = "test/path"
    file_content = {}
    operator_id = "test_user_1"
    operator_name = "Test user"
    mocker.patch("server.services.history_table.create_file", side_effect=SQLAlchemyError)
    with pytest.raises(DatabaseError) as exc:
        history_table.create_download_history(file_id, file_path, file_content, operator_id, operator_name)
    assert str(exc.value) == str(E.FAILED_CREATE_DOWNLOAD_HISTORY_RECORD % {"file_id": file_id})
