# Identity Module — API Reference

Base path: `/api/v1/auth/`. Interactive docs (auto-generated from these same views via drf-spectacular) are available at `/api/docs/` once the server is running, and the raw OpenAPI schema at `/api/schema/`. This document is the human-readable companion — same endpoints, with the reasoning behind each one's shape.

All responses use the standard envelope from `shared_kernel/api/response.py`:

```json
// success
{ "success": true, "data": { ... } }

// error
{ "success": false, "error": { "code": "invalid_credentials", "message": "...", "details": null } }
```

Authenticated endpoints expect `Authorization: Bearer <access_token>`.

---

## Authentication

### `POST /api/v1/auth/login/`
Public. Exchanges email + password for a token pair.

Request:
```json
{ "email": "someone@example.com", "password": "correct-horse-battery-staple" }
```

Response `200`:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

Errors: `401 invalid_credentials` (wrong email or password — deliberately identical for both, so this endpoint can't be used to enumerate registered emails), `401 inactive_user`.

### `POST /api/v1/auth/token/refresh/`
Public (the caller authenticates via the refresh token itself, not a bearer access token). Rotates a refresh token: the presented one is immediately revoked and a new access + refresh pair is issued.

Request:
```json
{ "refresh_token": "eyJ..." }
```

Response `200`: same shape as login.

Errors: `401 invalid_token` (malformed/expired/wrong type), `401 token_revoked` (already used — replay of a rotated-out token, or the account's password changed since this token was issued).

### `POST /api/v1/auth/logout/`
Requires authentication. Revokes the presented refresh token and the access token used to make this call.

Request:
```json
{ "refresh_token": "eyJ..." }
```

Response `200`:
```json
{ "success": true, "data": { "detail": "Logged out." } }
```

### `GET /api/v1/auth/me/`
Requires authentication. Returns the caller's own profile, current roles, and effective (union of all roles') permission codes.

Response `200`:
```json
{
  "success": true,
  "data": {
    "id": "018f...",
    "email": "someone@example.com",
    "is_active": true,
    "is_system_account": false,
    "employee_id": null,
    "roles": [{ "id": "018f...", "name": "HR Admin" }],
    "permission_codes": ["identity.view_users", "identity.manage_users", "identity.view_roles", "identity.manage_roles"]
  }
}
```

---

## Password reset

### `POST /api/v1/auth/password-reset/request/`
Public. Always responds `200` with the same message regardless of whether the email is registered — this is deliberate, not an oversight; distinguishing the two responses would let this endpoint enumerate valid accounts. If the email does belong to an account, a single-use, 30-minute token is generated and "sent" (currently: logged, not emailed — see below).

Request: `{ "email": "someone@example.com" }`
Response `200`: `{ "success": true, "data": { "detail": "If that email exists, a reset link was sent." } }`

### `POST /api/v1/auth/password-reset/confirm/`
Public. Completes the reset. Invalidates every existing session for that account (any access or refresh token issued before this moment stops working, regardless of its own expiry — see `password_changed_at` in the architecture notes below).

Request:
```json
{ "token": "the-raw-token-from-the-email", "new_password": "a-new-strong-password" }
```

Response `200`: `{ "success": true, "data": { "detail": "Password changed successfully." } }`

Errors: `422 invalid_reset_token` (unknown or already-used), `422 expired_reset_token`.

**Email delivery status**: implemented behind an `EmailSenderPort` interface; the current implementation (`LoggingEmailSender`) logs the reset link instead of sending a real email, since no SMTP/SES/SendGrid provider is configured yet. Swapping in a real provider is a one-file change (`apps/identity/infrastructure/email_sender.py`) — no use case, view, or serializer needs to change.

---

## User provisioning

### `POST /api/v1/auth/users/`
Requires `identity.manage_users`. Creates a new authentication account. Not public self-service signup — accounts are provisioned by an administrator. (The Employee module, when built, will link its own records to a `User` via `employee_id`, but does not need this endpoint to do so — see the User/Employee separation note below.)

Request:
```json
{ "email": "new.person@example.com", "password": "a-strong-password", "is_system_account": false }
```

Response `201`: same shape as the `me` endpoint's `data`, minus `roles`/`permission_codes` populated (a freshly created user has none).

Errors: `409 duplicate_email`, `403 insufficient_permission`.

---

## Role management

### `GET /api/v1/auth/roles/`
Requires `identity.view_roles`. Lists every role with its permission codes.

### `POST /api/v1/auth/roles/`
Requires `identity.manage_roles`. Creates a role.

Request:
```json
{ "name": "Auditor", "description": "Read-only access for compliance review.", "permission_codes": ["identity.view_users"] }
```

Response `201`: the created role. Every code in `permission_codes` must already exist as a `Permission` row — an unknown code is a `404 permission_not_found`, not a silently-ignored typo.

Errors: `409 duplicate_role_name`, `404 permission_not_found`.

### `POST /api/v1/auth/users/{user_id}/roles/`
Requires `identity.manage_roles`. Grants a role to a user.

Request: `{ "role_id": "018f..." }`
Errors: `404 user_not_found`, `404 role_not_found`, `409 role_already_assigned`.

### `DELETE /api/v1/auth/users/{user_id}/roles/{role_id}/`
Requires `identity.manage_roles`. Revokes a role from a user. `404 role_not_found` if the user doesn't currently hold it.

---

## Telegram linking — moved to the Employee module

**Identity exposes no Telegram-specific endpoints at all.** Earlier phases had four (`telegram/link/request/`, `telegram/link/verify/`, `telegram/unlink/`, `telegram/status/`) — all removed by the Employee & Telegram Authentication refactor. Employees using Telegram are never issued a `User` account or a JWT; **Identity authentication is exclusively for HR staff, administrators, managers, and other internal users accessing the web application.**

The equivalent flow now lives entirely in `apps/employees` — see `EMPLOYEE_API.md`'s "Telegram linking" section and `TELEGRAM_GATEWAY.md`. It's authenticated differently, too: those endpoints check a static `X-Internal-Service-Key` header (proving the caller is the Gateway itself), not a bearer JWT, since there is no employee-held credential to bear.

---

## System roles and permissions (seeded)

Seeded by `apps/identity/infrastructure/migrations/0002_seed_system_roles.py`, run automatically by `migrate`:

| Role | Identity permissions granted by default |
|---|---|
| Employee | none |
| Manager | none |
| HR Admin | `identity.view_users`, `identity.manage_users`, `identity.view_roles`, `identity.manage_roles` |
| Payroll Admin | none |
| Recruiter | none |

Only HR Admin gets identity-administration permissions out of the box — the other four are business-facing roles with no reason to manage accounts. Future modules (Leave, Payroll, ...) add their own `Permission` rows and grant them to whichever roles make sense, via their own migrations — this seed data never needs to change for that to happen.

---

## Error codes reference

| HTTP | code | Meaning |
|---|---|---|
| 401 | `invalid_credentials` | Login failed — wrong email or password |
| 401 | `inactive_user` | Account exists but is deactivated |
| 401 | `invalid_token` | Token malformed, bad signature, expired, or wrong type (e.g. refresh token used as access token) |
| 401 | `token_revoked` | Token was explicitly revoked (logout, rotation, or password change) |
| 403 | `insufficient_permission` | Caller lacks the required role/permission |
| 404 | `user_not_found` / `role_not_found` / `permission_not_found` | — |
| 409 | `duplicate_email` / `duplicate_role_name` / `role_already_assigned` | Conflicts with existing state |
| 422 | `validation_error` / `invalid_reset_token` / `expired_reset_token` | Request failed a business rule |
| 500 | `internal_error` | Unexpected server error |

Telegram-linking error codes (`employee_not_found`, `duplicate_telegram_link`, `employee_not_linked_to_telegram`, `employee_not_active`, `invalid_employee_link_otp`, `expired_employee_link_otp`) are documented in `EMPLOYEE_API.md` — Identity's views can no longer raise any of them.

---

## Architecture notes relevant to consumers of this API

**User and Employee are separate, and this API only ever returns `User` data.** `employee_id` on the user profile is a nullable reference to a future `Employee` record — it will be `null` for every user until the Employee module exists and links one. Don't build frontend assumptions that every authenticated user has employee data; system accounts, external auditors, and consultants may authenticate here without ever having one.

**Access tokens are stateless but not eternal.** A 15-minute access token is not re-validated against the database claim-by-claim — except for two things that *are* checked fresh on every request: whether the account is still active, and whether the token was issued before the account's last password change. Both make revocation take effect within one request, not after a 15-minute delay.

**Refresh tokens rotate.** Every `/token/refresh/` call invalidates the refresh token it was given and returns a new one. A client that doesn't update its stored refresh token after calling this endpoint will find its *next* refresh attempt rejected with `401 token_revoked` — this is by design (replay protection), not a bug.
