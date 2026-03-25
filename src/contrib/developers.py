#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Helpers for developers contributing to the project."""

import typing as t

from flask import (
    Blueprint,
    Response,
    jsonify,
    make_response,
    redirect,
    request,
    session,
)
from flask_login import login_user

from server.auth import build_account_store_key
from server.datastore import account_store
from server.entities.login_user import LoginUser


if t.TYPE_CHECKING:
    from server.config import RuntimeConfig


def create_developer_blueprint(config: RuntimeConfig) -> Blueprint:
    """Create a Flask blueprint for developer tools.

    Returns:
        Blueprint: The developer tools blueprint.
    """
    bp = Blueprint("developer", __name__)

    dev_config = config.DEVELOP
    dev_accounts = {a.eppn: a for a in dev_config.accounts} if dev_config else {}

    @bp.post("/login")
    def login() -> Response:
        """Handle developer login.

        Returns:
            Response: A response indicating successful login.
        """
        if not dev_config or (eppn := request.json.get("eppn")) not in dev_accounts:
            return Response(status=401)

        account_data = dev_accounts[eppn]
        user = LoginUser(
            map_id=account_data.id,
            eppn=account_data.eppn,
            is_member_of=account_data.is_member_of,
            user_name=account_data.user_name,
            session_id="",
        )
        login_user(user)
        user.session_id = session_id = session["_id"]

        key = build_account_store_key(session_id)
        alias: t.Callable[[str], str] = LoginUser.model_config.get(
            "alias_generator", lambda x: x
        )  # pyright: ignore[reportAssignmentType]
        account_data = user.model_dump(mode="json", by_alias=True) | {
            alias("is_system_admin"): str(user.is_system_admin)
        }

        account_store.hset(key, mapping=account_data)
        session_ttl: int = config.SESSION.sliding_lifetime
        if session_ttl >= 0:
            account_store.expire(key, session_ttl)

        next_location = request.args.get("next")
        location = "/" if not next_location else f"/?next={next_location}"
        return make_response(redirect(location))

    @bp.get("/accounts")
    def accounts() -> Response:
        """Developer accounts list.

        Returns:
            Response: A response containing the list of developer accounts.
        """
        return jsonify(eppns=list(dev_accounts.keys()))

    return bp
