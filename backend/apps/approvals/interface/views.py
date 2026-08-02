"""Approval Engine HTTP endpoints.

Two parallel surfaces, both delegating to the exact same `ApprovalService`
— no business logic is duplicated between them, only "how do we know which
employee this is" differs, matching `apps.leave.interface.views`'s
identical two-surface pattern:

* Self-service / HR (this file's `*View` classes without `Telegram` in the
  name) — JWT-authenticated, employee resolved from
  `request.user.user_id`.
* Gateway-facing (`*TelegramView` classes) — `HasInternalServiceKey`, no
  JWT, employee resolved from a `telegram_user_id` the Gateway supplies.

Every method does exactly three things — deserialize, call the service,
serialize the result (CODING_STANDARD.md: "no business logic in views").
"""
from __future__ import annotations

import uuid

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.approvals.application.dtos import DecideApprovalRequest
from apps.approvals.domain.enums import ApprovalChannel
from apps.approvals.domain.exceptions import ApprovalCallerNotAnEmployeeError
from apps.approvals.interface import dependencies
from apps.approvals.interface.serializers import (
    ApprovalRequestResponseSerializer,
    DecideApprovalSerializer,
    DecideApprovalTelegramSerializer,
    TelegramUserIdQuerySerializer,
)
from shared_kernel.api.permissions import HasInternalServiceKey
from shared_kernel.api.response import success_response
from shared_kernel.api.throttling import StandardUserRateThrottle

# See apps/employees/interface/telegram_views.py's docstring for the full
# explanation of why this is required, not just permission_classes.
_NO_AUTHENTICATION: list = []


def _resolve_employee_id_for_user(user_id: uuid.UUID) -> uuid.UUID:
    employee_id = dependencies.build_employee_lookup().get_employee_id_by_user_id(user_id)
    if employee_id is None:
        raise ApprovalCallerNotAnEmployeeError()
    return employee_id


def _resolve_employee_id_for_user_or_none(user_id: uuid.UUID) -> uuid.UUID | None:
    """Same lookup as `_resolve_employee_id_for_user`, but never raises —
    for READ endpoints only (`MyPendingApprovalsView`,
    `ApprovalRequestDetailView`, `ApprovalHistoryBySubjectView`). A caller
    with no linked Employee record (a pure Admin/HR account) is trivially
    "not the requester and not an approver" of anything — that is either an
    empty list or a permission-gated fallback, never a 404 raised purely
    because the caller isn't an employee. `DecideApprovalView` (a WRITE)
    keeps using the raising resolver above — deciding an approval without
    being an employee really is an error."""
    return dependencies.build_employee_lookup().get_employee_id_by_user_id(user_id)


def _resolve_employee_id_for_telegram_user(telegram_user_id: int) -> uuid.UUID:
    employee_id = dependencies.build_employee_lookup().get_employee_id_by_telegram_user_id(telegram_user_id)
    if employee_id is None:
        raise ApprovalCallerNotAnEmployeeError()
    return employee_id


# ============================================================================
# Self-service / HR surface — JWT
# ============================================================================


class MyPendingApprovalsView(APIView):
    """GET /api/v1/approvals/pending/me/ — every approval request currently
    awaiting a decision from the caller, across every subject module
    (Leave today; Attendance/Business Trip/Asset Requests/... in
    the future, with zero changes to this view)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="List my pending approvals", responses={200: ApprovalRequestResponseSerializer(many=True)}
    )
    def get(self, request: Request) -> Response:
        # `_or_none`: a caller with no linked Employee record has zero
        # pending approvals — an empty list, not a 404. See
        # `_resolve_employee_id_for_user_or_none`'s docstring.
        employee_id = _resolve_employee_id_for_user_or_none(request.user.user_id)
        if employee_id is None:
            return success_response([])
        result = dependencies.build_approval_service().list_pending_for_approver(
            employee_id, channel=ApprovalChannel.WEB.value
        )
        return success_response(ApprovalRequestResponseSerializer(result, many=True).data)


class ApprovalRequestDetailView(APIView):
    """GET /api/v1/approvals/<pk>/ — full detail (every step reached so
    far, in level order) for one approval request. The caller must be
    either the original requester or the approver of some step on this
    request; anyone else needs `approvals.view_approvals`."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(summary="Get approval request details", responses={200: ApprovalRequestResponseSerializer})
    def get(self, request: Request, pk: uuid.UUID) -> Response:
        from apps.approvals.interface.permissions import VIEW_APPROVALS

        # `_or_none`: a caller with no linked Employee record can still be
        # entitled to view this via `approvals.view_approvals` below — see
        # `_resolve_employee_id_for_user_or_none`'s docstring. `employee_id`
        # being `None` simply makes `is_requester`/`is_an_approver` False,
        # same as any other non-participant.
        employee_id = _resolve_employee_id_for_user_or_none(request.user.user_id)
        result = dependencies.build_approval_service().get_detail(pk)

        is_requester = result.requested_by_employee_id == employee_id
        is_an_approver = any(step.approver_employee_id == employee_id for step in result.steps)
        if not (is_requester or is_an_approver):
            principal = request.user
            if not (principal and principal.is_authenticated and principal.has_permission(VIEW_APPROVALS)):
                # Re-raised as "not found" rather than "forbidden" — same
                # data-ownership-mismatch judgment call
                # apps.leave.domain.exceptions.LeaveRequestOwnershipError's
                # docstring makes: a caller who could only reach this by
                # guessing another employee's approval request id gets a
                # generic 404, not a signal that the id was valid.
                from apps.approvals.domain.exceptions import ApprovalRequestNotFoundError

                raise ApprovalRequestNotFoundError()
        return success_response(ApprovalRequestResponseSerializer(result).data)


class ApprovalHistoryBySubjectView(APIView):
    """GET /api/v1/approvals/subject/<subject_type>/<subject_id>/ — every
    approval request ever raised for one subject (Phase 13: backs "View
    Leave Details"'s approval-status/history panel, but is subject-agnostic
    — any future subject module gets this for free, no new endpoint). Pure
    delegation to `ApprovalService.list_by_subject`, already implemented
    and unused by any endpoint before this phase.

    Same three-way authorization `ApprovalRequestDetailView` already uses
    for a single request, applied across the whole list: the caller may see
    it if they were the requester or an approver on ANY request for this
    subject, or if they hold `approvals.view_approvals`. An empty result
    (subject has no approval history, or doesn't exist) is returned as an
    empty list rather than a 404 — there is nothing ownership-sensitive to
    hide about "no rows," and the subject module's own detail endpoint
    (e.g. `LeaveRequestDetailView`) is what actually gates whether the
    subject itself may be viewed at all."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Get approval history for a subject",
        responses={200: ApprovalRequestResponseSerializer(many=True)},
    )
    def get(self, request: Request, subject_type: str, subject_id: uuid.UUID) -> Response:
        from apps.approvals.interface.permissions import VIEW_APPROVALS

        # `_or_none`: same reasoning as `ApprovalRequestDetailView.get`
        # above — a non-employee caller can still be entitled via
        # `approvals.view_approvals`.
        employee_id = _resolve_employee_id_for_user_or_none(request.user.user_id)
        result = dependencies.build_approval_service().list_by_subject(
            subject_type=subject_type, subject_id=subject_id
        )

        if result:
            is_requester = any(r.requested_by_employee_id == employee_id for r in result)
            is_an_approver = any(
                step.approver_employee_id == employee_id for r in result for step in r.steps
            )
            if not (is_requester or is_an_approver):
                principal = request.user
                if not (principal and principal.is_authenticated and principal.has_permission(VIEW_APPROVALS)):
                    result = []
        return success_response(ApprovalRequestResponseSerializer(result, many=True).data)


class DecideApprovalView(APIView):
    """POST /api/v1/approvals/<pk>/decide/ — approve or reject the current
    level, on the caller's own behalf."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Approve or reject an approval request",
        request=DecideApprovalSerializer,
        responses={200: ApprovalRequestResponseSerializer},
    )
    def post(self, request: Request, pk: uuid.UUID) -> Response:
        serializer = DecideApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee_id = _resolve_employee_id_for_user(request.user.user_id)
        result = dependencies.build_approval_service().decide(
            DecideApprovalRequest(
                approval_request_id=pk,
                acting_employee_id=employee_id,
                decision=data["decision"],
                comments=data["comments"],
                channel=ApprovalChannel.WEB.value,
            )
        )
        return success_response(ApprovalRequestResponseSerializer(result).data)


# ============================================================================
# Telegram Gateway-facing surface — HasInternalServiceKey, no JWT
# ============================================================================


class PendingApprovalsTelegramView(APIView):
    """GET /api/v1/approvals/telegram/pending/?telegram_user_id=... — backs
    the Gateway's `/pending_approvals` command."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="List pending approvals (Telegram)",
        parameters=[TelegramUserIdQuerySerializer],
        responses={200: ApprovalRequestResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = TelegramUserIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        employee_id = _resolve_employee_id_for_telegram_user(query.validated_data["telegram_user_id"])
        result = dependencies.build_approval_service().list_pending_for_approver(
            employee_id, channel=ApprovalChannel.TELEGRAM.value
        )
        return success_response(ApprovalRequestResponseSerializer(result, many=True).data)


class DecideApprovalTelegramView(APIView):
    """POST /api/v1/approvals/telegram/decide/ — backs the Gateway's
    inline Approve/Reject buttons (with an optional typed-in comment)."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="Approve or reject an approval request (Telegram)",
        request=DecideApprovalTelegramSerializer,
        responses={200: ApprovalRequestResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = DecideApprovalTelegramSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee_id = _resolve_employee_id_for_telegram_user(data["telegram_user_id"])
        result = dependencies.build_approval_service().decide(
            DecideApprovalRequest(
                approval_request_id=data["approval_request_id"],
                acting_employee_id=employee_id,
                decision=data["decision"],
                comments=data["comments"],
                channel=ApprovalChannel.TELEGRAM.value,
            )
        )
        return success_response(ApprovalRequestResponseSerializer(result).data)
