#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Model for search GET request."""

import typing as t

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from server.const import MAP_LIST_RESPONSE_SCHEMA

from .common import camel_case_config, forbid_extra_config


class SearchRequestParameter(BaseModel):
    """Model for search GET request query parameters."""

    filter: str | None = None
    """The filter expression to be applied to the search."""

    start_index: int | None = None
    """The 1-based index of the first result to be returned."""

    count: int | None = None
    """The maximum number of results to be returned."""

    sort_by: str | None = None
    """The attribute to sort the results by."""

    sort_order: t.Literal["ascending", "descending"] | None = None
    """The order in which to sort the results."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class SearchResponse[T: BaseModel](BaseModel):
    """Model for search GET response payload."""

    schemas: t.Annotated[t.Sequence[str], Field(frozen=True)] = [
        MAP_LIST_RESPONSE_SCHEMA
    ]
    """Schema URIs that define the attributes present in the response."""

    total_results: int
    """The total number of results matching the search criteria."""

    start_index: int
    """The 1-based index of the first result in the current set."""

    items_per_page: int
    """The number of results returned per page."""

    resources: t.Annotated[
        list[T], Field(validation_alias="Resources", serialization_alias="Resources")
    ]
    """The list of resources returned by the search."""

    model_config = camel_case_config | forbid_extra_config
    """Configure to use camelCase aliasing and forbid extra fields."""


class SearchResult[T: BaseModel](BaseModel):
    """Model for individual search result item."""

    total: int
    """The total number of results matching the search criteria."""

    page_size: int
    """The number of results returned per page."""

    offset: int
    """The offset of the current result set."""

    resources: list[T]
    """The list of resources returned by the search."""

    model_config = camel_case_config | {"extra": "allow"}
    """Configure to use camelCase aliasing and allow extra fields."""


class FilterOption[T: BaseModel](BaseModel):
    """Model for filter option used in search requests."""

    key: str
    """The key of the filter option."""

    description: str | None = None
    """The description of the filter option."""

    type: t.Literal["string", "number", "date"]
    """The type of the filter option."""

    multiple: bool
    """Whether multiple selections are allowed for the filter option."""

    items: t.Sequence[t.Mapping[str, str | int]] | None = None
    """The items of the filter option as a dictionary of value-label pairs."""

    _alias_generator: t.ClassVar[t.Callable[[str], str]] = to_camel
    """Alias generator to convert item keys to camelCase."""

    model_config = forbid_extra_config
    """Configure to forbid extra fields."""
