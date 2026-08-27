import typing as t

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid7

import openpyxl
import pytest

from redis.exceptions import ConnectionError as RedisConnectionError
from werkzeug.datastructures import FileStorage

from server.const import USER_EXPORT_HEADERS_V1, USER_ROLES
from server.db.history import Files, UploadHistory, _FileContent
from server.entities.bulk import (
    EachResult,
    ExecuteResults,
    ResultSummary,
    UserAggregated,
    ValidateResults,
)
from server.entities.bulk_request import BulkOperation, BulkResponse
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup, MemberGroup, MemberUser
from server.entities.map_user import EPPN, Email, Group, MapUser
from server.entities.patch_request import AddOperation, RemoveOperation
from server.entities.search_request import SearchResponse
from server.entities.summaries import GroupSummary
from server.entities.user_detail import RepositoryRole, UserDetail
from server.exc import (
    DatastoreError,
    FileFormatError,
    FileNotFound,
    FileUploadError,
    FileValidationError,
    InvalidFormError,
    OAuthTokenError,
    RecordNotFound,
    TaskExecutionError,
    UnexpectedResponseError,
)
from server.messages import E, I
from server.services import bulks
from server.services.bulks import _RepositoryMember
from server.services.utils.affiliations import Affiliations, _Group

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def assert_unordered_model_list_equal(list1, list2):
    def to_tuple(x):
        def deep_tuple(obj):
            if isinstance(obj, dict):
                return tuple(sorted((k, deep_tuple(v)) for k, v in obj.items()))
            if isinstance(obj, list):
                return tuple(deep_tuple(i) for i in obj)
            return obj

        return deep_tuple(x.dict())

    assert set(map(to_tuple, list1)) == set(map(to_tuple, list2))


def test_upload_file(app, db, config, mocker: MockerFixture, caplog):
    repository_id = "test_repo_ac_jp"
    mock_file = mocker.MagicMock(spec=FileStorage, filename="test_upload_file")
    mock_save = mock_file.save

    mocker.patch("server.services.history_table.create_file_record")
    mock_commit = db.session.commit
    mock_task = mocker.patch("server.services.bulks.delete_temporary_file.apply_async")
    expected_path = f"{config.STORAGE.local.temporary}/%s_test_upload_file"

    uploaded_id = bulks.upload_file(repository_id, mock_file)

    assert isinstance(uploaded_id, UUID)
    mock_save.assert_called_once_with(expected_path % uploaded_id)
    mock_commit.assert_called_once()
    mock_task.assert_called_once_with((str(uploaded_id),), countdown=3600)
    assert_message(caplog.records[0], I.SUCCESS_UPLOAD_FILES, {"file_path": Path(expected_path % uploaded_id)})


def test_upload_file_with_exception(app, db, mocker: MockerFixture, caplog):
    repository_id = "test_repo_ac_jp"
    mock_file = mocker.MagicMock()
    mock_file.save.side_effect = FileNotFoundError

    mocker.patch("server.services.history_table.create_file_record")
    mock_commit = db.session.commit
    mock_task = mocker.patch("server.services.bulks.delete_temporary_file.apply_async")

    with pytest.raises(FileUploadError, match=regex(E.FAILED_SAVE_UPLOADED_FILE)):
        bulks.upload_file(repository_id, mock_file)

    mock_commit.assert_not_called()
    mock_task.assert_called_once_with((mocker.ANY,), countdown=3600)
    assert_message(caplog.records[0], E.FAILED_SAVE_UPLOADED_FILE)


def test_validate_upload_data(app, mocker: MockerFixture):
    operator_id = "test_user_id"
    operator_name = "test_user_name"
    tmp_file_id = uuid7()
    file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    file_content = _FileContent(
        repositories=[{"id": "repo1", "serviceName": "test_service"}],
        groups=[{"id": "group1", "displayName": "Group 1"}, {"id": "group2", "displayName": "Group 2"}],
        users=[{"id": "user1", "userName": "User 1"}, {"id": "user2", "userName": "User 2"}],
    )
    files = Files()
    files.id = tmp_file_id
    files.file_path = file_path
    files.file_content = file_content
    mock_get_file_by_id = mocker.patch("server.services.history_table.get_file_by_id", return_value=files)
    repository_member = _RepositoryMember(groups={"group1", "group2"}, users={"user1", "user2"})
    mock_get_repository_member = mocker.patch(
        "server.services.bulks.get_repository_member", return_value=repository_member
    )
    mocker.patch("server.services.bulks.build_user_from_file", return_value=(None, None))
    mocker.patch("server.services.bulks.build_user_detail_from_dict", return_value=mocker.MagicMock())
    mocker.patch("server.services.bulks.build_user_detail_from_dict_by_name", return_value=mocker.MagicMock())
    missing_users = [UserDetail(id="user3", user_name="User 3")]
    mocker.patch("server.services.bulks._get_missing_users", return_value=missing_users)
    mocker.patch("server.services.bulks._get_repo_user_by_id", return_value=None)
    check_results = [
        EachResult(
            id="user1",
            eppn=["eppn1"],
            email=["user1@example.com"],
            user_name="User 1",
            groups={"group1"},
            status="update",
            code=None,
        ),
        EachResult(
            id="user2",
            eppn=["eppn2"],
            email=["user2@example.com"],
            user_name="User 2",
            groups={"group2"},
            status="skip",
            code=None,
        ),
        EachResult(
            id="user3",
            eppn=["eppn3"],
            email=["user3@example.com"],
            user_name="User 3",
            groups={"group1", "group2"},
            status="create",
            code=None,
        ),
    ]
    summary = ResultSummary(create=1, update=1, delete=0, skip=1, error=0)
    mocker.patch(
        "server.services.bulks._build_check_results",
        return_value=(
            check_results,
            summary,
        ),
    )
    mock_history = UploadHistory()
    mock_history.id = uuid7()
    mock_create_upload = mocker.patch(
        "server.services.history_table.create_upload",
        return_value=mock_history,
    )
    validate_summary = ValidateResults(
        items=check_results, summary=summary, missing_users=missing_users, offset=0, page_size=3
    )
    result = bulks.validate_upload_data(operator_id, operator_name, tmp_file_id)
    assert isinstance(result, UUID)
    mock_get_file_by_id.assert_called_once_with(tmp_file_id)
    mock_get_repository_member.assert_called_once_with("repo1")
    mock_create_upload.assert_called_once_with(
        operator_id=operator_id,
        operator_name=operator_name,
        file_id=tmp_file_id,
        results=validate_summary.model_dump(mode="json"),
    )


def test_get_repository_member(map_groups, user_summaries, mocker: MockerFixture):
    map_groups[0].members = [MemberUser(value=user_summaries[USER_ROLES.CONTRIBUTOR].id)]
    map_groups[2].members = [
        MemberUser(value=user_summaries[USER_ROLES.COMMUNITY_ADMIN].id),
        MemberGroup(value="test_lower_group"),
    ]
    map_groups[3].members = [
        MemberUser(value=user_summaries[USER_ROLES.COMMUNITY_ADMIN].id),
        MemberUser(value=user_summaries[USER_ROLES.GENERAL_USER].id),
    ]
    search_result = SearchResponse[MapGroup](
        total_results=len(map_groups), start_index=0, items_per_page=len(map_groups), resources=map_groups
    )
    mock_search = mocker.patch("server.services.groups.search", return_value=search_result)

    repository_id = "test_repo_ac_jp"
    expected_groups = {g.id for g in map_groups}
    expected_users = {u.id for u in list(user_summaries.values())[2:]}

    groups, users = bulks.get_repository_member(repository_id)

    assert groups == expected_groups
    assert users == expected_users
    mock_search.assert_called_once_with(mocker.ANY, raw=True)
    (criteria,), _ = mock_search.call_args
    assert criteria.r == [repository_id]
    assert criteria.l == -1


def test_build_user_from_file(app, mocker: MockerFixture):
    metadata = ["created:", "2026-01-01", "version:", "1.0"]
    header = [
        "id",
        "user_name",
        "groups[].id",
        "groups[].name",
        "role",
        "edu_person_principal_names[]",
        "emails[]",
        "preferred_language",
    ]
    meta = ["readonly", "readonly", "writable", "readonly", "writeble", "readonly", "readonly", "readonly"]
    data1 = [
        "user1",
        "User 1",
        "jc_repo1_gr_test_group1",
        "Group 1",
        "repository_admin",
        "test@eppn",
        "user1@example.com",
        "en",
    ]
    data2 = [
        "user1",
        "User 1",
        "jc_repo1_gr_test_group2",
        "Group 2",
        "community_admin",
        "test@eppn",
        "user1@example.com",
        "en",
    ]
    data3 = ["", "User 2", "jc_repo1_gr_test_group1", "Group 1", "contributor", "test@eppn", "user2@example.com", "ja"]
    data4 = ["", "User 3", "jc_repo1_gr_test_group1", "Group 1", "general_user", "test@eppn", "user3@example.com", "ja"]
    data5 = []
    data6 = ["", "", "jc_repo1_gr_test_group1", "Group 1", "repository_admin", "test@eppn", "user4@example.com", "ja"]
    rows = [metadata, header, meta, data1, data2, data3, data4, data5, data6]
    mock_read_file = mocker.patch("server.services.bulks._read_file", return_value=iter(rows))
    expected_data = {
        "user1": {
            "user_name": ["User 1", "User 1"],
            "groups[].id": ["jc_repo1_gr_test_group1", "jc_repo1_gr_test_group2"],
            "groups[].name": ["Group 1", "Group 2"],
            "role": ["repository_admin", "community_admin"],
            "edu_person_principal_names[]": ["test@eppn", "test@eppn"],
            "emails[]": ["user1@example.com", "user1@example.com"],
            "preferred_language": ["en", "en"],
        }
    }
    expected_new_data = {
        "User 2": {
            "id": [""],
            "groups[].id": ["jc_repo1_gr_test_group1"],
            "groups[].name": ["Group 1"],
            "role": ["contributor"],
            "edu_person_principal_names[]": ["test@eppn"],
            "emails[]": ["user2@example.com"],
            "preferred_language": ["ja"],
        },
        "User 3": {
            "id": [""],
            "groups[].id": ["jc_repo1_gr_test_group1"],
            "groups[].name": ["Group 1"],
            "role": ["general_user"],
            "edu_person_principal_names[]": ["test@eppn"],
            "emails[]": ["user3@example.com"],
            "preferred_language": ["ja"],
        },
    }
    dummy_file_path = "/var/tmp/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    data, new_data = bulks.build_user_from_file(dummy_file_path)
    mock_read_file.assert_called_once_with(dummy_file_path)
    assert data == expected_data
    assert new_data == expected_new_data


def test__read_file(tmp_path):
    file_path = tmp_path / "test_file.csv"
    rows = [
        ["created:", "2026-03-01T03:00:00Z", "version:", "1.0"],
        USER_EXPORT_HEADERS_V1,
    ]
    file_path.write_text("\n".join([",".join(r) for r in rows]), encoding="utf-8")

    iterator = bulks._read_file(str(file_path))

    assert next(iterator) == rows[0]
    assert next(iterator) == rows[1]


def test__read_file_xlsx(tmp_path):
    file_path = tmp_path / "test_file.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws
    rows = [
        ["created:", "2026-03-01T03:00:00Z", "version:", "1.0"],
        USER_EXPORT_HEADERS_V1,
    ]
    for row in rows:
        ws.append(row)
    wb.save(file_path)

    iterator = bulks._read_file(str(file_path))

    assert [_ for _ in next(iterator) if _] == rows[0]
    assert [_ for _ in next(iterator) if _] == rows[1]


def test__read_file_no_ws(app, mocker: MockerFixture, caplog, tmp_path):
    file_path = tmp_path / "test_broken_file.xlsx"
    mock_wb = openpyxl.Workbook()
    mock_wb.save(file_path)
    for sheet in mock_wb.sheetnames:
        del mock_wb[sheet]
    mocker.patch("server.services.bulks.openpyxl.load_workbook", return_value=mock_wb)

    iterator = bulks._read_file(str(file_path))
    with pytest.raises(FileValidationError, match=regex(E.INVALID_FILE_STRUCTURE)):
        next(iterator)

    assert_message(caplog.records[0], E.FILE_NOT_ACTIVE_SHEET, {"path": file_path})


def test__read_file_non_exist(tmp_path):
    file_path = tmp_path / "test_file.csv"

    iterator = bulks._read_file(str(file_path))
    with pytest.raises(FileNotFound, match=regex(E.FILE_EXPIRED)):
        next(iterator)


def test__read_file_unsupported(tmp_path):
    file_path = tmp_path / "test_unsupported.txt"
    rows = [
        ["created:", "2026-03-01T03:00:00Z", "version:", "1.0"],
        USER_EXPORT_HEADERS_V1,
    ]
    file_path.write_text("\n".join([",".join(r) for r in rows]), encoding="utf-8")

    result = bulks._read_file(file_path)
    with pytest.raises(FileFormatError, match=regex(E.FILE_FORMAT_UNSUPPORTED)):
        next(result)


def test_build_user_detail_from_dict():
    data = {
        "user1": {
            "user_name": ["User 1", "User 1"],
            "groups[].id": ["jc_repo1_gr_test_group1", "jc_repo1_gr_test_group2", "jc_repo1_gr_test_group3"],
            "groups[].name": ["Group 1", "Group 2"],
            "role": ["repository_admin"],
            "edu_person_principal_names[]": ["test@eppn", "test@eppn"],
            "emails[]": ["user1@example.com", "user1@example.com"],
            "preferred_language": ["en", "en"],
        },
        "user2": {
            "user_name": ["User 2", "User 2"],
            "groups[].id": ["jc_repo1_gr_test_group1"],
            "groups[].name": ["Group 1", "Group 2"],
            "role": ["contributor"],
            "edu_person_principal_names[]": ["test@eppn", "test@eppn"],
            "emails[]": ["user2@example.com", "user2@example.com"],
            "preferred_language": ["ja", "ja"],
        },
        "": {
            "user_name": [""],
            "groups[].id": [""],
            "groups[].name": [""],
            "role": ["contributor"],
            "edu_person_principal_names[]": [""],
            "emails[]": [""],
            "preferred_language": [""],
        },
    }
    expected = UserAggregated(
        root=[
            UserDetail(
                id="user1",
                user_name="User 1",
                groups=[
                    GroupSummary(id="jc_repo1_gr_test_group1", display_name="Group 1"),
                    GroupSummary(id="jc_repo1_gr_test_group2", display_name="Group 2"),
                    GroupSummary(id="jc_repo1_gr_test_group3"),
                ],
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                repository_roles=[RepositoryRole(id="repo1", service_name=None, user_role=USER_ROLES.REPOSITORY_ADMIN)],
            ),
            UserDetail(
                id="user2",
                user_name="User 2",
                groups=[
                    GroupSummary(id="jc_repo1_gr_test_group1", display_name="Group 1"),
                ],
                eppns=["test@eppn"],
                emails=["user2@example.com"],
                preferred_language="ja",
                repository_roles=[RepositoryRole(id="repo1", service_name=None, user_role=USER_ROLES.CONTRIBUTOR)],
            ),
        ]
    )
    repository_id = "repo1"
    assert bulks.build_user_detail_from_dict(data, repository_id) == expected


def test_build_user_detail_from_dict_by_name():
    data = {
        "User 2": {
            "id": [""],
            "groups[].id": ["jc_repo1_gr_test_group1"],
            "groups[].name": ["Group 1"],
            "role": ["repository_admin"],
            "edu_person_principal_names[]": ["test@eppn"],
            "emails[]": ["user2@example.com"],
            "preferred_language": ["ja"],
        },
        "User 3": {
            "id": [""],
            "groups[].id": ["jc_repo1_gr_test_group1"],
            "groups[].name": ["Group 1", ""],
            "role": ["contributor"],
            "edu_person_principal_names[]": ["test@eppn"],
            "emails[]": ["user3@example.com"],
            "preferred_language": ["ja"],
        },
        "": {
            "id": [""],
            "groups[].id": [""],
            "groups[].name": [""],
            "role": ["contributor"],
            "edu_person_principal_names[]": [""],
            "emails[]": [""],
            "preferred_language": [""],
        },
    }
    expected = UserAggregated(
        root=[
            UserDetail(
                user_name="User 2",
                groups=[
                    GroupSummary(id="jc_repo1_gr_test_group1", display_name="Group 1"),
                ],
                eppns=["test@eppn"],
                emails=["user2@example.com"],
                preferred_language="ja",
                repository_roles=[RepositoryRole(id="repo1", service_name=None, user_role=USER_ROLES.REPOSITORY_ADMIN)],
            ),
            UserDetail(
                user_name="User 3",
                groups=[
                    GroupSummary(id="jc_repo1_gr_test_group1", display_name="Group 1"),
                ],
                preferred_language="ja",
                eppns=["test@eppn"],
                emails=["user3@example.com"],
                repository_roles=[RepositoryRole(id="repo1", service_name=None, user_role=USER_ROLES.CONTRIBUTOR)],
            ),
        ]
    )
    repository_id = "repo1"
    assert bulks.build_user_detail_from_dict_by_name(data, repository_id) == expected


def test__get_missing_users(group_summaries, map_users, user_details, mocker: MockerFixture):
    groups = {g.id for g in group_summaries[:2]}
    users = {u.id for u in list(map_users.values())[-3:]}
    members = (groups, users)
    included_users = {u.id for u in list(map_users.values())[-3:-1]}

    search_response = SearchResponse[MapUser](
        total_results=1,
        start_index=0,
        items_per_page=20,
        resources=list(map_users.values())[-1:],
    )
    mock_search = mocker.patch("server.services.users.search", return_value=search_response)
    mocker.patch("server.services.utils.transformers.make_user_detail", side_effect=list(user_details.values())[-1:])

    result = bulks._get_missing_users(_RepositoryMember(*members), included_users)

    assert result == list(user_details.values())[-1:]
    mock_search.assert_called_once_with(mocker.ANY, raw=True)
    (criteria,), _ = mock_search.call_args
    assert criteria.i == [list(users)[-1]]
    assert criteria.l == -1


def test__get_missing_users_no_missing(group_summaries, map_users, mocker: MockerFixture):
    groups = {g.id for g in group_summaries[:2]}
    users = {u.id for u in list(map_users.values())[-2:]}
    members = (groups, users)
    included_users = users

    mock_search = mocker.patch("server.services.users.search")

    result = bulks._get_missing_users(_RepositoryMember(*members), included_users)

    assert result == []
    mock_search.assert_not_called()


def test__get_repo_user_by_id(group_summaries, map_users, user_details, mocker: MockerFixture):
    groups = {g.id for g in group_summaries[:2]}
    users = {u.id for u in list(map_users.values())[-2:]}
    members = (groups, users)
    included_users = users

    search_response = SearchResponse[MapUser](
        total_results=1,
        start_index=0,
        items_per_page=20,
        resources=list(map_users.values())[-2:],
    )
    mock_search = mocker.patch("server.services.users.search", return_value=search_response)
    mocker.patch("server.services.utils.transformers.make_user_detail", side_effect=list(user_details.values())[-2:])

    result = bulks._get_repo_user_by_id(_RepositoryMember(*members), included_users)

    assert result == {u.id: u for u in list(user_details.values())[-2:]}
    mock_search.assert_called_once_with(mocker.ANY, raw=True)
    (criteria,), _ = mock_search.call_args
    assert criteria.i == list(users)
    assert criteria.l == -1


def test__get_repo_user_by_id_no_user(group_summaries, map_users, mocker: MockerFixture):
    groups = {g.id for g in group_summaries[:2]}
    users = {u.id for u in list(map_users.values())[-2:]}
    members = (groups, users)
    included_users = {u.id for u in list(map_users.values())[:2]}

    mock_search = mocker.patch("server.services.users.search")

    result = bulks._get_repo_user_by_id(_RepositoryMember(*members), included_users)

    assert result == {}
    mock_search.assert_not_called()


def test__build_check_results(app, mocker: MockerFixture):
    mocker.patch("server.services.bulks._check_immutable_attributes", return_value=None)
    update_user = [
        UserDetail(
            user_name="User 1",
            eppns=["test@eppn"],
            emails=["user1@example.com"],
            groups=[
                GroupSummary(id="group1", display_name="Group 1"),
            ],
        ),
        UserDetail(
            id="user2",
            user_name="User 2",
            eppns=["test@eppn"],
            emails=["user2@example.com"],
            groups=[GroupSummary(id="group1", display_name="Group 1")],
        ),
        UserDetail(id="user3", user_name="User 3", eppns=["test@eppn"], emails=["user3@example.com"]),
        UserDetail(id="not_repo_user", user_name="User 1", eppns=["test@eppn"], emails=["user1@example.com"]),
    ]
    create_user = [
        UserDetail(
            id="user4",
            user_name="User 4",
            eppns=["test@eppn"],
            emails=["user4@example.com"],
            groups=[
                GroupSummary(id="group4", display_name="Group 4"),
            ],
        ),
        UserDetail(id="user5", user_name="User 5", eppns=["test@eppn"], emails=["user5@example.com"]),
    ]
    repository_member = _RepositoryMember(groups={"group1", "group2"}, users={"user1", "user2", "user3"})
    repo_user_by_id = {
        "user1": UserDetail(id="user1", user_name="User 1", eppns=["test@eppn"], emails=["user1@example.com"]),
        "user2": UserDetail(
            id="user2",
            user_name="User 2",
            eppns=["test@eppn"],
            emails=["user2@example.com"],
            groups=[GroupSummary(id="group2", display_name="Group 2")],
        ),
        "user3": UserDetail(id="user3", user_name="User 3", eppns=["test@eppn"], emails=["user3@example.com"]),
    }
    expected_check_results = [
        EachResult(
            id="user4",
            eppn=["test@eppn"],
            email=["user4@example.com"],
            user_name="User 4",
            groups={"group4"},
            status="error",
            code="Group ID does not exist",
        ),
        EachResult(
            id="user5",
            eppn=["test@eppn"],
            email=["user5@example.com"],
            user_name="User 5",
            groups=set(),
            status="create",
        ),
        EachResult(
            id="user2",
            eppn=["test@eppn"],
            email=["user2@example.com"],
            user_name="User 2",
            groups={"group1"},
            status="update",
        ),
        EachResult(
            id="user3",
            eppn=["test@eppn"],
            email=["user3@example.com"],
            user_name="User 3",
            groups=set(),
            status="skip",
        ),
    ]
    expected_summary = ResultSummary(create=1, update=1, delete=0, skip=1, error=1)
    mocker.patch("server.services.bulks.validate_user_to_map_user", return_value=MapUser())
    result = bulks._build_check_results(update_user, create_user, repository_member, repo_user_by_id)
    assert result == (expected_check_results, expected_summary)


def test__build_check_results_invalid_form(app, mocker: MockerFixture):
    update_user = []
    create_user = [
        UserDetail(user_name="User 1"),
    ]
    repository_member = _RepositoryMember(groups={"group1", "group2"}, users={"user1", "user2"})
    repo_user_by_id = {
        "user1": UserDetail(id="user1", user_name="User 1", eppns=["test@eppn"], emails=["user1@example.com"]),
        "user2": UserDetail(
            id="user2",
            user_name="User 2",
            eppns=["test@eppn"],
            emails=["user2@example.com"],
            groups=[GroupSummary(id="group2", display_name="Group 2")],
        ),
    }
    expected_check_results = [
        EachResult(
            id=None,
            eppn=[],
            email=[],
            user_name="User 1",
            groups=set(),
            status="error",
            code=E.USER_REQUIRES_EPPN.code,  # pyright: ignore[reportAttributeAccessIssue]
            message=E.USER_REQUIRES_EPPN.data,  # pyright: ignore[reportAttributeAccessIssue]
        ),
    ]
    expected_summary = ResultSummary(create=0, update=0, delete=0, skip=0, error=1)
    mocker.patch("server.services.bulks.validate_user_to_map_user", side_effect=InvalidFormError(E.USER_REQUIRES_EPPN))
    result = bulks._build_check_results(update_user, create_user, repository_member, repo_user_by_id)
    assert result == (expected_check_results, expected_summary)


@pytest.mark.parametrize(
    ("user_detail", "expected"),
    [
        (
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
            ),
            False,
        ),
        (
            UserDetail(
                id="invalid@id",
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
            ),
            False,
        ),
        (
            UserDetail(
                id="user1",
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
            ),
            True,
        ),
    ],
)
def test__check_value(app, mocker: MockerFixture, user_detail, expected):
    assert bulks._check_value(user_detail) == expected


@pytest.mark.parametrize(
    ("original", "update_user", "expected"),
    [
        (
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group1", display_name="Group 1")],
            ),
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group2", display_name="Group 2")],
            ),
            None,
        ),
        (
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group1", display_name="Group 1")],
            ),
            UserDetail(
                user_name="User 2",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group2", display_name="Group 2")],
            ),
            "user_name is immutable",
        ),
        (
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group1", display_name="Group 1")],
            ),
            UserDetail(
                user_name="User 1",
                eppns=["test2@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group2", display_name="Group 2")],
            ),
            "eppns are immutable",
        ),
        (
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group1", display_name="Group 1")],
            ),
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user2@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group2", display_name="Group 2")],
            ),
            "emails are immutable",
        ),
        (
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="en",
                groups=[GroupSummary(id="group1", display_name="Group 1")],
            ),
            UserDetail(
                user_name="User 1",
                eppns=["test@eppn"],
                emails=["user1@example.com"],
                preferred_language="ja",
                groups=[GroupSummary(id="group2", display_name="Group 2")],
            ),
            "preferred_language is immutable",
        ),
    ],
)
def test__check_immutable_attributes(app, mocker: MockerFixture, original, update_user, expected):
    assert bulks._check_immutable_attributes(original, update_user) == expected


def test_get_validate_task_result(app, mocker: MockerFixture):
    task_id = uuid7()
    expected = mocker.MagicMock()
    mocker.patch("server.services.bulks.validate_upload_data.AsyncResult", return_value=expected)
    assert bulks.get_validate_task_result(task_id) == expected


def test_get_validate_task_result_none(app, mocker: MockerFixture):
    task_id = uuid7()
    mocker.patch("server.services.bulks.validate_upload_data.AsyncResult", return_value=None)
    expected = E.TASK_NOT_FOUND % {"task_id": task_id}
    with pytest.raises(TaskExecutionError) as exc:
        bulks.get_validate_task_result(task_id)
    assert str(exc.value) == str(expected)


def test_get_validate_task_result_with_exception(app, mocker: MockerFixture):
    task_id = uuid7()
    expected_exception = RedisConnectionError("Failed to connect to Redis")
    mocker.patch("server.services.bulks.validate_upload_data.AsyncResult", side_effect=expected_exception)
    with pytest.raises(DatastoreError) as exc:
        bulks.get_validate_task_result(task_id)
    assert str(exc.value) == str(E.FAILED_CONNECT_REDIS % {"error": str(expected_exception)})


def test_get_validate_result(app, mocker: MockerFixture):
    result = [
        {
            "id": "user1",
            "eppn": ["test@eppn"],
            "email": ["user1@example.com"],
            "user_name": "User 1",
            "groups": [],
            "status": "create",
            "code": None,
        }
    ]
    mocker.patch("server.services.history_table.get_paginated_upload_results", return_value=result)
    summary = ResultSummary(create=1, update=0, delete=0, skip=0, error=0)
    missing_user = []
    mocker.patch("server.services.history_table.get_upload_results", side_effect=[summary, missing_user])
    repository_member = _RepositoryMember(groups={"group1"}, users={"user1"})
    mocker.patch("server.services.bulks.get_repository_member", return_value=repository_member)
    history_id = uuid7()
    status_filter = ["create"]
    offset = 1
    limit = 20
    expected = ValidateResults(
        items=[
            EachResult(
                id="user1",
                eppn=["test@eppn"],
                email=["user1@example.com"],
                user_name="User 1",
                groups=set(),
                status="create",
                code=None,
            )
        ],
        summary=summary,
        missing_users=missing_user,
        offset=offset,
        page_size=limit,
    )
    assert bulks.get_validate_result(history_id, status_filter, offset, limit) == expected


def test_update_users_success(app, mocker):
    history_id = uuid7()
    tmp_file_id = uuid7()

    check_results = [
        EachResult(id="user1", eppn=[], email=[], user_name="User 1", groups=set(), status="create", code=None)
    ]
    upload_data = mocker.MagicMock(spec=UploadHistory)
    upload_data.file.file_content = {"repositories": [{"id": "repo1"}]}
    upload_data.results = {
        "results": check_results,
        "summary": {"error": 0},
    }
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=upload_data)

    mocker.patch("server.services.bulks._build_bulk_operations_from_check_results", return_value=(["bulk_op"], 0))
    mocker.patch("server.services.bulks.save_file", return_value="file_id")
    mock_update_status = mocker.patch("server.services.history_table.update_upload_status")
    mocker.patch("server.services.history_table.delete_file_by_id")
    mocker.patch("server.services.bulks.get_access_token", return_value="token")
    mocker.patch("server.services.bulks.get_client_secret", return_value="secret")
    mocker.patch(
        "server.services.bulks.bulks.post",
        return_value=BulkResponse(operations=[BulkOperation(method="POST", path="/Users/user1", status="201")]),
    )

    result = bulks.update_users(history_id, tmp_file_id, remove_users=None)

    assert result == history_id
    mock_update_status.assert_any_call(
        history_id=history_id,
        status="P",
        file_id="file_id",
        new_results={"results": check_results, "summary": {"error": 0, "delete": 0}},
    )
    mock_update_status.assert_any_call(
        history_id=history_id,
        status="S",
    )


def test_update_users_history_not_found(app, mocker):
    history_id = uuid7()
    tmp_file_id = uuid7()
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=None)
    with pytest.raises(RecordNotFound) as exc:
        bulks.update_users(history_id, tmp_file_id, remove_users=None)
    assert str(exc.value) == str(E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id})


def test_update_users_error_in_summary(app, mocker):
    history_id = uuid7()
    tmp_file_id = uuid7()
    upload_data = mocker.MagicMock()
    upload_data.file.file_content = {"repositories": [{"id": "repo1"}]}
    upload_data.results = {"results": [], "summary": {"error": 1}}
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=upload_data)
    with pytest.raises(FileValidationError) as exc:
        bulks.update_users(history_id, tmp_file_id, remove_users=None)
    assert str(exc.value) == str(E.VALIDATION_ERROR_BLOCK)


def test_update_users_bulk_oauth_token_error(app, mocker):
    history_id = uuid7()
    tmp_file_id = uuid7()
    check_results = [
        EachResult(id="user1", eppn=[], email=[], user_name="User 1", groups=set(), status="create", code=None)
    ]
    summary = {"error": 0}
    upload_data = mocker.MagicMock()
    upload_data.file.file_content = {"repositories": [{"id": "repo1"}]}
    upload_data.results = {"results": check_results, "summary": summary}
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=upload_data)
    mocker.patch("server.services.bulks._build_bulk_operations_from_check_results", return_value=(["bulk_op"], 0))
    mocker.patch("server.services.bulks.save_file", return_value="file_id")
    mocker.patch("server.services.history_table.update_upload_status", return_value=None)
    mocker.patch("server.services.history_table.delete_file_by_id")
    expected_error_message = "OAuth tokens are not stored on the server."
    mocker.patch("server.services.bulks.get_access_token", side_effect=OAuthTokenError(expected_error_message))
    with pytest.raises(OAuthTokenError) as exc:
        bulks.update_users(history_id, tmp_file_id, remove_users=None)
    assert str(exc.value) == expected_error_message


def test_update_users_map_error(app, mocker):
    history_id = uuid7()
    tmp_file_id = uuid7()
    check_results = [
        EachResult(id="user1", eppn=[], email=[], user_name="User 1", groups=set(), status="create", code=None)
    ]
    summary = {"error": 0}
    upload_data = mocker.MagicMock()
    upload_data.file.file_content = {"repositories": [{"id": "repo1"}]}
    upload_data.results = {"results": check_results, "summary": summary}
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=upload_data)
    mocker.patch("server.services.bulks._build_bulk_operations_from_check_results", return_value=(["bulk_op"], 0))
    mocker.patch("server.services.bulks.save_file", return_value="file_id")
    mocker.patch("server.services.history_table.update_upload_status")
    mocker.patch("server.services.history_table.delete_file_by_id")
    mocker.patch("server.services.bulks.get_access_token", return_value="token")
    mocker.patch("server.services.bulks.get_client_secret", return_value="secret")
    mocker.patch(
        "server.services.bulks.bulks.post",
        return_value=MapError(status="400", scim_type="invalidValue", detail="error"),
    )
    with pytest.raises(UnexpectedResponseError):
        bulks.update_users(history_id, tmp_file_id, remove_users=None)


def test_update_users_failed(app, mocker):
    history_id = uuid7()
    tmp_file_id = uuid7()
    check_results = [
        EachResult(id="user1", eppn=[], email=[], user_name="User 1", groups=set(), status="create", code=None),
        EachResult(id="user2", eppn=[], email=[], user_name="User 2", groups=set(), status="update", code=None),
    ]
    summary = {"error": 0}
    upload_data = mocker.MagicMock()
    upload_data.file.file_content = {"repositories": [{"id": "repo1"}]}
    upload_data.results = {"results": check_results, "summary": summary}
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=upload_data)
    mocker.patch("server.services.bulks._build_bulk_operations_from_check_results", return_value=(["bulk_op"], 0))
    mocker.patch("server.services.bulks.save_file", return_value="file_id")
    mocker.patch("server.services.history_table.update_upload_status")
    mocker.patch("server.services.history_table.delete_file_by_id")
    mocker.patch("server.services.bulks.get_access_token", return_value="token")
    mocker.patch("server.services.bulks.get_client_secret", return_value="secret")
    mocker.patch(
        "server.services.bulks.bulks.post",
        return_value=BulkResponse(
            operations=[
                BulkOperation(method="POST", path="/Users/user1", status="201"),
                BulkOperation(method="POST", path="/Groups/group1", status="500"),
            ]
        ),
    )

    result = bulks.update_users(history_id, tmp_file_id, remove_users=None)

    assert result == history_id


def test_save_file_as_permanent(config, mocker: MockerFixture, tmp_path):
    tmp_file_id = uuid7()

    tmp_file = tmp_path / "test_file.csv"
    tmp_file.touch()

    mock_file_record = mocker.MagicMock(spec=Files)
    mock_file_record.file_content = _FileContent(
        repositories=[{"id": "repo1", "serviceName": "test_service"}],
        groups=[{"id": "group1", "displayName": "Group 1"}, {"id": "group2", "displayName": "Group 2"}],
        users=[{"id": "user1", "userName": "User 1"}, {"id": "user2", "userName": "User 2"}],
    )
    mock_file_record.file_path = str(tmp_file)
    mock_get_file = mocker.patch("server.services.history_table.get_file_by_id", return_value=mock_file_record)

    mock_create = mocker.patch(
        "server.services.history_table.create_file_record",
        side_effect=lambda _, __, file_id: mocker.MagicMock(spec=Files, id=file_id),
    )
    expected_save_dir = Path(config.STORAGE.local.storage) / datetime.now(UTC).strftime("%Y/%m")

    mock_delete = mocker.patch("server.services.history_table.delete_file_by_id")

    created_id = bulks.save_file_as_permanent(tmp_file_id)

    mock_get_file.assert_called_once_with(tmp_file_id)
    (saved_path, _), kwargs = mock_create.call_args
    assert saved_path == str(expected_save_dir / f"{created_id}.csv")
    assert created_id == kwargs["file_id"]
    mock_delete.assert_called_once_with(tmp_file_id)
    assert not tmp_file.exists()
    assert (expected_save_dir / f"{created_id}.csv").exists()


def test_save_file_with_exception(app, mocker: MockerFixture):
    file_id = uuid7()
    file_content = _FileContent(
        repositories=[{}],
        groups=[{"id": "group1", "displayName": "Group 1"}, {"id": "group2", "displayName": "Group 2"}],
        users=[{"id": "user1", "userName": "User 1"}, {"id": "user2", "userName": "User 2"}],
    )
    mocker.patch(
        "server.services.history_table.get_file_by_id", return_value=mocker.MagicMock(file_content=file_content)
    )
    with pytest.raises(FileNotFound) as exc:
        bulks.save_file_as_permanent(file_id)
    assert str(exc.value) is not None


def test_save_file_not_found(app, mocker: MockerFixture):
    file_content = _FileContent(
        repositories=[{"id": "repo1", "serviceName": "test_service"}],
        groups=[{"id": "group1", "displayName": "Group 1"}, {"id": "group2", "displayName": "Group 2"}],
        users=[{"id": "user1", "userName": "User 1"}, {"id": "user2", "userName": "User 2"}],
    )
    file_path = "/var/tmp/jcgroups/test_file.csv"  # ruff: ignore[hardcoded-temp-file]
    mock_get_file_by_id = mocker.patch(
        "server.services.history_table.get_file_by_id",
        return_value=mocker.MagicMock(file_content=file_content, file_path=file_path),
    )
    mocker.patch("server.services.history_table.create_file", return_value=None)
    file_id = uuid7()
    with pytest.raises(FileNotFound) as exc:
        bulks.save_file_as_permanent(file_id)
    mock_get_file_by_id.assert_called_once_with(file_id)
    assert str(exc.value) == str(E.FILE_EXPIRED % {"path": file_path})


def test_save_file_invalid_suffix(app, mocker: MockerFixture):
    file_content = _FileContent(
        repositories=[{"id": "repo1", "serviceName": "test_service"}],
        groups=[{"id": "group1", "displayName": "Group 1"}, {"id": "group2", "displayName": "Group 2"}],
        users=[{"id": "user1", "userName": "User 1"}, {"id": "user2", "userName": "User 2"}],
    )
    file_path = "/var/tmp/jcgroups/test_file.css"  # ruff: ignore[hardcoded-temp-file]
    mock_get_file_by_id = mocker.patch(
        "server.services.history_table.get_file_by_id",
        return_value=mocker.MagicMock(file_content=file_content, file_path=file_path),
    )
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("server.services.history_table.create_file", return_value=None)
    file_id = uuid7()
    with pytest.raises(FileFormatError) as exc:
        bulks.save_file_as_permanent(file_id)
    mock_get_file_by_id.assert_called_once_with(file_id)
    assert str(exc.value) == str(E.FILE_FORMAT_UNSUPPORTED % {"suffix": Path(file_path).suffix})


def test_build_map_user_from_check_result(app, mocker: MockerFixture):
    check_result = EachResult(
        id="user1",
        eppn=["test@eppn"],
        email=["test@example.com"],
        user_name="User 1",
        groups={"group1", "group2"},
        status="create",
        code=None,
    )
    expected = MapUser(
        id="user1",
        user_name="User 1",
        edu_person_principal_names=[EPPN(value="test@eppn")],
        emails=[Email(value="test@example.com")],
        groups=[Group(value="group1"), Group(value="group2")],
    )
    result = bulks.build_map_user_from_check_result(check_result)
    assert result.id == expected.id
    assert result.user_name == expected.user_name
    assert_unordered_model_list_equal(result.edu_person_principal_names, expected.edu_person_principal_names)
    assert_unordered_model_list_equal(result.emails, expected.emails)
    assert_unordered_model_list_equal(result.groups, expected.groups)


def test_build_remove_user_path(app, mocker: MockerFixture):
    user = UserDetail(id="user1", user_name="User 1", eppns=["test@eppn"], emails=["test@example.com"])
    repository_id = "repo1"
    expected = BulkOperation(
        method="PATCH",
        bulk_id=None,
        path="Users/user1",
        data=RemoveOperation(path="groups[(value eq 'jc_repo1_gr_group1')]"),
        location=None,
        response=None,
        status=None,
    )
    mocker.patch(
        "server.services.utils.detect_affiliations",
        return_value=Affiliations(
            roles=[],
            groups=[_Group(repository_id=repository_id, group_id="jc_repo1_gr_group1", user_defined_id="group1")],
        ),
    )
    result = bulks.build_remove_user_path(user, repository_id)
    assert result == expected


def test__build_bulk_operations_from_check_results(app, mocker: MockerFixture):
    repository_id = "repo1"
    check_results = [
        EachResult(
            id="user1",
            eppn=["test@eppn"],
            email=["test@example.com"],
            user_name="User 1",
            groups={"group1", "group2"},
            status="create",
            code=None,
        ),
        EachResult(
            id="user2",
            eppn=["test@eppn"],
            email=["test2@example.com"],
            user_name="User 2",
            groups={"group1", "group2"},
            status="update",
            code=None,
        ),
        EachResult(
            id="user3",
            eppn=["test@eppn"],
            email=["test3@example.com"],
            user_name="User 3",
            groups={"group1", "group2"},
            status="update",
            code=None,
        ),
    ]
    remove_users = ["user1"]
    expected = (
        [
            BulkOperation(
                method="POST",
                path="/Users",
                data=MapUser(
                    id="user1",
                    user_name="User 1",
                    edu_person_principal_names=[EPPN(value="test@eppn")],
                    emails=[Email(value="test@example.com")],
                    groups=[Group(value="group2"), Group(value="group1")],
                ),
            ),
            BulkOperation(
                method="POST",
                path="/Users",
                data=MapUser(
                    id="user1",
                    user_name="User 1",
                    edu_person_principal_names=[EPPN(value="test@eppn")],
                    emails=[Email(value="test@example.com")],
                    groups=[Group(value="group2"), Group(value="group1")],
                ),
            ),
        ],
        1,
    )
    mocker.patch(
        "server.services.bulks.get_repository_member",
        return_value=_RepositoryMember(groups={"group1", "group2"}, users={"user1"}),
    )
    mocker.patch(
        "server.services.bulks._get_repo_user_by_id",
        return_value={
            "user2": UserDetail(
                id="user2",
                user_name="User 2",
                eppns=["test@eppn"],
                emails=["test@example.com"],
                groups=[GroupSummary(id="group3")],
            ),
        },
    )
    mocker.patch("server.services.bulks._build_groups_update_bulk_operations", return_value=[])
    mocker.patch(
        "server.services.users.search",
        return_value=SearchResponse[MapUser](
            total_results=0,
            start_index=0,
            items_per_page=20,
            resources=[
                MapUser(
                    id="user3",
                    user_name="User 3",
                    edu_person_principal_names=[EPPN(value="test@eppn")],
                    emails=[Email(value="test3@example.com")],
                ),
                MapUser(
                    user_name="User 4",
                    edu_person_principal_names=[EPPN(value="test@eppn")],
                    emails=[Email(value="test4@example.com")],
                ),
            ],
        ),
    )
    mocker.patch(
        "server.services.utils.detect_affiliations",
        return_value=Affiliations(
            roles=[],
            groups=[_Group(repository_id=repository_id, group_id="jc_repo1_gr_group1", user_defined_id="group1")],
        ),
    )
    result = bulks._build_bulk_operations_from_check_results(repository_id, check_results, remove_users)
    assert len(result[0]) == len(expected[0])
    for r, e in zip(result[0], expected[0], strict=False):
        assert r.method == e.method
        assert r.path == e.path
        assert isinstance(r.data, MapUser)
        assert isinstance(e.data, MapUser)
        assert r.data.id == e.data.id
        assert r.data.user_name == e.data.user_name
        assert_unordered_model_list_equal(r.data.edu_person_principal_names, e.data.edu_person_principal_names)
        assert_unordered_model_list_equal(r.data.emails, e.data.emails)
        assert_unordered_model_list_equal(r.data.groups, e.data.groups)
    assert result[1] == expected[1]


def test__build_groups_update_bulk_operations(app, mocker: MockerFixture):
    mocker.patch("server.services.users.get_system_admins", return_value={"admin1"})
    mocker.patch(
        "server.services.groups.get_by_id",
        return_value=MapGroup(
            id="jc_repo1_gr_group1",
            display_name="Group 1",
            members=[MemberUser(value="user1"), MemberUser(value="user2"), MemberGroup(value="group1")],
        ),
    )
    bulks._build_groups_update_bulk_operations({"group1": {"add": {"user1"}, "remove": {"user2", "user3"}}})


def test__build_groups_update_bulk_operations_no_group(app, mocker: MockerFixture):
    mocker.patch("server.services.users.get_system_admins", return_value={"admin1"})
    mocker.patch("server.services.groups.get_by_id", side_effect=None)
    result = bulks._build_groups_update_bulk_operations({"group1": {"add": set(), "remove": set()}})
    assert result == [
        BulkOperation(
            method="PATCH",
            path="Groups/group1",
            data=AddOperation(op="add", path="members", value={"type": "User", "value": "admin1"}),
        )
    ]


def test_get_execute_task_result(app, mocker: MockerFixture):
    task_id = uuid7()
    expected = mocker.MagicMock()
    mocker.patch("server.services.bulks.update_users.AsyncResult", return_value=expected)
    assert bulks.get_execute_task_result(task_id) == expected


def test_get_execute_task_result_none(app, mocker: MockerFixture):
    task_id = uuid7()
    mocker.patch("server.services.bulks.update_users.AsyncResult", return_value=None)
    expected = E.TASK_NOT_FOUND % {"task_id": task_id}
    with pytest.raises(TaskExecutionError) as exc:
        bulks.get_execute_task_result(task_id)
    assert str(exc.value) == str(expected)


def test_get_execute_task_result_with_exception(app, mocker: MockerFixture):
    task_id = uuid7()
    expected_exception = RedisConnectionError("Failed to connect to Redis")
    mocker.patch("server.services.bulks.update_users.AsyncResult", side_effect=expected_exception)
    with pytest.raises(DatastoreError) as exc:
        bulks.get_execute_task_result(task_id)
    assert str(exc.value) == str(E.FAILED_CONNECT_REDIS % {"error": str(expected_exception)})


def test_get_upload_result(app, mocker: MockerFixture):
    history_id = uuid7()
    status_filter = ["create"]
    offset = 0
    size = 10
    file_id = uuid7()
    file_name = "test_file.csv"
    operator = "test_operator"
    start_timestamp = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    items = [
        EachResult(
            id="user1",
            eppn=["test@eppn"],
            email=["test@example.com"],
            user_name="User 1",
            groups={"group1"},
            status="create",
            code=None,
        )
    ]
    mock_file = mocker.MagicMock(file_path="var/tmp/test_file.csv")
    upload = mocker.MagicMock(
        file_id=file_id, file=mock_file, operator_name=operator, timestamp=start_timestamp, end_timestamp=None
    )
    raw_results = [i.model_dump() for i in items]
    summary = ResultSummary(create=1, update=1, delete=0, skip=0, error=0)
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=upload)
    mocker.patch("server.services.history_table.get_paginated_upload_results", return_value=raw_results)
    mocker.patch("server.services.history_table.get_upload_results", return_value=summary)

    result = bulks.get_upload_result(history_id, status_filter, offset, size)

    expected = ExecuteResults(
        items=items,
        summary=summary,
        file_id=file_id,
        file_name=file_name,
        operator=operator,
        start_timestamp=start_timestamp,
        total=0,
        offset=offset,
        page_size=size,
    )
    assert result == expected


def test_get_upload_result_history_not_found(app, mocker: MockerFixture):
    history_id = uuid7()
    expected = E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": history_id}
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=None)
    with pytest.raises(RecordNotFound) as exc:
        bulks.get_upload_result(history_id, status_filter=["create"], offset=1, size=20)
    assert str(exc.value) == str(expected)


@pytest.mark.parametrize(
    ("file_path", "file_exist"),
    [
        ("/var/tmp/test_file.csv", True),  # ruff: ignore[hardcoded-temp-file]
        ("/var/tmp/test_file.csv", False),  # ruff: ignore[hardcoded-temp-file]
    ],
)
def test_delete_temporary_file(app, mocker: MockerFixture, file_path, file_exist):
    file_id = uuid7()
    mocker.patch("server.services.history_table.get_file_by_id", return_value=mocker.MagicMock(file_path=file_path))
    mocker.patch("pathlib.Path.exists", return_value=file_exist)
    mocker.patch("pathlib.Path.unlink")
    mocker.patch("server.services.history_table.delete_file_by_id")
    bulks.delete_temporary_file(file_id)


def test_delete_temporary_file_with_exception(app, mocker: MockerFixture):
    file_id = uuid7()
    mocker.patch("server.services.history_table.get_file_by_id", side_effect=RecordNotFound(""))
    assert bulks.delete_temporary_file(file_id) is None


def test_chack_permission_to_operation(app, mocker: MockerFixture):
    mock_upload_record = UploadHistory()
    mock_upload_record.operator_id = "user1"
    history_id = uuid7()
    mock_get_upload = mocker.patch("server.services.history_table.get_upload_by_id", return_value=mock_upload_record)
    assert bulks.chack_permission_to_operation(history_id, "user1") is True
    mock_get_upload.assert_called_once_with(history_id)


def test_chack_permission_to_operation_no_history(app, mocker: MockerFixture):
    history_id = uuid7()
    expected = E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": history_id}
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=None)
    with pytest.raises(RecordNotFound) as exc:
        bulks.chack_permission_to_operation(history_id, "user1")
    assert str(exc.value) == str(expected)


def test_chack_permission_to_view(app, mocker: MockerFixture):
    history_id = uuid7()
    mock_upload_record = mocker.MagicMock()
    mock_upload_record.file.file_content["repositories"][0]["id"] = "repo1"
    mock_upload_record.public = False
    mocker.patch("server.services.bulks.get_permitted_repository_ids", return_value=set())
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=mock_upload_record)
    assert bulks.chack_permission_to_view(history_id) is False


def test_chack_permission_to_view_is_system_admin(app, mocker: MockerFixture):
    history_id = uuid7()
    mocker.patch("server.services.bulks.is_current_user_system_admin", return_value=True)
    assert bulks.chack_permission_to_view(history_id) is True


def test_chack_permission_to_view_history_none(app, mocker: MockerFixture):
    history_id = uuid7()
    mocker.patch("server.services.bulks.get_permitted_repository_ids", return_value=set())
    mocker.patch("server.services.history_table.get_upload_by_id", return_value=None)
    expected = E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": history_id}
    with pytest.raises(RecordNotFound) as exc:
        bulks.chack_permission_to_view(history_id)
    assert str(exc.value) == str(expected)
