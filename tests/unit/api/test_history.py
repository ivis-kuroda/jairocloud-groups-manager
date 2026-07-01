import typing as t

from http import HTTPStatus
from uuid import uuid7

from flask import Flask, Response

import server.api.history

from server.api import history
from server.api.schemas import ErrorResponse, HistoryPublic, HistoryQuery, OperatorQuery
from server.entities.history_detail import DownloadHistoryData, UploadHistoryData
from server.entities.search_request import FilterOption, SearchResult
from server.exc import InvalidQueryError, RecordNotFound
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_filter_options(mocker: MockerFixture):
    expected = [FilterOption(key="o", description="operator", type="string", multiple=True, items=[])]
    mock_get_options = mocker.patch.object(server.api.history, "search_history_filter_options", return_value=expected)

    res = unwrap(history.filter_options)()

    assert res == expected
    mock_get_options.assert_called_once_with()


def test_filter_options_operators(user_summaries, mocker: MockerFixture):
    total, page, page_size, offset = len(user_summaries), 1, 20, 0
    expected = SearchResult(total=total, page_size=page_size, offset=offset, resources=list(user_summaries.values()))
    mock_get_operators = mocker.patch.object(server.api.history.history, "get_filter_items", return_value=expected)
    tab, query = "download", OperatorQuery(p=page, l=page_size)

    res, status = unwrap(history.filter_options_operators)(tab, query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_get_operators.assert_called_once_with(tab, key="o", criteria=query)


def test_filter_options_operators_invalid_query(mocker: MockerFixture):
    page, page_size = 1, 20
    mock_get_operators = mocker.patch.object(
        server.api.history.history,
        "get_filter_items",
        side_effect=InvalidQueryError(E.FAILED_GET_FILTER_ITEMS % {"key": "i"}),
    )
    tab, query = "download", OperatorQuery(q="invalid", p=page, l=page_size)

    res, status = unwrap(history.filter_options_operators)(tab, query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FAILED_GET_FILTER_ITEMS, {"key": "i"})
    mock_get_operators.assert_called_once_with(tab, key="o", criteria=query)


def test_get_download(mocker: MockerFixture):
    total, page, page_size, offset = 0, 1, 20, 0
    expected = SearchResult[DownloadHistoryData](total=total, page_size=page_size, offset=offset, resources=[])
    mock_get_down = mocker.patch.object(server.api.history.history, "get_download_history_data", return_value=expected)
    mock_get_up = mocker.patch.object(server.api.history.history, "get_upload_history_data")
    query = HistoryQuery(p=page, l=page_size)

    res, status = unwrap(history.get)("download", query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_get_down.assert_called_once_with(query)
    mock_get_up.assert_not_called()


def test_get_upload(mocker: MockerFixture):
    total, page, page_size, offset = 0, 1, 20, 0
    expected = SearchResult[UploadHistoryData](total=total, page_size=page_size, offset=offset, resources=[])
    mock_get_down = mocker.patch.object(server.api.history.history, "get_download_history_data")
    mock_get_up = mocker.patch.object(server.api.history.history, "get_upload_history_data", return_value=expected)
    query = HistoryQuery(p=page, l=page_size)

    res, status = unwrap(history.get)("upload", query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_get_up.assert_called_once_with(query)
    mock_get_down.assert_not_called()


def test_public_status(mocker: MockerFixture):
    tab, body = "download", HistoryPublic(public=(pub := True))
    history_id = uuid7()
    expected = HistoryPublic(public=pub)
    mock_update = mocker.patch.object(server.api.history.history, "update_public_status")
    mock_update.return_value = pub

    res, status = unwrap(history.public_status)(tab, history_id, body)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_update.assert_called_once_with(tab, history_id, public=body.public)


def test_public_status_record_not_found(mocker: MockerFixture):
    tab, body = "upload", HistoryPublic(public=(pub := False))
    history_id = uuid7()

    mock_update = mocker.patch.object(server.api.history.history, "update_public_status")
    mock_update.side_effect = RecordNotFound(E.FAILED_GET_HISTORY_RECORD % {"history_id": history_id, "table": tab})

    res, status = unwrap(history.public_status)(tab, history_id, body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FAILED_GET_HISTORY_RECORD, {"history_id": history_id, "table": tab})
    mock_update.assert_called_once_with(tab, history_id, public=pub)


def test_files(app: Flask, tmp_path, mocker: MockerFixture):
    file_id = uuid7()
    file_path = tmp_path / f"{str(file_id)[:7]}.tsv"
    file_path.write_text("mocked file content")

    mock_get_path = mocker.patch.object(server.api.history.history, "get_file_path", return_value=file_path)

    with app.test_request_context():
        res = unwrap(history.files)(file_id)

    assert isinstance(res, Response)
    assert res.status_code == HTTPStatus.OK
    assert next(iter(res.response)) == b"mocked file content"
    mock_get_path.assert_called_once_with(file_id)


def test_files_not_found(app: Flask, tmp_path, mocker: MockerFixture, caplog):
    file_id = uuid7()
    file_path = tmp_path / f"{str(file_id)[:7]}.tsv"

    mocker.patch.object(server.api.history.history, "get_file_path", return_value=file_path)

    with app.test_request_context():
        res, status = unwrap(history.files)(file_id)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FILE_NOT_FOUND, {"path": file_path})
    assert_message(caplog.records[0], E.FILE_NOT_FOUND % {"path": file_path})


def test_files_record_not_found(mocker: MockerFixture):
    file_id = uuid7()
    mock_get_path = mocker.patch.object(server.api.history.history, "get_file_path")
    mock_get_path.side_effect = RecordNotFound(E.FILE_RECORD_NOT_FOUND % {"file_id": file_id})

    res, status = unwrap(history.files)(file_id)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FILE_RECORD_NOT_FOUND, {"file_id": file_id})
