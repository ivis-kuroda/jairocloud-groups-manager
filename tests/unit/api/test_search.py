from flask import Flask
from pytest_mock import MockerFixture

from server.api import search as search_api
from server.api.schemas import ErrorResponse, GlobalSearchQuery, GlobalSearchResult
from server.entities.search_request import SearchResult
from server.exc import InvalidQueryError

from tests.helpers import unwrap


def test_get_success(app: Flask, mocker: MockerFixture) -> None:
    query = GlobalSearchQuery(q="test", l=10)
    excepted_status = 200
    result_repo = SearchResult(total=1, page_size=10, offset=0, resources=[])
    result_group = SearchResult(total=2, page_size=10, offset=0, resources=[])
    result_user = SearchResult(total=3, page_size=10, offset=0, resources=[])
    mocker.patch("server.services.repositories.search", return_value=result_repo)
    mocker.patch("server.services.groups.search", return_value=result_group)
    mocker.patch("server.services.users.search", return_value=result_user)
    original_func = unwrap(search_api.get)
    resp, status = original_func(query)
    assert status == excepted_status
    assert isinstance(resp, GlobalSearchResult)


def test_get_partial_invalid_query_error(app: Flask, mocker: MockerFixture) -> None:
    query = GlobalSearchQuery(q="test", l=10)
    excepted_status = 200

    result_repo = SearchResult(total=1, page_size=10, offset=0, resources=[])
    mocker.patch("server.services.repositories.search", return_value=result_repo)
    mocker.patch("server.services.groups.search", side_effect=InvalidQueryError("fail"))
    result_user = SearchResult(total=3, page_size=10, offset=0, resources=[])
    mocker.patch("server.services.users.search", return_value=result_user)
    original_func = unwrap(search_api.get)
    resp, status = original_func(query)
    assert status == excepted_status
    assert isinstance(resp, GlobalSearchResult)


def test_get_all_invalid_query_error(app: Flask, mocker: MockerFixture) -> None:
    query = GlobalSearchQuery(q="test", l=10)
    excepted_status = 400
    mocker.patch("server.services.repositories.search", side_effect=InvalidQueryError("fail"))
    mocker.patch("server.services.groups.search", side_effect=InvalidQueryError("fail"))
    mocker.patch("server.services.users.search", side_effect=InvalidQueryError("fail"))
    original_func = unwrap(search_api.get)
    resp, status = original_func(query)
    assert status == excepted_status
    assert isinstance(resp, ErrorResponse)
    assert resp.message == "Failed to get search results"
