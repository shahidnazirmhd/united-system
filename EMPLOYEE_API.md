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

Every endpoint requires `Authorization: Bearer <access_token>` (see `IDENTITY_API.md` for how to obtain one) and one of two Employee-scoped permissions: `employees.view_employees` (read endpoints) or `employees.manage_employees` (write endpoints, including activate/deactivate). Both are seeded by `apps/employees/migrations/0002_seed_employee_permissions.py` onto the **HR Admin** role (`view` + `manage`) and **Manager** role (`view` only) — see that migration for the full grant list, and `IDENTITY_API.md`'s role-management endpoints for how to grant either role to a user, or a custom role, via Identity's `POST /api/v1/auth/roles/`.

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
    "termination_date": null,
    "status": "active",
    "department_name": "Engineering",
    "manager_name": null,
    "is_linked_to_telegram": false,
    "telegram_username": null,
    "telegram_linked_at": null
  }
}
```

`department_name`/`manager_name` (Phase 7) are resolved for single-record reads only — create, update, `GET .../{id}/`, and `GET .../me/`. List/search responses (below) leave both `null` unconditionally, to avoid an N+1 lookup cost per row; see `application/services/employee_query_service.py`'s docstring.

`is_linked_to_telegram`/`telegram_username`/`telegram_linked_at` (Employee & Telegram Authentication refactor) are always present on every `EmployeeResponse`, list/search included — see "Telegram linking" below for how they get set.

Errors: `404 department_not_found`, `409 duplicate_work_email`, `409 user_already_linked` (the given `user_id` is already linked to a different employee), `403 insufficient_permission`.

### `GET /api/v1/employees/{id}/`
Requires `employees.view_employees`. Returns the same shape as create's `data`.

Errors: `404 employee_not_found`.

### `PATCH /api/v1/employees/{id}/`
Requires `employees.manage_employees`. **Full-replace update**, despite the PATCH verb — every field in the request body is required, this is not field-level partial patching (see `interface/serializers.py:UpdateEmployeeSerializer`'s docstring for why that was kept out of this phase's scope). Does not change `status` — use activate/deactivate for that.

Request: same shape as create, minus `user_id`, plus optional `termination_date`.

Response `200`: updated employee, same shape as create's `data`.

Errors: `404 employee_not_found`, `404 department_not_found`, `409 duplicate_work_email`.

### `GET /api/v1/employees/me/`
Requires only authentication (a JWT) — **not** `employees.view_employees`. Self-service for an HR System **User** who happens to also have an `Employee` record linked via `user_id`: returns that linked employee record (`department_name`/`manager_name` resolved, same as a single `GET .../{id}/`).

Deliberately a narrower grant than the general detail endpoint: `employees.view_employees` gates viewing *anyone's* record (HR Admin/Manager territory), which is a strictly bigger permission than "see your own profile" — the same reasoning `IDENTITY_API.md`'s `GET /api/v1/auth/me/` already established for `User` data, extended here to `Employee` data.

**This is not the endpoint the Telegram Gateway calls.** Telegram-linked employees never have a `User` account or a JWT at all (Employee & Telegram Authentication refactor) — the Gateway's equivalent is `GET /telegram/profile/`, below, authenticated differently and keyed by `telegram_user_id` instead of a bearer token. The two self-service paths are deliberately separate: this one for HR Users who are also employees, that one for Telegram-only employees.

Response `200`: same shape as create's `data`.

Errors: `404 employee_not_found` (the caller's `User` isn't linked to any employee record).

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
| 404 | `department_not_found` | Given `department_id` doesn't exist |
| 409 | `duplicate_work_email` | Another employee already has this work email |
| 409 | `user_already_linked` | Given `user_id` is already linked to a different employee |
| 409 | `invalid_employee_status_transition` | e.g. activating a terminated employee |
| 403 | `insufficient_permission` | Caller lacks `employees.view_employees`/`employees.manage_employees` |
| 403 | (no code — DRF `PermissionDenied`) | Missing/wrong `X-Internal-Service-Key` on a Telegram-linking endpoint |
| 422 | `validation_error` | Request failed a business rule (e.g. `termination_date` before `date_of_joining`) |
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

**Employee and User remain separate, exactly as `IDENTITY_API.md` described before this module existed.** `user_id` is `null` for any employee without login access, and is never required at creation. Linking happens by passing an existing `identity.users.id` as `user_id` when creating (or, in a future phase, via a dedicated link endpoint) — there is no endpoint here that creates a `User` as a side effect, and none in Identity that creates an `Employee` as a side effect.

**`employee_code` is never client-supplied.** It's generated from a real Postgres sequence at creation time (`EMP-000001`, `EMP-000002`, ...) — race-safe under concurrent creates, unlike a row-count-based scheme.

**Soft delete, not hard delete.** Employee records use `shared_kernel`'s `SoftDeleteModel` — there is no delete endpoint in this phase; deactivation (`SUSPENDED`) is the supported way to take an employee out of active circulation without destroying history.

**Future modules (Leave, Attendance, Payroll, Documents, Assets, ...) will reference `employee_id` as a plain UUID**, the same cross-module-reference pattern already established between Identity and Employee — none of them require a change to this module to do so.
