"""Parses an HTTP request's query string into a `QueryParams` (see
shared_kernel/domain/repository.py) — the one place HTTP-specific
query-string parsing happens, so a ViewSet's `list()` method stays a
three-line call rather than repeating `request.query_params.get(...)`
parsing in every module.
"""
from __future__ import annotations

from rest_framework.request import Request

from shared_kernel.domain.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from shared_kernel.domain.repository import QueryParams


def parse_list_query_params(
    request: Request,
    *,
    filter_fields: tuple[str, ...] = (),
    search_fields: tuple[str, ...] = (),
    default_ordering: tuple[str, ...] = (),
) -> QueryParams:
    params = request.query_params

    filters: dict[str, object] = {}
    for field_name in filter_fields:
        value = params.get(field_name)
        if value not in (None, ""):
            filters[field_name] = value

    search = params.get("search") or params.get("q") or None

    ordering_param = params.get("ordering")
    ordering = tuple(ordering_param.split(",")) if ordering_param else default_ordering

    try:
        page = int(params.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = int(params.get("page_size", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    page_size = min(page_size, MAX_PAGE_SIZE)

    return QueryParams(
        filters=filters,
        search=search,
        search_fields=search_fields,
        ordering=ordering,
        page=page,
        page_size=page_size,
    )
