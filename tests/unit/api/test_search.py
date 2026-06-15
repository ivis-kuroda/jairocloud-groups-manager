from http import HTTPStatus
from types import SimpleNamespace

from pytest_mock import MockerFixture

import server.api.search

from server.api import search as search_api
from server.api.schemas import ErrorResponse, GlobalSearchQuery, GlobalSearchResult
from server.entities.search_request import SearchResult
from server.exc import InvalidQueryError
from server.messages import E

from tests.helpers import assert_message, unwrap


def test_get(user_summaries, group_summaries, repository_summaries, mocker: MockerFixture):
    term, size, offset = "test", 5, 1
    query = GlobalSearchQuery(q=term, l=size)
    expected_query = SimpleNamespace(q=term, l=size)
    mock_make_criteria = mocker.patch.object(server.api.search, "make_criteria_object")
    mock_make_criteria.side_effect = lambda *_, **kwargs: SimpleNamespace(**kwargs)

    rnum, gnum, unum = len(repository_summaries), len(group_summaries), len(user_summaries)
    rresrc, gresrc, uresrc = repository_summaries[:size], group_summaries[:size], list(user_summaries.values())[:size]
    rresult = SearchResult(total=rnum, page_size=size, offset=offset, resources=rresrc)
    gresult = SearchResult(total=gnum, page_size=size, offset=offset, resources=gresrc)
    uresult = SearchResult(total=unum, page_size=size, offset=offset, resources=uresrc)
    mock_rsearch = mocker.patch.object(server.api.search.repositories, "search", return_value=rresult)
    mock_gsearch = mocker.patch.object(server.api.search.groups, "search", return_value=gresult)
    mock_usearch = mocker.patch.object(server.api.search.users, "search", return_value=uresult)

    res, status = unwrap(search_api.get)(query)

    assert status == HTTPStatus.OK
    assert isinstance(res, GlobalSearchResult)
    assert res.root[0].total == rnum
    assert res.root[0].resources == rresrc
    assert getattr(res.root[0], "type", None) == "repositories"
    mock_rsearch.assert_called_once_with(expected_query)

    assert res.root[1].total == gnum
    assert res.root[1].resources == gresrc
    assert getattr(res.root[1], "type", None) == "groups"
    mock_gsearch.assert_called_once_with(expected_query)

    assert res.root[2].total == unum
    assert res.root[2].resources == uresrc
    assert getattr(res.root[2], "type", None) == "users"
    mock_usearch.assert_called_once_with(expected_query)


def test_get_partial_invalid_query_error(repository_summaries, user_summaries, mocker: MockerFixture):
    search_term, size = "test", 10
    query = GlobalSearchQuery(q=search_term, l=size)

    rnum, unum = len(repository_summaries), len(user_summaries)
    rresrc, uresrc = repository_summaries[:size], list(user_summaries.values())[:size]
    rresult = SearchResult(total=rnum, page_size=size, offset=0, resources=rresrc)
    uresult = SearchResult(total=unum, page_size=size, offset=0, resources=uresrc)

    mocker.patch.object(server.api.search.repositories, "search", return_value=rresult)
    mock_groups_search = mocker.patch.object(server.api.search.groups, "search")
    mock_groups_search.side_effect = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)
    mocker.patch.object(server.api.search.users, "search", return_value=uresult)

    resp, status = unwrap(search_api.get)(query)

    assert status == HTTPStatus.OK
    assert isinstance(resp, GlobalSearchResult)


def test_get_all_invalid_query_error(mocker: MockerFixture):
    search_term, size = "test", 10
    query = GlobalSearchQuery(q=search_term, l=size)
    error = InvalidQueryError(E.UNSUPPORTED_SEARCH_FILTER)

    mocker.patch.object(server.api.search.repositories, "search", side_effect=error)
    mocker.patch.object(server.api.search.groups, "search", side_effect=error)
    mocker.patch.object(server.api.search.users, "search", side_effect=error)

    res, status = unwrap(search_api.get)(query)

    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(res, ErrorResponse)
    assert_message(res.message, E.FAILED_GLOBAL_SEARCH)
