import typing as t

from http import HTTPStatus
from uuid import uuid4

import pytest
import requests

from pydantic_core import ValidationError
from requests import Response

import server.services.core.groups

from server.const import MAP_DUPLICATE_ID_PATTERN, MAP_NOT_FOUND_PATTERN, USER_ROLES
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup
from server.entities.patch_request import ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse, SearchResult
from server.entities.summaries import GroupSummary
from server.exc import (
    InvalidQueryError,
    OAuthTokenError,
    ResourceInvalid,
    ResourceNotFound,
    UnexpectedResponseError,
)
from server.messages import E, I, W
from server.services.core import groups
from server.services.utils.search_queries import GroupsCriteria

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.entities.group_detail import GroupDetail


@pytest.fixture
def token_and_secret(mocker: MockerFixture):
    """Return a tuple of (token, secret) for testing purposes."""
    mock_get_token = mocker.patch.object(server.services.core.groups, "get_access_token", autospec=True)
    mock_get_token.return_value = (access_token := uuid4().hex[:8])
    mock_get_secret = mocker.patch.object(server.services.core.groups, "get_client_secret", autospec=True)
    mock_get_secret.return_value = (client_secret := uuid4().hex[:16])

    return access_token, client_secret


def test_search(repository_summaries, group_summaries, map_groups, token_and_secret, mocker: MockerFixture):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter)
    repository = mocker.MagicMock(display=repository_summaries[0].service_name)

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)

    total, size, index = 1, 1, 1
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    mock_search.return_value = SearchResponse[MapGroup](
        total_results=total, items_per_page=size, start_index=index, resources=map_groups[:1]
    )
    mocker.patch.object(server.services.core.groups, "detect_affiliated_repository", return_value=repository)
    mock_make_summary = mocker.patch.object(
        server.services.core.groups, "make_group_summary", return_value=group_summaries[0]
    )
    expected = SearchResult[GroupSummary](total=total, page_size=size, offset=index, resources=group_summaries[:1])

    result = groups.search(criteria)

    assert result == expected
    mock_search.assert_called_once_with(query, include=mocker.ANY, access_token=token, client_secret=secret)
    mock_make_summary.assert_called_once_with(map_groups[0], repository.display)


def test_search_with_raw(map_groups, token_and_secret, mocker: MockerFixture):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter)

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)

    total, size, index = 1, 1, 1
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    mock_search.return_value = expected = SearchResponse[MapGroup](
        total_results=total, items_per_page=size, start_index=index, resources=map_groups[:1]
    )

    result = groups.search(criteria, raw=True)

    assert result == expected
    mock_search.assert_called_once_with(query, include=mocker.ANY, access_token=token, client_secret=secret)


def test_search_map_error(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "jc_test_repo_ac_jp_gr_test"'))

    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    map_error = MapError(detail="eq is not supported.", status="400", scim_type="invalidSyntax")
    mock_search.return_value = map_error

    with pytest.raises(InvalidQueryError, match=regex(E.UNSUPPORTED_SEARCH_FILTER)):
        groups.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_GROUPS, {"filter": filter_str})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_search_unauthorized(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "jc_test_repo_ac_jp_gr_test"'))

    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_search.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        groups.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_GROUPS, {"filter": filter_str})


def test_search_unexpected_response(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "jc_test_repo_ac_jp_gr_test"'))

    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_search.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_GROUPS, {"filter": filter_str})


def test_search_request_exception(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "jc_test_repo_ac_jp_gr_test"'))

    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    mock_search.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        groups.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_GROUPS, {"filter": filter_str})


def test_search_validation_error(app, token_and_secret, mocker: MockerFixture, caplog):
    criteria = mocker.MagicMock(spec=GroupsCriteria)
    query = mocker.MagicMock(spec=SearchRequestParameter, filter=(filter_str := 'id eq "jc_test_repo_ac_jp_gr_test"'))

    mocker.patch.object(server.services.core.groups, "build_search_query", return_value=query)
    mock_search = mocker.patch.object(server.services.core.groups.groups, "search", autospec=True)
    mock_search.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        groups.search(criteria)

    mock_search.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_SEARCH_GROUPS, {"filter": filter_str})


def test_get_by_id(repository_summaries, map_groups, group_details, token_and_secret, mocker: MockerFixture):
    group = expected = group_details[0]
    map_group = map_groups[0]

    token, secret = token_and_secret
    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id", autospec=True)
    mock_get.return_value = map_group
    mock_make_detail = mocker.patch.object(server.services.core.groups, "make_group_detail", return_value=group)

    result = groups.get_by_id(map_group.id)

    assert result == expected
    mock_get.assert_called_once_with(map_group.id, access_token=token, client_secret=secret)
    mock_make_detail.assert_called_once_with(map_group, more_detail=False)


def test_get_by_id_with_more_detail(
    repository_summaries, map_groups, group_details, token_and_secret, mocker: MockerFixture
):
    group = expected = group_details[0]
    map_group = map_groups[0]

    token, secret = token_and_secret
    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id", autospec=True)
    mock_get.return_value = map_group
    mock_make_detail = mocker.patch.object(server.services.core.groups, "make_group_detail", return_value=group)

    result = groups.get_by_id(map_group.id, more_detail=True)

    assert result == expected
    mock_get.assert_called_once_with(map_group.id, access_token=token, client_secret=secret)
    mock_make_detail.assert_called_once_with(map_group, more_detail=True)


def test_get_by_id_with_raw(map_groups, token_and_secret, mocker: MockerFixture):
    map_group = map_groups[0]

    token, secret = token_and_secret
    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id", autospec=True)
    mock_get.return_value = map_group

    result = groups.get_by_id(map_group.id, raw=True)

    assert result == map_group
    mock_get.assert_called_once_with(map_group.id, access_token=token, client_secret=secret)


def test_get_by_id_map_error(app, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    map_group = map_groups[0]

    map_error = MapError(detail="Invalid group ID.", status="404", scim_type="invalidValue")
    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id", return_value=map_error)

    result = groups.get_by_id(map_group.id)

    assert result is None
    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_GROUP, {"id": map_group.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_get_by_id_unauthorized(app, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    map_group = map_groups[0]

    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id")
    mock_get.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        groups.get_by_id(map_group.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_GROUP, {"id": map_group.id})


def test_get_by_id_unexpected_response(app, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    map_group = map_groups[0]

    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id")
    mock_get.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.get_by_id(map_group.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_GROUP, {"id": map_group.id})


def test_get_by_id_request_exception(app, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    map_group = map_groups[0]

    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id")
    mock_get.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        groups.get_by_id(map_group.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_GROUP, {"id": map_group.id})


def test_get_by_id_validation_error(app, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    map_group = map_groups[0]

    mock_get = mocker.patch.object(server.services.core.groups.groups, "get_by_id")
    mock_get.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        groups.get_by_id(map_group.id)

    mock_get.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_GET_GROUP, {"id": map_group.id})


def test_create(
    app,
    repository_summaries,
    group_details,
    map_groups,
    user_summaries,
    token_and_secret,
    signal_send,
    mocker: MockerFixture,
    caplog,
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    repository_id = repository_summaries[0].id
    group = expected = group_details[0]
    map_group = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post", autospec=True)
    mock_post.return_value = map_group
    mocker.patch.object(server.services.core.groups, "make_group_detail", return_value=group)

    result = groups.create(group, admins)

    assert result == expected
    mock_post.assert_called_once_with(prepared, exclude=mocker.ANY, access_token=token, client_secret=secret)
    assert_message(caplog.records[0], I.SUCCESS_CREATE_GROUP, {"id": map_group.id, "rid": repository_id})
    signal_send["group_created"].assert_called_once()


def test_create_already_exists(
    app, group_details, map_groups, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    group = group_details[0]
    map_group: MapGroup = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    map_error = MapError(
        detail=MAP_DUPLICATE_ID_PATTERN.replace("(.*)", group.id), status="409", scim_type="uniqueness"
    )

    mock_post = mocker.patch.object(server.services.core.groups.groups, "post", return_value=map_error)

    with pytest.raises(ResourceInvalid, match=regex(E.GROUP_DUPLICATE_ID)):
        groups.create(group, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_GROUP, {"id": group.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_create_unexpected_map_error(
    app, group_details, map_groups, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    group = group_details[0]
    map_group = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    map_error = MapError(detail="Unexpected error.", status="500", scim_type="invalidValue")
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post", return_value=map_error)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.create(group, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_GROUP, {"id": group.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_create_unauthorized(
    app, group_details, map_groups, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    group = group_details[0]
    map_group = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        groups.create(group, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_GROUP, {"id": group.id})


def test_create_unexpected_response(
    app, group_details, map_groups, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    group = group_details[0]
    map_group = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.create(group, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_GROUP, {"id": group.id})


def test_create_request_exception(
    app, group_details, map_groups, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    group = group_details[0]
    map_group = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        groups.create(group, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_GROUP, {"id": group.id})


def test_create_validation_error(
    app, group_details, map_groups, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    group = group_details[0]
    map_group = map_groups[0]
    prepared = map_group.model_copy(update={"id": None})

    mocker.patch.object(server.services.core.groups, "prepare_group", return_value=prepared)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        groups.create(group, admins)

    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_GROUP, {"id": group.id})


def test_create_role_groups(
    app,
    map_rolegroups,
    repository_summaries,
    user_summaries,
    token_and_secret,
    signal_send,
    mocker: MockerFixture,
    caplog,
):
    repository = repository_summaries[0]
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    prepared = list(map_rolegroups.values())[1:]  # Exclude SYSTEM_ADMIN role group for testing

    token, secret = token_and_secret
    mock_prepare = mocker.patch.object(server.services.core.groups, "prepare_role_groups", return_value=prepared)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post", autospec=True)

    groups.create_role_groups(repository.id, repository.service_name, admins)

    mock_prepare.assert_called_once_with(repository.id, repository.service_name, admins)
    assert mock_post.call_count == len(prepared)
    mock_post.assert_any_call(map_rolegroups[USER_ROLES.REPOSITORY_ADMIN], access_token=token, client_secret=secret)
    mock_post.assert_any_call(map_rolegroups[USER_ROLES.COMMUNITY_ADMIN], access_token=token, client_secret=secret)
    mock_post.assert_any_call(map_rolegroups[USER_ROLES.CONTRIBUTOR], access_token=token, client_secret=secret)
    mock_post.assert_any_call(map_rolegroups[USER_ROLES.GENERAL_USER], access_token=token, client_secret=secret)
    signal_send["group_created"].assert_called()
    assert_message(caplog.records[0], I.SUCCESS_CREATE_ROLEGROUPS, {"id": repository.id})


def test_create_role_groups_conflict(
    app,
    map_rolegroups,
    repository_summaries,
    user_summaries,
    token_and_secret,
    signal_send,
    mocker: MockerFixture,
    caplog,
):
    repository = repository_summaries[0]
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    prepared = list(map_rolegroups.values())[1:]  # Exclude SYSTEM_ADMIN role group for testing

    mock_prepare = mocker.patch.object(server.services.core.groups, "prepare_role_groups", return_value=prepared)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.CONFLICT)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = [
        requests.HTTPError(response=mock_response) if g.id == map_rolegroups[USER_ROLES.CONTRIBUTOR].id else None
        for g in prepared
    ]

    groups.create_role_groups(repository.id, repository.service_name, admins)

    mock_prepare.assert_called_once_with(repository.id, repository.service_name, admins)
    assert mock_post.call_count == len(prepared)
    signal_send["group_created"].assert_called()
    assert_message(caplog.records[0], W.ROLE_GROUP_ALREADY_EXISTS, {"rid": repository.id, "gid": prepared[2].id})
    assert_message(caplog.records[1], I.SUCCESS_CREATE_ROLEGROUPS, {"id": repository.id})


def test_create_role_groups_unauthorized(
    app, map_rolegroups, repository_summaries, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_summaries[0]
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    prepared = list(map_rolegroups.values())[1:]  # Exclude SYSTEM_ADMIN role group for testing

    mock_prepare = mocker.patch.object(server.services.core.groups, "prepare_role_groups", return_value=prepared)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        groups.create_role_groups(repository.id, repository.service_name, admins)

    mock_prepare.assert_called_once()
    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_ROLEGROUP, {"rid": repository.id, "gid": prepared[0].id})


def test_create_role_groups_unexpected_response(
    app, map_rolegroups, repository_summaries, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_summaries[0]
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    prepared = list(map_rolegroups.values())[1:]  # Exclude SYSTEM_ADMIN role group for testing

    mock_prepare = mocker.patch.object(server.services.core.groups, "prepare_role_groups", return_value=prepared)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.create_role_groups(repository.id, repository.service_name, admins)

    mock_prepare.assert_called_once()
    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_ROLEGROUP, {"rid": repository.id, "gid": prepared[0].id})


def test_create_role_groups_request_exception(
    app, map_rolegroups, repository_summaries, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_summaries[0]
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    prepared = list(map_rolegroups.values())[1:]  # Exclude SYSTEM_ADMIN role group for testing

    mock_prepare = mocker.patch.object(server.services.core.groups, "prepare_role_groups", return_value=prepared)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        groups.create_role_groups(repository.id, repository.service_name, admins)

    mock_prepare.assert_called_once()
    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_ROLEGROUP, {"rid": repository.id, "gid": prepared[0].id})


def test_create_role_groups_validation_error(
    app, map_rolegroups, repository_summaries, user_summaries, token_and_secret, mocker: MockerFixture, caplog
):
    repository = repository_summaries[0]
    admins = {user_summaries[USER_ROLES.SYSTEM_ADMIN].id}
    prepared = list(map_rolegroups.values())[1:]  # Exclude SYSTEM_ADMIN role group for testing

    mock_prepare = mocker.patch.object(server.services.core.groups, "prepare_role_groups", return_value=prepared)
    mock_post = mocker.patch.object(server.services.core.groups.groups, "post")
    mock_post.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        groups.create_role_groups(repository.id, repository.service_name, admins)

    mock_prepare.assert_called_once()
    mock_post.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_CREATE_ROLEGROUP, {"rid": repository.id, "gid": prepared[0].id})


def test_update(
    app, repository_summaries, group_details, map_groups, token_and_secret, signal_send, mocker: MockerFixture, caplog
):
    repository_id = repository_summaries[0].id
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    updated_detail = expected = group.model_copy()
    current_group: MapGroup = map_groups[0]
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]
    include_fields = {"display_name", "description"}

    token, secret = token_and_secret
    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mock_build_ops = mocker.patch.object(server.services.core.groups, "build_patch_operations", autospec=True)
    mock_build_ops.return_value = operations
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id", autospec=True)
    mock_patch.return_value = validated
    mocker.patch.object(server.services.core.groups, "make_group_detail", return_value=updated_detail)

    result = groups.update(group)

    assert result == expected
    mock_build_ops.assert_called_once_with(current_group, validated, include=include_fields)
    mock_patch.assert_called_once_with(
        validated.id, operations, exclude=mocker.ANY, access_token=token, client_secret=secret
    )
    signal_send["group_updated"].assert_called_once()
    assert_message(caplog.records[0], I.SUCCESS_UPDATE_GROUP, {"id": validated.id, "rid": repository_id})


def test_update_not_found(app, group_details, mocker: MockerFixture, caplog):
    group = group_details[0]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=None)

    with pytest.raises(ResourceNotFound, match=regex(E.GROUP_NOT_FOUND)):
        groups.update(group)

    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})


def test_update_unauthorized(app, group_details, token_and_secret, mocker: MockerFixture, caplog):
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    current_group: MapGroup = server.services.core.groups.make_map_group(current_detail)
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mocker.patch.object(server.services.core.groups, "build_patch_operations", return_value=operations)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.UNAUTHORIZED)
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id")
    mock_patch.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(OAuthTokenError, match=regex(E.ACCESS_TOKEN_NOT_AVAILABLE)):
        groups.update(group)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})


def test_update_unexpected_response(app, group_details, token_and_secret, mocker: MockerFixture, caplog):
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    current_group: MapGroup = server.services.core.groups.make_map_group(current_detail)
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mocker.patch.object(server.services.core.groups, "build_patch_operations", return_value=operations)
    mock_response = mocker.MagicMock(spec=Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id")
    mock_patch.side_effect = requests.HTTPError(response=mock_response)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.update(group)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})


def test_update_request_exception(app, group_details, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    current_group = map_groups[0]
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mocker.patch.object(server.services.core.groups, "build_patch_operations", return_value=operations)
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id")
    mock_patch.side_effect = requests.RequestException("Connection error.")

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_COMMUNICATE_API)):
        groups.update(group)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})


def test_update_validation_error(app, group_details, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    current_group = map_groups[0]
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mocker.patch.object(server.services.core.groups, "build_patch_operations", return_value=operations)
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id")
    mock_patch.side_effect = ValidationError("failed to parse.", [])

    with pytest.raises(UnexpectedResponseError, match=regex(E.FAILED_PARSE_RESPONSE)):
        groups.update(group)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})


def test_update_map_error_not_found(app, group_details, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    current_group = map_groups[0]
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mocker.patch.object(server.services.core.groups, "build_patch_operations", return_value=operations)
    map_error = MapError(
        detail=MAP_NOT_FOUND_PATTERN.replace("(.*)", validated.id), status="400", scim_type="invalidValue"
    )
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id", return_value=map_error)

    with pytest.raises(ResourceNotFound, match=regex(E.GROUP_NOT_FOUND)):
        groups.update(group)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})


def test_update_map_error_unexpected(app, group_details, map_groups, token_and_secret, mocker: MockerFixture, caplog):
    current_detail: GroupDetail = group_details[0]
    group = current_detail.model_copy(
        update={"display_name": (updated_name := f"Updated {current_detail.display_name}")}
    )
    current_group = map_groups[0]
    validated = current_group.model_copy(update={"display_name": updated_name})
    operations = [ReplaceOperation(path="display_name", value=updated_name)]

    mocker.patch.object(server.services.core.groups, "get_by_id", return_value=current_detail)
    mocker.patch.object(server.services.core.groups, "validate_group_to_map_group", return_value=validated)
    mocker.patch.object(server.services.core.groups, "make_map_group", return_value=current_group)
    mocker.patch.object(server.services.core.groups, "build_patch_operations", return_value=operations)
    map_error = MapError(detail="Unexpected error.", status="500", scim_type="invalidValue")
    mock_patch = mocker.patch.object(server.services.core.groups.groups, "patch_by_id", return_value=map_error)

    with pytest.raises(UnexpectedResponseError, match=regex(E.RECEIVE_UNEXPECTED_RESPONSE)):
        groups.update(group)

    mock_patch.assert_called_once()
    assert_message(caplog.records[0], E.FAILED_UPDATE_GROUP, {"id": group.id})
    assert_message(caplog.records[1], E.RECEIVE_RESPONSE_MESSAGE, {"message": map_error.detail})
