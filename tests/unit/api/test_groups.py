import typing as t

from http import HTTPStatus
from types import SimpleNamespace

import server.api.groups

from server.api import groups
from server.api.schemas import (
    DeleteGroupsBody,
    ErrorResponse,
    GroupPatchOperation,
    GroupPatchRequest,
    GroupsQuery,
)
from server.const import USER_ROLES
from server.entities.search_request import FilterOption, SearchResult
from server.exc import InvalidFormError, InvalidQueryError, RequestConflict, ResourceInvalid, ResourceNotFound
from server.messages import E

from tests.helpers import assert_message, unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get(group_details, mocker: MockerFixture):
    total, page_size, offset = len(group_details), len(group_details), 0
    searched = expected = SearchResult(resources=[], total=total, page_size=page_size, offset=offset)
    mock_search = mocker.patch.object(server.api.groups.groups, "search", return_value=searched)
    query = GroupsQuery()

    res, status = unwrap(groups.get)(query)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_search.assert_called_once_with(query)


def test_get_invalid_query_error(mocker: MockerFixture):
    mock_search = mocker.patch.object(server.api.groups.groups, "search")
    mock_search.side_effect = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)
    query = GroupsQuery()

    res, status = unwrap(groups.get)(query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.UNSUPPORTED_SEARCH_FILTER)


def test_post(use_blueprint, app, group_details, mocker: MockerFixture):
    body = expected = group_details[0]
    mock_create = mocker.patch.object(server.api.groups.groups, "create", return_value=expected)

    res, status, headers = unwrap(groups.post)(body)

    assert res == expected
    assert status == HTTPStatus.CREATED
    assert headers["Location"] == f"https://localhost/api/groups/{expected.id}"
    mock_create.assert_called_once_with(body)


def test_post_forbidden(group_details, mocker: MockerFixture):
    body = group_details[0]

    mock_create = mocker.patch.object(server.api.groups.groups, "create")
    mock_create.side_effect = InvalidFormError(E.GROUP_FORBIDDEN_REPOSITORY)

    res, status = unwrap(groups.post)(body)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_FORBIDDEN_REPOSITORY)


def test_post_invalid_form_error(group_details, mocker: MockerFixture):
    body = group_details[0]
    mock_create = mocker.patch.object(server.api.groups.groups, "create")
    mock_create.side_effect = InvalidFormError(E.GROUP_REQUIRES_USER_DEFINED_ID)

    res, status = unwrap(groups.post)(body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_REQUIRES_USER_DEFINED_ID)


def test_post_conflict(group_details, mocker: MockerFixture):
    group = group_details[0]
    mock_create = mocker.patch.object(server.api.groups.groups, "create")
    mock_create.side_effect = ResourceInvalid(E.GROUP_DUPLICATE_ID % {"id": group.id})

    res, status = unwrap(groups.post)(group)

    assert status == HTTPStatus.CONFLICT
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_DUPLICATE_ID, {"id": group.id})


def test_id_get(group_details, mocker: MockerFixture):
    target = expected = group_details[0]
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(target.id,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_get = mocker.patch.object(server.api.groups.groups, "get_by_id", return_value=target)

    result, status = unwrap(groups.id_get)(target.id)

    assert status == HTTPStatus.OK
    assert result == expected
    mock_get.assert_called_once_with(target.id, more_detail=True)


def test_id_get_not_detected(app, mocker: MockerFixture, caplog):
    gid = "unknown-group"
    mock_detect = mocker.patch.object(server.api.groups, "detect_affiliation", return_value=None)

    res, status = unwrap(groups.id_get)(gid)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": gid})
    assert_message(caplog.records[0].message, E.GROUP_UNRECOGNIZED_ID, {"id": gid})
    mock_detect.assert_called_once_with(gid)


def test_id_get_forbidden(app, group_details, mocker: MockerFixture, caplog):
    gid = group_details[0].id
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(gid,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=False)

    res, status = unwrap(groups.id_get)(gid)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_FORBIDDEN, {"id": gid})
    assert_message(caplog.records[0].message, E.GROUP_FORBIDDEN, {"id": gid})


def test_id_get_not_found(app, mocker: MockerFixture, caplog):
    gid = "non-existent-group"
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(gid,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mocker.patch.object(server.api.groups.groups, "get_by_id", return_value=None)

    res, status = unwrap(groups.id_get)(gid)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": gid})
    assert_message(caplog.records[0].message, E.GROUP_NOT_FOUND, {"id": gid})


def test_id_put(group_details, mocker: MockerFixture):
    body = expected = group_details[0]
    gid, body.id = body.id, None
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(gid,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update", return_value=expected)

    res, status = unwrap(groups.id_put)(gid, body)

    assert status == HTTPStatus.OK
    assert res == expected
    assert body.id == gid
    mock_update.assert_called_once_with(body)


def test_id_put_not_detected(app, group_details, mocker: MockerFixture, caplog):
    body = group_details[0]
    gid, body.id = "unknown-group", None
    mock_detect = mocker.patch.object(server.api.groups, "detect_affiliation", return_value=None)

    res, status = unwrap(groups.id_put)(gid, body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": gid})
    assert_message(caplog.records[0].message, E.GROUP_UNRECOGNIZED_ID, {"id": gid})
    mock_detect.assert_called_once_with(gid)


def test_id_put_forbidden(app, group_details, mocker: MockerFixture, caplog):
    body = group_details[0]
    gid, body.id = body.id, None

    mock_permission = mocker.patch.object(server.api.groups, "has_permission", return_value=False)

    result, status = unwrap(groups.id_put)(gid, body)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(result, ErrorResponse)
    assert_message(result.message, E.GROUP_FORBIDDEN, {"id": gid})
    assert_message(caplog.records[0].message, E.GROUP_FORBIDDEN, {"id": gid})
    mock_permission.assert_called_once_with(gid)


def test_id_put_invalid_form_error(group_details, mocker: MockerFixture):
    body = group_details[0]
    gid, body.id = body.id, None
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(gid,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update")
    mock_update.side_effect = InvalidFormError(E.GROUP_REQUIRES_ID)

    res, status = unwrap(groups.id_put)(gid, body)
    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_REQUIRES_ID)


def test_id_put_not_found(group_details, mocker: MockerFixture):
    body = group_details[0]
    gid, body.id = body.id, None
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(gid,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update")
    mock_update.side_effect = ResourceNotFound(E.GROUP_NOT_FOUND % {"id": gid})

    res, status = unwrap(groups.id_put)(gid, body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": gid})


def test_id_patch(group_details, mocker: MockerFixture):
    target = expected = group_details[0]
    ops = [
        GroupPatchOperation(op="add", path="members", value=["user1"]),
        GroupPatchOperation(op="remove", path="members", value=["user2"]),
    ]
    body = GroupPatchRequest(operations=ops)
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(target.id,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update_member", return_value=target)

    res, status = unwrap(groups.id_patch)(target.id, body)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_update.assert_called_once_with(target.id, add={"user1"}, remove={"user2"})


def test_id_patch_unsupported_operation(group_details, mocker: MockerFixture):
    target = expected = group_details[0]
    ops = [SimpleNamespace(op="replace", path="members", value=["user1"])]
    body = SimpleNamespace(operations=ops)
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(target.id,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update_member", return_value=target)

    res, status = unwrap(groups.id_patch)(target.id, body)

    assert status == HTTPStatus.OK
    assert res == expected
    mock_update.assert_called_once_with(target.id, add=set(), remove=set())


def test_id_patch_unsupported_path(app, group_details, mocker: MockerFixture, caplog):
    target = group_details[0]
    ops = [GroupPatchOperation(op="add", path="display_name", value=["user1"])]
    body = GroupPatchRequest(operations=ops)
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(target.id,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)

    res, status = unwrap(groups.id_patch)(target.id, body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_UNSUPPORTED_PATCH_PATH, {"path": "display_name"})
    assert_message(caplog.records[0].message, E.GROUP_UNSUPPORTED_PATCH_PATH, {"path": "display_name"})


def test_id_patch_not_detected(app, mocker: MockerFixture, caplog):
    group_id = "unknown-group"
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=None)
    body = GroupPatchRequest(operations=[])

    res, status = unwrap(groups.id_patch)(group_id, body)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": group_id})
    assert_message(caplog.records[0].message, E.GROUP_UNRECOGNIZED_ID, {"id": group_id})


def test_id_patch_forbidden(app, group_details, mocker: MockerFixture, caplog):
    target = group_details[0]
    body = GroupPatchRequest(operations=[])
    mocker.patch.object(server.api.groups, "has_permission", return_value=False)

    res, status = unwrap(groups.id_patch)(target.id, body)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_FORBIDDEN, {"id": target.id})
    assert_message(caplog.records[0].message, E.GROUP_FORBIDDEN, {"id": target.id})


def test_id_patch_conflict(group_details, mocker: MockerFixture):
    target = group_details[0]
    ops = [
        GroupPatchOperation(op="add", path="members", value=["user1"]),
        GroupPatchOperation(op="remove", path="members", value=["user1"]),
    ]
    body = GroupPatchRequest(operations=ops)
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(target.id,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update_member")
    mock_update.side_effect = RequestConflict(E.CONFLICT_MEMBER_OPERATION % {"id": target.id, "uids": "user1"})

    res, status = unwrap(groups.id_patch)(target.id, body)

    assert status == HTTPStatus.CONFLICT
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.CONFLICT_MEMBER_OPERATION, {"id": target.id, "uids": "user1"})


def test_id_patch_not_found(group_details, mocker: MockerFixture):
    target = group_details[0]
    ops = [GroupPatchOperation(op="add", path="members", value=["user1"])]
    body = GroupPatchRequest(operations=ops)
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=(target.id,))
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_update = mocker.patch.object(server.api.groups.groups, "update_member")
    mock_update.side_effect = ResourceNotFound(E.GROUP_NOT_FOUND % {"id": target.id})

    res, status = unwrap(groups.id_patch)(target.id, body)

    assert isinstance(res, ErrorResponse)
    assert status == HTTPStatus.NOT_FOUND
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": target.id})


def test_id_delete(group_details, mocker: MockerFixture):
    gid = group_details[0].id
    detected = SimpleNamespace(group_id=gid, type="group")
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=detected)
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_delete = mocker.patch.object(server.api.groups.groups, "delete_by_id")

    res, status = unwrap(groups.id_delete)(gid)

    assert status == HTTPStatus.NO_CONTENT
    assert not res
    mock_delete.assert_called_once_with(gid)


def test_id_delete_not_detected(app, mocker: MockerFixture, caplog):
    group_id = "unknown-group"
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=None)

    res, status = unwrap(groups.id_delete)(group_id)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_NOT_FOUND, {"id": group_id})
    assert_message(caplog.records[0].message, E.GROUP_UNRECOGNIZED_ID, {"id": group_id})


def test_id_delete_rolegroup(app, group_details, mocker: MockerFixture, caplog):
    gid = group_details[0].id
    detected = SimpleNamespace(group_id=gid, type="role")
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=detected)

    res, status = unwrap(groups.id_delete)(gid)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.ROLEGROUP_CANNOT_DELETE)
    assert_message(caplog.records[0].message, E.ROLEGROUP_CANNOT_DELETE)


def test_id_delete_forbidden(app, group_details, mocker: MockerFixture, caplog):
    gid = group_details[0].id
    detected = SimpleNamespace(group_id=gid, type="group")
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=detected)
    mocker.patch.object(server.api.groups, "has_permission", return_value=False)

    res, status = unwrap(groups.id_delete)(gid)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_FORBIDDEN, {"id": gid})
    assert_message(caplog.records[0].message, E.GROUP_FORBIDDEN, {"id": gid})


def test_id_delete_not_found(group_details, mocker: MockerFixture):
    gid = group_details[0].id
    detected = SimpleNamespace(group_id=gid, type="group")
    mocker.patch.object(server.api.groups, "detect_affiliation", return_value=detected)
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_delete = mocker.patch.object(server.api.groups.groups, "delete_by_id")
    mock_delete.side_effect = ResourceNotFound(E.GROUP_NOT_FOUND % {"id": gid})

    result, status = unwrap(groups.id_delete)(gid)

    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(result, ErrorResponse)
    assert_message(result.message, E.GROUP_NOT_FOUND, {"id": gid})


def test_delete_post(group_details, mocker: MockerFixture):
    gids = {group_details[0].id, group_details[1].id}
    body = DeleteGroupsBody(group_ids=gids)
    detected = [], [SimpleNamespace(group_id=gid, type="group") for gid in gids]
    mocker.patch.object(server.api.groups, "detect_affiliations", return_value=detected)
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mock_delete = mocker.patch.object(server.api.groups.groups, "delete_multiple", return_value=None)

    res, status = unwrap(groups.delete_post)(body)

    assert status == HTTPStatus.NO_CONTENT
    assert not res
    mock_delete.assert_called_once_with(gids)


def test_delete_post_partial_failure(group_details, mocker: MockerFixture):
    gids = {group_details[0].id, group_details[1].id}
    body = DeleteGroupsBody(group_ids=gids)
    detected = [], [SimpleNamespace(group_id=gid, type="group") for gid in gids]
    mocker.patch.object(server.api.groups, "detect_affiliations", return_value=detected)
    mocker.patch.object(server.api.groups, "has_permission", return_value=True)
    mocker.patch.object(server.api.groups.groups, "delete_multiple", return_value=[group_details[1].id])

    res, status = unwrap(groups.delete_post)(body)

    assert status == HTTPStatus.ACCEPTED
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FAILED_PARTIAL_DELETE_GROUPS, {"ids": group_details[1].id})


def test_delete_post_rolegroup(app, group_details, rolegroup_details, mocker: MockerFixture, caplog):
    gids = [group_details[0].id, rolegroup_details[USER_ROLES.CONTRIBUTOR].id]
    body = DeleteGroupsBody(group_ids=set(gids))
    detected = [(gids[1],)], [(gids[0],)]
    mocker.patch.object(server.api.groups, "detect_affiliations", return_value=detected)

    res, status = unwrap(groups.delete_post)(body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.ROLEGROUP_CANNOT_DELETE)
    assert_message(caplog.records[0].message, E.ROLEGROUP_CANNOT_DELETE)


def test_delete_post_not_detected(app, group_details, mocker: MockerFixture, caplog):
    gids = {group_details[0].id, "unknown-group"}
    body = DeleteGroupsBody(group_ids=gids)
    detected = [], [SimpleNamespace(group_id=group_details[0].id, type="group")]
    mocker.patch.object(server.api.groups, "detect_affiliations", return_value=detected)

    res, status = unwrap(groups.delete_post)(body)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.SOME_GROUP_UNRECOGNIZED, {"ids": "unknown-group"})
    assert_message(caplog.records[0].message, E.SOME_GROUP_UNRECOGNIZED, {"ids": "unknown-group"})


def test_delete_post_forbidden(app, group_details, mocker: MockerFixture, caplog):
    gids = {group_details[0].id, group_details[1].id}
    body = DeleteGroupsBody(group_ids=gids)
    detected = [], [SimpleNamespace(group_id=gid, type="group") for gid in gids]
    mocker.patch.object(server.api.groups, "detect_affiliations", return_value=detected)
    mocker.patch.object(server.api.groups, "has_permission", return_value=False)

    res, status = unwrap(groups.delete_post)(body)

    assert status == HTTPStatus.FORBIDDEN
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.GROUP_FORBIDDEN, {"id": ", ".join(gids)})
    assert_message(caplog.records[0].message, E.GROUP_FORBIDDEN, {"id": ", ".join(gids)})


def test_filter_options(mocker: MockerFixture):
    options = expected = [FilterOption(key="t", description="test opttion", type="string", multiple=False)]
    mock_options = mocker.patch.object(server.api.groups, "search_groups_options", return_value=options)

    res = unwrap(groups.filter_options)()

    assert res == expected
    mock_options.assert_called_once_with()


def test_has_permission(mocker: MockerFixture):
    mocker.patch.object(server.api.groups, "is_current_user_system_admin", return_value=True)

    assert groups.has_permission("test_group_id") is True


def test_has_permission_permitted(mocker: MockerFixture):
    gids = ["test_1_group_id", "test_2_group_id"]
    mocker.patch.object(server.api.groups, "is_current_user_system_admin", return_value=False)
    mocker.patch.object(server.api.groups, "filter_permitted_group_ids", return_value=set(gids))

    assert groups.has_permission(*gids) is True


def test_has_permission_not_permitted(mocker: MockerFixture):
    gids = ["test_1_group_id", "test_2_group_id"]
    mocker.patch.object(server.api.groups, "is_current_user_system_admin", return_value=False)
    mocker.patch.object(server.api.groups, "filter_permitted_group_ids", return_value=set("test_1_group_id"))

    assert groups.has_permission(*gids) is False
