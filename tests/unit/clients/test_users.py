import typing as t

from http import HTTPStatus
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from pydantic import AliasGenerator
from pydantic.alias_generators import to_camel
from requests.exceptions import HTTPError

import server.clients.users

from server.clients import users
from server.const import MAP_EXIST_EPPN_ENDPOINT, MAP_SELF_ENDPOINT, MAP_USERS_ENDPOINT
from server.entities.map_user import MapUser
from server.entities.patch_request import ReplaceOperation
from server.entities.search_request import SearchRequestParameter, SearchResponse

from tests.helpers import unwrap


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig


@pytest.fixture(autouse=True)
def alias(mocker: MockerFixture):
    original = users._a
    mock_alias = mocker.patch.object(users, "_a", side_effect=lambda x: x)

    return original, mock_alias


@pytest.fixture
def original_alias(alias):
    original, _ = alias
    users._a = original

    return original


def test_search(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, user, _ = map_user

    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    total, size = 1, 1
    expected = SearchResponse[MapUser](total_results=total, items_per_page=size, start_index=index, resources=[user])

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.search)(query, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}"
    assert "attributes" not in kwargs["params"]
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["params"]["startIndex"] == index
    assert kwargs["params"]["count"] == count
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_search_with_include(config, map_user, mocker: MockerFixture):
    _, user, _ = map_user

    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    total, size = 1, 1
    expected = SearchResponse[MapUser](total_results=total, items_per_page=size, start_index=index, resources=[user])

    include = {"user_name", "preferred_language"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.search)(query, include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"


def test_search_with_exclude(config, map_user, mocker: MockerFixture):
    _, user, _ = map_user

    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    total, size = 1, 1
    expected = SearchResponse[MapUser](total_results=total, items_per_page=size, start_index=index, resources=[user])

    exclude = {"meta"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.search)(query, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}"
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"


def test_search_map_error_with_bad_request(config, map_error, mocker: MockerFixture):
    _, expected, raw_error = map_error

    filter_string, index, count = 'userName eq "Test User"', 1, 10
    query = SearchRequestParameter(filter=filter_string, start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_error
    mock_get.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = unwrap(users.search)(query, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_search_http_error(config, mocker: MockerFixture):
    index, count = 1, 10
    query = SearchRequestParameter(start_index=index, count=count)
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_get.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        unwrap(users.search)(query, access_token=access_token, client_secret=client_secret)


def test_get_by_id(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    user_id = expected.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.get_by_id)(user_id, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{user_id}"
    assert "attributes" not in kwargs["params"]
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_id_with_include(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    user_id = expected.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    include = {"user_name", "preferred_language"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.get_by_id)(user_id, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{user_id}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_id_with_exclude(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    user_id = expected.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    exclude = {"meta"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.get_by_id)(user_id, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{user_id}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_id_map_error_with_bad_request(config: RuntimeConfig, map_user, map_error, mocker: MockerFixture):
    _, user, _ = map_user
    _, expected, raw_error = map_error
    user_id = user.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_error
    mock_get.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = unwrap(users.get_by_id)(user_id, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_get_by_id_http_error(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, user, _ = map_user
    user_id = user.id
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_get.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        unwrap(users.get_by_id)(user_id, access_token=access_token, client_secret=client_secret)


def test_get_by_eppn(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    eppn = expected.edu_person_principal_names[0].value if expected.edu_person_principal_names else ""
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.get_by_eppn)(eppn, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_EXIST_EPPN_ENDPOINT}/{eppn}"
    assert "attributes" not in kwargs["params"]
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_eppn_with_include(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    eppn = expected.edu_person_principal_names[0].value if expected.edu_person_principal_names else ""
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    include = {"user_name", "preferred_language"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.get_by_eppn)(eppn, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_EXIST_EPPN_ENDPOINT}/{eppn}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_eppn_with_exclude(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    eppn = expected.edu_person_principal_names[0].value if expected.edu_person_principal_names else ""
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    exclude = {"meta"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = unwrap(users.get_by_eppn)(eppn, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_EXIST_EPPN_ENDPOINT}/{eppn}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_by_eppn_map_error_with_bad_request(config: RuntimeConfig, map_user, map_error, mocker: MockerFixture):
    _, user, _ = map_user
    _, expected, raw_error = map_error
    eppn = user.edu_person_principal_names[0].value if user.edu_person_principal_names else ""
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_error
    mock_get.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = unwrap(users.get_by_eppn)(eppn, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_get_by_eppn_http_error(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, user, _ = map_user
    eppn = user.edu_person_principal_names[0].value if user.edu_person_principal_names else ""
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_get.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        unwrap(users.get_by_eppn)(eppn, access_token=access_token, client_secret=client_secret)


def test_post(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    mock_post = mocker.patch.object(server.clients.users.requests, "post")
    mock_post.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_post.return_value.status_code = HTTPStatus.OK

    result = users.post(expected, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_post.assert_called_once()
    (url,), kwargs = mock_post.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["userName"] == expected.user_name
    assert kwargs["json"]["preferredLanguage"] == expected.preferred_language
    assert all("idpEntityId" not in eppn for eppn in kwargs["json"].get("eduPersonPrincipalNames", []))
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_post_with_include(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    include = {"user_name", "preferred_language"}

    mock_post = mocker.patch.object(server.clients.users.requests, "post")
    mock_post.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_post.return_value.status_code = HTTPStatus.OK

    result = users.post(expected, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_post.assert_called_once()
    (url,), kwargs = mock_post.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["userName"] == expected.user_name
    assert kwargs["json"]["preferredLanguage"] == expected.preferred_language
    assert "emails" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_post_with_exclude(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    exclude = {"meta", "emails", "edu_person_principal_names"}

    mock_post = mocker.patch.object(server.clients.users.requests, "post")
    mock_post.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_post.return_value.status_code = HTTPStatus.OK

    result = users.post(expected, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_post.assert_called_once()
    (url,), kwargs = mock_post.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["userName"] == expected.user_name
    assert kwargs["json"]["preferredLanguage"] == expected.preferred_language
    assert "emails" not in kwargs["json"]
    assert "eduPersonPrincipalNames" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_post_map_error_with_bad_request(config: RuntimeConfig, map_user, map_error, mocker: MockerFixture):
    _, user, _ = map_user
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_post = mocker.patch.object(server.clients.users.requests, "post")
    mock_post.return_value.text = raw_error
    mock_post.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = users.post(user, access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_post_http_error(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, user, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_post = mocker.patch.object(server.clients.users.requests, "post")
    mock_post.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_post.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        users.post(user, access_token=access_token, client_secret=client_secret)


def test_put_by_id(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    mock_put = mocker.patch.object(server.clients.users.requests, "put")
    mock_put.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_put.return_value.status_code = HTTPStatus.OK
    mock_send = signal_send["user_updated"]

    result = users.put_by_id(expected, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_put.assert_called_once()
    (url,), kwargs = mock_put.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{expected.id}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["userName"] == expected.user_name
    assert kwargs["json"]["preferredLanguage"] == expected.preferred_language
    assert all("idpEntityId" not in eppn for eppn in kwargs["json"].get("eduPersonPrincipalNames", []))
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout

    _, kwargs = mock_send.call_args
    assert kwargs["user"] == expected


def test_put_by_id_with_include(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    include = {"user_name", "preferred_language"}

    mock_put = mocker.patch.object(server.clients.users.requests, "put")
    mock_put.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_put.return_value.status_code = HTTPStatus.OK

    result = users.put_by_id(expected, include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_put.assert_called_once()
    (url,), kwargs = mock_put.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{expected.id}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["userName"] == expected.user_name
    assert kwargs["json"]["preferredLanguage"] == expected.preferred_language
    assert "emails" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_put_by_id_with_exclude(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    exclude = {"meta", "emails", "edu_person_principal_names"}

    mock_put = mocker.patch.object(server.clients.users.requests, "put")
    mock_put.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_put.return_value.status_code = HTTPStatus.OK

    result = users.put_by_id(expected, exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_put.assert_called_once()
    (url,), kwargs = mock_put.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{expected.id}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["id"] == expected.id
    assert kwargs["json"]["userName"] == expected.user_name
    assert kwargs["json"]["preferredLanguage"] == expected.preferred_language
    assert "emails" not in kwargs["json"]
    assert "eduPersonPrincipalNames" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_put_by_id_map_error_with_bad_request(
    config: RuntimeConfig, map_user, map_error, signal_send, mocker: MockerFixture
):
    _, user, _ = map_user
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_put = mocker.patch.object(server.clients.users.requests, "put")
    mock_put.return_value.text = raw_error
    mock_put.return_value.status_code = HTTPStatus.BAD_REQUEST
    mock_send = signal_send["user_updated"]

    result = users.put_by_id(user, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_send.assert_not_called()


def test_put_by_id_http_error(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, user, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_put = mocker.patch.object(server.clients.users.requests, "put")
    mock_put.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_put.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)
    mock_send = signal_send["user_updated"]

    with pytest.raises(HTTPError):
        users.put_by_id(user, access_token=access_token, client_secret=client_secret)

    mock_send.assert_not_called()


def test_patch_by_id(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="preferredLanguage", value="ja")]
    payload = {
        "schemas": [mocker.ANY],
        "operations": [{"op": "replace", "path": "preferredLanguage", "value": "ja"}],
    }
    expected.preferred_language = "ja"

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    mock_patch = mocker.patch.object(server.clients.users.requests, "patch")
    mock_patch.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_patch.return_value.status_code = HTTPStatus.OK
    mock_send = signal_send["user_updated"]

    result = users.patch_by_id(expected.id, operations, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_patch.assert_called_once()
    (url,), kwargs = mock_patch.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{expected.id}"
    assert kwargs["json"]["request"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["json"]["request"]["signature"] == spy_signature.spy_return
    assert kwargs["json"]["Operations"] == payload["operations"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout

    _, kwargs = mock_send.call_args
    assert kwargs["user"] == expected


def test_patch_by_id_with_include(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="preferredLanguage", value="ja")]
    include = {"user_name", "preferred_language"}

    mock_patch = mocker.patch.object(server.clients.users.requests, "patch")
    mock_patch.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_patch.return_value.status_code = HTTPStatus.OK

    result = users.patch_by_id(
        expected.id, operations, include=include, access_token=access_token, client_secret=client_secret
    )

    assert result == expected
    mock_patch.assert_called_once()
    (url,), kwargs = mock_patch.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{expected.id}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]


def test_patch_by_id_with_exclude(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, expected, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="preferredLanguage", value="ja")]
    exclude = {"meta"}

    mock_patch = mocker.patch.object(server.clients.users.requests, "patch")
    mock_patch.return_value.text = expected.model_dump_json(ensure_ascii=False, by_alias=True)
    mock_patch.return_value.status_code = HTTPStatus.OK

    result = users.patch_by_id(
        expected.id, operations, exclude=exclude, access_token=access_token, client_secret=client_secret
    )

    assert result == expected
    mock_patch.assert_called_once()
    (url,), kwargs = mock_patch.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_USERS_ENDPOINT}/{expected.id}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)


def test_patch_by_id_map_error_with_bad_request(
    config: RuntimeConfig, map_user, map_error, signal_send, mocker: MockerFixture
):
    _, user, _ = map_user
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="preferredLanguage", value="ja")]

    mock_patch = mocker.patch.object(server.clients.users.requests, "patch")
    mock_patch.return_value.text = raw_error
    mock_patch.return_value.status_code = HTTPStatus.BAD_REQUEST
    mock_send = signal_send["user_updated"]

    result = users.patch_by_id(user.id, operations, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_send.assert_not_called()


def test_patch_by_id_http_error(config: RuntimeConfig, map_user, signal_send, mocker: MockerFixture):
    _, user, _ = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    operations = [ReplaceOperation(path="preferredLanguage", value="ja")]

    mock_patch = mocker.patch.object(server.clients.users.requests, "patch")
    mock_patch.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_patch.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)
    mock_send = signal_send["user_updated"]

    with pytest.raises(HTTPError):
        users.patch_by_id(user.id, operations, access_token=access_token, client_secret=client_secret)

    mock_send.assert_not_called()


def test_get_self(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = users.get_self(access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_SELF_ENDPOINT}"
    assert "attributes" not in kwargs["params"]
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_self_with_include(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    include = {"user_name", "preferred_language"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = users.get_self(include=include, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_SELF_ENDPOINT}"
    assert kwargs["params"]["attributes"] == ",".join(include | {"id"})
    assert "excludedAttributes" not in kwargs["params"]
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_self_with_exclude(config: RuntimeConfig, map_user, mocker: MockerFixture):
    _, expected, raw_json = map_user
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    spy_time_stamp = mocker.spy(server.clients.users, "get_time_stamp")
    spy_signature = mocker.spy(server.clients.users, "compute_signature")

    exclude = {"meta"}

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_json
    mock_get.return_value.status_code = HTTPStatus.OK

    result = users.get_self(exclude=exclude, access_token=access_token, client_secret=client_secret)

    assert result == expected
    mock_get.assert_called_once()
    (url,), kwargs = mock_get.call_args
    _, _, path, *_ = urlsplit(url)
    assert path == f"{MAP_SELF_ENDPOINT}"
    assert "attributes" not in kwargs["params"]
    assert kwargs["params"]["excludedAttributes"] == ",".join(exclude)
    assert kwargs["params"]["time_stamp"] == spy_time_stamp.spy_return
    assert kwargs["params"]["signature"] == spy_signature.spy_return
    assert kwargs["headers"]["Authorization"] == f"Bearer {access_token}"
    assert kwargs["timeout"] == config.MAP_CORE.timeout


def test_get_self_map_error_with_bad_request(config: RuntimeConfig, map_error, mocker: MockerFixture):
    _, expected, raw_error = map_error
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.text = raw_error
    mock_get.return_value.status_code = HTTPStatus.BAD_REQUEST

    result = users.get_self(access_token=access_token, client_secret=client_secret)

    assert result == expected


def test_get_self_http_error(config: RuntimeConfig, mocker: MockerFixture):
    access_token, client_secret = uuid4().hex[:8], uuid4().hex

    mock_get = mocker.patch.object(server.clients.users.requests, "get")
    mock_get.return_value.status_code = HTTPStatus.UNAUTHORIZED
    mock_get.return_value.raise_for_status.side_effect = HTTPError(HTTPStatus.UNAUTHORIZED.phrase)

    with pytest.raises(HTTPError):
        users.get_self(access_token=access_token, client_secret=client_secret)


def test__alias_generator(original_alias, mocker: MockerFixture):
    mock_generator = mocker.MagicMock(side_effect=to_camel)
    mocker.patch.object(MapUser, "model_config", {"alias_generator": mock_generator})

    assert unwrap(users._a)("user_name") == "userName"

    mock_generator.assert_called_once_with("user_name")


def test__alias_serialization(original_alias, mocker: MockerFixture):
    mock_generator = mocker.NonCallableMock(spec_set=AliasGenerator)
    mock_generator.serialization_alias.side_effect = to_camel
    mocker.patch.object(MapUser, "model_config", {"alias_generator": mock_generator})

    assert unwrap(users._a)("user_name") == "userName"

    mock_generator.serialization_alias.assert_called_once_with("user_name")


def test__alias_not_set(original_alias, mocker: MockerFixture):
    mock_config = mocker.MagicMock(spec=dict)
    mock_config.get.return_value = None
    mocker.patch.object(MapUser, "model_config", mock_config)

    assert unwrap(users._a)("user_name") == "user_name"
    mock_config.get.assert_called_once_with("alias_generator")


def test_handle_user_updated(map_user, mocker: MockerFixture):
    _, user, _ = map_user
    eppn_values = [eppn.value for eppn in user.edu_person_principal_names or []]

    mock_get_by_id_clear = mocker.patch.object(users.get_by_id, "clear_cache")
    mock_get_by_eppn_clear = mocker.patch.object(users.get_by_eppn, "clear_cache")

    unwrap(users.handle_user_updated)(None, user_id=user.id)

    mock_get_by_id_clear.assert_not_called()
    mock_get_by_eppn_clear.assert_not_called()

    unwrap(users.handle_user_updated)(None, user=user)

    mock_get_by_id_clear.assert_called_once_with(user.id)
    mock_get_by_eppn_clear.assert_called_once_with(*eppn_values)


def test_handle_user_updated_by_eppn(map_user, mocker: MockerFixture):
    _, user, _ = map_user
    eppn_values = [eppn.value for eppn in user.edu_person_principal_names or []]

    mock_clear = mocker.patch.object(users.get_by_eppn, "clear_cache")

    unwrap(users.handle_user_updated_by_eppn)(None, eppns=[])

    mock_clear.assert_not_called()

    unwrap(users.handle_user_updated_by_eppn)(None, eppns=eppn_values)

    mock_clear.assert_called_once_with(*eppn_values)


def test_handle_user_updated_by_id(map_user, mocker: MockerFixture):
    _, user, _ = map_user

    mock_clear = mocker.patch.object(users.get_by_id, "clear_cache")

    unwrap(users.handle_user_updated_by_id)(None, user=user)

    mock_clear.assert_not_called()

    unwrap(users.handle_user_updated_by_id)(None, user_id=user.id)

    mock_clear.assert_called_once_with(user.id)


def test_handle_reset_search_cache(mocker: MockerFixture):
    mock_clear = mocker.patch.object(users.search, "clear_cache")

    unwrap(users.handle_reset_search_cache)(None)

    mock_clear.assert_called_once()
