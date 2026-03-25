#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Entry point for the background task processing application."""

import typing as t

from server.factory import create_app


if t.TYPE_CHECKING:
    from celery import Celery

flask_app = create_app(__name__)
celery_app: Celery = flask_app.extensions["celery"]
