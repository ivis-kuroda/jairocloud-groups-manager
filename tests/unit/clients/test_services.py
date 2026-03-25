import hashlib
import importlib
import json
import time
import typing as t

from http import HTTPStatus
from unittest.mock import Mock

import pytest

from requests.exceptions import HTTPError

import server.clients.services as services_mod

from server.clients import services
from server.clients.services import handle_repository_updated, handle_repository_updated_by_id
from server.config import config
from server.const import MAP_SERVICES_ENDPOINT
from server.entities.login_user import LoginUser
from server.entities.map_error import MapError
from server.entities.map_service import MapService
from server.entities.patch_request import PatchOperation, ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse

from tests.helpers import load_json_data, unwrap


if t.TYPE_CHECKING:
    from flask import Flask
    from pytest_mock import MockerFixture


# --- search ---
def test_search_success(app: Flask, mocker: MockerFixture) -> None:
    query = SearchRequestParameter(
        filter="serviceName eq 'test'", start_index=1, count=10, sort_by="serviceName", sort_order="ascending"
    )
    access_token = "token"
    client_secret = "secret"
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    fake_service = MapService.model_validate({
        "id": "s1",
        "schemas": ["a"],
        "serviceName": "s",
    })
    expected_result = SearchResponse(
        total_results=1,
        items_per_page=1,
        start_index=1,
        resources=[fake_service],
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:ListResponse"],
    )
    expected_kwargs = {
        "params": {
            "time_stamp": time_stamp,
            "signature": signature,
            "filter": "serviceName eq 'test'",
            "startIndex": 1,
            "count": 10,
            "sortBy": "serviceName",
            "sortOrder": "ascending",
        },
        "headers": expected_headers,
        "timeout": expected_timeout,
    }
    expected_call_args = (expected_requests_url,)
    response = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [fake_service.model_dump(mode="json", by_alias=True)],
    }

    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_get = mocker.patch("server.clients.services.requests.get")
    mock_get.return_value.text = json.dumps(response)
    mock_get.return_value.status_code = 200
    original_func = unwrap(services.search)

    result = original_func(
        query,
        access_token=access_token,
        client_secret=client_secret,
    )

    mock_get.assert_called_once()
    assert mock_get.call_args == (expected_call_args, expected_kwargs)
    assert result == expected_result


def test_search_with_include(app: Flask, mocker: MockerFixture) -> None:
    query = SearchRequestParameter(
        filter="serviceName eq 'test'", start_index=1, count=10, sort_by="serviceName", sort_order="descending"
    )
    include = {"service_name"}
    access_token = "token"
    client_secret = "secret"
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "s1", "schemas": ["a"], "serviceName": "s"}],
    }
    expected_params = {
        "attributes": "service_name,id",
    }
    fake_service = MapService.model_validate({
        "id": "s1",
        "schemas": ["a"],
        "serviceName": "s",
    })
    expected_result = SearchResponse(
        total_results=1,
        items_per_page=1,
        start_index=1,
        resources=[fake_service],
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:ListResponse"],
    )

    expected_attributes = expected_params["attributes"].split(",")
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}"
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mock_get = mocker.patch("server.clients.services.requests.get")
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = unwrap(services.search)

    result = original_func(
        query,
        include=include,
        access_token=access_token,
        client_secret=client_secret,
    )

    call_args, called_kwargs = mock_get.call_args
    actual_attributes = called_kwargs["params"]["attributes"].split(",")
    mock_get.assert_called_once()
    assert isinstance(result, SearchResponse)
    assert result == expected_result
    assert call_args[0] == expected_requests_url
    assert set(actual_attributes) == set(expected_attributes)
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_search_with_exclude(app: Flask, mocker: MockerFixture) -> None:
    query = SearchRequestParameter()
    exclude = {"meta"}
    access_token = "token"
    client_secret = "secret"
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "totalResults": 1,
        "itemsPerPage": 1,
        "startIndex": 1,
        "Resources": [{"id": "s1", "schemas": ["a"], "serviceName": "s"}],
    }
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}"
    expected_headers = {"Authorization": f"Bearer {access_token}"}
    expected_timeout = config.MAP_CORE.timeout
    expected_kwargs = {
        "params": {
            "filter": query.filter,
            "startIndex": query.start_index,
            "count": query.count,
            "sortBy": query.sort_by,
            "sortOrder": query.sort_order,
            "excluded_attributes": "meta",
            "time_stamp": time_stamp,
            "signature": signature,
        },
        "headers": expected_headers,
        "timeout": expected_timeout,
    }
    fake_service = MapService.model_validate({
        "id": "s1",
        "schemas": ["a"],
        "serviceName": "s",
    })
    expected_result = SearchResponse(
        total_results=1,
        items_per_page=1,
        start_index=1,
        resources=[fake_service],
        schemas=["urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:ListResponse"],
    )
    mock_get = mocker.patch("server.clients.services.requests.get")
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mock_get.return_value.text = json.dumps(response_data)
    mock_get.return_value.status_code = 200
    original_func = unwrap(services.search)

    result = original_func(
        query,
        exclude=exclude,
        access_token=access_token,
        client_secret=client_secret,
    )

    mock_get.assert_called_once()
    expected_call_args = (expected_requests_url,)

    assert mock_get.call_args == (expected_call_args, expected_kwargs)
    assert result == expected_result


def test_search_not_found(app: Flask, mocker: MockerFixture) -> None:
    query = SearchRequestParameter(
        filter="serviceName eq 'test'", start_index=1, count=0, sort_by="serviceName", sort_order="ascending"
    )
    access_token = "token"
    client_secret = "secret"
    error_data = load_json_data("data/map_error.json")
    expected_error = MapError.model_validate(error_data | {"detail": error_data["detail"] % "search_query"})
    mock_get = mocker.patch("server.clients.services.requests.get")
    mock_get.return_value.raise_for_status.side_effect = Exception("Not Found")
    mock_get.return_value.text = expected_error.model_dump_json()
    mock_get.return_value.status_code = 404
    original_func = unwrap(services.search)

    with pytest.raises(Exception, match="Not Found"):
        original_func(query, access_token=access_token, client_secret=client_secret)


def test_search_http_error(app: Flask, mocker: MockerFixture) -> None:
    query = SearchRequestParameter(
        filter="serviceName eq 'test'", start_index=1, count=10, sort_by="serviceName", sort_order="ascending"
    )
    mock_get = mocker.patch("server.clients.services.requests.get")
    mock_get.return_value.status_code = 401
    mock_get.return_value.raise_for_status.side_effect = Exception("401 Unauthorized")
    original_func = unwrap(services.search)

    with pytest.raises(Exception, match="401 Unauthorized"):
        original_func(query, access_token="token", client_secret="secret")


def test_get_by_id_success(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, expected_service = service_data
    service_id: str = json_data["id"]
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_call_args = (expected_requests_url,)
    expected_kwargs = {
        "params": {
            "time_stamp": time_stamp,
            "signature": signature,
        },
        "headers": expected_headers,
        "timeout": expected_timeout,
    }

    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.services.requests.get")
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(services.get_by_id)
    result = original_func(service_id, access_token="token", client_secret="secret")

    mock_response.assert_called_once()
    assert mock_response.call_args == (expected_call_args, expected_kwargs)
    assert result == expected_service


def test_get_by_id_with_include(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    service_id: str = json_data["id"]
    include = {"service_name"}
    signature = hashlib.sha256(b"hash").hexdigest()
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    time_stamp = str(int(time.time()))
    expected_params = {
        "attributes": "id,service_name",
    }
    expected_attributes = expected_params["attributes"].split(",")
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}"

    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.services.requests.get")
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(services.get_by_id)
    result = original_func(service_id, include=include, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_response.call_args
    actual_attributes = called_kwargs["params"]["attributes"].split(",")
    mock_response.assert_called_once()
    assert isinstance(result, MapService)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.service_name == response_data["serviceName"]
    assert call_args[0] == expected_requests_url
    assert set(actual_attributes) == set(expected_attributes)
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_get_by_id_with_exclude(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    service_id = json_data["id"]
    exclude = {"meta"}
    signature = hashlib.sha256(b"hash").hexdigest()
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    time_stamp = str(int(time.time()))
    expected_call_args = (f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}",)
    expected_kwargs = {
        "params": {
            "time_stamp": time_stamp,
            "signature": signature,
            "excluded_attributes": "meta",
        },
        "headers": {"Authorization": "Bearer token"},
        "timeout": config.MAP_CORE.timeout,
    }
    expected_result = MapService.model_validate(response_data)

    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_response = mocker.patch("server.clients.services.requests.get")
    mock_response.return_value.text = json.dumps(response_data)
    mock_response.return_value.status_code = 200

    original_func = unwrap(services.get_by_id)
    result = original_func(service_id, exclude=exclude, access_token="token", client_secret="secret")

    mock_response.assert_called_once()

    assert mock_response.call_args == (expected_call_args, expected_kwargs)
    assert result == expected_result
    assert result.meta is None


def test_get_by_id_not_found(app: Flask, mocker: MockerFixture) -> None:
    json_data = load_json_data("data/map_error.json")
    service_id = "nonexistent_service"
    expected_error = MapError.model_validate(json_data | {"detail": json_data["detail"] % service_id})
    mock_response = mocker.patch("server.clients.services.requests.get")
    mock_response.return_value.text = expected_error.model_dump_json()
    mock_response.return_value.status_code = 404

    original_func = unwrap(services.get_by_id)
    result = original_func(service_id, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_get_by_id_http_error(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    service_id: str = json_data["id"]
    mock_response = mocker.patch("server.clients.services.requests.get")
    mock_response.return_value.text = json.dumps(json_data)
    mock_response.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_response.return_value.status_code = 401
    original_func = unwrap(services.get_by_id)

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(service_id, access_token="token", client_secret="secret")


# --- post ---
def test_post_success(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    service_obj: MapService = service
    expected_service = MapService.model_validate(json_data)
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_call_args = (expected_requests_url,)
    expected_kwargs = {
        "params": {},
        "headers": expected_headers,
        "timeout": expected_timeout,
        "json": service.model_dump(mode="json", by_alias=True)
        | {"request": {"time_stamp": time_stamp, "signature": signature}},
    }
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_post = mocker.patch("server.clients.services.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.status_code = 200

    original_func = unwrap(services.post)
    result = original_func(
        service_obj,
        include=None,
        exclude=None,
        access_token="token",
        client_secret="secret",
    )

    mock_post.assert_called_once()
    assert mock_post.call_args == (expected_call_args, expected_kwargs)
    assert result == expected_service


def test_post_with_include(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    service_obj: MapService = service
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    include = {"service_name"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    expected_call_args = (f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}",)
    expected_kwargs = {
        "params": {
            "attributes": "service_name",
        },
        "headers": {"Authorization": "Bearer token"},
        "timeout": config.MAP_CORE.timeout,
        "json": service.model_dump(mode="json", by_alias=True)
        | {"request": {"time_stamp": time_stamp, "signature": signature}},
    }

    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_post = mocker.patch("server.clients.services.requests.post")
    mock_post.return_value.text = json.dumps(response_data)
    mock_post.return_value.status_code = 200

    original_func = unwrap(services.post)
    result = original_func(
        service_obj,
        include=include,
        exclude=None,
        access_token="token",
        client_secret="secret",
    )

    mock_post.assert_called_once()
    expected_result = MapService.model_validate(response_data)
    assert mock_post.call_args == (expected_call_args, expected_kwargs)
    assert result == expected_result


def test_post_with_exclude(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    time_stamp = str(int(time.time()))
    service_obj: MapService = service
    signature = hashlib.sha256(b"hash").hexdigest()
    exclude = {"meta"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    expected_params = {
        "excluded_attributes": "meta",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}"

    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_app_cache_decoraters = mocker.patch("server.clients.decoraters.app_cache", new_callable=Mock)
    mock_app_cache_decoraters.scan.return_value = (0, [])

    mock_app_cache_datastore = mocker.patch("server.datastore.app_cache", new_callable=Mock)
    mock_app_cache_datastore.scan.return_value = (0, [])
    mock_post = mocker.patch("server.clients.services.requests.post")
    mock_post.return_value.text = json.dumps(response_data)
    mock_post.return_value.status_code = HTTPStatus.CONFLICT

    original_func = unwrap(services.post)
    result = original_func(
        service_obj,
        include=None,
        exclude=exclude,
        access_token="token",
        client_secret="secret",
    )

    mock_post.assert_called_once()
    call_args, called_kwargs = mock_post.call_args
    actual_excluded = called_kwargs["params"]["excluded_attributes"].split(",")
    expected_excluded = expected_params["excluded_attributes"].split(",")
    assert isinstance(result, MapService)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.service_name == response_data["serviceName"]
    assert result.meta is None
    assert call_args[0] == expected_requests_url
    assert set(actual_excluded) == set(expected_excluded)
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_post_not_found(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data = load_json_data("data/map_error.json")
    mock_post = mocker.patch("server.clients.services.requests.post")
    mock_post.return_value.text = json.dumps(json_data)
    mock_app_cache_decoraters = mocker.patch("server.clients.decoraters.app_cache", new_callable=Mock)
    mock_app_cache_decoraters.scan.return_value = (0, [])

    mock_app_cache_datastore = mocker.patch("server.datastore.app_cache", new_callable=Mock)
    mock_app_cache_datastore.scan.return_value = (0, [])
    mock_post.return_value.status_code = 404
    _, service = service_data

    service_obj: MapService = service
    original_func = unwrap(services.post)
    result = original_func(
        service_obj,
        include=None,
        exclude=None,
        access_token="token",
        client_secret="secret",
    )

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_post_http_error(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data = load_json_data("data/map_error.json")

    mock_post = mocker.patch("server.clients.services.requests.post")

    mock_app_cache_decoraters = mocker.patch("server.clients.decoraters.app_cache", new_callable=Mock)
    mock_app_cache_decoraters.scan.return_value = (0, [])

    mock_app_cache_datastore = mocker.patch("server.datastore.app_cache", new_callable=Mock)
    mock_app_cache_datastore.scan.return_value = (0, [])

    mock_post.return_value.text = json.dumps(json_data)
    mock_post.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_post.return_value.status_code = 401
    json_data, service = service_data

    service_obj: MapService = service
    original_func = unwrap(services.post)
    with pytest.raises(HTTPError, match="401 Unauthorized"):
        original_func(service_obj, access_token="token", client_secret="secret")


# --- put_by_id ---
def test_put_by_id_success(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    service_obj: MapService = service
    expected_service = MapService.model_validate(json_data)
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{json_data['id']}"
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    mock_app_cache_decoraters = mocker.patch("server.clients.decoraters.app_cache", new_callable=Mock)
    mock_app_cache_decoraters.scan.return_value = (0, [])

    mock_app_cache_datastore = mocker.patch("server.datastore.app_cache", new_callable=Mock)
    mock_app_cache_datastore.scan.return_value = (0, [])

    mocker.patch("server.clients.services.get_time_stamp", return_value=str(int(time.time())))
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mocker.patch("server.clients.decoraters.app_cache.scan", return_value=(0, []))
    mock_put = mocker.patch("server.clients.services.requests.put")
    mock_put.return_value.text = json.dumps(json_data)
    mock_put.return_value.status_code = 200

    mocker.patch("server.clients.services.repository_updated")
    original_func = unwrap(services.put_by_id)
    result = original_func(service_obj, access_token="token", client_secret="secret")

    mock_put.assert_called_once()
    call_args, called_kwargs = mock_put.call_args
    assert isinstance(result, MapService)
    assert result.schemas == expected_service.schemas
    assert result.id == expected_service.id
    assert result.service_name == expected_service.service_name
    assert result.meta == expected_service.meta
    assert call_args[0] == expected_requests_url
    assert called_kwargs["params"] == {}
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_put_by_id_with_include(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    service_obj: MapService = service
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    include = {"service_name"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    expected_params = {
        "attributes": "id,service_name",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{json_data['id']}"

    mock_app_cache_decoraters = mocker.patch("server.clients.decoraters.app_cache", new_callable=Mock)
    mock_app_cache_decoraters.scan.return_value = (0, [])

    mock_app_cache_datastore = mocker.patch("server.datastore.app_cache", new_callable=Mock)
    mock_app_cache_datastore.scan.return_value = (0, [])

    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.decoraters.app_cache.scan", return_value=(0, []))
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_put = mocker.patch("server.clients.services.requests.put")
    mocker.patch("server.clients.services.repository_updated")
    mocker.patch("server.clients.decoraters.app_cache.scan", return_value=(0, []))
    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = HTTPStatus.BAD_REQUEST

    original_func = unwrap(services.put_by_id)
    result = original_func(service_obj, include=include, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_put.call_args
    actual_attributes = called_kwargs["params"]["attributes"].split(",")
    assert isinstance(result, MapService)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.service_name == response_data["serviceName"]
    assert call_args[0] == expected_requests_url
    assert set(actual_attributes) == set(expected_params["attributes"].split(","))
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_put_by_id_with_exclude(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    service_obj: MapService = service
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    exclude = {"meta"}
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    expected_params = {
        "excluded_attributes": "meta",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{json_data['id']}"

    mock_app_cache_decoraters = mocker.patch("server.clients.decoraters.app_cache", new_callable=Mock)
    mock_app_cache_decoraters.scan.return_value = (0, [])

    mock_app_cache_datastore = mocker.patch("server.datastore.app_cache", new_callable=Mock)
    mock_app_cache_datastore.scan.return_value = (0, [])
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_put = mocker.patch("server.clients.services.requests.put")
    mocker.patch("server.clients.services.repository_updated")

    mock_put.return_value.text = json.dumps(response_data)
    mock_put.return_value.status_code = 200

    original_func = unwrap(services.put_by_id)
    result = original_func(service_obj, exclude=exclude, access_token="token", client_secret="secret")

    call_args, called_kwargs = mock_put.call_args
    actual_excluded = called_kwargs["params"]["excluded_attributes"].split(",")
    expected_excluded = expected_params["excluded_attributes"].split(",")
    assert isinstance(result, MapService)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.service_name == response_data["serviceName"]
    assert result.meta is None
    assert call_args[0] == expected_requests_url
    assert set(actual_excluded) == set(expected_excluded)
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout


def test_put_by_id_not_found(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_error_data = load_json_data("data/map_error.json")
    mock_put = mocker.patch("server.clients.services.requests.put")
    mock_put.return_value.text = json.dumps(json_error_data)
    mock_put.return_value.status_code = 200
    _, service = service_data

    result = services.put_by_id(service, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_put_by_id_http_error(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, service = service_data
    mock_put = mocker.patch("server.clients.services.requests.put")
    mock_put.return_value.text = json.dumps(json_data)
    mock_put.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_put.return_value.status_code = 401

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        services.put_by_id(service, access_token="token", client_secret="secret")


# --- patch_by_id ---
def test_patch_by_id_success(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    service_id: str = json_data["id"]
    operations: list[ReplaceOperation] = [ReplaceOperation(op="replace", path="serviceName", value="NewName")]
    expected_service = MapService.model_validate(json_data)
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    expected_request = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}"
    mock_app_cache = mocker.patch("server.datastore.app_cache")
    mock_app_cache.scan.return_value = (0, [])
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_patch = mocker.patch("server.clients.services.requests.patch")
    mock_patch.return_value.text = json.dumps(json_data)
    mock_patch.return_value.status_code = 200

    mocker.patch("server.clients.services.repository_updated")
    original_func = unwrap(services.patch_by_id)
    result = original_func(service_id, operations, access_token="token", client_secret="secret")

    mock_patch.assert_called_once()
    call_args, called_kwargs = mock_patch.call_args
    assert isinstance(result, MapService)
    assert result.schemas == expected_service.schemas
    assert result.id == expected_service.id
    assert result.service_name == expected_service.service_name
    assert result.meta == expected_service.meta
    assert call_args[0] == expected_requests_url
    assert called_kwargs["params"] == {}
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["json"]["request"] == expected_request


def test_patch_by_id_with_include(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    service_id: str = json_data["id"]
    include = {"service_name"}
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    operations: list[ReplaceOperation] = [ReplaceOperation(op="replace", path="serviceName", value="NewName")]
    expected_request = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    expected_params = {
        "attributes": "id,service_name",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}"

    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_patch = mocker.patch("server.clients.services.requests.patch")
    mock_app_cache = mocker.patch("server.datastore.app_cache")
    mock_app_cache.scan.return_value = (0, [])
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200

    mocker.patch("server.clients.services.repository_updated")
    original_func = unwrap(services.patch_by_id)
    result = original_func(
        service_id,
        operations,
        include=include,
        access_token="token",
        client_secret="secret",
    )

    call_args, called_kwargs = mock_patch.call_args
    actual_attributes = called_kwargs["params"]["attributes"].split(",")
    assert isinstance(result, MapService)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.service_name == response_data["serviceName"]
    assert call_args[0] == expected_requests_url
    assert set(actual_attributes) == set(expected_params["attributes"].split(","))
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["json"]["request"] == expected_request


def test_patch_by_id_with_exclude(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    service_id: str = json_data["id"]
    exclude = {"meta"}
    time_stamp = str(int(time.time()))
    signature = hashlib.sha256(b"hash").hexdigest()
    operations: list[ReplaceOperation] = [ReplaceOperation(op="replace", path="serviceName", value="NewName")]
    expected_request = {
        "time_stamp": time_stamp,
        "signature": signature,
    }
    response_data = {
        "schemas": json_data["schemas"],
        "id": json_data["id"],
        "serviceName": json_data["serviceName"],
    }

    expected_params = {
        "excluded_attributes": "meta",
    }
    expected_headers = {"Authorization": "Bearer token"}
    expected_timeout = config.MAP_CORE.timeout
    expected_requests_url = f"{config.MAP_CORE.base_url}{MAP_SERVICES_ENDPOINT}/{service_id}"
    mocker.patch("server.clients.decoraters.app_cache")
    mocker.patch("server.clients.services.get_time_stamp", return_value=time_stamp)
    mocker.patch("server.clients.services.compute_signature", return_value=signature)
    mock_patch = mocker.patch("server.clients.services.requests.patch")
    mocker.patch.object(services, "alias_generator", side_effect=lambda x: x)
    mock_patch.return_value.text = json.dumps(response_data)
    mock_patch.return_value.status_code = 200
    mocker.patch("server.clients.services.repository_updated")
    original_func = unwrap(services.patch_by_id)
    result = original_func(
        service_id,
        operations,
        exclude=exclude,
        access_token="token",
        client_secret="secret",
    )

    call_args, called_kwargs = mock_patch.call_args
    actual_excluded = called_kwargs["params"]["excluded_attributes"].split(",")
    expected_excluded = expected_params["excluded_attributes"].split(",")
    assert isinstance(result, MapService)
    assert result.schemas == response_data["schemas"]
    assert result.id == response_data["id"]
    assert result.service_name == response_data["serviceName"]
    assert result.meta is None
    assert call_args[0] == expected_requests_url
    assert set(actual_excluded) == set(expected_excluded)
    assert called_kwargs["headers"] == expected_headers
    assert called_kwargs["timeout"] == expected_timeout
    assert called_kwargs["json"]["request"] == expected_request


def test_patch_by_id_not_found(app: Flask, mocker: MockerFixture) -> None:
    error_data = load_json_data("data/map_error.json")
    operations: list[ReplaceOperation] = [ReplaceOperation(op="replace", path="serviceName", value="NewName")]
    service_id = "dummy_id"
    mock_patch = mocker.patch("server.clients.services.requests.patch")
    mock_patch.return_value.text = json.dumps(error_data)
    mock_patch.return_value.status_code = 404

    original_func = unwrap(services.patch_by_id)
    result = original_func(service_id, operations, access_token="token", client_secret="secret")

    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_patch_by_id_http_error(app: Flask, mocker: MockerFixture, service_data) -> None:
    json_data, _ = service_data
    operations: list[PatchOperation] = [ReplaceOperation(op="replace", path="serviceName", value="NewName")]
    service_id = json_data["id"]
    mock_patch = mocker.patch("server.clients.services.requests.patch")
    mock_patch.return_value.text = json.dumps(json_data)
    mock_patch.return_value.raise_for_status.side_effect = HTTPError("401 Unauthorized")
    mock_patch.return_value.status_code = 401

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        services.patch_by_id(service_id, operations, access_token="token", client_secret="secret")


def test_delete_by_id_success(app: Flask, mocker: MockerFixture) -> None:

    service_id = "s1"
    access_token = "token"
    client_secret = "secret"
    mock_delete = mocker.patch("server.clients.services.requests.delete")
    mock_delete.return_value.text = ""
    mock_delete.return_value.status_code = 200
    mocker.patch("server.clients.services.repository_deleted.send")
    mocker.patch("server.clients.services.repository_updated")
    result = services.delete_by_id(service_id, access_token=access_token, client_secret=client_secret)
    mock_delete.assert_called_once()
    assert result is None


def test_delete_by_id_error_response(app: Flask, mocker: MockerFixture) -> None:
    service_id = "s1"
    access_token = "token"
    client_secret = "secret"
    error_data = load_json_data("data/map_error.json")
    mock_delete = mocker.patch("server.clients.services.requests.delete")
    mocker.patch("server.clients.services.repository_deleted.send")

    mock_delete.return_value.text = json.dumps(error_data)
    mock_delete.return_value.ok = False

    result = services.delete_by_id(service_id, access_token=access_token, client_secret=client_secret)
    mock_delete.assert_called_once()
    assert isinstance(result, MapError)
    assert "Not Found" in result.detail


def test_delete_by_id_http_error(app: Flask, mocker: MockerFixture) -> None:
    service_id = "s1"
    access_token = "token"
    client_secret = "secret"
    mock_delete = mocker.patch("server.clients.services.requests.delete")
    mocker.patch("server.clients.services.repository_deleted.send")
    mocker.patch("server.clients.services.repository_updated")
    mock_delete.return_value.text = ""
    mock_delete.return_value.ok = False

    result = services.delete_by_id(service_id, access_token=access_token, client_secret=client_secret)
    assert result is None


def test__get_alias_generator_with_serialization_alias_services(monkeypatch):
    """Covers the branch where generator has serialization_alias attribute for services."""

    class Dummy:
        def __init__(self):
            self.serialization_alias = lambda x: f"alias_{x}"

    monkeypatch.setitem(MapService.model_config, "alias_generator", Dummy())
    importlib.reload(services)
    result = services.alias_generator
    assert callable(result)
    assert result("foo") == "alias_foo"


def test__get_alias_generator_with_none_services(monkeypatch):
    """Covers the branch where generator is None and falls back to lambda x: x for services."""

    monkeypatch.setitem(MapService.model_config, "alias_generator", None)
    importlib.reload(services)
    result = services.alias_generator
    assert callable(result)
    assert result("bar") == "bar"


def test_handle_repository_updated_clears_cache(mocker):
    """Covers get_by_id.clear_cache(service.id) branch for handle_repository_updated."""
    mock_clear = mocker.patch("server.clients.services.get_by_id.clear_cache")

    service = MapService.model_validate({"id": "service42", "schemas": ["a"], "serviceName": "dummy"})
    handle_repository_updated(_sender=None, service=service)
    mock_clear.assert_called_once_with(service.id)


def test_handle_repository_updated_no_service_id(mocker):
    """Covers branch where service or service.id is falsy."""
    mock_clear = mocker.patch("server.clients.services.get_by_id.clear_cache")
    handle_repository_updated(_sender=None, service=None)
    mock_clear.assert_not_called()


def test_handle_repository_updated_by_id_clears_cache(mocker):
    """Covers get_by_id.clear_cache(service_id) branch for handle_repository_updated_by_id."""
    mock_clear = mocker.patch("server.clients.services.get_by_id.clear_cache")
    service_id = "repo123"
    handle_repository_updated_by_id(_sender=None, service_id=service_id)
    mock_clear.assert_called_once_with(service_id)


def test_handle_repository_updated_by_id_no_service_id(mocker):
    """Covers branch where service_id is falsy."""
    mock_clear = mocker.patch("server.clients.services.get_by_id.clear_cache")
    handle_repository_updated_by_id(_sender=None, service_id=None)
    mock_clear.assert_not_called()


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
def test_search_cache_identifier_services(mocker, is_logged_in, is_admin, permitted, expected):

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
    mocker.patch("server.clients.services.current_user", current_user)
    mocker.patch("server.clients.services.is_user_logged_in", return_value=is_logged_in)
    result = services._search_cache_identifier()  # noqa: SLF001
    assert result == expected


def test_handle_reset_search_cache_calls_clear_cache(mocker):
    """Test that handle_reset_search_cache calls search.clear_cache with _search_cache_identifier()."""

    importlib.reload(services_mod)
    mock_clear_cache = mocker.patch.object(services_mod.search, "clear_cache")
    mock_identifier = mocker.patch.object(services_mod, "_search_cache_identifier", return_value="dummy_id")
    services_mod.handle_reset_search_cache(_sender=None)
    mock_identifier.assert_called_once_with()
    mock_clear_cache.assert_called_once_with("dummy_id")


@pytest.fixture
def service_data() -> tuple[dict[str, t.Any], MapService]:
    json_data: dict[str, t.Any] = load_json_data("data/map_service.json")
    service: MapService = MapService.model_validate(json_data)
    return json_data, service
