#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for Bulk operations of mAP Core API."""

from http import HTTPStatus

import requests

from pydantic import TypeAdapter

from server.clients.utils import compute_signature, get_time_stamp
from server.config import config
from server.const import (
    MAP_BULK_ENDPOINT,
)
from server.entities.bulk_request import (
    BulkOperation,
    BulkRequestPayload,
    BulkResponse,
)
from server.entities.map_error import MapError


type PostBulkResponse = BulkResponse | MapError
adapter: TypeAdapter[PostBulkResponse] = TypeAdapter(PostBulkResponse)


def post(
    operations: list[BulkOperation], access_token: str, client_secret: str
) -> PostBulkResponse:
    """Post bulk request in mAP Core.

    Args:
        operations (list[BulkOperation]): bulk operation request body.
        access_token (str): OAuth access token for authorization.
        client_secret (str): Client secret for Basic Authentication.

    Returns:
        PostBulkResponse:
          The BulkResponse resource if Bulk operation success, otherwise None.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)
    auth_params = {
        "time_stamp": time_stamp,
        "signature": signature,
    }

    payload = BulkRequestPayload(operations=operations).model_dump(
        mode="json",
        by_alias=True,
        exclude_unset=False,
    )

    response = requests.post(
        f"{config.MAP_CORE.base_url}{MAP_BULK_ENDPOINT}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={"request": auth_params} | payload,
        timeout=config.MAP_CORE.timeout,
    )

    if response.status_code > HTTPStatus.BAD_REQUEST:
        response.raise_for_status()

    return adapter.validate_json(response.text)
