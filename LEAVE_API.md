# Leave Module — API Reference

Base path: `/api/v1/leave/`. Interactive docs at `/api/docs/`, raw OpenAPI schema at `/api/schema/` — same source (drf-spectacular reading these same views) as `EMPLOYEE_API.md`/`IDENTITY_API.md`. This document is the human-readable companion.

Two parallel surfaces expose the same underlying `LeaveService`, no business logic duplicated between them — see `HRMS_Architecture.md`'s Phase 8 notes for the full reasoning:

- **Self-service / HR** (below, no `telegram/` in the path) — JWT-authenticated, same envelope/auth convention as `EMPLOYEE_API.md`.
- **Telegram Gateway-facing** (`telegram/` prefix) — `X-Internal-Service-Key`-authenticated, no JWT, employee resolved by `telegram_user_id` — mirrors `EMPLOYEE_API.md`'s "Telegram linking" endpoints exactly. Only the Telegram Gateway calls these.

Standard response envelope (`shared_kernel/api/response.py`):
```json
{ "success": true, "data": { ... } }
{ "success": true, "data": [ ... ], "meta": { "page": 1, "page_size": 25, "total_count": 3, "total_pages": 1 } }
{ "success": false, "error": { "code": "insufficient_leave_balance", "message": "...", "details": null } }
```

## Permissions

`leave.view_leave` (read anyone's balance/history) and `leave.manage_leave` (every HR/Admin write action beyond self-service: Leave Type Management, apply/cancel on behalf of an employee, and Leave Balance Adjustment/Opening — see Phase 13 below), both originally seeded by `apps/leave/migrations/0002_seed_leave_permissions.py` onto **HR Admin** (both) and **Manager** (`view` only) — HR Admin was renamed to **Admin** (which still holds both grants) and Manager was removed as a built-in role by `apps/identity/migrations/0006_rename_admin_role_and_prune_system_roles.py` (Role & Permission Management phase; see `IDENTITY_API.md`). Self-service endpoints (`.../me/`, apply, cancel your own) require only `IsAuthenticated` — no `leave.*` grant needed to manage your own leave, matching `EMPLOYEE_API.md`'s `/employees/me/` precedent.

## Leave module tab scope (Leave review round)

The self-service endpoints below (`GET .../balance/me/`, `GET .../requests/`, apply, cancel) are unchanged — they still exist, are still `IsAuthenticated`-only, and are still exercised by the Telegram bot exactly as before. What changed is **frontend-only**: the web Leave module tab no longer calls them or shows any individual's own leave — it's now purely an HR/Admin processing queue built on the new `GET .../requests/manage/` endpoint below. An employee's own balance/history moved to their Employee Details page instead, reading these same self-service endpoints scoped to that one employee (`GET .../balance/<employee_id>/` / `GET .../requests/employee/<employee_id>/`, both already `leave.view_leave`-gated, unchanged). No backend endpoint was removed or restricted further for this — only the frontend's usage of them changed, per "never simplify architecture unless requested."

## Error codes

| Code | HTTP | Meaning |
|---|---|---|
| `employee_not_found` | 404 | The resolved employee does not exist (Leave's own exception — see architecture notes on `EmployeeLookupPort`). |
| `leave_type_not_found` | 404 | Unknown or inactive leave type id. |
| `leave_request_not_found` | 404 | Unknown leave request id. |
| `invalid_leave_date_range` | 422 | `end_date` is before `start_date`. |
| `past_leave_start_date` | 422 | `start_date` is in the past (`LEAVE_ALLOW_PAST_START_DATE=False`, the default). |
| `duplicate_leave_request` | 422 | An identical (employee, leave type, exact dates) request is already pending/approved. |
| `overlapping_leave_request` | 422 | Dates overlap another pending/approved request for this employee (any leave type). |
| `insufficient_leave_balance` | 422 | Not enough remaining balance for this leave type/year, after subtracting other pending requests. |
| `leave_request_ownership_mismatch` | 422 | Caller tried to view/cancel a leave request that isn't theirs and lacks `leave.view_leave`. |
| `leave_request_not_cancellable` | 409 | Request is already `cancelled`/`rejected`/`draft` — nothing to cancel. |
| `no_manager_assigned` | 422 | (Phase 9) Applying employee has no manager set — see "Approval integration" below. |
| `manager_not_linked_to_telegram` | 422 | (Phase 9) The employee's manager hasn't linked their Telegram account — see "Approval integration" below. |
| `duplicate_leave_type_code` | 409 | (Phase 13) Another leave type already uses this `code`. |
| `invalid_leave_balance_adjustment` | 422 | (Phase 13) `entitled_days`/`used_days`/`carried_forward_days` submitted to Adjust/Open was negative. |

---

## Leave Types

### `GET /api/v1/leave/types/`
Any authenticated caller. Returns every **active** row from the `leave_types` lookup table (seeded: `ANNUAL`, `SICK`, `UNPAID` — see `apps/leave/migrations/0003_seed_default_leave_types.py`) — the dropdown every apply-leave form uses. Never returns a deactivated type.

```json
{ "success": true, "data": [
  { "id": "018f...", "name": "Annual Leave", "code": "ANNUAL", "default_annual_days": "20.00", "is_paid": true, "requires_approval": true, "is_active": true }
] }
```

### `GET /api/v1/leave/types/manage/?is_active=&search=&page=1&page_size=25` — Leave Type Management (Phase 13)
Requires `leave.manage_leave`. Every leave type, active or not (paginated, searchable by name/code) — the admin listing behind "Leave Type Management," distinct from the plain read above.

### `POST /api/v1/leave/types/manage/` — Create a leave type
Requires `leave.manage_leave`.
```json
{ "name": "Compassionate Leave", "code": "COMPASSIONATE", "default_annual_days": "5.00", "is_paid": true, "requires_approval": true }
```
`409 duplicate_leave_type_code` if another leave type already uses `code`.

### `PATCH /api/v1/leave/types/manage/<id>/` — Update a leave type
Requires `leave.manage_leave`. Full-replace, including reactivating/deactivating via `is_active`. No delete endpoint — `leave_types` is `RESTRICT`-referenced by every balance/request row, so deactivation (matching Department's own precedent) is the only removal path.
```json
{ "name": "Compassionate Leave", "code": "COMPASSIONATE", "default_annual_days": "7.00", "is_paid": true, "requires_approval": true, "is_active": false }
```

---

## Leave Balance

### `GET /api/v1/leave/balance/me/?year=2026`
Caller's own balance, one row per active leave type. `year` optional, defaults to the current year. A leave type with no provisioned balance row returns zeroed fields rather than a 404. **Empty State Handling:** a caller with no linked Employee record at all (a pure Admin/HR account) returns `200 { "data": [] }` rather than `404 employee_not_found` — see the equivalent note on `APPROVALS_API.md`'s `GET .../pending/me/`.

```json
{ "success": true, "data": [
  { "employee_id": "018f...", "leave_type_id": "018f...", "leave_type_name": "Annual Leave", "year": 2026,
    "entitled_days": "20.00", "used_days": "3.00", "carried_forward_days": "0.00",
    "available_days": "17.00", "pending_days": "2.00" }
] }
```

`pending_days` is the sum of this employee's still-`pending` requests for that type/year — informational, already reflected in the sufficiency check `POST .../requests/` runs. `available_days` = `entitled + carried_forward - used` (it does **not** subtract `pending_days` — that's a display-time signal, the actual gate is applied at apply time).

### `GET /api/v1/leave/balance/<employee_id>/?year=2026`
Same shape, for any employee. Requires `leave.view_leave`.

### `POST /api/v1/leave/balances/adjust/` — Leave Balance Adjustment / Opening (Phase 13)
Requires `leave.manage_leave`. One upsert write path backs both named features: creates the balance row if none exists yet for this employee/leave type/year (`adjustment_type: "opening"` in the response — e.g. a new year's entitlement, or a leave type added after the employee joined), or overwrites the existing row's absolute values (`"adjustment"` — e.g. correcting a data-entry error). Every call writes an immutable audit row (who, when, previous values, new values, reason) to `leave_balance_adjustments`.

Request:
```json
{ "employee_id": "018f...", "leave_type_id": "018f...", "year": 2026,
  "entitled_days": "22.00", "used_days": "0.00", "carried_forward_days": "3.00",
  "reason": "Opening entitlement for the new year" }
```

Response `200`:
```json
{ "success": true, "data": {
  "id": "018f...", "employee_id": "018f...", "leave_type_id": "018f...", "year": 2026,
  "adjustment_type": "opening",
  "previous_entitled_days": "0.00", "previous_used_days": "0.00", "previous_carried_forward_days": "0.00",
  "new_entitled_days": "22.00", "new_used_days": "0.00", "new_carried_forward_days": "3.00",
  "reason": "Opening entitlement for the new year", "adjusted_by": "018f...", "created_at": "2026-07-30T10:00:00Z"
} }
```
`422 invalid_leave_balance_adjustment` if any of the three day values is negative.

---

## Leave Requests

### `POST /api/v1/leave/requests/` — Apply Leave
Self-service only — always applies on the caller's own behalf. Always creates `status: "pending"`; there is no approval workflow yet (Phase 8), so a request stays `pending` until a future Approval module acts on it.

Request:
```json
{ "leave_type_id": "018f...", "start_date": "2026-09-01", "end_date": "2026-09-03", "reason": "Family trip" }
```

Response `201` — see the response shape under `GET .../requests/{id}/` below.

Runs, in order: employee exists → leave type exists/active → valid date range → not in the past (unless `LEAVE_ALLOW_PAST_START_DATE=True`) → no exact duplicate → no overlap with any other active request (any leave type) → sufficient balance (entitled + carried forward − used − already-pending days for that type/year ≥ requested days).

### `GET /api/v1/leave/requests/?status=pending&page=1&page_size=25` — View Leave History
Caller's own history, paginated. `status` optional filter. **Empty State Handling:** a caller with no linked Employee record returns a `200` empty page (`"data": []`, `meta.total_count: 0`) rather than `404 employee_not_found` — same reasoning as the balance endpoint above. `POST` on this same path (Apply Leave) is unaffected — applying for leave without a linked Employee record is still a genuine `404 employee_not_found`.

### `GET /api/v1/leave/requests/employee/<employee_id>/` — same, for any employee (`leave.view_leave`).

### `GET /api/v1/leave/requests/<id>/` — View Leave Request Details
Caller's own, or any employee's if the caller holds `leave.view_leave`.

```json
{ "success": true, "data": {
  "id": "018f...", "employee_id": "018f...", "leave_type_id": "018f...", "leave_type_name": "Annual Leave",
  "start_date": "2026-09-01", "end_date": "2026-09-03", "total_days": "3.00", "reason": "Family trip",
  "status": "pending", "approved_by": null, "decided_at": null, "decision_comments": null,
  "cancelled_at": null, "cancellation_reason": null
} }
```

### `POST /api/v1/leave/requests/<id>/cancel/` — Cancel Leave Request
Self-service only. Valid from `pending` or `approved` (cancelling an `approved` request restores the balance it consumed). `400`/`409` `leave_request_not_cancellable` from `rejected`/`cancelled`/`draft`.

```json
{ "cancellation_reason": "No longer needed" }
```

### `POST /api/v1/leave/requests/employee/<employee_id>/apply/` — Apply Leave on behalf of an employee (Phase 13)
Requires `leave.manage_leave`. Identical request/response/validation pipeline to self-service Apply Leave above — same `LeaveService.apply_leave`, no logic duplicated — except `employee_id` is a path parameter instead of being resolved from the caller's own JWT. The resulting approval request's `requested_by_employee_id` is always the named employee, never the HR caller, so the assigned manager's Telegram notification and the employee's own eventual decision notification are identical to a self-submitted request — see `APPROVALS_API.md`.

### `POST /api/v1/leave/requests/<id>/cancel-for-employee/` — Cancel any employee's leave request (Phase 13)
Requires `leave.manage_leave`. Same as self-service cancel above, but bypasses the "must be your own request" ownership check — only a `leave.manage_leave`-holding caller reaches this endpoint at all, so that check is correctly skipped rather than duplicated.

### `GET /api/v1/leave/requests/manage/?employee_id=&status=&leave_type_id=&start_date_from=&start_date_to=&page=1&page_size=25` — HR leave processing queue (Leave review round)
Requires `leave.view_leave`. Every leave request across **every** employee, paginated and filterable — every query param above is optional. This is the endpoint behind the Leave module tab's redesigned purpose: **processing** leave applications for the whole organization, not showing any one person's own leave (that moved to the Employee Details page — see "Leave module scope" below). Distinct from `GET .../requests/` (caller's own history) and `GET .../requests/employee/<employee_id>/` (one already-picked employee's history, still used once HR has selected someone from this list).

Response rows are the same shape as `GET .../requests/<id>/` (below), plus two enrichment fields resolved per-row from Employees:
```json
{ "success": true, "data": [
  { "id": "018f...", "employee_id": "018f...", "employee_name": "Grace Hopper", "employee_code": "EMP-000002",
    "leave_type_id": "018f...", "leave_type_name": "Annual Leave",
    "start_date": "2026-09-01", "end_date": "2026-09-03", "total_days": "3.00", "reason": "Family trip",
    "status": "pending", "approved_by": null, "decided_at": null, "decision_comments": null,
    "cancelled_at": null, "cancellation_reason": null }
], "meta": { "page": 1, "page_size": 25, "total_count": 1, "total_pages": 1 } }
```
`employee_name`/`employee_code` are resolved one lookup per row (bounded by page size, not table size — a deliberate, proportionate tradeoff over either an unbounded N+1 or a new batch-lookup API nobody asked for) via the same `EmployeeLookupPort` this module already uses elsewhere; they're `null` only in the pathological case of a dangling `employee_id` with no matching Employee record.

---

## Telegram Gateway-facing surface

Identical operations, `X-Internal-Service-Key`-authenticated, employee resolved via `telegram_user_id` (query param on GETs, body field on POSTs) instead of a JWT:

- `GET /api/v1/leave/telegram/types/`
- `GET /api/v1/leave/telegram/balance/?telegram_user_id=...&year=...`
- `GET /api/v1/leave/telegram/requests/?telegram_user_id=...&status=...`
- `GET /api/v1/leave/telegram/requests/<id>/?telegram_user_id=...`
- `POST /api/v1/leave/telegram/requests/apply/` — body: `telegram_user_id`, `leave_type_id`, `start_date`, `end_date`, `reason`
- `POST /api/v1/leave/telegram/requests/<id>/cancel/` — body: `telegram_user_id`, `cancellation_reason`

No Telegram-specific logic lives inside `apps.leave` — these are ordinary REST endpoints the Gateway happens to be the only caller of, same discipline as `EMPLOYEE_API.md`'s Telegram linking endpoints.

**This surface is fully implemented on the Gateway side** — `/leave_balance`, `/leave_types`, `/apply_leave` (guided multi-step conversation), `/leave_history`, `/leave_request <id>`, `/cancel_leave`. See `TELEGRAM_GATEWAY.md` §3b for the bot commands, the Apply Leave conversation flow diagram, and the callback_data mechanics.

---

## Approval integration (Phase 9; two-level chain added in the Leave review round; channel restriction added in the Approval Workflow Changes review round; dual-mode + separate level permissions added in v2)

`LeaveRequestService.approve()`/`.reject()` (the methods referenced above) are no longer reachable only from application code — they're now called automatically by `apps/leave/interface/event_handlers.py`'s `handle_approval_decided`, subscribed to the generic Approval Engine's `ApprovalDecided` event (`apps.approvals`, see `APPROVALS_API.md`). No new Leave-facing HTTP endpoint was added for this — a leave request's `status` simply transitions to `approved`/`rejected` on its own, in the background, once the chain is fully decided.

`POST /api/v1/leave/requests/` (Apply Leave) now also opens an approval request as part of the same transaction — see `APPROVALS_API.md`'s "How an approval request comes to exist" section for the full mechanics, and its `no_manager_assigned`/`manager_not_linked_to_telegram` error codes, both raised from this endpoint (not from anything under `/approvals/`) before either row is written.

**The chain is now two levels, not one** (`apps/leave/infrastructure/leave_approval_chain_resolver.py`'s `LeaveApprovalChainResolver`):

1. **Level 1 — the applicant's manager, dual-mode as of Approval Workflow Changes v2** (`ApproverAssignment.for_employee_or_permission_by_channel(employee_id=manager_id, permission_code="approvals.level1_approve", permission_required_for_channel=ApprovalChannel.WEB.value)`). The earlier "Telegram only, never the HR system" restriction was explicitly removed per updated business direction — manager approval can now be completed through **either** surface:
   - **Via Telegram** (`POST /api/v1/approvals/telegram/decide/`) — identity-gated exactly as since Phase 9: only the applicant's actual manager can decide, regardless of permissions.
   - **Via the web HR system** (`POST /api/v1/approvals/<id>/decide/`) — permission-gated instead: the caller must hold `approvals.level1_approve`, whether or not they are literally the manager. A manager without that permission is rejected here with `403 not_the_assigned_approver`; a non-manager who holds it succeeds.

   The web HR system displays level 1's status regardless of who may act on it — pending (with the currently-referenced approver's name/employee code, via the `approver_employee_name`/`approver_employee_code` enrichment) or, once decided, "Approved by <actual decider's name> (<employee code>)" — which reflects whoever really clicked Approve/Reject (`decided_by_employee_id`), not necessarily the manager. See `APPROVALS_API.md`'s "Dual-mode approver assignment" section for the full mechanics.
2. **Level 2 — any user holding `approvals.level2_approve`** (`ApproverAssignment.for_permission("approvals.level2_approve", requester_notification_message=..., restricted_to_channel=ApprovalChannel.WEB.value)`). **Unchanged in shape from the previous round — still web-only** — a user who also happens to be linked to Telegram cannot decide this step via `/telegram/decide/` (`403 approval_channel_not_allowed`); it must go through the HR web app's Approvals screen. **The permission code changed** (Approval Workflow Changes v2): previously `leave.manage_leave`, now the separate, engine-level `approvals.level2_approve` — deciding the final approval step is now decoupled from `leave.manage_leave`, which continues to gate Leave's own management screens (types, balances, the HR queue) and nothing about deciding an approval. The manager (or whoever completed level 1) does **not** finalize the leave request or touch the balance — it only advances the request to level 2 and notifies every `approvals.level2_approve` holder that a new step is awaiting them (see `APPROVALS_API.md`'s permission-based approver section). Only once someone decides at level 2 does `handle_approval_decided` fire with `final_status`, and only then are `LeaveRequest.status`/balance actually updated and the applicant's final Telegram confirmation sent.

The **applicant** (not the manager, not HR) gets their own, distinct push the moment the manager approves: `LeaveApprovalChainResolver`'s level-2 assignment carries the exact sentence `"Your manager has approved your leave request. It is now awaiting HR processing."` as `ApproverAssignment.requester_notification_message`, which `ApprovalService._approve()` forwards to `ApprovalNotificationPort.notify_step_advanced(...)` (see `APPROVALS_API.md`'s "Notifying the requester when a non-final level advances" section) — never the final "your leave is confirmed" wording, which only fires once HR/Admin actually decides at level 2 (`ApprovalDecided`/`notify_decision_made`). The resolver returns `None` after level 2, so the chain is always exactly two levels for Leave; a manager and an HR/Admin user can never be the same decision if there's only one level's worth of people, since the two levels are gated by different criteria (one specific employee vs. a permission code) even in a small org.

`LeaveRequest.approved_by`/`decided_at`/`decision_comments` are populated from the Approval Engine's **final** decision only (the level-2 HR/Admin decision) — `approved_by` holds that deciding employee's `employee_id`, not the manager's, and not a `User.id` (see `handle_approval_decided`'s docstring). Approving increments `LeaveBalance.used_days` by `total_days`; rejecting (at either level) does not touch the balance, since a `pending` request was never deducted. A reject at level 1 (the manager) ends the chain immediately, same as any single-level reject — HR never sees a request the manager already rejected.
