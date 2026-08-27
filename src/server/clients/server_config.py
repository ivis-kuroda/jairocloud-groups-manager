#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Client for mAP Core service configuration."""

import requests

from server.config import config

from .utils import compute_signature, get_time_stamp


MAP_SP_CONFIG_ENDPOINT = "/api/v2/ServiceProviderConfig"
MAP_SCHEMAS_ENDPOINT = "/api/v2/Schemas"


def get_config(
    *,
    access_token: str,
    client_secret: str,
) -> dict:
    """Get the Service Provider configuration from mAP Core.

    Args:
        access_token (str): The access token for authentication.
        client_secret (str): The client secret for signature computation.

    Returns:
        dict: Service Provider configuration.
    """
    time_stamp = get_time_stamp()
    signature = compute_signature(client_secret, access_token, time_stamp)

    response = requests.get(
        f"{config.MAP_CORE.base_url}{MAP_SP_CONFIG_ENDPOINT}",
        params={
            "time_stamp": time_stamp,
            "signature": signature,
        },
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=config.MAP_CORE.timeout,
    )

    response.raise_for_status()

    return response.json()
