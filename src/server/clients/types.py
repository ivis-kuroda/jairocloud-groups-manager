#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Types for client-related.

These types are used in client arguments.
"""

import typing as t


# ruff: file-ignore[unused-private-protocol]


class _SpCerts(t.Protocol):
    """Certificates for mutual TLS authentication."""

    crt: str
    """Path to the client certificate file."""

    key: str
    """Path to the client private key file."""


class _ClientCreds(t.Protocol):
    """Client credentials issued from mAP Core Authorization Server."""

    client_id: str
    """Client ID."""

    client_secret: str
    """Client secret."""
