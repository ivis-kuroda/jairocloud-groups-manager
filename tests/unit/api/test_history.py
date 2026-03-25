import inspect
import typing as t

from http import HTTPStatus
from pathlib import Path
from uuid import UUID

import pytest

from server.api import history
from server.api.schemas import ErrorResponse, HistoryPublic, OperatorQuery
from server.entities.history_detail import DownloadHistoryData, HistoryQuery, UploadHistoryData
from server.entities.search_request import FilterOption, SearchResult
from server.exc import InvalidQueryError, RecordNotFound
from server.messages import E


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_filter_options(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.filter_options)
    with (
        app.test_request_context("/"),
    ):
        expected = [
            FilterOption(key="o", description="operator", type="string", multiple=True, items=[]),
            FilterOption(
                key="r",
                description="repositories",
                type="string",
                multiple=True,
                items=[],
            ),
            FilterOption(key="g", description="groups", type="string", multiple=True, items=[]),
            FilterOption(key="u", description="users", type="string", multiple=True, items=[]),
        ]
        mock_get_filters = mocker.patch("server.api.history.search_history_filter_options", return_value=expected)
        test_func()
        mock_get_filters.assert_called_once_with()


def test_filter_options_operators(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.filter_options_operators)
    expected = SearchResult(total=0, page_size=20, offset=1, resources=[])
    with (
        app.test_request_context(),
    ):
        mock_get_filter_option = mocker.patch(
            "server.services.history.get_filter_items",
            return_value=expected,
        )
        resp = test_func(tab="download", query=OperatorQuery(p=1, l=20))
        assert resp[0] == expected
        assert resp[1] == HTTPStatus.OK
        mock_get_filter_option.assert_called_once_with("download", key="o", criteria=OperatorQuery(q=None, p=1, l=20))


def test_filter_options_operators_invalid_query(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.filter_options_operators)
    with (
        app.test_request_context(),
    ):
        exception_message = "Invalid Unsupported criteria type: DummyCriteria"
        mock_get_filter_option = mocker.patch(
            "server.services.history.get_filter_items",
            side_effect=InvalidQueryError(exception_message),
        )
        resp = test_func(tab="download", query=OperatorQuery(p=0, l=20))
        assert resp[0] == ErrorResponse(message=exception_message)
        assert resp[1] == HTTPStatus.BAD_REQUEST
        mock_get_filter_option.assert_called_once_with("download", key="o", criteria=OperatorQuery(q=None, p=0, l=20))


@pytest.mark.parametrize(
    ("tab", "expected"),
    [
        ("download", SearchResult[DownloadHistoryData](total=0, page_size=20, offset=1, resources=[])),
        ("upload", SearchResult[UploadHistoryData](total=0, page_size=20, offset=1, resources=[])),
    ],
)
def test_get(app, mocker: MockerFixture, tab, expected):
    test_func = inspect.unwrap(history.get)
    with (
        app.test_request_context(),
    ):
        mock_get_download_history = mocker.patch(
            "server.services.history.get_download_history_data",
            return_value=expected,
        )
        mock_get_upload_history = mocker.patch(
            "server.services.history.get_upload_history_data",
            return_value=expected,
        )
        resp = test_func(tab=tab, query=HistoryQuery(p=1, l=20))
        assert resp[0] == expected
        assert resp[1] == HTTPStatus.OK
        if tab == "download":
            mock_get_download_history.assert_called_once_with(HistoryQuery(q=None, p=1, l=20))
            mock_get_upload_history.assert_not_called()
        else:
            mock_get_upload_history.assert_called_once_with(HistoryQuery(q=None, p=1, l=20))
            mock_get_download_history.assert_not_called()


def test_public_status(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.public_status)
    request_body = HistoryPublic(public=True)
    history_id = "019c794e-0ac6-7380-8cbf-eac8175f9b21"
    with app.test_request_context():
        response = True
        mock_update_public_status = mocker.patch(
            "server.services.history.update_public_status",
            return_value=response,
        )
        resp = test_func(tab="download", history_id=UUID(history_id), body=request_body)
        assert resp[0] == HistoryPublic(public=response)
        assert resp[1] == HTTPStatus.OK
        mock_update_public_status.assert_called_once_with(
            tab="download", history_id=UUID(history_id), public=request_body.public
        )


def test_public_status_record_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.public_status)
    request_body = HistoryPublic(public=True)
    history_id = "019c794e-b6a7-77eb-bad9-2d1f2a561222"
    with app.test_request_context():
        exception_message = f"{history_id} is not found"
        mock_update_public_status = mocker.patch(
            "server.services.history.update_public_status",
            side_effect=RecordNotFound(exception_message),
        )
        resp = test_func(tab="download", history_id=UUID(history_id), body=request_body)
        assert resp[0] == ErrorResponse(message=exception_message)
        assert resp[1] == HTTPStatus.NOT_FOUND
        mock_update_public_status.assert_called_once_with(
            tab="download", history_id=UUID(history_id), public=request_body.public
        )


def test_files(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.files)
    file_id = "019c794e-0cae-7020-b297-16831f57b71b"
    file_path = __file__
    mock_send_file = mocker.patch("server.api.history.send_file", return_value="mocked response")
    mock_get_file_path = mocker.patch("server.services.history.get_file_path", return_value=file_path)
    with app.test_request_context():
        resp = test_func(file_id=UUID(file_id))
        assert resp == "mocked response"
        mock_send_file.assert_called_once_with(path_or_file=Path(file_path))
        mock_get_file_path.assert_called_once_with(UUID(file_id))


def test_files_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.files)
    file_id = "019c794e-b9af-7444-9474-123bcef06dfe"
    file_path = "/non/existent/file/path"
    mock_get_file_path = mocker.patch("server.services.history.get_file_path", return_value=file_path)
    with app.test_request_context():
        resp = test_func(file_id=UUID(file_id))
        assert resp[0] == ErrorResponse(message=E.FILE_NOT_FOUND % {"path": file_path})
        assert resp[1] == HTTPStatus.NOT_FOUND
        mock_get_file_path.assert_called_once_with(UUID(file_id))


def test_files_record_not_found(app, mocker: MockerFixture):
    test_func = inspect.unwrap(history.files)
    file_id = "019c794e-b84f-76bf-91af-a07616a7abf1"
    exception_message = f"{file_id} is not found"
    mock_get_file_path = mocker.patch(
        "server.services.history.get_file_path",
        side_effect=RecordNotFound(exception_message),
    )
    with app.test_request_context():
        resp = test_func(file_id=UUID(file_id))
        assert resp[0] == ErrorResponse(message=exception_message)
        assert resp[1] == HTTPStatus.NOT_FOUND
        mock_get_file_path.assert_called_once_with(UUID(file_id))
