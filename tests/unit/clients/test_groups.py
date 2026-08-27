import typing as t

from http import HTTPStatus
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from pydantic import AliasGenerator
from pydantic.alias_generators import to_camel
from requests.exceptions import HTTPError

import server.clients.groups

from server.clients import groups
from server.const import MAP_GROUPS_ENDPOINT
from server.entities.map_group import MapGroup
from server.entities.patch_request import ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse

from tests.helpers import unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


@pytest.fixture(autouse=True)
def alias(mocker: MockerFixture):
    original = groups._a
    mock_alias = mocker.patch.object(groups, "_a", side_effect=lambda x: x)

    return original, mock_alias


@pytest.fixture
def use_alias(alias):
    original, _ = alias
    groups._a = original

    return original


def test_search(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, group, _ = map_group

    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    total, size = 1, 1
    expected = SearchResponse[MapGroup](total_results=total, items_per_page=size, start_index=index, resources=[group])

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(groups.search)(query, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}"
    assert "attributes" not in kwargs["params"]
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["params"]["startIndex"] == index
    assert kwargs["params"]["count"] == count
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_search_with_include(config, map_group, mocker: MockerFixture):
    _, group, _ = map_group

    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    total, size = 1, 1
    expected = SearchResponse[MapGroup](total_results=total, items_per_page=size, start_index=index, resources=[group])

    include = {"display_name", "description"}

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(groups.search)(query, include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"


def test_search_with_exclude(config, map_group, mocker: MockerFixture):
    _, group, _ = map_group

    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    total, size = 1, 1
    expected = SearchResponse[MapGroup](total_results=total, items_per_page=size, start_index=index, resources=[group])

    exclude = {"meta", "suspended"}

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(groups.search)(query, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}"
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"


def test_search_map_error_with_bad_request(config, map_error, mocker: MockerFixture):
    _, expected, raw_error = map_error

    filter_string, index, count = 'displayName eq "Test Group"', 1, 10
    query = SearchRequestParameter(filter=filter_string, start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = raw_error
    mock_get.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = unwrap(groups.search)(query, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_search_http_error(config, mocker: MockerFixture):
    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_get.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        unwrap(groups.search)(query, access_token=access_token, client_secret=client_secret)


def test_get_by_id(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, expected, raw_json = map_group
    group_id = expected.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(groups.get_by_id)(group_id, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{group_id}"
    assert "attributes" not in kwargs["params"]
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_id_with_include(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, expected, raw_json = map_group
    group_id = expected.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    include = {"display_name", "description"}

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(groups.get_by_id)(group_id, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{group_id}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_id_with_exclude(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, expected, raw_json = map_group
    group_id = expected.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    exclude = {"meta", "suspended"}

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(groups.get_by_id)(group_id, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{group_id}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_id_map_error_with_bad_request(config: RuntimeConfig, map_group, map_error, mocker: MockerFixture):
    _, group, _ = map_group
    _, expected, raw_error = map_error
    group_id = group.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.text = raw_error
    mock_get.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = unwrap(groups.get_by_id)(group_id, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_get_by_id_http_error(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, group, _ = map_group
    group_id = group.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.groups.requests, "get")
    mock_get.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_get.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        unwrap(groups.get_by_id)(group_id, access_token=access_token, client_secret=client_secret)


def test_post(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    mock_post = mocker.patch.object(server.clients.groups.requests, "post")
    mock_post.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_post.return_value.status_code = HTTPStatus.OK

    result = groups.post(expected, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_post.assert_called_once()
    (url,), kwargs = mock_post.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["displayName"] == expected.display_name
    assert kwargs["json"]["description"] == expected.description
    assert kwargs["json"]["suspended"] == expected.suspended
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_post_with_include(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    include = {"display_name", "description"}

    mock_post = mocker.patch.object(server.clients.groups.requests, "post")
    mock_post.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_post.return_value.status_code = HTTPStatus.OK

    result = groups.post(expected, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_post.assert_called_once()
    (url,), kwargs = mock_post.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["displayName"] == expected.display_name
    assert kwargs["json"]["description"] == expected.description
    assert "suspended" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_post_with_exclude(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    exclude = {"meta", "suspended"}

    mock_post = mocker.patch.object(server.clients.groups.requests, "post")
    mock_post.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_post.return_value.status_code = HTTPStatus.OK

    result = groups.post(expected, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_post.assert_called_once()
    (url,), kwargs = mock_post.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["displayName"] == expected.display_name
    assert kwargs["json"]["description"] == expected.description
    assert "suspended" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_post_map_error_with_bad_request(config: RuntimeConfig, map_group, map_error, mocker: MockerFixture):
    _, group, _ = map_group
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_post = mocker.patch.object(server.clients.groups.requests, "post")
    mock_post.return_value.text = raw_error
    mock_post.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = groups.post(group, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_post_http_error(config: RuntimeConfig, map_group, mocker: MockerFixture):
    _, group, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_post = mocker.patch.object(server.clients.groups.requests, "post")
    mock_post.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_post.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        groups.post(group, access_token=access_token, client_secret=client_secret)


def test_put_by_id(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    mock_put = mocker.patch.object(server.clients.groups.requests, "put")
    mock_put.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_put.return_value.status_code = HTTPStatus.OK
    mock_send = signal_send["group_updated"]

    result = groups.put_by_id(expected, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_put.assert_called_once()
    (url,), kwargs = mock_put.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{expected.id}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["displayName"] == expected.display_name
    assert kwargs["json"]["description"] == expected.description
    assert kwargs["json"]["suspended"] == expected.suspended
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout

    _, kwargs = mock_send.call_args
    assert kwargs["group"] == expected


def test_put_by_id_with_include(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    include = {"display_name", "description"}

    mock_put = mocker.patch.object(server.clients.groups.requests, "put")
    mock_put.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_put.return_value.status_code = HTTPStatus.OK

    result = groups.put_by_id(expected, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_put.assert_called_once()
    (url,), kwargs = mock_put.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{expected.id}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["displayName"] == expected.display_name
    assert kwargs["json"]["description"] == expected.description
    assert "suspended" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_put_by_id_with_exclude(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    exclude = {"meta", "suspended"}

    mock_put = mocker.patch.object(server.clients.groups.requests, "put")
    mock_put.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_put.return_value.status_code = HTTPStatus.OK

    result = groups.put_by_id(expected, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_put.assert_called_once()
    (url,), kwargs = mock_put.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{expected.id}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["displayName"] == expected.display_name
    assert kwargs["json"]["description"] == expected.description
    assert "suspended" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_put_by_id_map_error_with_bad_request(
    config: RuntimeConfig, map_group, map_error, signal_send, mocker: MockerFixture
):
    _, group, _ = map_group
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_put = mocker.patch.object(server.clients.groups.requests, "put")
    mock_put.return_value.text = raw_error
    mock_put.return_value.status_code = HTTPStatus.BAD_REQUEST
    mock_send = signal_send["group_updated"]

    result = groups.put_by_id(group, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_send.assert_not_called()


def test_put_by_id_http_error(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, group, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_put = mocker.patch.object(server.clients.groups.requests, "put")
    mock_put.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_put.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)
    mock_send = signal_send["group_updated"]

    with pytest.raises(HTTPError):
        groups.put_by_id(group, access_token=access_token, client_secret=client_secret)

    mock_send.assert_not_called()


def test_patch_by_id(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="displayName", value="Updated Name")]
    payload = {
        "schemas": [mocker.ANY],
        "operations": [{"op": "replace", "path": "displayName", "value": "Updated Name"}],
    }
    expected.display_name = "Updated Name"

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    mock_patch = mocker.patch.object(server.clients.groups.requests, "patch")
    mock_patch.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_patch.return_value.status_code = HTTPStatus.OK
    mock_send = signal_send["group_updated"]

    result = groups.patch_by_id(expected.id, operations, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_patch.assert_called_once()
    (url,), kwargs = mock_patch.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{expected.id}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["Operations"] == payload["operations"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout

    _, kwargs = mock_send.call_args
    assert kwargs["group"] == expected


def test_patch_by_id_with_include(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="displayName", value="Updated Name")]
    include = {"display_name", "description"}

    mock_patch = mocker.patch.object(server.clients.groups.requests, "patch")
    mock_patch.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_patch.return_value.status_code = HTTPStatus.OK

    result = groups.patch_by_id(
        expected.id, operations, include=include, access_token=access_token, client_secret=client_secret
    )

    assert result == expected
    mock_patch.assert_called_once()
    (url,), kwargs = mock_patch.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{expected.id}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]


def test_patch_by_id_with_exclude(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, expected, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="displayName", value="Updated Name")]
    exclude = {"meta", "suspended"}

    mock_patch = mocker.patch.object(server.clients.groups.requests, "patch")
    mock_patch.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_patch.return_value.status_code = HTTPStatus.OK

    result = groups.patch_by_id(
        expected.id, operations, exclude=exclude, access_token=access_token, client_secret=client_secret
    )

    assert result == expected
    mock_patch.assert_called_once()
    (url,), kwargs = mock_patch.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{expected.id}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)


def test_patch_by_id_map_error_with_bad_request(
    config: RuntimeConfig, map_group, map_error, signal_send, mocker: MockerFixture
):
    _, group, _ = map_group
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="displayName", value="Updated Name")]

    mock_patch = mocker.patch.object(server.clients.groups.requests, "patch")
    mock_patch.return_value.text = raw_error
    mock_patch.return_value.status_code = HTTPStatus.BAD_REQUEST
    mock_send = signal_send["group_updated"]

    result = groups.patch_by_id(group.id, operations, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_send.assert_not_called()


def test_patch_by_id_http_error(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, group, _ = map_group
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="displayName", value="Updated Name")]

    mock_patch = mocker.patch.object(server.clients.groups.requests, "patch")
    mock_patch.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_patch.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)
    mock_send = signal_send["group_updated"]

    with pytest.raises(HTTPError):
        groups.patch_by_id(group.id, operations, access_token=access_token, client_secret=client_secret)

    mock_send.assert_not_called()


def test_delete_by_id(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, group, _ = map_group
    group_id = group.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.groups, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.groups, "compute_signature")

    mock_delete = mocker.patch.object(server.clients.groups.requests, "delete")
    mock_delete.return_value.text = ""
    mock_delete.return_value.status_code = HTTPStatus.NO_CONTENT
    mock_send = signal_send["group_deleted"]

    result = groups.delete_by_id(group_id, access_token=access_token, client_secret=client_secret)

    assert result is None
    mock_delete.assert_called_once()
    (url,), kwargs = mock_delete.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_GROUPS_ENDPOINT}/{group_id}"
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout

    _, kwargs = mock_send.call_args
    assert kwargs["group_id"] == group_id


def test_delete_by_id_map_error_with_bad_request(
    config: RuntimeConfig, map_group, map_error, signal_send, mocker: MockerFixture
):
    _, group, _ = map_group
    _, expected, raw_error = map_error
    group_id = group.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_delete = mocker.patch.object(server.clients.groups.requests, "delete")
    mock_delete.return_value.text = raw_error
    mock_delete.return_value.status_code = HTTPStatus.BAD_REQUEST
    mock_send = signal_send["group_deleted"]

    result = groups.delete_by_id(group_id, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_send.assert_not_called()


def test_delete_by_id_http_error(config: RuntimeConfig, map_group, signal_send, mocker: MockerFixture):
    _, group, _ = map_group
    group_id = group.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_delete = mocker.patch.object(server.clients.groups.requests, "delete")
    mock_delete.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_delete.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)
    mock_send = signal_send["group_deleted"]

    with pytest.raises(HTTPError):
        groups.delete_by_id(group_id, access_token=access_token, client_secret=client_secret)

    mock_send.assert_not_called()


def test__alias_generator(use_alias, mocker: MockerFixture):
    mock_generator = mocker.MagicMock(side_effect=to_camel)
    mocker.patch.object(MapGroup, "model_config", {"alias_generator": mock_generator})

    assert unwrap(groups._a)("display_name") == "displayName"

    mock_generator.assert_called_once_with("display_name")


def test__alias_serialization(use_alias, mocker: MockerFixture):
    mock_generator = mocker.NonCallableMock(spec_set=AliasGenerator)
    mock_generator.serialization_alias.side_effect = to_camel
    mocker.patch.object(MapGroup, "model_config", {"alias_generator": mock_generator})

    assert unwrap(groups._a)("display_name") == "displayName"

    mock_generator.serialization_alias.assert_called_once_with("display_name")


def test__alias_not_set(use_alias, mocker: MockerFixture):
    mock_config = mocker.MagicMock(spec=dict)
    mock_config.get.return_value = None
    mocker.patch.object(MapGroup, "model_config", mock_config)

    assert unwrap(groups._a)("display_name") == "display_name"
    mock_config.get.assert_called_once_with("alias_generator")


def test_handle_group_updated_by_id(map_group, mocker: MockerFixture):
    _, group, _ = map_group
    mock_clear = mocker.patch.object(groups.get_by_id, "clear_cache")

    unwrap(groups.handle_group_updated_by_id)(None, group=group)

    mock_clear.assert_not_called()

    unwrap(groups.handle_group_updated_by_id)(None, group_id=group.id)

    mock_clear.assert_called_once_with(group.id)


def test_handle_group_updated_by_ids(map_group, mocker: MockerFixture):
    _, group, _ = map_group
    mock_clear = mocker.patch.object(groups.get_by_id, "clear_cache")

    unwrap(groups.handle_group_updated_by_ids)(None, group_ids=[])

    mock_clear.assert_not_called()

    unwrap(groups.handle_group_updated_by_ids)(None, group_ids=[group.id])

    mock_clear.assert_called_once_with(group.id)


def test_handle_reset_search_cache(mocker: MockerFixture):
    mock_clear = mocker.patch.object(groups.search, "clear_cache")

    unwrap(groups.handle_reset_search_cache)(None)

    mock_clear.assert_called_once()
