#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API endpoints for global search in the application."""

import traceback
import typing as t

from flask import Blueprint
from flask_login import login_required
from flask_pydantic import validate

from server.const import USER_ROLES
from server.entities.search_request import SearchResult
from server.exc import InvalidQueryError
from server.services import groups, repositories, users
from server.services.utils import make_criteria_object

from .helpers import roles_required
from .schemas import ErrorResponse, GlobalSearchQuery, GlobalSearchResult


bp = Blueprint("search", __name__)


@bp.get("/", strict_slashes=False)
@login_required
@roles_required(USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN)
@validate(response_by_alias=True)
def get(
    query: GlobalSearchQuery,
) -> tuple[GlobalSearchResult | ErrorResponse, int]:
    """Endpoint to perform a global search across repositories.

    Args:
        query (GlobalSearchQuery): The search query parameters.

    Returns:
         - If succeeded in getting search results,
            GlobalSearchResult and status code 200
         - If query is invalid or search fails in all categories,
            error message and status code 400
    """
    base_criteria = {"q": query.q, "l": query.l}
    categories: dict[str, tuple[t.Callable, t.Callable]] = {
        "repositories": (
            repositories.search,
            lambda: make_criteria_object("repositories", **base_criteria),
        ),
        "groups": (
            groups.search,
            lambda: make_criteria_object("groups", **base_criteria),
        ),
        "users": (
            users.search,
            lambda: make_criteria_object("users", **base_criteria),
        ),
    }

    results: list[SearchResult] = []
    errors = []
    for category, (search_func, criteria) in categories.items():
        try:
            result: SearchResult = search_func(criteria())
            results.append(result.model_copy(update={"type": category}))

        except InvalidQueryError as exc:
            traceback.print_exc()
            errors.append(exc)

    if errors and not results:
        return ErrorResponse(code="", message="Failed to get search results"), 400

    return GlobalSearchResult(root=results), 200
