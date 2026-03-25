#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Models for updating cache db entities."""

import typing as t

from datetime import datetime

from pydantic import BaseModel

from .common import camel_case_config, forbid_extra_config
from .summaries import RepositorySummary


class RepositoryCache(RepositorySummary):
    """Model for repository cache entity."""

    updated: datetime | None = None
    """The update timestamp of the repository cache entry."""

    status: RepositoryStatus | None = None
    """The status of the cache update task."""


class TaskDetail(BaseModel):
    """Model for task detail entity."""

    results: list[RepositoryCache]
    """The list of results from the task."""

    status: TaskStatus | None = None
    """The status of the task."""

    current: str
    """The repository id currently being processed."""

    done: int
    """The number of completed items."""

    total: int
    """The total number of items to process."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


type RepositoryStatus = t.Literal["success", "failed"]


type TaskStatus = t.Literal["pending", "started", "in_progress", "completed"]
