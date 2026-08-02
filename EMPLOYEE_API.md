# Employee Module — API Reference

Base path: `/api/v1/employees/`. Interactive docs at `/api/docs/`, raw OpenAPI schema at `/api/schema/` — same source (drf-spectacular reading these same views) as `IDENTITY_API.md`. This document is the human-readable companion.

All responses use the standard envelope from `shared_kernel/api/response.py`, same as every other module:

```json
// success
{ "success": true, "data": { ... } }

// success, list endpoints — adds pagination metadata
{ "success": true, "data": [ ... ], "meta": { "page": 1, "page_size": 25, "total_count": 3, "total_pages": 1 } }

// error
{ "success": false, "error": { "code": "employee_not_found", "message": "...", "details": null } }
```

Every endpoint requires `Authorization: Bearer <access_token>` (see `IDENTITY_API.md` for how to obtain one) and one of two Employee-scoped permissions: `employees.view_employees` (read endpoints) or `employees.manage_employees` (write endpoints, including activate/deactivate). Both were originally seeded by `apps/employees/migrations/0002_seed_employee_permissions.py` onto the **HR Admin** role (`view` + `manage`) and **Manager** role (`view` only); **HR Admin was renamed to Admin, and Manager was removed as a built-in role**, by `apps/identity/migrations/0006_rename_admin_role_and_prune_system_roles.py` (Role & Permission Management phase) — see `IDENTITY_API.md`'s "System roles and permissions" section. `Admin` still holds both grants (the rename preserved them); a `Manager`-equivalent role, or any other, can be recreated and granted these permissions via Identity's `POST /api/v1/auth/roles/`.

---

## Create, read, update

### `POST /api/v1/employees/`
Requires `employees.manage_employees`. `employee_code` is generated server-side (a real Postgres sequence — see `infrastructure/sequence.py` — not supplied by the caller).

Request:
```json
{
  "first_name": "Ada",
  "last_name": "Lovelace",
  "work_email": "ada.lovelace@example.com",
  "personal_email": null,
  "phone_number": null,
  "date_of_birth": null,
  "gender": null,
  "department_id": "018f...",
  "manager_id": null,
  "job_title": "Software Engineer",
  "employment_type": "full_time",
  "date_of_joining": "2024-01-15",
  "user_id": null
}
```

Response `201`:
```json
{
  "success": true,
  "data": {
    "id": "018f...",
    "employee_code": "EMP-000001",
    "user_id": null,
    "first_name": "Ada",
    "last_name": "Lovelace",
    "full_name": "Ada Lovelace",
    "date_of_birth": null,
    "gender": null,
    "work_email": "ada.lovelace@example.com",
    "personal_email": null,
    "phone_number": null,
    "department_id": "018f...",
    "manager_id": null,
    "job_title": "Software Engineer",
    "employment_type": "full_time",
    "date_of_joining": "2024-01-15",
    "last_working_date": null,
    "status": "active",
    "department_name": "Engineering",
    "manager_name": null,
    "linked_user_email": null,
    "is_linked_to_telegram": false,
    "telegram_username": null,
    "telegram_linked_at": null
  }
}
```

`manager_name` (Phase 7) is resolved for single-record reads only — create, update, `GET .../{id}/`, and `GET .../me/`. List/search responses (below) leave it `null` unconditionally, to avoid an N+1 lookup cost per row (`manager_id` is a self-referential FK with no cheap batch lookup); see `application/services/employee_query_service.py`'s docstring.

`department_name` is resolved on **every** read, including list/search (bugfix: the Employee List table's Department column previously showed "—" for every row, because this field used to follow the same single-record-only rule as `manager_name` above). List/search responses resolve it via one batched `DepartmentRepository.get_by_ids()` call per page — one query for every distinct department on that page, not one query per employee row — so this stays free of the N+1 cost `manager_name` avoids by skipping resolution outright.

`linked_user_email` (Phase 12 bugfix) is the email of the Identity `User` this employee's `user_id` points to, resolved the same way and on the same single-record-only reads as `manager_name` — `null` if `user_id` is `null`, and also `null` on list/search rows regardless of `user_id`. Backs the Employee Details screen's "linked user account" indicator.

`is_linked_to_telegram`/`telegram_username`/`telegram_linked_at` (Employee & Telegram Authentication refactor) are always present on every `EmployeeResponse`, list/search included — see "Telegram linking" below for how they get set.

Errors: `404 department_not_found`, `409 duplicate_work_email`, `409 user_already_linked` (the given `user_id` is already linked to a different employee), `403 insufficient_permission`.

### `GET /api/v1/employees/{id}/`
Requires `employees.view_employees`. Returns the same shape as create's `data`.

Errors: `404 employee_not_found`.

### `PATCH /api/v1/employees/{id}/`
Requires `employees.manage_employees`. **Full-replace update**, despite the PATCH verb — every field in the request body is required, this is not field-level partial patching (see `interface/serializers.py:UpdateEmployeeSerializer`'s docstring for why that was kept out of this phase's scope). Does not change `status` — use activate/deactivate for that.

Request: same shape as create, minus `user_id`, plus optional `last_working_date`.

Response `200`: updated employee, same shape as create's `data`.

Errors: `404 employee_not_found`, `404 department_not_found`, `409 duplicate_work_email`.

### `GET /api/v1/employees/me/`
Requires only authentication (a JWT) — **not** `employees.view_employees`. Self-service for an HR System **User** who happens to also have an `Employee` record linked via `user_id`: returns that linked employee record (`department_name`/`manager_name` resolved, same as a single `GET .../{id}/`).

Deliberately a narrower grant than the general detail endpoint: `employees.view_employees` gates viewing *anyone's* record (Admin, or any custom role granted it, territory), which is a strictly bigger permission than "see your own profile" — the same reasoning `IDENTITY_API.md`'s `GET /api/v1/auth/me/` already established for `User` data, extended here to `Employee` data.

**This is not the endpoint the Telegram Gateway calls.** Telegram-linked employees never have a `User` account or a JWT at all (Employee & Telegram Authentication refactor) — the Gateway's equivalent is `GET /telegram/profile/`, below, authenticated differently and keyed by `telegram_user_id` instead of a bearer token. The two self-service paths are deliberately separate: this one for HR Users who are also employees, that one for Telegram-only employees.

Response `200`: same shape as create's `data`.

Errors: `404 employee_not_found` (the caller's `User` isn't linked to any employee record).

### `POST /api/v1/employees/{id}/link-user/`
Requires `employees.manage_employees` (Phase 12, User Management). Links an existing employee record to an existing `User` account, by id. The only other way to set `user_id` is at creation time (above) — this closes the gap for an employee record that already exists without login access.

Request:
```json
{ "user_id": "018f..." }
```

Response `200`: the updated employee, same shape as create's `data` (`user_id` now set).

Errors: `404 employee_not_found`, `404 user_not_found` (the given `user_id` doesn't exist in Identity — validated via a cross-module port, see the architecture notes below), `409 user_already_linked` (this `user_id` is already linked to a *different* employee — relinking the same employee to the same user again is a no-op, not a conflict).

---

## Telegram linking

**Gateway-facing only.** Every endpoint below is called exclusively by the Telegram Gateway (a trusted server-side client), never by an end user's browser or by an employee directly — see `TELEGRAM_GATEWAY.md`. None of them accept a JWT; instead, every request must carry:

```
X-Internal-Service-Key: <the shared secret in INTERNAL_SERVICE_API_KEY>
```

checked by `shared_kernel.api.permissions.HasInternalServiceKey`. A missing or wrong key gets `403`, regardless of anything else in the request. This proves "this caller really is the Gateway" — it does not identify *which* employee a call is about; that travels as an ordinary `telegram_user_id` parameter on each request below.

Employees linked through this flow **never** get an Identity `User` account, a password, or a JWT — see `IDENTITY_API.md`'s note on why Identity authentication is HR-staff-only. The permanent link is `Employee.telegram_user_id`, set directly on the `Employee` record.

### `POST /api/v1/employees/telegram/link/request/`
Step 1 of linking: validates the employee code and dispatches a one-time OTP to **every email address the employee has on file** — `work_email` always (mandatory on every Employee), plus `personal_email` too when the employee has one set (optional field). Both copies carry the identical OTP and either one verifies it in step 2; sending to both just gives the employee a second inbox to check if their work email isn't handy at the moment they're standing in front of the bot. Sent as separate emails, one per address, not a single email with two recipients.

Request:
```json
{ "employee_code": "EMP-000123", "telegram_user_id": 123456789, "chat_id": 123456789, "telegram_username": "ada" }
```

Response `200`: `{ "detail": "OTP dispatched to the employee's registered email(s)." }`

Errors: `404 employee_not_found`, `422 employee_not_active` (employee is `terminated`), `409 duplicate_telegram_link` (this Telegram account is already linked to a *different* employee), `409 employee_already_linked_to_telegram` (this *employee* is already linked to a different Telegram account — re-linking is not silent; the employee must `/unlink` from the current account first, or contact HR), `502 email_delivery_failed` (the OTP was generated and stored, but every recipient email failed to send — the token is still valid for its full 10 minutes, so a retried `/link` a moment later can succeed without anything being lost).

**Re-requesting a code for an already-linked chat is allowed.** `employee_already_linked_to_telegram` only fires when the *requesting* `telegram_user_id` differs from the one already on the Employee record — the same Telegram account asking for a fresh code (e.g. the first one expired) is treated as an ordinary retry, not a re-link attempt.

**SMTP configuration.** Each OTP email is sent via `shared_kernel.infrastructure.email_client`: a real `SmtpEmailClient` if `SMTP_HOST` is configured (see root `.env.example` for the full variable list, including a step-by-step guide to a temporary Gmail account for local testing), or a log-only `LoggingEmailClient` fallback otherwise — the OTP is written to the backend's console/log output instead of being emailed, so local development works with zero external setup. With the fallback, expect one log line per recipient (two, if the employee has a personal_email on file).

**Deliverability (avoiding Spam).** `SmtpEmailClient` sets `From` with a display name, plus `Date` and `Message-ID` headers — missing versions of all three are common, free spam signals, independent of content. The much bigger factor is `SMTP_FROM_EMAIL` matching the domain of the authenticated `SMTP_USERNAME` account (Gmail in particular treats a mismatch as likely spoofing and downgrades or rejects the message); the backend logs a startup warning if it detects this specific mismatch with a Gmail host. None of this reaches full inbox-grade deliverability on its own — that requires a domain with SPF/DKIM/DMARC DNS records published, which a personal Gmail account cannot provide. See `.env.example`'s SMTP section for the full explanation and why Gmail should be treated as a development-only convenience, not a production email provider (use a transactional provider like SES/SendGrid/Mailgun/Postmark for that — same `SmtpEmailClient`, just different `SMTP_*` values).

### `POST /api/v1/employees/telegram/link/verify/`
Step 2: verifies the OTP and, on success, stores `telegram_user_id` directly on the `Employee` record.

Request:
```json
{ "telegram_user_id": 123456789, "chat_id": 123456789, "otp": "123456", "telegram_username": "ada" }
```

Response `200`: the now-linked employee, same shape as create's `data` (`is_linked_to_telegram: true`). **No token pair is returned** — there is nothing to authenticate with going forward except `telegram_user_id` itself.

Errors: `422 invalid_employee_link_otp`, `422 expired_employee_link_otp`, `422 too_many_otp_attempts`, `404 employee_not_found`, `409 duplicate_telegram_link`.

**Brute-force lockout.** Each OTP allows 5 wrong guesses (`MAX_OTP_ATTEMPTS` in `employee_telegram_linking_service.py`) before it's permanently locked — the 6th attempt gets `too_many_otp_attempts` even if it's the *correct* code, not another `invalid_employee_link_otp`. The employee must call `link/request/` again for a fresh code; the Gateway clears its own "awaiting OTP" state as soon as it sees this specific error, so the next `/link` works immediately rather than bouncing off a stale "linking already in progress" conflict.

### `POST /api/v1/employees/telegram/unlink/`
Request: `{ "telegram_user_id": 123456789 }`

Response `200`: `{ "detail": "Telegram account unlinked." }`

Errors: `404 employee_not_linked_to_telegram`.

### `GET /api/v1/employees/telegram/status/?telegram_user_id=123456789`
Response `200`: `{ "is_linked": true, "telegram_username": "ada", "linked_at": "2024-01-15T10:30:00Z" }` (or `is_linked: false`, other fields `null`, if nothing is linked — this endpoint never 404s).

### `GET /api/v1/employees/telegram/profile/?telegram_user_id=123456789`
The endpoint every post-linking Telegram request resolves through — "My Profile" and "Employment Status" (`TELEGRAM_GATEWAY.md` §5) are both this same call, read differently by the Gateway's formatter. Same response shape as create's `data`.

Errors: `404 employee_not_linked_to_telegram` — no employee currently has this Telegram user id linked (the employee must `/link` first).

---

## List and search

### `GET /api/v1/employees/`
Requires `employees.view_employees`. Query parameters:

| Param | Meaning |
|---|---|
| `department_id` | exact-match filter |
| `employment_status` | exact-match filter (`active`\|`on_leave`\|`suspended`\|`terminated`) |
| `employment_type` | exact-match filter (`full_time`\|`part_time`\|`contract`\|`intern`) |
| `ordering` | comma-separated field names, e.g. `ordering=last_name,-date_of_joining`. Defaults to `employee_code`. |
| `page`, `page_size` | pagination (`page_size` capped at 100) |

Response `200`: `data` is a list of employees (same per-item shape as create's `data`), `meta` carries `page`/`page_size`/`total_count`/`total_pages`.

### `GET /api/v1/employees/search/?q=<text>` (or `?search=<text>`)
Requires `employees.view_employees`. Same endpoint mechanism as list — matches `q`/`search` case-insensitively against first name, last name, employee code, and work email — plus every filter/ordering/pagination param list accepts. Deliberately not a separate query path: see `application/services/employee_query_service.py`'s docstring.

---

## Department CRUD (Phase 12)

Departments are part of the Employee bounded context, not a separate module or permission scope — every endpoint below reuses `employees.view_employees`/`employees.manage_employees`, the same codes Employee CRUD uses. No delete endpoint: same "deactivate, don't hard-delete" precedent Employee already established (`is_active` toggle only), doubly so here since `parent_department_id` and `Employee.department_id` are both RESTRICT-constrained foreign keys — a real delete on a referenced department would fail at the database level regardless.

### `POST /api/v1/employees/departments/`
Requires `employees.manage_employees`.

Request:
```json
{
  "name": "Quality Assurance",
  "code": "QA",
  "parent_department_id": null,
  "head_employee_id": null
}
```

Response `201`:
```json
{
  "success": true,
  "data": {
    "id": "018f...",
    "name": "Quality Assurance",
    "code": "QA",
    "parent_department_id": null,
    "head_employee_id": null,
    "is_active": true,
    "parent_department_name": null,
    "head_employee_name": null
  }
}
```

Errors: `409 duplicate_department_code`, `422 invalid_department_parent` (parent_department_id equals this department's own id — only possible on update, never on create, since the id doesn't exist yet), `404 department_not_found` (parent_department_id doesn't exist), `404 employee_not_found` (head_employee_id doesn't exist), `403 insufficient_permission`.

### `GET /api/v1/employees/departments/{id}/`
Requires `employees.view_employees`. `parent_department_name`/`head_employee_name` are resolved for this single-record read (`null` if there's no parent/head, or if either was deleted out from under a stale reference).

Errors: `404 department_not_found`.

### `PATCH /api/v1/employees/departments/{id}/`
Requires `employees.manage_employees`. Full-replace update, same convention as Employee's PATCH — every field required, including `is_active` (this is how a department is reactivated after being deactivated).

Request:
```json
{
  "name": "Quality Assurance",
  "code": "QA",
  "parent_department_id": null,
  "head_employee_id": "018f...",
  "is_active": true
}
```

Response `200`: updated department, same shape as create's `data`.

Errors: `404 department_not_found`, `404 employee_not_found`, `409 duplicate_department_code`, `422 invalid_department_parent`.

### `GET /api/v1/employees/departments/`
Requires `employees.view_employees`. Query parameters:

| Param | Meaning |
|---|---|
| `is_active` | exact-match filter (`true`\|`false`) |
| `search` / `q` | case-insensitive match against `name` or `code` |
| `ordering` | comma-separated field names. Defaults to `name`. |
| `page`, `page_size` | pagination (`page_size` capped at 100) |

Response `200`: `data` is a list of departments. `parent_department_name`/`head_employee_name` are **not** resolved on list rows (always `null`) — same N+1-avoidance reasoning as Employee's `department_name`/`manager_name` on its own list endpoint; fetch `GET .../departments/{id}/` for the enriched single-record view.

Departments `GEN`, `ENG`, `HR` are seeded automatically by migration `0003_seed_departments` — useful as `department_id`/`parent_department_id` values without creating one first.

---

## Status transitions

### `POST /api/v1/employees/{id}/activate/`
Requires `employees.manage_employees`. `ACTIVE` ← `SUSPENDED`/`ON_LEAVE`. No request body.

Errors: `404 employee_not_found`, `409 invalid_employee_status_transition` (attempted on a `TERMINATED` employee — see below).

### `POST /api/v1/employees/{id}/deactivate/`
Requires `employees.manage_employees`. `ACTIVE`/`ON_LEAVE` → `SUSPENDED`. No request body.

Errors: `404 employee_not_found`, `409 invalid_employee_status_transition`.

**Termination is not modeled as an action in this phase.** Activate/deactivate toggle a reversible administrative hold (`ACTIVE` ⇄ `SUSPENDED`); a `TERMINATED` employee cannot be reactivated through either endpoint — reinstating someone who left is treated as a rehire (a new employee record), not a status flip, so it's deliberately out of scope here rather than silently allowed.

---

## Error codes reference

| HTTP | code | Meaning |
|---|---|---|
| 404 | `employee_not_found` | — |
| 404 | `department_not_found` | Given `department_id`/`parent_department_id` doesn't exist |
| 404 | `user_not_found` | Given `user_id` (link-user endpoint) doesn't exist in Identity |
| 409 | `duplicate_work_email` | Another employee already has this work email |
| 409 | `user_already_linked` | Given `user_id` is already linked to a different employee |
| 409 | `duplicate_department_code` | Another department already has this code |
| 422 | `invalid_department_parent` | A department was given itself as its own parent |
| 409 | `invalid_employee_status_transition` | e.g. activating a terminated employee |
| 403 | `insufficient_permission` | Caller lacks `employees.view_employees`/`employees.manage_employees` |
| 403 | (no code — DRF `PermissionDenied`) | Missing/wrong `X-Internal-Service-Key` on a Telegram-linking endpoint |
| 422 | `validation_error` | Request failed a business rule (e.g. `last_working_date` before `date_of_joining`) |
| 409 | `duplicate_telegram_link` | This Telegram account is already linked to a different employee |
| 409 | `employee_already_linked_to_telegram` | This employee is already linked to a *different* Telegram account — send `/unlink` from that account first |
| 404 | `employee_not_linked_to_telegram` | No employee currently has this `telegram_user_id` linked |
| 422 | `employee_not_active` | Telegram-linking attempted for a `terminated` employee |
| 422 | `invalid_employee_link_otp` | Wrong or already-used OTP |
| 422 | `expired_employee_link_otp` | OTP submitted after its 10-minute lifetime |
| 422 | `too_many_otp_attempts` | This OTP has been guessed wrong 5 times and is now locked — request a new one |
| 502 | `email_delivery_failed` | The OTP was generated but could not be emailed to any registered address |
| 500 | `internal_error` | Unexpected server error |

---

## Architecture notes relevant to consumers of this API

**Employee and User remain separate, exactly as `IDENTITY_API.md` described before this module existed.** `user_id` is `null` for any employee without login access, and is never required at creation. Linking happens by passing an existing `identity.users.id` as `user_id` when creating, or afterwards via `POST /api/v1/employees/{id}/link-user/` (Phase 12) — there is no endpoint here that creates a `User` as a side effect, and none in Identity that creates an `Employee` as a side effect.

**The link-user endpoint validates `user_id` without importing Identity's models.** `apps.employees` depends on Identity only through `UserLookupPort`/`UserServiceLookupAdapter` (`apps/employees/infrastructure/user_lookup_adapter.py`), which calls Identity's own composed use case (`apps.identity.interface.dependencies.build_get_user_by_id_use_case()`) — the same cross-module dependency-inversion pattern already used the other direction by `apps.leave`'s `EmployeeLookupPort` to check employee ids without importing Employee's ORM models. Neither module ever imports another module's models or repositories directly; only its already-composed public service, via that module's own `interface/dependencies.py`.

**Department CRUD follows Employee's own precedent almost exactly** — a `BaseService`-driven command service, a hand-written query service that resolves enrichment fields only on single-record reads, and a thin facade the ViewSet depends on, all for the identical reason: `BaseViewSet`'s generic `list()`/`retrieve()` need an *enriched* response DTO back, not a raw domain entity.

**`employee_code` is never client-supplied.** It's generated from a real Postgres sequence at creation time (`EMP-000001`, `EMP-000002`, ...) — race-safe under concurrent creates, unlike a row-count-based scheme.

**Soft delete, not hard delete.** Employee records use `shared_kernel`'s `SoftDeleteModel` — there is no delete endpoint in this phase; deactivation (`SUSPENDED`) is the supported way to take an employee out of active circulation without destroying history.

**Future modules (Leave, Attendance, Payroll, Documents, Assets, ...) will reference `employee_id` as a plain UUID**, the same cross-module-reference pattern already established between Identity and Employee — none of them require a change to this module to do so.

**Employee-to-User linking now syncs both directions (Phase 12 bugfix).** `Employee.user_id` and `identity.User.employee_id` are two independent, non-foreign-key fields (see `IDENTITY_API.md`'s architecture notes) — this module owns the write (`user_id` set at creation or via `link-user/`), and publishes `EmployeeCreated` (carrying `user_id` when set at creation) or `EmployeeLinkedToUser` (published by `link-user/`) so `apps.identity` can keep its own `employee_id` field in sync. Before this fix, nothing populated Identity's side at all, so `GET /auth/me/` and `GET /auth/users/...` always showed `employee_id: null` even for an employee visibly linked via `user_id` here. Links made before the fix shipped needed a one-time `python manage.py backfill_user_employee_links` to catch up (see that command's docstring); every link made from now on syncs automatically.
