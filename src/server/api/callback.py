#
# Copyright (C) 2025 National Institute of Informatics.
#

"""API router for callback endpoints."""

import traceback

from flask import Blueprint, Response, make_response, redirect
from flask_pydantic import validate

from server.exc import CredentialsError, DatabaseError, OAuthTokenError
from server.services import token

from .schemas import OAuthTokenQuery


bp = Blueprint("callback", __name__)


@bp.get("/auth-code")
@validate()
def auth_code(query: OAuthTokenQuery) -> Response:
    """Handle the authorization code callback.

    This endpoint receives the authorization code from the
    mAP Core Authorization Server following user operation.

    Returns:
        Response: Redirect response to the home page.
    """
    try:
        token.issue_access_token(query.code)
    except OAuthTokenError, DatabaseError, CredentialsError:
        traceback.print_exc()

    return make_response(redirect("/"))
