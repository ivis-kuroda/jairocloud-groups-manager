#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides properties for path to server storages."""

import typing as t

from flask import current_app
from werkzeug.local import LocalProxy


if t.TYPE_CHECKING:
    from pathlib import Path

    from server.ext import JAIROCloudGroupsManager


def __get_storage(_type: str) -> Path:
    ext: JAIROCloudGroupsManager = current_app.extensions["jairocloud-groups-manager"]
    return getattr(ext, _type)


def _storage(_type: str):  # ruff:ignore[missing-return-type-private-function], for intersection-type inference
    def __type_asertion(_: object) -> t.TypeIs[Path]:
        return True

    proxy = LocalProxy(lambda: __get_storage(_type))

    if not __type_asertion(proxy):
        raise NotImplementedError  # pragma: no cover

    return proxy


current_storage = _storage("storage")
"""Property for path to the server storage directory."""

current_temporary_storage = _storage("temporary_storage")
"""Property for path to the temporary storage directory."""
