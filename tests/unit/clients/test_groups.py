import hashlib
import importlib
import inspect
import json
import time
import typing as t

import pytest

from requests.exceptions import HTTPError

from server.clients import groups
from server.config import config
from server.const import MAP_GROUPS_ENDPOINT
from server.entities.login_user import LoginUser
from server.entities.map_error import MapError
from server.entities.map_group import MapGroup
from server.entities.patch_request import PatchOperation, PatchRequestPayload, ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse
from tests.helpers import load_json_data


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


@pytest.fixture
def group_data() -> tuple[dict[str, t.Any], MapGroup]:
    json_data = load_json_data("data/map_group.json")
    group: MapGroup = MapGroup.model_validate(json_data)
    return json_data, group


def test_search_success(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that groups are returned when a valid search request is provided."""
    _, group = group_data

    query = SearchRequestParameter()
    access_token = "token"
    client_secret = "secret"
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    response = SearchResponse[MapGroup](total_results=1, items_per_page=1, start_index=1, resources=[group])
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout

    mock_get = mocker.patch("server.clients.groups.requests.get")
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_get.return_value.text = response.model_dump_json()
    mock_get.return_value.status_code = 200
    original_func = inspect.unwrap(groups.search)

    result = original_func(query, access_token=access_token, client_secret=client_secret)

    mock_get.assert_called_once()
    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": None,
        "count": None,
        "startIndex": None,
        "sortBy": None,
        "sortOrder": None,
    }
    expected_result: SearchResponse[MapGroup] = SearchResponse[MapGroup].model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_with_include(app: Flask, mocker: MockerFixture) -> None:
    """Test that include params are reflected in attributes_params for search and partial response is handled."""
    count_number = 5
    query = SearchRequestParameter(count=count_number)
    include = {"display_name", "description"}
    access_token = "token"
    client_secret = "secret"
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "g1", "schemas": ["a"], "displayName": "g"}],
    }
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_attributes = set(include | {"id"})
    mocker.patch("server.clients.groups.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mock_get = mocker.patch("server.clients.groups.requests.get")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = inspect.unwrap(groups.search)
    result = original_func(query, include=include, access_token=access_token, client_secret=client_secret)

    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": None,
        "count": count_number,
        "startIndex": None,
        "sortBy": None,
        "sortOrder": None,
    }
    expected_result: SearchResponse[MapGroup] = SearchResponse[MapGroup].model_validate(response_data)
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_with_exclude(app: Flask, mocker: MockerFixture) -> None:
    """Test that exclude params are reflected in attributes_params for search and excluded fields are missing."""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    exclude = {"meta"}
    access_token = "token"
    client_secret = "secret"
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "g1", "schemas": ["a"], "displayName": "g"}],
    }
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_excluded = set(exclude)
    mocker.patch("server.clients.groups.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mock_get = mocker.patch("server.clients.groups.requests.get")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = inspect.unwrap(groups.search)

    result = original_func(query, exclude=exclude, access_token=access_token, client_secret=client_secret)

    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": filter_string,
        "count": None,
        "startIndex": None,
        "sortBy": None,
        "sortOrder": None,
    }
    expected_result: SearchResponse[MapGroup] = SearchResponse[MapGroup].model_validate(response_data)
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_groups_with_all_params(app: Flask, mocker: MockerFixture) -> None:
    """Tests group search with all parameter types."""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    include = {"display_name", "description"}
    exclude = {"meta"}
    access_token = "token"
    client_secret = "secret"
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "g1", "schemas": ["a"], "displayName": "g"}],
    }
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_excluded = set(exclude)
    expected_attributes = set(include | {"id"})
    mocker.patch("server.clients.groups.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mock_get = mocker.patch("server.clients.groups.requests.get")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = inspect.unwrap(groups.search)

    result = original_func(
        query, include=include, exclude=exclude, access_token=access_token, client_secret=client_secret
    )

    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": filter_string,
        "count": None,
        "startIndex": None,
        "sortBy": None,
        "sortOrder": None,
    }
    expected_result: SearchResponse[MapGroup] = SearchResponse[MapGroup].model_validate(response_data)
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_status_400_returns_maperror(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that when status_code=400, MapError is returned"""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    access_token = "token"
    client_secret = "secret"
    error_data = load_json_data("data/map_error.json")
    mock_get = mocker.patch("server.clients.groups.requests.get")
    mock_get.return_value.text = MapError.model_validate(error_data).model_dump_json()
    mock_get.return_value.status_code = 400
    original_func = inspect.unwrap(groups.search)

    result = original_func(query, access_token=access_token, client_secret=client_secret)
    assert isinstance(result, MapError)


def test_search_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that HTTP errors are raised when status_code > 400 in search."""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    mock_get = mocker.patch("server.clients.groups.requests.get")
    mock_get.return_value.status_code = 401
    mock_get.return_value.raise_for_status.side_effect = Exception("401 Unauthorized")
    original_func = inspect.unwrap(groups.search)

    with pytest.raises(Exception, match="401 Unauthorized"):
        original_func(query, access_token="token", client_secret="secret")


def test_get_by_id_success(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that a group is returned when a valid group_id is provided."""
    json_data, expected_result = group_data
    group_id = None
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/None"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    mock_response = mocker.patch("server.clients.groups.requests.get")
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.status_code = 200

    original_func = inspect.unwrap(groups.get_by_id)
    result = original_func(group_id, access_token="token", client_secret="secret")

    mock_response.assert_called_once()
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_get_by_id_with_include(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that include params are reflected in attributes_params for get_by_id and partial response is handled."""
    json_data, _ = group_data
    group_id: str = json_data["id"]
    include = {"display_name", "description"}
    signature = hashlib.sha256(b"hash").hexdigest()
    time_stamp = str(int(time.time()))

    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_attributes = set(include | {"id"})
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"
    mock_response = mocker.patch("server.clients.groups.requests.get")
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200
    original_func = inspect.unwrap(groups.get_by_id)

    result = original_func(group_id, include=include, access_token="token", client_secret="secret")
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_result: MapGroup = MapGroup.model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_get_by_id_with_exclude(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that exclude params are reflected in attributes_params for get_by_id and excluded fields are missing."""
    json_data, _ = group_data
    group_id = json_data["id"]
    exclude = {"description"}
    signature = hashlib.sha256(b"hash").hexdigest()
    time_stamp = str(int(time.time()))
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_excluded = set(exclude)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"

    mock_response = mocker.patch("server.clients.groups.requests.get")
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    original_func = inspect.unwrap(groups.get_by_id)
    result = original_func(group_id, exclude=exclude, access_token="token", client_secret="secret")

    mock_response.assert_called_once()
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_result: MapGroup = MapGroup.model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_get_by_id_with_all_params(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Tests get_by_id with all parameter types (include/exclude)."""
    json_data, _ = group_data
    group_id = json_data["id"]
    include = {"display_name", "description"}
    exclude = {"meta"}
    signature = hashlib.sha256(b"hash").hexdigest()
    time_stamp = str(int(time.time()))
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_attributes = set(include | {"id"})
    expected_excluded = set(exclude)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"

    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.groups.requests.get")
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    original_func = inspect.unwrap(groups.get_by_id)
    result = original_func(group_id, include=include, exclude=exclude, access_token="token", client_secret="secret")

    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_result: MapGroup = MapGroup.model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_get_by_id_status_400_returns_maperror(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that when status_code=400, MapError is returned"""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    error_data = load_json_data("data/map_error.json")
    mock_get = mocker.patch("server.clients.groups.requests.get")
    mock_get.return_value.text = MapError.model_validate(error_data).model_dump_json()
    mock_get.return_value.status_code = 400
    original_func = inspect.unwrap(groups.get_by_id)

    result = original_func(group_id, access_token="token", client_secret="secret")
    assert isinstance(result, MapError)


def test_get_by_id_http_error(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in get_by_id."""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    mock_response = mocker.patch("server.clients.groups.requests.get")
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_response.return_value.status_code = 401
    original_func = inspect.unwrap(groups.get_by_id)

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(group_id, access_token="token", client_secret="secret")


def test_post_success(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that a group is created successfully via post."""
    json_data, group = group_data

    expected_result: MapGroup = group
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout

    mock_post = mocker.patch("server.clients.groups.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.status_code = 200

    original_func = inspect.unwrap(groups.post)
    result = original_func(group, include=None, exclude=None, access_token="token", client_secret="secret")

    mock_post.assert_called_once()
    call_args, called_kwargs = mock_post.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {}
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_post_with_include(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that include params are reflected in post and partial response is handled."""
    json_data, group = group_data

    include = {"display_name", "description"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_result: MapGroup = MapGroup.model_validate(response_data)
    expected_attributes = set(include)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"
    mock_post = mocker.patch("server.clients.groups.requests.post")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_post.return_value.text = json.dumps(response_data)
    mock_post.return_value.status_code = 200

    original_func = inspect.unwrap(groups.post)
    result = original_func(group, include=include, exclude=None, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_post.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {}
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_post_with_exclude(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that exclude params are reflected in attributes_params for post and excluded fields are missing."""
    json_data, group = group_data

    exclude = {"meta"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_result: MapGroup = MapGroup.model_validate(response_data)
    expected_excluded = set(exclude)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"

    mock_post = mocker.patch("server.clients.groups.requests.post")
    mock_post.return_value.text = json.dumps(response_data)
    mock_post.return_value.status_code = 200
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)

    result = groups.post(group, include=None, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_post.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {}
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_post_with_all_params(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Tests post with all parameter types (include/exclude)."""
    json_data, group = group_data
    include = {"display_name", "description"}
    exclude = {"meta"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_attributes = set(include)
    expected_excluded = set(exclude)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}"

    mock_post = mocker.patch("server.clients.groups.requests.post")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_post.return_value.text = json.dumps(response_data)
    mock_post.return_value.status_code = 200

    original_func = inspect.unwrap(groups.post)
    result = original_func(group, include=include, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_post.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_result: MapGroup = MapGroup.model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {}
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_post_status_400_returns_maperror(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that when status_code=400, MapError is returned in post"""
    _, group = group_data
    error_data = load_json_data("data/map_error.json")

    mock_post = mocker.patch("server.clients.groups.requests.post")
    mock_post.return_value.text = MapError.model_validate(error_data).model_dump_json()
    mock_post.return_value.status_code = 400

    original_func = inspect.unwrap(groups.post)
    result = original_func(group, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_post_http_error(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in post."""
    json_data, group = group_data

    mock_post = mocker.patch("server.clients.groups.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_post.return_value.status_code = 401

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        groups.post(group, include=None, exclude=None, access_token="token", client_secret="secret")


def test_put_by_id_success(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that a group is updated successfully via put_by_id."""
    json_data, group = group_data

    expected_result: MapGroup = group
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{json_data['id']}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    mocker.patch("server.clients.groups.search.clear_cache")

    mock_put = mocker.patch("server.clients.groups.requests.put")
    mock_put.return_value.text = json.dumps(json_data)
    mock_put.return_value.status_code = 200
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")
    original_func = inspect.unwrap(groups.put_by_id)

    result = original_func(group, access_token="token", client_secret="secret")

    mock_put.assert_called_once()
    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["json"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["json"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result
    clear_id.assert_called_once_with(group.id)


def test_put_by_id_with_include(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that include params are reflected in put_by_id and partial response is handled."""
    json_data, group = group_data

    include = {"display_name", "description"}

    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_result: MapGroup = MapGroup.model_validate(response_data)
    expected_attributes = set(include)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{json_data['id']}"
    mocker.patch("server.clients.groups.get_by_id", return_value=group)
    mock_put = mocker.patch("server.clients.groups.requests.put")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.groups.search.clear_cache")
    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = 200
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    original_func = inspect.unwrap(groups.put_by_id)
    result = original_func(group, include=include, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result
    clear_id.assert_called_once_with(group.id)


def test_put_by_id_with_exclude(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that exclude params are reflected in put_by_id and excluded fields are missing."""
    json_data, group = group_data

    exclude = {"meta"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_result: MapGroup = MapGroup.model_validate(response_data)
    expected_excluded = {"meta"}
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{json_data['id']}"
    mocker.patch("server.clients.groups.get_by_id", return_value=group)
    mock_put = mocker.patch("server.clients.groups.requests.put")
    mocker.patch("server.clients.groups.search.clear_cache")
    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = 200
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")
    original_func = inspect.unwrap(groups.put_by_id)
    result = original_func(group, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result
    clear_id.assert_called_once_with(group.id)


def test_put_by_id_with_all_params(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Tests put_by_id with all parameter types (include/exclude)."""
    json_data, group = group_data
    include = {"display_name", "description"}
    exclude = {"meta"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_attributes = set(include)
    expected_excluded = set(exclude)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{json_data['id']}"

    mocker.patch("server.clients.groups.get_by_id", return_value=group)
    mock_put = mocker.patch("server.clients.groups.requests.put")
    mocker.patch("server.clients.groups.search.clear_cache")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = 200
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    original_func = inspect.unwrap(groups.put_by_id)
    result = original_func(group, include=include, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")
    expected_result: MapGroup = MapGroup.model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result
    clear_id.assert_called_once_with(group.id)


def test_put_by_id_status_400_returns_maperror(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that when status_code=400, MapError is returned in put_by_id"""
    _, group = group_data
    error_data = load_json_data("data/map_error.json")
    mock_put = mocker.patch("server.clients.groups.requests.put")
    mock_put.return_value.text = MapError.model_validate(error_data).model_dump_json()
    mock_put.return_value.status_code = 400
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    result = groups.put_by_id(group, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    clear_id.assert_not_called()


def test_put_by_id_http_error(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in put_by_id."""
    json_data, group = group_data

    mock_put = mocker.patch("server.clients.groups.requests.put")
    mock_put.return_value.text = json.dumps(json_data)
    mock_put.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_put.return_value.status_code = 401
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        groups.put_by_id(group, access_token="token", client_secret="secret")
    clear_id.assert_not_called()


def test_patch_by_id_success(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that a group is patched successfully via patch_by_id."""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    operations: list[PatchOperation[MapGroup]] = [ReplaceOperation(op="replace", path="displayName", value="NewName")]
    expected_result: MapGroup = MapGroup.model_validate(json_data)
    expected_payload = PatchRequestPayload(operations=operations).model_dump(
        mode="json", by_alias=True, exclude_unset=False
    )
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"
    mock_patch = mocker.patch("server.clients.groups.requests.patch")
    mocker.patch("server.clients.groups.search.clear_cache")
    mock_patch.return_value.text = json.dumps(json_data)
    mock_patch.return_value.status_code = 200

    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")
    original_func = inspect.unwrap(groups.patch_by_id)

    result = original_func(group_id, operations, access_token="token", client_secret="secret")
    mock_patch.assert_called_once()
    call_args, called_kwargs = mock_patch.call_args
    expected_request = called_kwargs["json"].get("request")
    expected_json = {"request": expected_request} | expected_payload

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert expected_request is not None
    assert called_kwargs["json"] == expected_json
    assert isinstance(result, MapGroup)
    assert result == expected_result
    clear_id.assert_called_once_with(group_id)


def test_patch_by_id_with_include(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that include params are reflected in patch_by_id and partial response is handled."""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    include = {"display_name", "description"}
    operations = [ReplaceOperation(op="replace", path="displayName", value="NewName")]

    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_result: MapGroup = MapGroup.model_validate(response_data)
    expected_attributes = set(include)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"
    mock_patch = mocker.patch("server.clients.groups.requests.patch")
    mocker.patch("server.clients.groups.search.clear_cache")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200

    mocker.patch("server.clients.groups.get_by_id.clear_cache")
    original_func = inspect.unwrap(groups.patch_by_id)

    result = original_func(group_id, operations, include=include, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_patch.call_args
    expected_request = called_kwargs["json"].get("request")
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert expected_request is not None
    assert called_kwargs["json"]["request"] == expected_request
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_patch_by_id_with_exclude(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that exclude params are reflected in patch_by_id and excluded fields are missing."""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    exclude = {"meta"}
    operations = [ReplaceOperation(op="replace", path="displayName", value="NewName")]
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_result: MapGroup = MapGroup.model_validate(response_data)
    expected_excluded = {"meta"}
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"

    mock_patch = mocker.patch("server.clients.groups.requests.patch")
    mocker.patch("server.clients.groups.search.clear_cache")
    mocker.patch("server.clients.groups.get_by_id.clear_cache")
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)

    original_func = inspect.unwrap(groups.patch_by_id)
    result = original_func(group_id, operations, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_patch.call_args
    expected_request = called_kwargs["json"].get("request")
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert expected_request is not None
    assert called_kwargs["json"]["request"] == expected_request
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_patch_by_id_with_all_params(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Tests patch_by_id with all parameter types (include/exclude)."""
    json_data, _ = group_data
    group_id = json_data["id"]
    include = {"display_name", "description"}
    exclude = {"meta"}
    operations = [ReplaceOperation(op="replace", path="displayName", value="NewName")]
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "displayName": json_data["displayName"],
    }
    expected_attributes = set(include)
    expected_excluded = set(exclude)
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"

    mocker.patch("server.clients.groups.get_by_id.clear_cache")
    mocker.patch("server.clients.groups.search.clear_cache")
    mock_patch = mocker.patch("server.clients.groups.requests.patch")
    mocker.patch.object(groups, "alias_generator", side_effect=lambda x: x)
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200

    original_func = inspect.unwrap(groups.patch_by_id)
    result = original_func(
        group_id, operations, include=include, exclude=exclude, access_token="token", client_secret="secret"
    )

    call_args, called_kwargs = mock_patch.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_result: MapGroup = MapGroup.model_validate(result.model_dump())
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, MapGroup)
    assert result == expected_result


def test_patch_by_id_status_400_returns_maperror(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that when status_code=400, MapError is returned in patch_by_id"""
    json_data, _ = group_data
    group_id: str = json_data["id"]
    operations = [ReplaceOperation(op="replace", path="displayName", value="NewName")]
    error_data = load_json_data("data/map_error.json")
    mock_patch = mocker.patch("server.clients.groups.requests.patch")
    mock_patch.return_value.text = MapError.model_validate(error_data).model_dump_json()
    mock_patch.return_value.status_code = 400
    original_func = inspect.unwrap(groups.patch_by_id)
    result = original_func(group_id, operations, access_token="token", client_secret="secret")
    assert isinstance(result, MapError)


def test_patch_by_id_http_error(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in patch_by_id."""
    json_data, _ = group_data

    operations = [ReplaceOperation(op="replace", path="displayName", value="NewName")]
    group_id = json_data["id"]
    mock_patch = mocker.patch("server.clients.groups.requests.patch")
    mock_patch.return_value.text = json.dumps(json_data)
    mock_patch.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_patch.return_value.status_code = 401
    mocker.patch("server.clients.groups.get_by_id.clear_cache")

    original_func = inspect.unwrap(groups.patch_by_id)
    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(group_id, operations, access_token="token", client_secret="secret")


def test_delete_by_id_success(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that a group is deleted successfully via delete_by_id."""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_GROUPS_ENDPOINT}/{group_id}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    mocker.patch("server.clients.groups.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.groups.compute_signature", return_value=signature)
    mocker.patch("server.clients.groups.search.clear_cache")
    mock_delete = mocker.patch("server.clients.groups.requests.delete")
    mock_delete.return_value.text = ""
    mock_delete.return_value.status_code = 200
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    result = groups.delete_by_id(group_id, access_token="token", client_secret="secret")

    mock_delete.assert_called_once()
    call_args, called_kwargs = mock_delete.call_args

    assert call_args[0] == expected_requests_url
    assert called_kwargs["params"] == expected_params
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert result is None
    clear_id.assert_called_once_with(group_id)


def test_delete_by_id_status_400_returns_maperror(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that when status_code=400, MapError is returned in delete_by_id"""
    json_data, _ = group_data
    group_id: str = json_data["id"]
    error_data = load_json_data("data/map_error.json")
    mock_delete = mocker.patch("server.clients.groups.requests.delete")
    mock_delete.return_value.text = MapError.model_validate(error_data).model_dump_json()
    mock_delete.return_value.status_code = 400
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    original_func = inspect.unwrap(groups.delete_by_id)
    result = original_func(group_id, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    clear_id.assert_not_called()


def test_delete_by_id_http_error(app: Flask, mocker: MockerFixture, group_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in delete_by_id."""
    json_data, _ = group_data

    group_id: str = json_data["id"]
    mock_delete = mocker.patch("server.clients.groups.requests.delete")
    mock_delete.return_value.text = json.dumps(json_data)
    mock_delete.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_delete.return_value.status_code = 401
    clear_id = mocker.patch("server.clients.groups.get_by_id.clear_cache")

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        groups.delete_by_id(group_id, access_token="token", client_secret="secret")

    clear_id.assert_not_called()


def test_handle_group_updated_clears_cache(group_data, mocker):
    """Covers get_by_id.clear_cache(group_id) branch for handle_group_updated_by_id."""
    _, group = group_data

    group: MapGroup = MapGroup(id="group123", display_name="Test Group")
    original_func = inspect.unwrap(groups.handle_group_updated)
    original_func(_sender=None, group_id=group)


def test_handle_group_updated_by_id_clears_cache(mocker):
    """Covers get_by_id.clear_cache(group_id) branch for handle_group_updated_by_id."""
    mock_clear = mocker.patch("server.clients.groups.get_by_id.clear_cache")
    group_id = "group123"
    original_func = inspect.unwrap(groups.handle_group_updated_by_id)
    original_func(_sender=None, group_id=group_id)
    mock_clear.assert_called_once_with(group_id)


def test_handle_group_updated_by_ids_clears_cache(mocker):
    """Covers get_by_id.clear_cache(*group_ids) branch for handle_group_updated_by_ids."""
    mock_clear = mocker.patch("server.clients.groups.get_by_id.clear_cache")
    group_ids = ["group1", "group2"]

    original_func = inspect.unwrap(groups.handle_group_updated_by_ids)
    original_func(_sender=None, group_ids=group_ids)
    mock_clear.assert_called_once_with(*group_ids)


def test__get_alias_generator_with_serialization_alias_groups(monkeypatch):
    """Covers the branch where generator has serialization_alias attribute for groups."""

    class Dummy:
        def __init__(self):
            self.serialization_alias = lambda x: f"alias_{x}"

    monkeypatch.setitem(MapGroup.model_config, "alias_generator", Dummy())
    importlib.reload(groups)
    result = groups.alias_generator
    assert callable(result)
    assert result("foo") == "alias_foo"


def test__get_alias_generator_with_none_groups(monkeypatch):
    """Covers the branch where generator is None and falls back to lambda x: x for groups."""

    monkeypatch.setitem(MapGroup.model_config, "alias_generator", None)
    importlib.reload(groups)
    result = groups.alias_generator
    assert callable(result)
    assert result("bar") == "bar"


@pytest.mark.parametrize(
    ("is_logged_in", "is_admin", "permitted", "expected"),
    [
        (False, False, [], "by_anonymous"),
        (True, True, [], "by_system_admin"),
        (True, False, ["repo1", "repo2"], "repo1,repo2"),
        (True, False, [], ""),
    ],
    ids=["not_logged_in", "system_admin", "permitted_repos", "empty_permitted"],
)
def test_search_cache_identifier_groups(mocker, is_logged_in, is_admin, permitted, expected):

    current_user = LoginUser(
        eppn="dummy",
        is_member_of="system_admin" if is_admin else "",
        user_name="dummy",
        map_id="dummy",
        session_id="dummy",
    )
    mocker.patch.object(
        type(current_user),
        "is_system_admin",
        new=property(lambda _: is_admin),
    )
    mocker.patch.object(
        type(current_user),
        "permitted_repositories",
        new=property(lambda _: set(permitted)),
    )
    mocker.patch("server.clients.groups.current_user", current_user)
    mocker.patch("server.clients.groups.is_user_logged_in", return_value=is_logged_in)
    result = groups._search_cache_identifier()  # noqa: SLF001
    assert result == expected
