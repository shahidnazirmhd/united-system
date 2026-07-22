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

`leave.view_leave` (read anyone's balance/history) and `leave.manage_leave` (reserved for future write actions beyond self-service, e.g. a future HR-initiated cancel), both seeded by `apps/leave/migrations/0002_seed_leave_permissions.py` onto **HR Admin** (both) and **Manager** (`view` only). Self-service endpoints (`.../me/`, apply, cancel your own) require only `IsAuthenticated` — no `leave.*` grant needed to manage your own leave, matching `EMPLOYEE_API.md`'s `/employees/me/` precedent.

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

---

## Leave Types

### `GET /api/v1/leave/types/`
Any authenticated caller. Returns every active row from the `leave_types` lookup table (seeded: `ANNUAL`, `SICK`, `UNPAID` — see `apps/leave/migrations/0003_seed_default_leave_types.py`; HR can extend this list as a data change once a "manage leave types" endpoint exists — not built this phase, only reads were requested).

```json
{ "success": true, "data": [
  { "id": "018f...", "name": "Annual Leave", "code": "ANNUAL", "default_annual_days": "20.00", "is_paid": true, "requires_approval": true, "is_active": true }
] }
```

---

## Leave Balance

### `GET /api/v1/leave/balance/me/?year=2026`
Caller's own balance, one row per active leave type. `year` optional, defaults to the current year. A leave type with no provisioned balance row returns zeroed fields rather than a 404.

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
Caller's own history, paginated. `status` optional filter.

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

## Approval module extension point (not exposed via any endpoint yet)

`LeaveRequestService.approve()`/`.reject()` are implemented and unit-tested but reachable only from application code, not HTTP — no Approval module exists yet to call them. When it's built, it calls these directly; `LeaveRequest.approved_by`/`decided_at`/`decision_comments` already exist on the table for it to populate, and approving increments `LeaveBalance.used_days` by `total_days` (rejecting does not touch the balance, since a `pending` request was never deducted).
