import hashlib
import importlib
import json
import time
import typing as t

from http import HTTPStatus

import pytest

from requests.exceptions import HTTPError

import server.clients.users as users_mod

from server.clients import users
from server.clients.users import handle_user_updated_by_eppn, handle_user_updated_by_id
from server.config import config
from server.const import MAP_EXIST_EPPN_ENDPOINT, MAP_PATCH_SCHEMA, MAP_USERS_ENDPOINT
from server.entities.login_user import LoginUser
from server.entities.map_error import MapError
from server.entities.map_user import MapUser
from server.entities.patch_request import AddOperation, PatchOperation, PatchRequestPayload, ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse
from tests.helpers import load_json_data, unwrap


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


def test_search_success(app: Flask, mocker: MockerFixture) -> None:
    """Test that search returns a SearchResponse[MapUser] with correct params."""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    access_token = "token"
    client_secret = "secret"
    time_stamp: str = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": filter_string,
        "startIndex": None,
        "count": None,
        "sortBy": None,
        "sortOrder": None,
    }

    user = MapUser.model_validate({"id": "u1", "schemas": ["a"], "userName": "u", "emails": []})
    response = SearchResponse[MapUser](
        total_results=1,
        items_per_page=1,
        start_index=1,
        resources=[user],
    )
    expected_result: SearchResponse[MapUser] = response
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = response.model_dump_json()
    mock_get.return_value.status_code = 200

    original_func = unwrap(users.search)

    result = original_func(
        query,
        access_token=access_token,
        client_secret=client_secret,
    )
    mock_get.assert_called_once()
    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_with_include(app: Flask, mocker: MockerFixture) -> None:
    """Test that include params are reflected in search and partial response is handled."""
    count_number = 5
    query = SearchRequestParameter(count=count_number)
    include = {"user_name", "email"}
    access_token = "token"
    client_secret = "secret"
    time_stamp: str = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "u1", "schemas": ["a"], "userName": "u", "emails": [{"value": "mail@example.com"}]}],
    }
    expected_result: SearchResponse[MapUser] = SearchResponse[MapUser].model_validate(response_data)
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": None,
        "startIndex": None,
        "count": count_number,
        "sortBy": None,
        "sortOrder": None,
    }
    expected_attributes = include | {"id"}

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = unwrap(users.search)
    result = original_func(
        query,
        include=include,
        access_token=access_token,
        client_secret=client_secret,
    )
    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_with_exclude(app: Flask, mocker: MockerFixture) -> None:
    """Test that exclude params are reflected in search and excluded fields are missing."""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    exclude = {"meta"}
    access_token = "token"
    client_secret = "secret"
    time_stamp: str = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "u1", "schemas": ["a"], "userName": "u", "emails": [{"value": "mail@example.com"}]}],
    }
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_excluded = set(exclude)
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
        "filter": filter_string,
        "startIndex": None,
        "count": None,
        "sortBy": None,
        "sortOrder": None,
    }
    expected_result: SearchResponse[MapUser] = SearchResponse[MapUser].model_validate(response_data)

    mock_get = mocker.patch("server.clients.users.requests.get")
    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = unwrap(users.search)
    result = original_func(
        query,
        exclude=exclude,
        access_token=access_token,
        client_secret=client_secret,
    )
    call_args, called_kwargs = mock_get.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded
    assert isinstance(result, SearchResponse)
    assert result == expected_result


def test_search_status_400_returns_maperror(app: Flask, mocker: MockerFixture) -> None:
    """Test that MapError is returned when the search result is not found."""

    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    access_token = "token"
    client_secret = "secret"
    error_data = load_json_data("data/map_error.json")
    expected_error = MapError.model_validate(error_data | {"detail": error_data["detail"] % "search_query"})

    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = expected_error.model_dump_json()
    mock_get.return_value.status_code = 400
    original_func = unwrap(users.search)
    result = original_func(query, access_token=access_token, client_secret=client_secret)
    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_search_http_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that HTTP errors are raised when status_code > 400."""
    filter_string = 'displayName eq "Test Group"'
    query = SearchRequestParameter(filter=filter_string)
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.status_code = 401
    mock_get.return_value.raise_for_status.side_effect = Exception("401 Unauthorized")
    original_func = unwrap(users.search)
    with pytest.raises(Exception, match="401 Unauthorized"):
        original_func(query, access_token="token", client_secret="secret")


def test_get_by_id_success(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that a user is returned when a valid user_id is provided."""
    json_data, _ = user_data

    expected_user = MapUser.model_validate(json_data)
    user_id: str = json_data["id"]
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()

    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.users.requests.get")
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(users.get_by_id)
    result = original_func(user_id, access_token="token", client_secret="secret")
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
    assert isinstance(result, MapUser)
    assert result == expected_user


def test_get_by_id_with_include(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that include params are reflected in attributes_params for get_by_id and partial response is handled."""
    json_data, _ = user_data

    user_id: str = json_data["id"]
    include = {"user_name", "email"}
    signature = hashlib.sha256(b"hash").hexdigest()

    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }
    expected_params = {
        "time_stamp": str(int(time.time())),
        "signature": signature,
    }
    expected_attributes = {"email", "id", "user_name"}
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_response = mocker.patch("server.clients.users.requests.get")
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(users.get_by_id)
    result = original_func(user_id, include=include, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == expected_attributes
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]


def test_get_by_id_with_exclude(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that exclude params are reflected in attributes_params for get_by_id and excluded fields are missing."""
    json_data, _ = user_data

    user_id = json_data["id"]
    exclude = {"preferredLanguage"}
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }

    expect_params = {
        "signature": signature,
        "time_stamp": str(int(time.time())),
    }
    expected_excluded_attributes = "preferredLanguage"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expect_result = MapUser(**response_data, preferred_language=None)
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.users.requests.get")
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(users.get_by_id)
    result = original_func(user_id, exclude=exclude, access_token="token", client_secret="secret")
    mock_response.assert_called_once()
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expect_params
    assert called_params_attributes is None
    assert called_params_excluded_attributes == expected_excluded_attributes
    assert isinstance(result, MapUser)
    assert result == expect_result


def test_get_by_id_not_found(app: Flask, mocker: MockerFixture) -> None:
    """Test that None is returned when the user is not found (404)."""
    json_data = load_json_data("data/map_error.json")

    user_id = "nonexistent_user"
    expected_error = MapError.model_validate(json_data | {"detail": json_data["detail"] % user_id})

    mock_response = mocker.patch("server.clients.users.requests.get")
    mock_response.return_value.text = expected_error.model_dump_json()
    mock_response.return_value.status_code = 404

    original_func = unwrap(users.get_by_id)
    result = original_func(user_id, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_get_by_id_http_error(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that HTTP errors are raised when status_code > 400."""
    json_data, _ = user_data

    user_id: str = json_data["id"]
    mock_response = mocker.patch("server.clients.users.requests.get")
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_response.return_value.status_code = 401

    original_func = unwrap(users.get_by_id)
    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(user_id, access_token="token", client_secret="secret")


def test_get_by_eppn_success(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that a user is returned when a valid eppn is provided."""
    json_data, _ = user_data

    expected_user = MapUser.model_validate(json_data)
    eppn: str = json_data["eduPersonPrincipalNames"][0]["value"]
    access_token = "token"
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_EXIST_EPPN_ENDPOINT}/{eppn}"

    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_params = {
        "time_stamp": str(int(time.time())),
        "signature": signature,
    }

    mocker.patch("server.clients.users.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.users.requests.get")
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(users.get_by_eppn)
    result = original_func(eppn, access_token=access_token, client_secret="secret")
    mock_response.assert_called_once()
    call_args, called_kwargs = mock_response.call_args

    assert isinstance(result, MapUser)
    assert result.schemas == expected_user.schemas
    assert result.id == expected_user.id
    assert result.external_id == expected_user.external_id
    assert result.user_name == expected_user.user_name
    assert result.preferred_language == expected_user.preferred_language
    assert result.meta == expected_user.meta
    assert result.edu_person_principal_names == expected_user.edu_person_principal_names
    assert result.emails == expected_user.emails
    assert result.groups == expected_user.groups

    assert call_args[0] == expected_requests_url
    assert called_kwargs["params"] == expected_params
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_get_by_eppn_with_includ(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that include params are reflected in attributes_params for get_by_eppn and partial response is handled."""
    json_data, _ = user_data

    eppn = json_data["eduPersonPrincipalNames"][0]["value"]
    include = {"user_name", "email"}
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }

    expected_params = {
        "attributes": "email,id,user_name",
        "time_stamp": str(int(time.time())),
        "signature": signature,
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_EXIST_EPPN_ENDPOINT}/{eppn}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200

    original_func = unwrap(users.get_by_eppn)
    result = original_func(eppn, include=include, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_get.call_args
    actual_attributes = called_kwargs["params"]["attributes"].split(",")

    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]
    assert call_args[0] == expected_requests_url
    assert set(actual_attributes) == set(expected_params["attributes"].split(","))
    assert called_kwargs["params"]["time_stamp"] == expected_params["time_stamp"]
    assert called_kwargs["params"]["signature"] == expected_params["signature"]
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_get_by_eppn_with_exclude(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that exclude params are reflected in attributes_params for get_by_eppn and excluded fields are missing."""
    json_data, _ = user_data

    eppn = json_data["eduPersonPrincipalNames"][0]["value"]
    exclude = {"preferredLanguage"}
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }

    expected_params = {
        "time_stamp": str(int(time.time())),
        "signature": signature,
        "excluded_attributes": "preferredLanguage",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_EXIST_EPPN_ENDPOINT}/{eppn}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200

    original_func = unwrap(users.get_by_eppn)
    result = original_func(eppn, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_get.call_args
    actual_excluded = called_kwargs["params"]["excluded_attributes"].split(",")

    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]
    assert result.preferred_language is None

    assert call_args[0] == expected_requests_url
    assert set(actual_excluded) == set(expected_params["excluded_attributes"].split(","))
    assert called_kwargs["params"]["time_stamp"] == expected_params["time_stamp"]
    assert called_kwargs["params"]["signature"] == expected_params["signature"]
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_get_by_eppn_400_returns_maperror(app: Flask, mocker: MockerFixture) -> None:
    """Test that MapError is returned when the user is not found (400) for get_by_eppn."""
    json_data = load_json_data("data/map_error.json")

    eppn = "nonexistent_eppn@example.com"
    expected_error = MapError.model_validate(json_data | {"detail": json_data["detail"] % eppn})

    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = expected_error.model_dump_json()
    mock_get.return_value.status_code = 400

    original_func = unwrap(users.get_by_eppn)
    result = original_func(eppn, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_get_by_eppn_http_error(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Tests that HTTP errors are raised when status_code > 400 in get_by_eppn."""
    json_data, _ = user_data

    eppn = json_data["eduPersonPrincipalNames"][0]["value"]
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = json.dumps(json_data)
    mock_get.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_get.return_value.status_code = 401

    original_func = unwrap(users.get_by_eppn)
    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(eppn, access_token="token", client_secret="secret")


def test_post_success(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that a user is created successfully via post."""
    json_data, user = user_data

    expected_user = MapUser.model_validate(json_data)
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()

    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_post = mocker.patch("server.clients.users.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.status_code = 200

    original_func = unwrap(users.post)
    result = original_func(user, include=None, exclude=None, access_token="token", client_secret="secret")
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
    assert isinstance(result, MapUser)
    assert result.schemas == expected_user.schemas
    assert result.id == expected_user.id
    assert result.external_id == expected_user.external_id
    assert result.user_name == expected_user.user_name
    assert result.preferred_language == expected_user.preferred_language
    assert result.meta == expected_user.meta
    assert result.edu_person_principal_names == expected_user.edu_person_principal_names
    assert result.emails == expected_user.emails
    assert result.groups == expected_user.groups


def test_post_with_include(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that include/exclude params are reflected in post and partial response is handled."""
    json_data, user = user_data

    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    include = {"user_name", "email"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }

    expected_params = {}

    expected_attributes = include
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_post = mocker.patch("server.clients.users.requests.post")
    mock_post.return_value.text = json.dumps(response_data)
    mock_post.return_value.status_code = 200

    original_func = unwrap(users.post)
    result = original_func(user, include=include, exclude=None, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_post.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert set(called_params_attributes.split(",")) == (set(expected_attributes))
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]


def test_post_with_exclude(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that exclude params are reflected in attributes_params for post and excluded fields are missing."""
    json_data, user = user_data

    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    exclude = {"preferredLanguage"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }

    expected_params = {}
    expected_excluded_attributes = {"preferredLanguage"}

    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_response = mocker.patch("server.clients.users.requests.post")
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    result = users.post(user, include=None, exclude=exclude, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_response.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == expected_params
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == expected_excluded_attributes
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]
    assert result.preferred_language is None


def test_post_400_returns_maperror(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that MapError is returned when the user is not found (400)."""
    json_data = load_json_data("data/map_error.json")

    mock_post = mocker.patch("server.clients.users.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.status_code = 400

    _, user = user_data
    result = users.post(user, include=None, exclude=None, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_post_http_error(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that HTTP errors are raised when status_code > 400."""
    json_data = load_json_data("data/map_error.json")

    mock_post = mocker.patch("server.clients.users.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_post.return_value.status_code = 401

    json_data, user = user_data
    with pytest.raises(HTTPError, match="401 Unauthorized"):
        users.post(user, access_token="token", client_secret="secret")


def test_put_by_id_success(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that a user is updated successfully via put_by_id."""
    json_data, user = user_data

    expected_user: MapUser = MapUser.model_validate(json_data)
    signature: str = hashlib.sha256(b"hash").hexdigest()

    expected_requests_url: str = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{json_data['id']}"
    expected_headers: dict[str, str] = {"Authorization": "Bearer token"}
    expected_timeout: int = config.MAP_CORE.timeout
    expected_emails = (json_data["eduPersonPrincipalNames"][0]["value"],)

    mocker.patch("server.clients.users.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_put = mocker.patch("server.clients.users.requests.put")
    mocker.patch("server.clients.users.search.clear_cache")
    mock_put.return_value.text = json.dumps(json_data)
    mock_put.return_value.status_code = 200

    clear_id = mocker.patch("server.clients.users.get_by_id.clear_cache")
    clear_eppn = mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    original_func = unwrap(users.put_by_id)
    result: MapUser = original_func(user, access_token="token", client_secret="secret")
    mock_put.assert_called_once()
    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {}
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert isinstance(result, MapUser)
    assert result.schemas == expected_user.schemas
    assert result.id == expected_user.id
    assert result.external_id == expected_user.external_id
    assert result.user_name == expected_user.user_name
    assert result.preferred_language == expected_user.preferred_language
    assert result.meta == expected_user.meta
    assert result.edu_person_principal_names == expected_user.edu_person_principal_names
    assert result.emails == expected_user.emails
    assert result.groups == expected_user.groups

    clear_id.assert_called_once_with(user.id)
    clear_eppn.assert_called_once()
    assert clear_id.call_count == 1
    assert clear_id.call_args[0][0] == user.id
    assert clear_eppn.call_count == 1
    assert clear_eppn.call_args[0] == expected_emails


def test_put_by_id_with_include(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that include params are reflected in put_by_id and partial response is handled."""
    json_data, user = user_data

    time_stamp: str = str(int(time.time()))
    signature: str = hashlib.sha256(b"hash").hexdigest()
    include: set[str] = {"user_name", "email"}

    response_data: dict[str, t.Any] = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }
    expected_params = {
        "attributes": ["email", "user_name"],
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url: str = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{json_data['id']}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.users.search.clear_cache")
    mock_put = mocker.patch("server.clients.users.requests.put")
    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = 200
    mocker.patch("server.clients.users.get_by_id.clear_cache")
    mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    original_func = unwrap(users.put_by_id)
    result: MapUser = original_func(user, include=include, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert set(called_params_attributes.split(",")) == set(expected_params["attributes"])
    assert called_params_excluded_attributes is None
    assert called_kwargs["params"] == {k: v for k, v in expected_params.items() if k != "attributes"}
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]


def test_put_by_id_with_exclude(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that exclude params are reflected in put_by_id and excluded fields are missing."""
    json_data, user = user_data

    time_stamp: str = str(int(time.time()))
    signature: str = hashlib.sha256(b"hash").hexdigest()
    exclude: set[str] = {"preferredLanguage"}
    response_data: dict[str, t.Any] = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }

    expected_params = {
        "excluded_attributes": "preferredLanguage",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url: str = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{json_data['id']}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_put = mocker.patch("server.clients.users.requests.put")
    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = 200
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.users.get_by_id.clear_cache")
    mocker.patch("server.clients.users.get_by_eppn.clear_cache")
    mocker.patch("server.clients.users.search.clear_cache")

    original_func = unwrap(users.put_by_id)
    result: MapUser = original_func(user, exclude=exclude, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_put.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes")
    expected_excluded = expected_params["excluded_attributes"].split(",")

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {k: v for k, v in expected_params.items() if k != "excluded_attributes"}
    assert called_params_attributes is None
    assert set(called_params_excluded_attributes.split(",")) == set(expected_excluded)
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]
    assert result.preferred_language is None


def test_put_by_id_400_returns_maperror(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that MapError is returned when the user is not found (400) from put_by_id."""
    json_error_data: dict[str, t.Any] = load_json_data("data/map_error.json")

    mock_put = mocker.patch("server.clients.users.requests.put")
    mock_put.return_value.text = json.dumps(json_error_data)
    mock_put.return_value.status_code = 400

    _, user = user_data
    result = users.put_by_id(user, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_put_by_id_http_error(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in put_by_id."""
    json_data, user = user_data

    mock_put = mocker.patch("server.clients.users.requests.put")
    mock_put.return_value.text = json.dumps(json_data)
    mock_put.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_put.return_value.status_code = 401

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        users.put_by_id(user, access_token="token", client_secret="secret")


def test_put_by_id_does_not_clear_cache_on_error(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that put_by_id does NOT clear cache when MapError is returned."""
    error_data: dict[str, t.Any] = load_json_data("data/map_error.json")

    mock_put = mocker.patch("server.clients.users.requests.put")
    mock_put.return_value.text = json.dumps(error_data)
    mock_put.return_value.status_code = 200

    clear_id = mocker.patch("server.clients.users.get_by_id.clear_cache")
    clear_eppn = mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    _, user = user_data
    result = users.put_by_id(user, access_token="token", client_secret="secret")
    assert isinstance(result, MapError)
    clear_id.assert_not_called()
    clear_eppn.assert_not_called()


def test_patch_by_id_success(app: Flask, mocker: MockerFixture, user_data) -> None:  # noqa: PLR0915
    """Test that a user is patched successfully via patch_by_id."""
    json_data, _ = user_data
    user_id: str = json_data["id"]
    operations = [ReplaceOperation(op="replace", path="nickName", value="Tomy")]
    expected_user: MapUser = MapUser.model_validate(json_data)
    expected_eppn = (json_data["eduPersonPrincipalNames"][0]["value"],)
    expected_payload = PatchRequestPayload(operations=operations).model_dump(  # type: ignore  # noqa: PGH003
        mode="json", by_alias=True, exclude_unset=False
    )
    time_stamp: str = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_request = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}"

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_patch = mocker.patch("server.clients.users.requests.patch")
    mock_patch.return_value.text = json.dumps(json_data)
    mock_patch.return_value.status_code = 200
    mocker.patch("server.clients.users.search.clear_cache")

    clear_id = mocker.patch("server.clients.users.get_by_id.clear_cache")
    clear_eppn = mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    original_func = unwrap(users.patch_by_id)
    result: MapUser = original_func(user_id, operations, access_token="token", client_secret="secret")
    mock_patch.assert_called_once()
    call_args, called_kwargs = mock_patch.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_json = {"request": expected_request} | expected_payload

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {}
    assert called_params_attributes is None
    assert called_params_excluded_attributes is None
    assert called_kwargs["json"] == expected_json
    assert isinstance(result, MapUser)
    assert result.schemas == expected_user.schemas
    assert result.id == expected_user.id
    assert result.external_id == expected_user.external_id
    assert result.user_name == expected_user.user_name
    assert result.preferred_language == expected_user.preferred_language
    assert result.meta == expected_user.meta
    assert result.edu_person_principal_names == expected_user.edu_person_principal_names
    assert result.emails == expected_user.emails
    assert result.groups == expected_user.groups

    clear_id.assert_called_once_with(user_id)
    clear_eppn.assert_called_once()
    assert clear_id.call_count == 1
    assert clear_id.call_args[0][0] == user_id
    assert clear_eppn.call_count == 1
    assert clear_eppn.call_args[0] == expected_eppn


def test_patch_by_id_with_include(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that include params are reflected in patch_by_id and partial response is handled."""
    json_data, _ = user_data

    user_id: str = json_data["id"]
    include = {"user_name", "email"}
    time_stamp: str = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    operations = [ReplaceOperation(op="replace", path="nickName", value="Tomy")]
    expected_request = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }
    expected_params = {
        "attributes": ["email", "user_name"],
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}"
    expected_payload = PatchRequestPayload(operations=operations).model_dump(  # type: ignore  # noqa: PGH003
        mode="json", by_alias=True, exclude_unset=False
    )

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=signature)
    mock_patch = mocker.patch("server.clients.users.requests.patch")
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200
    mocker.patch("server.clients.users.search.clear_cache")

    mocker.patch("server.clients.users.get_by_id.clear_cache")
    mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    original_func = unwrap(users.patch_by_id)
    result: MapUser = original_func(user_id, operations, include=include, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_patch.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes")
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_json = {"request": expected_request} | expected_payload

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert set(called_params_attributes.split(",")) == set(expected_params["attributes"])
    assert called_params_excluded_attributes is None
    assert called_kwargs["params"] == {k: v for k, v in expected_params.items() if k != "attributes"}
    assert expected_request is not None
    assert called_kwargs["json"] == expected_json
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]


def test_patch_by_id_with_exclude(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that exclude params are reflected in patch_by_id and excluded fields are missing."""
    json_data, _ = user_data

    user_id: str = json_data["id"]
    exclude = {"preferredLanguage"}
    time_stamp: str = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()

    expected_request = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    operations: list[PatchOperation] = [AddOperation(path="emails", value={"value": "john_doe@example.com"})]
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "userName": json_data["userName"],
        "emails": json_data["emails"],
    }
    expected_params = {
        "excluded_attributes": "preferredLanguage",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_USERS_ENDPOINT}/{user_id}"
    expected_payload = {
        "schemas": [MAP_PATCH_SCHEMA],
        "Operations": [{"op": "add", "path": "emails", "value": {"value": "john_doe@example.com"}}],
    }
    expected_json = {"request": expected_request} | expected_payload

    mocker.patch("server.clients.users.get_by_id.clear_cache")
    mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=hashlib.sha256(b"hash").hexdigest())
    mock_patch = mocker.patch("server.clients.users.requests.patch")
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.users.search.clear_cache")

    original_func = unwrap(users.patch_by_id)
    result: MapUser = original_func(user_id, operations, exclude=exclude, access_token="token", client_secret="secret")
    call_args, called_kwargs = mock_patch.call_args
    called_params_attributes = called_kwargs["params"].pop("attributes", None)
    called_params_excluded_attributes = called_kwargs["params"].pop("excluded_attributes", None)
    expected_json = {"request": expected_request} | expected_payload

    assert call_args[0] == expected_requests_url
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["params"] == {k: v for k, v in expected_params.items() if k != "excluded_attributes"}
    assert called_params_attributes is None
    assert called_params_excluded_attributes is not None
    assert set(called_params_excluded_attributes.split(",")) == set(expected_params["excluded_attributes"].split(","))
    assert expected_request is not None
    assert called_kwargs["json"] == expected_json
    assert isinstance(result, MapUser)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.user_name == response_data["userName"]
    assert result.emails
    assert result.emails[0].value == response_data["emails"][0]["value"]


def test_patch_by_id_status_400_returns_maperror(app: Flask, mocker: MockerFixture) -> None:
    """Test that MapError is returned when error response is received from patch_by_id."""
    error_data: dict[str, t.Any] = load_json_data("data/map_error.json")
    operations: list[PatchOperation] = [AddOperation(path="emails", value={"value": "john_doe@example.com"})]

    user_id = "dummy_id"
    mock_patch = mocker.patch("server.clients.users.requests.patch")
    mock_patch.return_value.text = json.dumps(error_data)
    mock_patch.return_value.status_code = 400

    original_func = unwrap(users.patch_by_id)
    result = original_func(user_id, operations, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_patch_by_id_http_error(app: Flask, mocker: MockerFixture, user_data) -> None:
    """Test that HTTP errors are raised when status_code > 400 in patch_by_id."""
    json_data, _ = user_data
    operations: list[PatchOperation] = [ReplaceOperation(path="userName", value="Tomy")]
    user_id = json_data["id"]
    mock_patch = mocker.patch("server.clients.users.requests.patch")
    mock_patch.return_value.text = json.dumps(json_data)
    mock_patch.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_patch.return_value.status_code = 401

    mocker.patch("server.clients.users.get_by_id.clear_cache")
    mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    original_func = unwrap(users.patch_by_id)
    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(user_id, operations, access_token="token", client_secret="secret")


def test_patch_by_id_does_not_clear_cache_on_error(app: Flask, mocker: MockerFixture) -> None:
    """Test that patch_by_id does NOT clear cache when MapError is returned."""
    error_data: dict[str, t.Any] = load_json_data("data/map_error.json")
    operations: list[PatchOperation] = [AddOperation(path="emails", value={"value": "john_doe@example.com"})]
    user_id = "dummy_id"
    mock_patch = mocker.patch("server.clients.users.requests.patch")
    mock_patch.return_value.text = json.dumps(error_data)
    mock_patch.return_value.status_code = 200

    clear_id = mocker.patch("server.clients.users.get_by_id.clear_cache")
    clear_eppn = mocker.patch("server.clients.users.get_by_eppn.clear_cache")

    original_func = unwrap(users.patch_by_id)
    result = original_func(user_id, operations, access_token="token", client_secret="secret")
    assert isinstance(result, MapError)
    clear_id.assert_not_called()
    clear_eppn.assert_not_called()


@pytest.mark.parametrize(
    ("status_code", "response_json", "expected_type"),
    [
        (200, "data/map_user.json", MapUser),
        (400, "data/map_error.json", MapError),
        (404, "data/map_error.json", MapError),
    ],
    ids=["success", "bad_request", "not_found"],
)
def test_get_self_various_status(app: Flask, mocker: MockerFixture, status_code, response_json, expected_type):
    json_data = load_json_data(response_json)
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = json.dumps(json_data)
    mock_get.return_value.status_code = status_code
    time_stamp = str(int(time.time()))
    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=hashlib.sha256(b"hash").hexdigest())

    if status_code > HTTPStatus.BAD_REQUEST:
        mock_get.return_value.raise_for_status.side_effect = Exception("HTTP error")
        with pytest.raises(Exception, match="HTTP error"):
            users.get_self(access_token="token", client_secret="secret")
    else:
        result = users.get_self(access_token="token", client_secret="secret")
        assert isinstance(result, expected_type)


def test_get_self_with_include_exclude(app: Flask, mocker: MockerFixture):
    json_data = load_json_data("data/map_user.json")
    mock_get = mocker.patch("server.clients.users.requests.get")
    mock_get.return_value.text = json.dumps(json_data)
    mock_get.return_value.status_code = 200
    time_stamp = str(int(time.time()))
    mocker.patch("server.clients.users.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.users.compute_signature", return_value=hashlib.sha256(b"hash").hexdigest())
    mocker.patch.object(users, "alias_generator", side_effect=lambda x: x)

    include = {"user_name", "email"}
    exclude = {"meta"}
    result = users.get_self(include=include, exclude=exclude, access_token="token", client_secret="secret")
    assert isinstance(result, MapUser)


def test__get_alias_generator_with_serialization_alias(monkeypatch):
    """Covers the branch where generator has serialization_alias attribute."""

    class Dummy:
        def __init__(self):
            self.serialization_alias = lambda x: f"alias_{x}"

    monkeypatch.setitem(users_mod.MapUser.model_config, "alias_generator", Dummy())
    importlib.reload(users_mod)
    result = users_mod.alias_generator
    assert callable(result)
    assert result("foo") == "alias_foo"


def test__get_alias_generator_with_none(monkeypatch):
    """Covers the branch where generator is None and falls back to lambda x: x."""

    monkeypatch.setitem(users_mod.MapUser.model_config, "alias_generator", None)
    importlib.reload(users_mod)
    result = users_mod.alias_generator
    assert callable(result)
    assert result("bar") == "bar"


def test_handle_user_updated_by_eppn_clears_cache(mocker):
    """Covers get_by_eppn.clear_cache(*eppns) branch."""

    mock_clear = mocker.patch("server.clients.users.get_by_eppn.clear_cache")
    eppns = ["eppn1", "eppn2"]
    handle_user_updated_by_eppn(_sender=None, eppns=eppns)
    mock_clear.assert_called_once_with(*eppns)


def test_handle_user_updated_by_id_clears_cache(mocker):
    """Covers get_by_id.clear_cache(user_id) branch."""

    mock_clear = mocker.patch("server.clients.users.get_by_id.clear_cache")
    user_id = "user123"
    handle_user_updated_by_id(_sender=None, user_id=user_id)
    mock_clear.assert_called_once_with(user_id)


def test_handle_user_updated_returns_early_on_non_mapuser(mocker):
    """Covers the early return branch in handle_user_updated when user is not a MapUser instance."""
    mock_clear_id = mocker.patch("server.clients.users.get_by_id.clear_cache")
    mock_clear_eppn = mocker.patch("server.clients.users.get_by_eppn.clear_cache")
    users.handle_user_updated(_sender=None, user=None)
    mock_clear_id.assert_not_called()
    mock_clear_eppn.assert_not_called()


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
def test_search_cache_identifier(app, mocker, is_logged_in, is_admin, permitted, expected):

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
    mocker.patch("server.clients.users.current_user", current_user)
    mocker.patch("server.clients.users.is_user_logged_in", return_value=is_logged_in)
    result = users_mod._search_cache_identifier()  # noqa: SLF001
    assert result == expected


@pytest.fixture
def user_data() -> tuple[dict[str, t.Any], MapUser]:
    json_data = load_json_data("data/map_user.json")
    user = MapUser.model_validate(json_data)
    return json_data, user
