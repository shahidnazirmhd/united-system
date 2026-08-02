"""Leave's implementation of `apps.approvals`'s
`ApprovalChainResolverPort` — the piece that tells the generic Approval
Engine "who approves a leave request, at a given level," without the
engine ever needing to know Leave exists.

Registered into `apps.approvals.application.registry.chain_resolver_registry`
by `apps/leave/apps.py`'s `ready()`, keyed by
`apps.leave.infrastructure.approval_request_adapter.SUBJECT_TYPE_LEAVE_REQUEST`
— the same "register a handler at Django app-startup time" idiom already
established by `EventBus.subscribe()` (see that file's docstring).

Two levels, as of Phase 13's HR review requirement: level 1 resolves to the
applicant's manager (unchanged since Phase 9); level 2 resolves to "any
employee currently holding `leave.manage_leave`" — a leave is not finalized
(balance updated, request recorded, employee notified it's fully
processed) until *this* level also approves, no matter what the manager
already decided on Telegram. Every level beyond that returns `None` (chain
complete). Extending Leave to a second approval level was a change to this
file's `resolve_next_approver` only — exactly the extensibility the
Phase 9 brief called for. `apps.approvals` itself needed no change to
support a second level existing, only a new *kind* of level assignment
(`ApproverAssignment.for_permission`, added generically to the engine so
any future subject module can use it too, not just Leave).

Approval Workflow Changes review round (v1): each level's `ApproverAssignment`
gained `restricted_to_channel` — level 1 was `ApprovalChannel.TELEGRAM`
("Level 1 approval must only be performed through Telegram") and level 2 was
`ApprovalChannel.WEB` ("Level 2 approval should always be completed from
the HR system").

Approval Workflow Changes v2 — level 1's Telegram-only restriction was
REMOVED per updated business direction: "Manager approval can be completed
through Telegram or the HR system." Level 1 is now a DUAL-MODE assignment
(`ApproverAssignment.for_employee_or_permission_by_channel`, new and fully
generic on `apps.approvals` itself — see that value object's docstring):
the applicant's manager (`employee_id`) can still decide via Telegram
purely by being that manager, identity-checked exactly as since Phase 9;
on the web HR system, decision authority instead requires holding the new
`approvals.level1_approve` permission (`permission_code`) — whether or not
the web caller is literally the manager. This is what "HR system Level 1
approval must be controlled by role permissions... do not hardcode users
or roles for approval access" means in practice: the engine never checks
"is this the manager" on the web path at all, only "does this caller hold
this permission code," resolved fresh via Identity's roles at decide-time,
exactly the same mechanism level 2 already used for its own permission.

Level 2 is unchanged in shape (still `for_permission`, still
`restricted_to_channel=ApprovalChannel.WEB` — "Level 2 approval must be
completed from the HR system" is unchanged) but its permission code
switches from `leave.manage_leave` to the new, engine-level
`approvals.level2_approve` — a deliberately SEPARATE permission from
`leave.manage_leave`, which continues to gate Leave's own management
screens (types, balances, the HR queue) and has nothing to do with
deciding an approval step. See
`apps/approvals/migrations/0006_seed_level_approval_permissions.py` for
where both new codes are registered and their default role grants.
"""
from __future__ import annotations

import uuid

from apps.approvals.application.ports import ApprovalChainResolverPort
from apps.approvals.domain.enums import ApprovalChannel
from apps.approvals.domain.value_objects import ApproverAssignment
from apps.leave.application.ports import EmployeeLookupPort

#: Must match `apps.approvals.interface.permissions.LEVEL1_APPROVE` exactly
#: — not imported from there directly, since this is infrastructure and
#: that is another module's interface layer (this module's own layering
#: rule: infrastructure depends on domain/application, never "up" into
#: interface, even within the same module, let alone a different one — the
#: cross-module `apps.OTHER_MODULE.interface.dependencies` imports seen
#: elsewhere in this codebase are a different, sanctioned exception for
#: reaching another module's composition root, not this).
_LEVEL1_APPROVE_PERMISSION_CODE = "approvals.level1_approve"

#: Must match `apps.approvals.interface.permissions.LEVEL2_APPROVE` exactly
#: — same non-import discipline as `_LEVEL1_APPROVE_PERMISSION_CODE` above.
#: Deliberately NOT `apps.leave.interface.permissions.MANAGE_LEAVE`
#: (`"leave.manage_leave"`) any more — see this module's docstring for why
#: final-approval authority was split out into its own, separate
#: permission.
_LEVEL2_APPROVE_PERMISSION_CODE = "approvals.level2_approve"

#: Leave review round: the exact sentence pushed to the APPLICANT the
#: moment the manager approves and the chain advances to level 2 — never a
#: substitute for the final "fully processed" push
#: `handle_approval_decided`/`ApprovalNotificationPort.notify_decision_made`
#: sends once HR/Admin actually decides. See
#: `ApproverAssignment.requester_notification_message`'s docstring for why
#: this subject-specific wording living here (not in `apps.approvals`) is
#: what keeps the engine itself generic.
_MANAGER_APPROVED_AWAITING_HR_MESSAGE = (
    "Your manager has approved your leave request. It is now awaiting HR processing."
)

#: Level 2's assignment never varies per-request — pulled out as a
#: module-level constant so `resolve_next_approver` reads as "what," not
#: "how."
#:
#: `restricted_to_channel=ApprovalChannel.WEB` (Approval Workflow Changes
#: review round, unchanged in v2): "Level 2 approval must be completed from
#: the HR system" — an HR/Admin user who happens to also be linked to
#: Telegram cannot decide this level from there; `ApprovalService.decide`
#: (and `list_pending_for_approver`'s filtering) enforce this generically,
#: this resolver only supplies the fact.
_HR_REVIEW_ASSIGNMENT = ApproverAssignment.for_permission(
    _LEVEL2_APPROVE_PERMISSION_CODE,
    requester_notification_message=_MANAGER_APPROVED_AWAITING_HR_MESSAGE,
    restricted_to_channel=ApprovalChannel.WEB.value,
)


class LeaveApprovalChainResolver(ApprovalChainResolverPort):
    def __init__(self, employee_lookup: EmployeeLookupPort) -> None:
        self._employees = employee_lookup

    def resolve_next_approver(
        self,
        *,
        subject_type: str,
        subject_id: uuid.UUID,
        requested_by_employee_id: uuid.UUID,
        level: int,
    ) -> ApproverAssignment | None:
        if level == 1:
            manager_id = self._employees.get_manager_employee_id(requested_by_employee_id)
            if manager_id is None:
                # No manager assigned — the chain can't even start. Expected
                # to already be prevented upstream by
                # `LeaveValidationService.validate_manager_available_for_approval`
                # (see `apps.leave.domain.exceptions.NoManagerAssignedError`),
                # so this should be unreachable in practice.
                return None
            # Approval Workflow Changes v2 — dual-mode: the manager
            # (`manager_id`) can decide via Telegram purely by being that
            # manager (identity check, unchanged since Phase 9); on the web
            # HR system (`permission_required_for_channel=ApprovalChannel
            # .WEB`), decision authority instead requires holding
            # `approvals.level1_approve` — whether or not the web caller is
            # literally the manager. Enforced generically by
            # `ApprovalStep.is_decidable_by`, not by this resolver — see
            # that method's docstring for the exact per-channel rule this
            # produces.
            return ApproverAssignment.for_employee_or_permission_by_channel(
                employee_id=manager_id,
                permission_code=_LEVEL1_APPROVE_PERMISSION_CODE,
                permission_required_for_channel=ApprovalChannel.WEB.value,
            )
        if level == 2:
            # HR/Admin review (Phase 13) — any employee holding
            # `approvals.level2_approve` may decide this level, not one
            # named person. See `ApproverAssignment.for_permission`'s
            # docstring for exactly what that means for notifications and
            # "My Pending Approvals."
            return _HR_REVIEW_ASSIGNMENT
        # Level 3+: chain complete. The moment level 2 approves,
        # `ApprovalService` marks the whole request APPROVED and fires
        # `ApprovalDecided`, which is what
        # `apps.leave.interface.event_handlers.handle_approval_decided`
        # reacts to by finally updating the balance and recording the leave
        # — never a moment earlier.
        return None
