# Telegram Gateway — Reference

`telegram_gateway/` is a separate deployable (own container, own codebase, own `requirements.txt`) implementing Phase 7 of the roadmap: employee self-service via Telegram. It is a pure integration layer — it holds no HR data of its own, no database driver, no ORM. Everything it knows about an employee, it just learned by calling the Django backend's REST API a moment ago.

This document describes how the Gateway is built and how to run it. For the backend endpoints it calls, see `EMPLOYEE_API.md`'s "Telegram linking" section — this document doesn't repeat their request/response shapes, only how the Gateway uses them.

**Employee & Telegram Authentication refactor.** Telegram-linked employees are never issued an Identity `User` account or a JWT — see this section and §3/§4 below, and `EMPLOYEE_API.md` for the backend side. Every reference in this document to a token pair, session, or encrypted token store describes the *old* (removed) design; the current design is simpler and is what's described here.

---

## 1. Architecture — the constraint this service exists to enforce

**Telegram is not the HR system. Telegram is only another client.** Concretely, that means:

```
Telegram User → Telegram Bot API → Telegram Gateway → Django REST API → Application Services → Repositories → PostgreSQL
```

The Gateway sits between "Telegram Bot API" and "Django REST API" in that chain and **never has an arrow to PostgreSQL.** This is enforced structurally, not just by convention: `telegram_gateway/requirements.txt` contains no `psycopg`/`django`/any ORM package at all. A future contributor who tries to "just import the model directly, it's faster" gets an `ImportError` at container build time, not a comment in code review.

**The Gateway holds no per-employee credential at all.** Employees using Telegram are never issued an Identity `User` account or a JWT — Identity's authentication is exclusively for HR staff/administrators/managers accessing the web application (`IDENTITY_API.md`). Instead, the backend stores the Telegram user id directly on the `Employee` record (`apps/employees/domain/entities.py`'s `Employee.link_telegram`), and every request after linking simply presents that same id again — there is nothing to refresh, encrypt, or expire on the Gateway's side.

The Gateway authenticates *itself* to the backend (not any individual employee) using a single static shared secret, `X-Internal-Service-Key`, checked by `shared_kernel.api.permissions.HasInternalServiceKey` on the Django side. This proves "this caller really is the Gateway," never "which employee is this" — *which* employee a call is about travels as an ordinary `telegram_user_id` request parameter, not as a credential.

## 2. Folder structure

```
telegram_gateway/
├── src/
│   ├── webhook/            # the one inbound HTTP surface — server.py, update_router.py, security.py, rate_limiter.py
│   ├── telegram_client/    # outbound calls TO the Telegram Bot API (send/edit message, answer callback)
│   ├── api_client/         # outbound calls TO the HRMS backend — the ONLY path to HR data
│   │   └── endpoints/      # one file per backend module called (today: employees.py — profile reads AND Telegram linking, both apps.employees now)
│   ├── auth/                # account linking conversation state (no token storage — see §4)
│   ├── handlers/            # one file per command family + the Open/Closed command registry
│   ├── formatting/          # pure functions: API JSON -> Telegram message text/keyboards
│   ├── config.py            # env-driven settings only — no HR configuration
│   └── main.py               # process entrypoint
├── tests/unit/
├── requirements.txt
└── (Dockerfile lives at ../infra/docker/telegram.Dockerfile, matching backend.Dockerfile's convention)
```

Every layer here has exactly one job, mirroring the backend's own module discipline:

- **`webhook/`** is the only inbound network surface. `security.py` rejects any request whose `X-Telegram-Bot-Api-Secret-Token` header doesn't match the configured secret, before the body is even parsed — Telegram's actual, documented anti-forgery mechanism, not a placeholder. `rate_limiter.py` applies a soft per-chat cap ahead of that.
- **`telegram_client/`** only knows how to talk to Telegram's Bot API. It has zero knowledge of HR data.
- **`api_client/`** only knows how to talk to the Django backend. `hrms_client.py` is the base HTTP client (attaches the static `X-Internal-Service-Key` header once, at construction, to every request; translates the backend's `{"success": false, "error": {...}}` envelope into `HRMSAPIError`); `endpoints/employees.py` maps 1:1 to every Gateway-facing endpoint under `apps/employees/interface/telegram_views.py` — profile reads and Telegram linking alike, since both are exclusively an Employee-module concern now.
- **`auth/`** holds only the Gateway's own transient "awaiting OTP" conversation state — see §3 and §4.
- **`handlers/`** contains one file per command (`start_handler.py`, `link_handler.py`, `profile_handler.py`, `status_handler.py`, `help_handler.py`) plus `registry.py`, the Open/Closed mechanism described in §6.
- **`formatting/`** turns `EmployeeProfile` data into the actual Telegram message text and keyboard markup, entirely separate from the handlers that fetch that data — a display change is a one-file edit regardless of how many commands show the same data.

## 3. Registration / linking flow

```
Employee sends: /link EMP-000123
        │
        ▼
Gateway calls  POST /api/v1/employees/telegram/link/request/  (employee_code, telegram_user_id, chat_id)
        │        (authenticated via X-Internal-Service-Key, not a bearer token)
        │
        ├─ 404 employee_not_found                    → friendly error, flow ends
        ├─ 409 duplicate_telegram_link                → friendly error, flow ends
        ├─ 409 employee_already_linked_to_telegram    → friendly error ("send /unlink from the other
        │        account, or contact HR"), flow ends — this employee already has a *different*
        │        Telegram account linked; re-linking is never silent (re-requesting a code for the
        │        SAME already-linked chat is fine and doesn't hit this — see EMPLOYEE_API.md)
        ├─ 422 employee_not_active                    → friendly error, flow ends
        ├─ 502 email_delivery_failed                  → friendly error ("try /link again in a moment");
        │        the token was still created and is valid for the full 10 minutes, only the email failed
        └─ 200 OK → OTP dispatched to every email the employee has on file — work_email
                     always, plus personal_email too if set (real SMTP or a log-only
                     fallback — see EMPLOYEE_API.md's "SMTP configuration" note)
                     Gateway records "awaiting OTP" state in its own Redis, 10-minute TTL
                     │
                     ▼
Employee replies with the 6-digit code
        │
        ▼
Gateway calls  POST /api/v1/employees/telegram/link/verify/  (telegram_user_id, chat_id, otp)
        │
        ├─ 422 invalid_employee_link_otp / expired_employee_link_otp → friendly error;
        │        pending state is LEFT IN PLACE so the employee can just retype the correct code
        ├─ 422 too_many_otp_attempts → friendly error ("send /link for a new code"); this token has
        │        had 5 wrong guesses and is now permanently locked (MAX_OTP_ATTEMPTS) — the Gateway
        │        clears its own "awaiting OTP" state on this specific error (unlike a plain wrong
        │        guess) so the very next /link isn't blocked by a stale "already in progress" check
        └─ 200 OK → the backend has already stored telegram_user_id directly on the Employee
                     record (Employee.link_telegram) — the response is the now-linked employee
                     profile, not a token pair. Employee is shown the main menu.
```

Two things worth calling out:

**No HR User is ever created.** This is the entire point of the Employee & Telegram Authentication refactor: a Telegram-linked employee never gets an Identity `User` account, a password, or a JWT — Identity authentication is exclusively for HR staff/administrators/managers accessing the web application. `POST /link/request/` and `POST /link/verify/` (`apps/employees/interface/telegram_views.py`) touch only the `Employee` table.

**Where "still waiting for an OTP" state lives.** `auth/account_linking.py`'s `AccountLinkingService` is the only file in this service that models a linking flow as a two-step conversation. That state lives in this service's own Redis (`telegram_gateway:linking:{telegram_user_id}`), with a TTL matching the backend's own OTP lifetime (`apps/employees/application/services/employee_telegram_linking_service.py`'s `LINK_OTP_LIFETIME`) — so the Gateway never tells an employee "still waiting" past the point the backend would already reject the code as expired. This is the *only* local state this service keeps about linking; whether an account is actually linked is always asked of the backend fresh (see §4).

## 4. "Session" management — there isn't one

Earlier phases of this service stored an encrypted access/refresh token pair per employee and refreshed it on demand (`auth/token_store.py`, `auth/session.py`). Both files are gone. Employees present the same `telegram_user_id` on every request; there is no token to go stale, no refresh to attempt, and no encrypted store to manage.

Every handler that needs employee data simply calls `ctx.employees.get_profile(telegram_user_id=ctx.telegram_user_id)` directly (`api_client/endpoints/employees.py`), and every handler that needs to know "is this Telegram account linked" calls `ctx.linking.is_linked(telegram_user_id)` (`auth/account_linking.py`), which asks the backend's `GET /telegram/status/` fresh — never a local cache. The Employee table is the single source of truth for link state, full stop.

## 5. Main menu and commands

| Command | Requires linking? | What it does |
|---|---|---|
| `/start` | No | Greets the employee; shows onboarding instructions if unlinked, the main menu if already linked |
| `/link <employee_id>` | No | Starts the registration flow (§3) |
| `/profile` | Yes | "My Profile" card — job title, department, manager, contact info, employment type, status. Fields the approved schema has no column for (Company, Branch) render as a friendly placeholder, never invented data |
| `/status` | Yes | A terser, status-only view |
| `/unlink` | Yes | Asks for confirmation (inline keyboard), then unlinks |
| `/help` | No | Static command list |

The persistent Reply Keyboard (shown in place of the phone's own keyboard once linked) is built **from the same command registry** the slash commands are registered in — see §6 — not a second, hand-maintained button list.

## 6. Open/Closed extensibility (`handlers/registry.py`)

The brief calls for a menu system "open for future HR modules" (Leave, Attendance, Payroll, Approvals — per the roadmap). The mechanism:

```python
# a hypothetical future handlers/leave_handlers.py
from src.handlers.registry import registry

@registry.command("leave_balance", menu_label="🌴 Leave Balance", menu_order=30)
async def handle_leave_balance(ctx):
    ...
```

That's the entire integration surface. `webhook/update_router.py` (the only file with branching logic — "which handler," never business rules) is never edited to add this; it already just calls `registry.dispatch(...)`. `formatting/keyboards.build_main_menu_keyboard()` reads `registry.menu_entries()`, so the new button appears automatically, ordered by `menu_order`. A command registered without a `menu_label` (like `/start`) simply never appears as a button.

## 7. Security

| Control | Where |
|---|---|
| Webhook signature verification (`X-Telegram-Bot-Api-Secret-Token`) | `webhook/security.py`, constant-time comparison |
| Per-chat soft rate limiting | `webhook/rate_limiter.py` |
| Every backend call authenticated as "the Gateway" via a static shared secret, constant-time compared | `api_client/hrms_client.py` sends `X-Internal-Service-Key`; `shared_kernel.api.permissions.HasInternalServiceKey` checks it backend-side |
| OTP verified server-side by the backend, never trusted client-side | `auth/account_linking.py` calls `verify_link()`, never inspects the OTP itself |
| No per-employee credential held by this service at all | Employees are identified by `telegram_user_id` alone — nothing to encrypt at rest, because nothing is stored |
| No database credentials in this container at all | `requirements.txt` — structural, not policy |
| Secrets never logged | `logging_config.py`'s `redact()` scrubs `otp`/`access_token`/`refresh_token`/`token`/`webhook_secret_token`/`password` keys defensively; the primary control is simply never passing them to a log call |

## 8. Error handling

`errors.py` defines two families: `GatewayError` subclasses (problems local to this service — invalid webhook signature, no linked session, a stray OTP-shaped message with no pending link) and `HRMSAPIError` (a structured wrapper around whatever the backend's error envelope said). `friendly_message_for(error)` is the single lookup table translating either into the text an employee actually reads — no handler invents its own copy of "the code is wrong," and no stack trace or raw backend error code ever reaches a chat message. Every `HRMSAPIError.code` this Gateway can receive (the complete vocabulary of `apps.employees.domain.exceptions`, including `employee_already_linked_to_telegram`, `too_many_otp_attempts`, `email_delivery_failed`, and `backend_unreachable`) has an explicit, hand-written entry in `_FRIENDLY_MESSAGES` — any code that *isn't* in that table falls back to a generic message, never to the error's own `message` text, since that can (for `backend_unreachable` specifically) be a raw transport-level string from `httpx` rather than backend-crafted copy. `webhook/update_router.py` also has a top-level catch-all so an unexpected exception in any handler degrades to a generic "something went wrong" reply instead of the bot silently going dark.

## 9. Logging

Every log line is a single JSON object (`logging_config.py`), with a consistent `event` field per log statement (`update_received`, `linking_started`, `linking_completed`, `linking_otp_rejected`, `account_unlinked`, `hrms_api_call`, `hrms_api_transport_error`, `handler_unexpected_error`, ...) so the whole request lifecycle — webhook receipt, backend calls, callback handling, errors — is greppable by event name in aggregated logs.

## 10. Running locally

```bash
cp telegram_gateway/.env.example .env   # values also live in the project root .env — see infra/docker-compose.yml
docker compose -f infra/docker-compose.yml up telegram_gateway_redis telegram_gateway
```

The `telegram_gateway` service in `infra/docker-compose.yml` depends on `backend` (for the API it calls) and its own `telegram_gateway_redis` (never the backend's `redis`). It exposes `8080` locally; for real Telegram webhook delivery during local development, tunnel that port (e.g. `ngrok http 8080`) and call Telegram's `setWebhook` with the tunnel URL and your configured `TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN`.

`GET /healthz` is a liveness probe (deliberately does not check Redis/backend connectivity — see `webhook/server.py`'s docstring on why).

## 11. Testing

`tests/unit/` uses hand-rolled async fakes (`tests/fakes.py`) for every I/O boundary — no mocking library, matching the backend's own "fakes, not mocks" convention. This works because the orchestration/handler layer (`auth/account_linking.py`, `handlers/*.py`, `webhook/update_router.py`) imports its infrastructure collaborators (`HRMSClient`, `EmployeesEndpoint`, `redis.Redis`) only under `TYPE_CHECKING` — they're never instantiated by that layer, only called by duck-typed shape. The practical result: `handlers/`, `auth/account_linking.py`, `webhook/update_router.py`, `webhook/rate_limiter.py`, `webhook/security.py`, `formatting/`, and `handlers/registry.py` are all unit-testable with zero third-party packages installed — the same "domain/application layer has no framework dependency" property `HRMS_Architecture.md` section 1.2 establishes for the backend, now true here too.

```bash
cd telegram_gateway
pip install -r requirements-dev.txt
pytest
```

## 12. Environment variables

See `telegram_gateway/.env.example` (and the same block duplicated in the project root `.env.example`, since `infra/docker-compose.yml`'s `telegram_gateway` service reads `env_file: ../.env`). Every variable is prefixed `TELEGRAM_GATEWAY_` so it can never collide with — or accidentally satisfy — the Django backend's own environment variables.

| Variable | Purpose |
|---|---|
| `TELEGRAM_GATEWAY_BOT_TOKEN` | Telegram Bot API token from @BotFather |
| `TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN` | Shared secret verified on every inbound webhook call |
| `TELEGRAM_GATEWAY_WEBHOOK_PATH` | Path this service registers with Telegram via `setWebhook` |
| `TELEGRAM_GATEWAY_HRMS_API_BASE_URL` | Base URL of the Django backend |
| `TELEGRAM_GATEWAY_INTERNAL_API_KEY` | Sent as `X-Internal-Service-Key` on every backend call — must match the backend's `INTERNAL_SERVICE_API_KEY` exactly |
| `TELEGRAM_GATEWAY_REDIS_URL` | This service's own Redis — the "awaiting OTP" conversation state (§3) and rate limiting only |
| `TELEGRAM_GATEWAY_RATE_LIMIT_PER_CHAT_PER_MINUTE` | Soft per-chat webhook throttle (default 20) |

---

## Architecture notes relevant to future phases

**Adding Leave/Attendance/Payroll/Approvals commands never requires touching `webhook/update_router.py`, `formatting/keyboards.py`, or any existing handler file** — see §6. The only new files needed are `api_client/endpoints/<module>.py` and `handlers/<module>_handlers.py`, matching the backend's own module-boundary discipline (a handler for a Leave command only ever imports `endpoints/leave.py`, never another module's endpoint file).

**This service will need its own CI job and its own container image**, independent of the backend's release cadence — that's the entire point of it being a separate deployable (`HRMS_Architecture.md` section 2's "monorepo, three deployables" decision).

**Proactive/outbound Telegram messages** (e.g. "your leave request was approved," pushed without the employee messaging first) are out of scope for this phase — every message today is a reply to an inbound webhook update. That capability, when built, is a new outbound path (likely triggered by a domain event via the backend's `EventBus`, delivered through `telegram_client/bot_api_client.py`'s existing `send_message`), not a change to anything described in this document.
