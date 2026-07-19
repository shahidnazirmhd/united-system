"""Standard API response envelope used by every module's interface layer.

A consistent shape means the future React frontend and Telegram Gateway can
parse any endpoint's response the same way (HRMS_Architecture.md section 6).
This is also the target shape the custom exception handler
(exception_handler.py) produces on error, so success and error responses are
always shaped consistently across the whole API.
"""
from __future__ import annotations

from typing import Any

from rest_framework.response import Response

from shared_kernel.domain.repository import PageResult


def success_response(
    data: Any = None,
    *,
    status_code: int = 200,
    meta: dict | None = None,
) -> Response:
    payload: dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=status_code)


def paginated_response(page_result: PageResult, serialized_items: Any) -> Response:
    """The envelope every module's list/search endpoint returns.

    Pagination here is driven by `BaseRepository`/`PageResult`
    (shared_kernel/domain/repository.py), not DRF's `DEFAULT_PAGINATION_CLASS`
    machinery — Clean Architecture puts pagination behind the repository, so
    a ViewSet built on `BaseViewSet` never touches DRF's paginator directly.
    `StandardResultsSetPagination` (pagination.py) remains available for any
    simpler endpoint that queries a plain queryset directly instead of going
    through a repository/service.
    """
    return success_response(
        serialized_items,
        meta={
            "page": page_result.page,
            "page_size": page_result.page_size,
            "total_count": page_result.total_count,
            "total_pages": page_result.total_pages,
        },
    )


def error_response(
    *,
    code: str,
    message: str,
    status_code: int = 400,
    details: Any = None,
) -> Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return Response({"success": False, "error": error}, status=status_code)
