# Approval Engine — API Reference

Base path: `/api/v1/approvals/`. Interactive docs at `/api/docs/`, raw OpenAPI schema at `/api/schema/` — same source (drf-spectacular reading these same views) as `EMPLOYEE_API.md`/`LEAVE_API.md`/`IDENTITY_API.md`. This document is the human-readable companion.

`apps.approvals` is a **generic, subject-agnostic engine** — it has no knowledge of Leave, Attendance, Overtime, Business Trips, Asset Requests, or any other HR module. Every field that identifies what's being approved (`subject_type`, `subject_id`, `subject_summary`) is a plain, opaque value supplied by the module that opened the approval request; this engine never interprets it. See `HRMS_Architecture.md`'s Phase 9 notes for the full reasoning, and `TELEGRAM_GATEWAY.md` §3d for how the Gateway integrates with it.

Two parallel surfaces expose the same underlying `ApprovalService`, no business logic duplicated between them — same split as `LEAVE_API.md`:

- **Self-service / HR** (below, no `telegram/` in the path) — JWT-authenticated, same envelope/auth convention as `EMPLOYEE_API.md`.
- **Telegram Gateway-facing** (`telegram/` prefix) — `X-Internal-Service-Key`-authenticated, no JWT, employee resolved by `telegram_user_id`.

Standard response envelope (`shared_kernel/api/response.py`):
```json
{ "success": true, "data": { ... } }
{ "success": true, "data": [ ... ] }
{ "success": false, "error": { "code": "not_the_assigned_approver", "message": "...", "details": null } }
```

## How an approval request comes to exist (there is no `POST /approvals/`)

This engine never receives a "create approval request" call over HTTP — a subject module (currently only Leave) calls `ApprovalService.create_approval_request(...)` directly, in-process, inside the same database transaction as the action being approved (e.g. `apps/leave/application/services/leave_request_service.py`'s `apply_leave()`, right after the `LeaveRequest` itself is created). This keeps the two writes atomic: if opening the approval request fails, the leave request itself is rolled back too, never left "submitted but with no approver."

Before that call happens, the requesting module runs its own validation to decide whether an approval request can be opened at all. For Leave specifically (`apps/leave/application/services/leave_validation_service.py`'s `validate_manager_available_for_approval`):

| Code | HTTP | Meaning |
|---|---|---|
| `no_manager_assigned` | 422 | The employee applying has no manager set (`Employee.manager_id` is null). Message: "No manager is assigned to your account. Please contact HR." |
| `manager_not_linked_to_telegram` | 422 | The employee's manager exists but hasn't linked their Telegram account. Message: "Your manager has not linked their Telegram account yet. Please contact HR." |

Both are raised (and the whole apply-leave transaction rolled back) **before** any `ApprovalRequest`/`LeaveRequest` row is written — these are Leave's own exceptions (`apps/leave/domain/exceptions.py`), not the Approval Engine's, since only the requesting module knows what "no valid approver" should mean for it. A future module reusing this engine (Attendance, Overtime, ...) implements its own equivalent pre-check the same way, against its own `ApprovalChainResolverPort` implementation.

## Approver assignment: one specific employee, "anyone with this permission," or both (dual-mode)

Each `ApprovalStep` is assigned via the domain's `ApproverAssignment` value object, in one of three ways:

- **`for_employee`** — one specific employee id (the original, still-used shape — e.g. "your manager").
- **`for_permission`** — any employee who currently holds a given permission code, resolved at decide-time, not baked into the step row. Added specifically so an HR/Admin approval level scales to "any qualifying HR staff member" in an organization with many admins, rather than hard-coding one designated person.
- **`for_employee_or_permission_by_channel`** (Approval Workflow Changes v2 — "dual-mode") — **both** an employee id and a permission code, plus which ONE channel the permission governs on. Added specifically so a level can be "identity-gated on one channel, permission-gated on another" — Leave's level 1 is exactly this: the applicant's manager can decide via Telegram purely by being that manager, while the web HR system is instead gated by holding `approvals.level1_approve`, whether or not the web caller is literally the manager.

`ApprovalStepResponseSerializer` reflects this directly — `approver_employee_id` and `approver_permission_code` are both nullable, and **at least one is always non-null** for a given step (enforced by a DB check constraint, `approval_steps_at_least_one_approver_mode`; a dual-mode step is the one case where both are non-null at once). A permission-only step's list/detail JSON looks like:

```json
{ "id": "018f...", "level": 2, "approver_employee_id": null, "approver_permission_code": "approvals.level2_approve", "status": "pending", ... }
```

A dual-mode step's looks like:

```json
{ "id": "018f...", "level": 1, "approver_employee_id": "018f...", "approver_permission_code": "approvals.level1_approve",
  "permission_required_for_channel": "web", "status": "pending", ... }
```

`POST .../decide/` and `GET .../pending/me/` both changed to match: a caller may decide a permission-based step if they hold that permission code at all (checked fresh via `ApprovalAuthorizationPort` on every call, not cached on the step), not just if they're the one specific person named on the row — so **any** qualifying user can pick up and decide the request, and "My Pending Approvals" for every such user shows the same still-pending step until one of them acts. Once decided, the event/notification correctly credits whichever specific employee actually clicked Approve/Reject (`ApprovalDecided`/`ApprovalStepAdvanced` still carry the deciding employee's real id, and — Approval Workflow Changes v2 — `ApprovalStepResponse.decided_by_employee_id` now records it on the step itself too), even though the step itself was never assigned to that one person ahead of time.

This is purely additive to the engine — `for_employee`/`for_permission` steps behave exactly as before, and a chain resolver is free to mix all three kinds across levels of the same chain (Leave does exactly this — see below).

## Restricting a step to one channel (Approval Workflow Changes review round)

`ApproverAssignment` (and the `ApprovalStep` it produces) carries a `restricted_to_channel: str | None` field, one of `apps.approvals.domain.enums.ApprovalChannel`'s `"web"` / `"telegram"` values, or `null` for "no restriction — decidable from either surface" (the default, and every dual-mode step — see below). This is the same opaque, engine-relays-but-never-interprets idiom as `subject_summary`/`requester_notification_message` above — `apps.approvals` has no idea what "the HR system" or "Telegram" mean; only the requesting module's chain resolver decides whether a given level should be pinned to one surface.

Leave's own resolver (`LeaveApprovalChainResolver`) uses this for level 2 only (HR/Admin, `approvals.level2_approve`): `restricted_to_channel="web"` — final approval must happen in the HR system, even for an HR/Admin employee who also happens to be linked to Telegram. **Level 1 is NOT channel-restricted as of Approval Workflow Changes v2** — the earlier "Telegram only" rule was replaced by the dual-mode permission gate described below, which is enforced without excluding either channel outright.

This is enforced in exactly one place, `ApprovalService.decide()`, checked **before** the existing identity/permission check (`ApprovalStep.is_decidable_by`) — a wrong-channel attempt is rejected outright, regardless of whether the caller would otherwise have been the right person:

```json
{ "success": false, "error": { "code": "approval_channel_not_allowed", "message": "This approval step can only be decided via web.", "details": null } }
```

`GET .../pending/me/` and `GET .../telegram/pending/` both also filter by channel — a Telegram-linked HR/Admin's `/pending_approvals` never lists the web-only level-2 step, even though they'd otherwise "qualify" by permission alone. (`ApprovalService.list_pending_for_approver`'s `channel` kwarg — `None`, the default, applies no filtering, which is what every pre-existing caller still gets.)

## Dual-mode approver assignment: identity on one channel, permission on another (Approval Workflow Changes v2)

`ApproverAssignment.for_employee_or_permission_by_channel(*, employee_id, permission_code, permission_required_for_channel, ...)` produces a step where BOTH `approver_employee_id` and `approver_permission_code` are set, plus a new field: `permission_required_for_channel` — the one channel on which `approver_permission_code` governs instead of `approver_employee_id`. Every OTHER channel is still governed by `approver_employee_id` alone, exactly like a plain `for_employee` step.

`ApprovalStep.is_decidable_by` enforces this directly:

- On `channel == permission_required_for_channel` (e.g. `"web"`): the caller must hold `approver_permission_code` — being `approver_employee_id` is neither necessary nor sufficient. Even the originally-referenced employee is rejected here if they don't hold the permission.
- On any other channel (e.g. `"telegram"`): the caller must be `approver_employee_id` exactly — holding the permission is irrelevant there, even for some other employee who happens to qualify.

Leave's level 1 is the concrete case: `employee_id` = the applicant's manager, `permission_code` = `"approvals.level1_approve"`, `permission_required_for_channel` = `"web"`. So the manager can always decide level 1 via Telegram (identity), while the web HR system is governed purely by holding `approvals.level1_approve` — an org can grant that permission to whichever role(s) it wants (a "Manager" role, a backup-approver role, anything), without this engine ever hardcoding the idea of "a manager."

`GET .../pending/me/` and `GET .../telegram/pending/` apply the identical per-channel rule when aggregating "what's pending for me" — a manager who doesn't hold `approvals.level1_approve` sees a dual-mode step in their Telegram list but not their web list; a non-manager permission holder sees it in their web list but not their Telegram list.

A `not_the_assigned_approver` (not `approval_channel_not_allowed`) is what a dual-mode step raises for a wrong-identity-or-permission attempt on an otherwise-open channel — channel restriction (`restricted_to_channel`) and this per-channel identity/permission split are deliberately separate mechanisms; a dual-mode step is, by construction, decidable from every channel, just via a different check on each.

## Approver name/code enrichment (Approval Workflow Changes review round; decided-by added in v2)

`ApprovalStepResponseSerializer` gained enrichment fields: `approver_employee_name` and `approver_employee_code`, plus (Approval Workflow Changes v2) the raw `decided_by_employee_id` they're now resolved from once a step is decided. `ApprovalService` resolves the name/code itself (a new `EmployeeLookupPort.get_employee_display_info(employee_id) -> (full_name, employee_code) | None` call, one bounded lookup per step per request/response, mirroring `apps.leave`'s own `_enrich_with_employee_display` precedent) — callers never need a second round-trip to the Employee API just to show "who."

**Which employee gets named:** `decided_by_employee_id` (who actually clicked Approve/Reject) once the step is decided, else `approver_employee_id` (who was originally assigned/referenced) while still pending. For a plain `for_employee` step these are always the same person. For a dual-mode or permission-based step they can differ — e.g. Leave's level 1 decided via the web by a non-manager `approvals.level1_approve` holder shows THAT person's name once decided, not the manager's, even though the manager's name/code is what showed while the step was still pending. A still-pending, non-dual-mode permission-based step (e.g. Leave's level 2 before anyone acts) has neither set yet, so `approver_employee_name`/`approver_employee_code` stay `null` — there is genuinely no single employee to name.

```json
{ "id": "018f...", "level": 1, "approver_employee_id": "018f...", "approver_permission_code": "approvals.level1_approve",
  "restricted_to_channel": null, "permission_required_for_channel": "web", "decided_by_employee_id": null,
  "approver_employee_name": "Jane Doe", "approver_employee_code": "EMP-0042",
  "status": "pending", "comments": null, "decided_at": null }
```

Once decided by a different `approvals.level1_approve` holder (not Jane):

```json
{ "id": "018f...", "level": 1, "approver_employee_id": "018f...", "approver_permission_code": "approvals.level1_approve",
  "restricted_to_channel": null, "permission_required_for_channel": "web", "decided_by_employee_id": "018f...",
  "approver_employee_name": "Beth BackupApprover", "approver_employee_code": "EMP-BACKUPL1-001",
  "status": "approved", "comments": "Covering for the manager", "decided_at": "2026-08-15T09:00:00Z" }
```

## New permissions: `approvals.level1_approve` / `approvals.level2_approve` (Approval Workflow Changes v2)

Two new, engine-level (not Leave-specific) permission codes, registered in Identity's permission catalog by `apps/approvals/migrations/0006_seed_level_approval_permissions.py` — same catalog `approvals.view_approvals`/`approvals.decide_approvals` already live in (`module="approvals"`), listed and assignable through Role & Permission Management like any other permission, no frontend changes needed for that. They live here (not in `apps.leave`) so any future subject module adopting the same generic two-level pattern can reuse them instead of minting its own — `apps.leave.infrastructure.leave_approval_chain_resolver` is simply the first resolver to actually reference them:

- **`approvals.level1_approve`** — required, on the web channel, to decide a dual-mode step's current level (e.g. Leave's level 1). Irrelevant to a Telegram decision, which is still governed by identity alone.
- **`approvals.level2_approve`** — required to decide a permission-based final level (e.g. Leave's level 2) from the web. This **replaces `leave.manage_leave`** for this one purpose — `leave.manage_leave` continues to gate Leave's own management screens (types, balances, the HR queue) and has nothing to do with deciding an approval step any more; the two are now deliberately decoupled, so an org can grant "manage Leave data" and "give final approval sign-off" independently.

Seeded by default to the "Admin" system role only (the one role this codebase still ships built-in as of the Role & Permission Management phase — see `IDENTITY_API.md`'s "System roles and permissions" section); an admin creating their own "Manager" (or equivalent) role via Role & Permission Management is expected to grant `approvals.level1_approve` to it explicitly — this is precisely what "do not hardcode users or roles for approval access" means in practice.

## Notifying the requester when a non-final level advances (Leave review round)

`ApproverAssignment` (whichever of `.for_employee`/`.for_permission` a chain resolver returns for the *next* level) carries a third, always-optional field: `requester_notification_message: str | None`. When a decision advances the chain to a further, still-not-final level, `ApprovalService._approve()` sends the **original requester** (not the new approver — they get the ordinary "approval requested" push instead) a push built from this string if the resolver supplied one, or a generic "moved to level N for further approval" fallback if it didn't. This is a second opaque, subject-composed string — same idiom as `subject_summary` — so `apps.approvals` never hardcodes any subject module's wording; Leave's resolver supplies exactly `"Your manager has approved your leave request. It is now awaiting HR processing."` for its level 1→2 transition (see `LEAVE_API.md`'s "Approval integration" section). This is distinct from the final `ApprovalDecided` push (`approval_decided`/`format_approval_decided_push`), which only ever fires once the whole chain concludes — see `TELEGRAM_GATEWAY.md` §3d for the `approval_step_advanced` notification type this produces.

## Error codes (the engine's own)

| Code | HTTP | Meaning |
|---|---|---|
| `employee_not_found` | 404 | **Write** endpoints only (`POST .../decide/`, both Telegram endpoints): the caller (resolved via JWT `user_id` or Telegram `telegram_user_id`) has no corresponding Employee record. The three READ endpoints below (`GET .../pending/me/`, `GET .../<id>/`, `GET .../subject/...`) never raise this — a caller with no linked Employee record simply has nothing assigned to them (empty list) or falls through to the `approvals.view_approvals` permission check, per the "Empty State Handling" note below. |
| `approval_request_not_found` | 404 | Unknown approval request id, or the caller has no right to see it (see the detail endpoint's ownership rule below). |
| `approval_step_not_found` | 404 | Defensive — the request's `current_level` has no matching step row (should not happen in normal operation). |
| `no_approval_chain_resolver_registered` | 422 | `subject_type` has no `ApprovalChainResolverPort` registered (a subject module forgot to register one in its `AppConfig.ready()`). |
| `no_approver_available` | 422 | The registered resolver returned no approver for level 1 (should be caught earlier by the requesting module's own validation, as with Leave's `no_manager_assigned` above — this is the engine's own defensive fallback). |
| `approval_request_not_pending` | 409 | The request has already been fully approved or rejected — cannot be decided again. |
| `approval_step_not_pending` | 409 | Defensive — the specific step is no longer pending. |
| `not_the_assigned_approver` | 403 | The caller is authenticated but isn't the approver assigned to the request's current level. |
| `approval_channel_not_allowed` | 403 | The step is restricted to one channel (`restricted_to_channel`) and the caller decided via the other one — e.g. a manager attempting Leave's level 1 via `POST .../decide/` (web) instead of `POST .../telegram/decide/`, or an HR/Admin attempting level 2 via Telegram instead of the web app. Checked *before* `not_the_assigned_approver`, so a wrong-channel attempt is rejected even for the otherwise-correct approver. |

---

## Approval Requests

### `GET /api/v1/approvals/pending/me/` — My Pending Approvals
Every approval request currently awaiting a decision from the caller, across every subject module — Leave today, any future module with zero changes to this endpoint. `IsAuthenticated` only, no special permission needed (same "your own inbox" precedent as `LEAVE_API.md`'s self-service endpoints). Filtered to the **web** channel (Approval Workflow Changes review round) — a step `restricted_to_channel: "telegram"` never appears here, even for the correct approver; and (v2) a dual-mode step only appears here for a caller who satisfies the WEB-side check (the permission, not identity) — see "Restricting a step to one channel" and "Dual-mode approver assignment" above.

**Empty State Handling:** a caller with no linked Employee record (a pure Admin/HR account never given an Employee row) returns `200 { "data": [] }` here — never `404 employee_not_found` — since such a caller trivially has zero pending approvals. This matters because the web frontend renders this as a normal empty state ("Nothing waiting on you"), not an error screen; before this fix the 404 surfaced as "Couldn't load, try again" for what was really just "no data."

```json
{ "success": true, "data": [
  { "id": "018f...", "subject_type": "leave.leave_request", "subject_id": "018f...",
    "requested_by_employee_id": "018f...", "subject_summary": "Annual Leave: 2026-09-01 → 2026-09-03 (3 day(s))",
    "status": "pending", "current_level": 1,
    "steps": [
      { "id": "018f...", "approval_request_id": "018f...", "level": 1, "approver_employee_id": "018f...",
        "approver_permission_code": "approvals.level1_approve", "restricted_to_channel": null,
        "permission_required_for_channel": "web", "decided_by_employee_id": null,
        "approver_employee_name": "Jane Doe", "approver_employee_code": "EMP-0042",
        "status": "pending", "comments": null, "decided_at": null }
    ] }
] }
```

### `GET /api/v1/approvals/<id>/` — Approval Request Detail
Full detail, every step reached so far in level order. The caller must be either the original requester or the approver of some step on this request; anyone else needs `approvals.view_approvals` (else `404 approval_request_not_found` — the same "don't confirm the id was valid" ownership pattern `LEAVE_API.md`'s `leave_request_ownership_mismatch` note describes, applied here as a 404 rather than a distinct error code). A caller with no linked Employee record is simply neither the requester nor an approver — they still see the detail if they hold `approvals.view_approvals`, rather than being rejected purely for having no Employee row.

### `GET /api/v1/approvals/subject/<subject_type>/<subject_id>/` — Approval history for a subject (Phase 13)
Every approval request ever raised for one subject — pure delegation to `ApprovalService.list_by_subject`, already implemented since Phase 9 but unused by any endpoint until this phase's Leave "View Leave Details" screen needed to show approval status/history. Subject-agnostic: any future subject module gets this for free, no new endpoint.

Same three-way authorization as the detail endpoint above, applied across the whole list: visible if the caller was the requester or an approver on *any* returned request, or holds `approvals.view_approvals`. Unlike the detail endpoint, a caller who fails that check (or a subject with no approval history at all) gets an **empty list**, `200`, not a `404` — there's nothing ownership-sensitive to hide about "zero rows," and the subject module's own detail endpoint (e.g. `LEAVE_API.md`'s `GET /leave/requests/<id>/`) is what actually gates whether the subject itself may be viewed.

```json
{ "success": true, "data": [
  { "id": "018f...", "subject_type": "leave.leave_request", "subject_id": "018f...", "requested_by_employee_id": "018f...",
    "subject_summary": "Annual Leave: 2026-09-01 → 2026-09-03 (3 day(s))", "status": "approved", "current_level": 1,
    "steps": [ { "id": "018f...", "level": 1, "approver_employee_id": "018f...",
                 "approver_permission_code": "approvals.level1_approve", "restricted_to_channel": null,
                 "permission_required_for_channel": "web", "decided_by_employee_id": "018f...",
                 "approver_employee_name": "Jane Doe", "approver_employee_code": "EMP-0042", "status": "approved",
                 "comments": "Enjoy your trip", "decided_at": "2026-08-15T09:00:00Z" } ] }
] }
```

### `POST /api/v1/approvals/<id>/decide/` — Approve or Reject
Only the approver assigned to the request's `current_level` may call this (`403 not_the_assigned_approver` otherwise). Only valid while `status: "pending"` (`409 approval_request_not_pending` otherwise). This endpoint always decides via the **web** channel (`ApprovalChannel.WEB`, hardcoded by the view — never client-supplied); if the current step is `restricted_to_channel: "web"`-incompatible (i.e. restricted to a different channel), this call is rejected with `403 approval_channel_not_allowed` regardless of who the caller is — see "Restricting a step to one channel" above. For a dual-mode step (v2), the caller must hold the required permission on the web side, even if they're the originally-referenced employee — see "Dual-mode approver assignment" above.

Request:
```json
{ "decision": "approve", "comments": "Enjoy your trip" }
```
`decision` is one of `"approve"` / `"reject"`. `comments` optional.

- **`decision: "reject"`** — the current step and the whole request move to `rejected` immediately, regardless of level. The engine notifies the original requester and publishes `ApprovalDecided(final_status="rejected", ...)`.
- **`decision: "approve"`** — the current step moves to `approved`; the engine then asks the registered chain resolver for the *next* level's approver:
  - If one is returned, a new step is created at that level, `current_level` advances, the request **stays `pending`** — the newly-assigned approver (or, for a permission-based/dual-mode step, every employee currently holding that permission) is notified, and an `ApprovalStepAdvanced` event is published. Leave's own chain is exactly this case: level 1 approving advances to level 2 (any `approvals.level2_approve` holder) instead of finalizing — see `LEAVE_API.md`'s "Approval integration" section.
  - If none is returned (the chain is exhausted), the request moves to `approved` — the requester is notified and `ApprovalDecided(final_status="approved", ...)` is published.

Response `200` — same shape as the detail endpoint, reflecting the request's state immediately after the decision.

---

## Telegram Gateway-facing surface

Identical operations, `X-Internal-Service-Key`-authenticated, employee resolved via `telegram_user_id` instead of a JWT:

- `GET /api/v1/approvals/telegram/pending/?telegram_user_id=...` — backs the Gateway's `/pending_approvals` command. Filtered to the **telegram** channel (Approval Workflow Changes review round) — Leave's web-only level-2 (HR/Admin) step never appears here, even for an HR/Admin employee who also happens to be Telegram-linked.
- `POST /api/v1/approvals/telegram/decide/` — body: `telegram_user_id`, `approval_request_id`, `decision`, `comments` — backs the Gateway's inline Approve/Reject buttons plus the optional typed-in comment. Always decides via the **telegram** channel; rejected with `403 approval_channel_not_allowed` against a web-only step (e.g. Leave's level 2), regardless of the caller's role/permissions. See `TELEGRAM_GATEWAY.md` §3d for the full push-notification + comment-collection flow, including the reverse-direction `POST /internal/notify` call the Gateway itself exposes (documented there, not here, since it isn't part of this module's own API surface — it's a Gateway endpoint the backend's Celery task calls). No Gateway code changes were required for this review round — the Gateway simply receives whatever the backend already filtered/permitted; see `TELEGRAM_GATEWAY.md` §3d's note.

No Telegram-specific logic lives inside `apps.approvals` — these are ordinary REST endpoints the Gateway happens to be the only caller of, same discipline as `LEAVE_API.md`'s Telegram-facing surface.

---

## Extending this engine to a future module

No changes to `apps.approvals` are ever required. A future module (Attendance corrections, Overtime, Business Trips, Asset Requests, ...) needs only:

1. Its own `ApprovalChainResolverPort` implementation (mirrors `apps/leave/infrastructure/leave_approval_chain_resolver.py`'s `LeaveApprovalChainResolver` — a single method, `resolve_next_approver(subject_type, subject_id, requested_by_employee_id, level)`, returning an `ApproverAssignment` (`.for_employee(id)` or `.for_permission(code)`) or `None`).
2. Registering it in its own `AppConfig.ready()` against a module-owned `subject_type` string constant (e.g. `"attendance.correction_request"`), via `apps.approvals.application.registry.chain_resolver_registry.register(...)` — mirrors Leave's registration exactly.
3. Calling `ApprovalService.create_approval_request(...)` (via its own `ApprovalRequestPort` + adapter, mirroring `apps/leave/infrastructure/approval_request_adapter.py`) inside the same transaction as the action being approved, with its own pre-check for "is there a valid approver at all" (mirroring `no_manager_assigned`/`manager_not_linked_to_telegram` above).
4. Subscribing to `ApprovalDecided` on the shared `EventBus`, filtering on its own `subject_type`, to react to the final decision (mirrors `apps/leave/interface/event_handlers.py`'s `handle_approval_decided`).

Multi-level chains (a request that needs more than one approver in sequence) require no engine changes either — a resolver simply answers `level=2`, `level=3`, etc. with a further approver instead of `None`, and `ApprovalService.decide()`'s existing advance-to-next-level logic (see the "Approve" bullet above) handles the rest.
