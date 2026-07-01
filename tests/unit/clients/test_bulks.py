import json
import typing as t

from http import HTTPStatus
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import requests

import server.clients.bulks

from server.clients import bulks
from server.const import MAP_BULK_ENDPOINT
from server.entities.bulk_request import BulkResponse
from server.entities.map_error import MapError

from tests.helpers import load_json_data


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_post(app, config, map_groups, mocker: MockerFixture):
    access_token, client_secret = uuid4().hex[:8], uuid4().hex[:16]
    spy_time_stamp = mocker.spy(server.clients.bulks, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.bulks, "compute_signature")

    response_data = load_json_data("data/map_bulk.json")
    expected = BulkResponse.model_validate(response_data)
    operations = expected.operations

    mock_response = mocker.MagicMock(spec=requests.Response, status_code=HTTPStatus.OK)
    mock_response.text = json.dumps(response_data)
    mock_post = mocker.patch.object(server.clients.bulks.requests, "post", return_value=mock_response)

    result = bulks.post(operations, access_token, client_secret)

    assert isinstance(result, BulkResponse)
    assert result == expected
    (url,), kwargs = mock_post.call_args
    scheme, netloc, path, *_ = urlsplit(url)
    assert f"{scheme}://{netloc}" == config.MAP_CORE.base_url
    assert path == MAP_BULK_ENDPOINT
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return


def test_post_return_map_error(config, mocker: MockerFixture):
    operations = []
    access_token, client_secret = uuid4().hex[:8], uuid4().hex[:16]

    response_data = load_json_data("data/map_error.json")

    mock_response = mocker.MagicMock(spec=requests.Response, status_code=HTTPStatus.BAD_REQUEST)
    mock_response.text = json.dumps(response_data)
    mocker.patch.object(server.clients.bulks.requests, "post", return_value=mock_response)
    expected = MapError.model_validate(response_data)

    result = bulks.post(operations, access_token, client_secret)

    assert isinstance(result, MapError)
    assert result == expected


def test_post_http_error(config, mocker: MockerFixture):
    operations = []
    access_token, client_secret = uuid4().hex[:8], uuid4().hex[:16]

    mock_response = mocker.MagicMock(spec=requests.Response, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_response.raise_for_status.side_effect = requests.HTTPError("Internal Server Error")
    mocker.patch.object(server.clients.bulks.requests, "post", return_value=mock_response)

    with pytest.raises(requests.HTTPError, match="Internal Server Error"):
        bulks.post(operations, access_token, client_secret)
