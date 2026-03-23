import typing as t

from datetime import UTC, date, datetime
from uuid import UUID, uuid7

import pytest

from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from server.api.schemas import OperatorQuery
from server.db.history import DownloadHistory, Files, UploadHistory, _FileContent, _ResultData
from server.entities.history_detail import DownloadHistoryData, HistoryQuery, UploadHistoryData
from server.entities.search_request import SearchResult
from server.entities.summaries import UserSummary
from server.exc import DatabaseError, InvalidQueryError, RecordNotFound
from server.messages import E
from server.services import history


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

test_files_table_data = Files()
test_files_table_data.id = UUID("019c794d-fb97-70f2-aba2-c3888973190d")
test_files_table_data.file_path = "ver/tmp/2026/01/test_file.csv"
test_files_table_data.file_content = _FileContent({
    "users": [{"id": "user1", "userName": "user1_name"}, {"id": "user2", "userName": "user2_name"}],
    "groups": [{"id": "group1", "displayName": "group1_name"}, {"id": "group2", "displayName": "group2_name"}],
    "repositories": [{"id": "repo1", "serviceName": "repo1_name"}],
})
test_upload_history_table_data = UploadHistory()
test_upload_history_table_data.id = UUID("019c794e-04c0-7403-8621-b04c40698107")
test_upload_history_table_data.timestamp = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
test_upload_history_table_data.file_id = test_files_table_data.id
test_upload_history_table_data.operator_id = "test_operator_id"
test_upload_history_table_data.operator_name = "test_operator_name"
test_upload_history_table_data.public = True
test_upload_history_table_data.status = "P"
test_upload_history_table_data.results = _ResultData({
    "summary": {"skip": 0, "error": 0, "create": 0, "delete": 0, "update": 0},
    "items": [
        {
            "id": "test_create_user_id",
            "code": "",
            "eppn": "test_create_user_eppn",
            "email": "test_create_user_email",
            "groups": "test_create_user_groups",
            "status": "create",
            "userName": "test_create_user_name",
        }
    ],
    "missing_users": [
        {
            "id": "test_user_id",
            "eppns": "test_user_eppn",
            "emails": "test_user_emails",
            "groups": "test_user_groups",
            "created": "2024-06-01T00:00:00Z",
            "userName": "test_user_name",
            "lastModified": "2024-06-01T00:00:00Z",
            "isSystemAdmin": False,
            "repositoryRoles": "repository_admin",
            "preferredLanguage": "ja",
        }
    ],
})

test_download_history_table_data = DownloadHistory()
test_download_history_table_data.id = UUID("019c794e-08a7-7483-9888-5349a610d4a8")
test_download_history_table_data.timestamp = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
test_download_history_table_data.file_id = test_files_table_data.id
test_download_history_table_data.operator_id = "test_operator_id"
test_download_history_table_data.operator_name = "test_operator_name"
test_download_history_table_data.public = True
test_download_history_table_data.parent_id = None


@pytest.mark.parametrize(
    ("criteria", "data_raw", "expected"),
    [
        (
            HistoryQuery(d="asc"),
            [],
            SearchResult[UploadHistoryData](total=1, page_size=20, offset=0, resources=[]),
        ),
        (
            HistoryQuery(d="desc"),
            [(test_upload_history_table_data, test_files_table_data)],
            SearchResult[UploadHistoryData](
                total=1,
                page_size=20,
                offset=0,
                resources=[
                    UploadHistoryData(
                        id=UUID("019c794e-04c0-7403-8621-b04c40698107"),
                        timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                        end_timestamp=None,
                        public=True,
                        operator=UserSummary(
                            id="test_operator_id",
                            user_name="test_operator_name",
                            role=None,
                            emails=None,
                            eppns=None,
                            last_modified=None,
                        ),
                        status="P",
                        file_path="ver/tmp/2026/01/test_file.csv",
                        file_id=UUID("019c794d-fb97-70f2-aba2-c3888973190d"),
                        repository_count=1,
                        group_count=2,
                        user_count=2,
                    )
                ],
            ),
        ),
    ],
)
def test_get_upload_history_data(app, mocker: MockerFixture, criteria, data_raw, expected):
    mocker.patch("server.services.history._build_filters_for_history", return_value=[])
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.execute.return_value.scalar_one.return_value = 1
    db.session.execute.return_value.all.return_value = data_raw
    reslut = history.get_upload_history_data(criteria)
    assert reslut.total == expected.total
    assert reslut.page_size == expected.page_size
    assert reslut.offset == expected.offset
    assert reslut.resources == expected.resources


@pytest.mark.parametrize(
    ("criteria", "data_raw", "expected"),
    [
        (
            HistoryQuery(d="asc"),
            [],
            SearchResult[DownloadHistoryData](total=1, page_size=20, offset=0, resources=[]),
        ),
        (
            HistoryQuery(d="desc"),
            [(test_download_history_table_data, test_files_table_data, 0)],
            SearchResult[DownloadHistoryData](
                total=1,
                page_size=20,
                offset=0,
                resources=[
                    DownloadHistoryData(
                        id=UUID("019c794e-08a7-7483-9888-5349a610d4a8"),
                        timestamp=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
                        operator=UserSummary(
                            id="test_operator_id",
                            user_name="test_operator_name",
                            role=None,
                            emails=None,
                            eppns=None,
                            last_modified=None,
                        ),
                        public=True,
                        parent_id=None,
                        file_id=UUID("019c794d-fb97-70f2-aba2-c3888973190d"),
                        file_path="ver/tmp/2026/01/test_file.csv",
                        repository_count=1,
                        group_count=2,
                        user_count=2,
                        children_count=0,
                    )
                ],
            ),
        ),
    ],
)
def test_get_download_history_data(app, mocker: MockerFixture, criteria, data_raw, expected):
    mocker.patch("server.services.history._build_filters_for_history", return_value=[])
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.execute.return_value.scalar_one.return_value = 1
    db.session.execute.return_value.all.return_value = data_raw
    reslut = history.get_download_history_data(criteria)
    assert reslut.total == expected.total
    assert reslut.page_size == expected.page_size
    assert reslut.offset == expected.offset
    assert reslut.resources == expected.resources


@pytest.mark.parametrize(
    ("is_system_admin", "criteria", "history_type", "expected_sqls", "expected_params"),
    [
        (
            True,
            HistoryQuery(
                r=["repo1", "repo2"],
                s=date(2026, 1, 1),
                e=date(2026, 1, 31),
            ),
            "upload",
            [
                (
                    "(files.file_content[:file_content_1] @> CAST(:param_1 AS JSONB)) OR "
                    "(files.file_content[:file_content_2] @> CAST(:param_2 AS JSONB))"
                ),
                "upload_history.timestamp >= :timestamp_1",
                "upload_history.timestamp < :timestamp_1",
            ],
            [
                {
                    "file_content_1": "repositories",
                    "file_content_2": "repositories",
                    "param_1": [
                        {
                            "id": "repo1",
                        },
                    ],
                    "param_2": [
                        {
                            "id": "repo2",
                        },
                    ],
                },
                {"timestamp_1": date(2026, 1, 1)},
                {"timestamp_1": date(2026, 2, 1)},
            ],
        ),
        (
            False,
            HistoryQuery(g=["group1", "group2"], s=date(2026, 1, 1)),
            "upload",
            [
                "upload_history.public IS true",
                "files.file_content[:file_content_1] @> CAST(:param_1 AS JSONB)",
                (
                    "(files.file_content[:file_content_1] @> CAST(:param_1 AS JSONB)) OR "
                    "(files.file_content[:file_content_2] @> CAST(:param_2 AS JSONB))"
                ),
                "upload_history.timestamp >= :timestamp_1",
                "upload_history.timestamp < :timestamp_1",
            ],
            [
                {},
                {"file_content_1": "repositories", "param_1": [{"id": "repo1"}]},
                {
                    "file_content_1": "groups",
                    "file_content_2": "groups",
                    "param_1": [
                        {
                            "id": "group1",
                        },
                    ],
                    "param_2": [
                        {
                            "id": "group2",
                        },
                    ],
                },
                {"timestamp_1": date(2026, 1, 1)},
                {"timestamp_1": date(2026, 1, 2)},
            ],
        ),
        (
            False,
            HistoryQuery(u=["user1", "user2"], e=date(2026, 1, 31)),
            "download",
            [
                "download_history.public IS true",
                "files.file_content[:file_content_1] @> CAST(:param_1 AS JSONB)",
                (
                    "(files.file_content[:file_content_1] @> CAST(:param_1 AS JSONB)) OR "
                    "(files.file_content[:file_content_2] @> CAST(:param_2 AS JSONB))"
                ),
                "download_history.timestamp < :timestamp_1",
                "download_history.parent_id IS NULL",
            ],
            [
                {},
                {"file_content_1": "repositories", "param_1": [{"id": "repo1"}]},
                {
                    "file_content_1": "users",
                    "file_content_2": "users",
                    "param_1": [
                        {
                            "id": "user1",
                        },
                    ],
                    "param_2": [
                        {
                            "id": "user2",
                        },
                    ],
                },
                {"timestamp_1": date(2026, 2, 1)},
                {},
            ],
        ),
        (
            False,
            HistoryQuery(i="019c8d57-b463-7675-bcf3-aba9d8df6822", o=["operator1", "operator2"]),
            "download",
            [
                "download_history.public IS true",
                "files.file_content[:file_content_1] @> CAST(:param_1 AS JSONB)",
                "download_history.operator_id IN (__[POSTCOMPILE_operator_id_1])",
                "download_history.parent_id = :parent_id_1",
            ],
            [
                {},
                {"file_content_1": "repositories", "param_1": [{"id": "repo1"}]},
                {"operator_id_1": ["operator1", "operator2"]},
                {"parent_id_1": UUID("019c8d57-b463-7675-bcf3-aba9d8df6822")},
            ],
        ),
    ],
)
def test__build_filters_for_history(
    mocker: MockerFixture,
    is_system_admin: bool,  # noqa: FBT001
    criteria: HistoryQuery,
    history_type: t.Literal["upload", "download"],
    expected_sqls,
    expected_params,
):
    mocker.patch("server.services.history.is_current_user_system_admin", return_value=is_system_admin)
    repoadmin_filter = mocker.patch("server.services.history.get_permitted_repository_ids", return_value={"repo1"})
    filters = history._build_filters_for_history(criteria, history_type)  # noqa: SLF001
    assert len(filters) == len(expected_sqls) == len(expected_params)
    for f, expected_sql, expected_param in zip(filters, expected_sqls, expected_params, strict=False):
        assert str(f) == expected_sql
        compiled = f.compile(dialect=postgresql.dialect())  # pyright: ignore[reportFunctionMemberAccess, reportAttributeAccessIssue]
        assert compiled.params == expected_param

    repoadmin_filter.assert_not_called() if is_system_admin else repoadmin_filter.assert_called_once()


def test_get_filter_items(app, mocker: MockerFixture):
    expected = SearchResult[UserSummary](
        total=0,
        page_size=20,
        offset=0,
        resources=[
            UserSummary(
                id="operator_1", user_name="Operator 1", role=None, emails=None, eppns=None, last_modified=None
            ),
            UserSummary(
                id="operator_2", user_name="Operator 2", role=None, emails=None, eppns=None, last_modified=None
            ),
        ],
    )
    mock_data = [("operator_1", "Operator 1"), ("operator_2", "Operator 2")]
    mocker.patch("server.db.db.session.execute", return_value=mocker.MagicMock(all=lambda: mock_data))
    result = history.get_filter_items("download", "o", OperatorQuery())
    assert result == expected


def test_get_filter_items_with_exception(app, mocker: MockerFixture):
    mocker.patch("server.db.db.session.execute", side_effect=SQLAlchemyError())
    with pytest.raises(DatabaseError) as exc:
        history.get_filter_items("download", "o", OperatorQuery())
    assert str(exc.value) == str(E.FAILED_GET_HISTORY_RECORDS % {"table": "download"})


def test_get_filter_items_invalid_query(app, mocker: MockerFixture):
    with pytest.raises(InvalidQueryError) as exc:
        history.get_filter_items("download", "O", OperatorQuery())
    assert str(exc.value) == str(InvalidQueryError(E.FAILED_GET_FILTER_ITEMS % {"key": "O"}))


def test_update_public_status_not_found(app, mocker: MockerFixture):
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.get.return_value = None
    history_id = uuid7()
    with pytest.raises(RecordNotFound) as exc:
        history.update_public_status(tab="upload", history_id=history_id, public=True)
    assert str(exc.value) == str(E.FAILED_GET_HISTORY_RECORD % {"history_id": history_id, "table": "upload"})


def test_update_public_status_db_error(app, mocker: MockerFixture):
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.get.side_effect = SQLAlchemyError
    history_id = uuid7()
    with pytest.raises(DatabaseError) as exc:
        history.update_public_status(tab="upload", history_id=history_id, public=True)
    assert str(exc.value) == str(E.FAILED_UPDATE_PUBLIC % {"history_id": history_id})


def test_update_public_status(app, mocker: MockerFixture):
    expected = False
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.get.return_value = test_files_table_data
    result = history.update_public_status(
        tab="download", history_id=UUID("019c794e-04c0-7403-8621-b04c40698107"), public=expected
    )
    assert result == expected


def test_get_file_path(app, mocker: MockerFixture):
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.get.return_value = test_files_table_data
    result = history.get_file_path(UUID("019c794e-04c0-7403-8621-b04c40698107"))
    assert result == test_files_table_data.file_path


def test_get_file_path_not_found(app, mocker: MockerFixture):
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.get.return_value = None
    file_id = uuid7()
    with pytest.raises(RecordNotFound) as exc:
        history.get_file_path(file_id)
    assert str(exc.value) == str(E.FAILED_GET_FILE_PATH % {"file_id": file_id})


def test_get_file_path_db_error(app, mocker: MockerFixture):
    db = mocker.MagicMock()
    mocker.patch("server.services.history.db", db)
    db.session.get.side_effect = SQLAlchemyError
    file_id = uuid7()
    with pytest.raises(DatabaseError) as exc:
        history.get_file_path(file_id)
    assert str(exc.value) == str(E.FAILED_GET_FILE_PATH % {"file_id": file_id})


def test_empty_history_criteria():
    criteria = history.empty_history_criteria()
    assert hasattr(criteria, "i")
    assert hasattr(criteria, "r")
    assert hasattr(criteria, "g")
    assert hasattr(criteria, "u")
    assert hasattr(criteria, "o")
    assert hasattr(criteria, "s")
    assert hasattr(criteria, "e")
    assert hasattr(criteria, "d")
    assert hasattr(criteria, "p")
    assert hasattr(criteria, "l")
    for attr in vars(criteria):
        assert getattr(criteria, attr) is None
