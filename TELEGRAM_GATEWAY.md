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
│   │   └── endpoints/      # one file per backend module called: employees.py (profile reads AND Telegram linking, both apps.employees), leave.py (types/balance/apply/history/detail/cancel, mirrors LEAVE_API.md's telegram/ surface)
│   ├── auth/                # conversation state this service keeps locally: account linking (no token storage — see §4) AND the multi-step Apply Leave flow (§3b)
│   ├── handlers/            # one file per command family + the Open/Closed command registry + calendar_widget.py (§3c, reusable date-picker dispatch)
│   ├── formatting/          # pure functions: API JSON -> Telegram message text/keyboards, incl. calendar_keyboard.py (§3c)
│   ├── config.py            # env-driven settings only — no HR configuration
│   └── main.py               # process entrypoint
├── tests/unit/
├── requirements.txt
└── (Dockerfile lives at ../infra/docker/telegram.Dockerfile, matching backend.Dockerfile's convention)
```

Every layer here has exactly one job, mirroring the backend's own module discipline:

- **`webhook/`** is the only inbound network surface. `security.py` rejects any request whose `X-Telegram-Bot-Api-Secret-Token` header doesn't match the configured secret, before the body is even parsed — Telegram's actual, documented anti-forgery mechanism, not a placeholder. `rate_limiter.py` applies a soft per-chat cap ahead of that.
- **`telegram_client/`** only knows how to talk to Telegram's Bot API. It has zero knowledge of HR data.
- **`api_client/`** only knows how to talk to the Django backend. `hrms_client.py` is the base HTTP client (attaches the static `X-Internal-Service-Key` header once, at construction, to every request; translates the backend's `{"success": false, "error": {...}}` envelope into `HRMSAPIError`; `get_with_meta()` is the one method that also returns the response envelope's `meta` block, needed for `endpoints/leave.py`'s paginated history call); `endpoints/employees.py` maps 1:1 to every Gateway-facing endpoint under `apps/employees/interface/telegram_views.py`; `endpoints/leave.py` maps 1:1 to every endpoint under `LEAVE_API.md`'s "Telegram Gateway-facing surface".
- **`auth/`** holds transient conversation state local to this service, never persisted to the backend: `account_linking.py`'s "awaiting OTP" state (§3, §4) and `leave_application.py`'s "mid-way through Apply Leave" state (§3b).
- **`handlers/`** contains one file per command family (`start_handler.py`, `link_handler.py`, `profile_handler.py`, `status_handler.py`, `help_handler.py`, `leave_handlers.py`) plus `registry.py`, the Open/Closed mechanism described in §6.
- **`formatting/`** turns endpoint response data into the actual Telegram message text and keyboard markup, entirely separate from the handlers that fetch that data — a display change is a one-file edit regardless of how many commands show the same data. `leave_formatter.py` and the Leave-specific builders in `keyboards.py` (`build_leave_type_selection_keyboard`, `build_apply_leave_confirm_keyboard`, `build_leave_request_selection_keyboard`, `build_cancel_leave_confirm_keyboard`) follow the same split.

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

## 3b. Leave commands and the Apply Leave conversation

All six commands call `apps/leave`'s `telegram/` surface (`LEAVE_API.md` §"Telegram Gateway-facing surface") via `api_client/endpoints/leave.py`, authenticated the same way as everything else in this document — `X-Internal-Service-Key`, employee resolved by `telegram_user_id`, no JWT. No business rule (balance sufficiency, overlap, date validity, cancellability) is decided in this service; every one of those is enforced backend-side and surfaces here only as an `HRMSAPIError` translated by `friendly_message_for()`. Implementation: `handlers/leave_handlers.py` (all six commands and their callbacks live in this one file, per §3.5 of `HRMS_Folder_Structure.md`).

| Command | Requires linking? | What it does |
|---|---|---|
| `/leave_types` | Yes | Lists active leave types and their default annual allowance. No menu button (referenced from `/apply_leave`'s picker instead). |
| `/leave_balance` | Yes | Caller's balance for every active leave type, current year. |
| `/apply_leave` | Yes | Starts the guided multi-step flow below. |
| `/leave_history [page]` | Yes | Paginated list of the caller's own requests, 5 per page. |
| `/leave_request <id>` | Yes | Full detail for one request. No menu button (an id isn't something an employee has memorized) — reachable from `/leave_history`'s listed ids. |
| `/cancel_leave` | Yes | Lists the caller's own `pending`/`approved` requests as buttons, then asks for confirmation before cancelling. |

**Apply Leave, step by step:**

```
Employee sends: /apply_leave
        │
        ▼
Gateway calls  GET /api/v1/leave/telegram/types/  → shows an inline keyboard, one button per leave type
        │        callback_data: "leave:apply:type:<leave_type_id>"
        ▼
Employee taps a leave type
        │
        ▼
Gateway starts conversation state (auth/leave_application.py, Redis, 30-minute TTL,
        keyed by telegram_user_id) → EDITS that same message into an inline
        calendar for the start date (handlers/calendar_widget.py — see §3c)
        │
        ▼
Employee taps a day (or "Today") on the calendar  ─┐
        │                                           │  Prev/Next page the
        ▼                                           │  grid without leaving
Gateway edits the SAME message into a calendar      │  the step; Cancel aborts
        for the end date, anchored on the month      │  the whole application
        the start date fell in                       │  (state cleared, message
        │                                           │  edited to "❌ Cancelled.")
        ▼                                           │
Employee taps a day (or "Today") on the calendar ───┘
        │
        ▼
Gateway edits the SAME message: "Reason? (or send 'skip')", buttons cleared
        │
        ▼
Employee replies with free text (reason, or "skip") — the one step still
        free text; there's no sensible button UI for an open-ended reason
        │
        ▼
Gateway shows a summary + Confirm/Cancel inline keyboard
        │        callback_data: "leave:apply:confirm" / "leave:apply:abort"
        ├─ Cancel tapped → conversation state cleared, "No leave application was submitted."
        └─ Confirm tapped → Gateway calls
                 POST /api/v1/leave/telegram/requests/apply/
                 │
                 ├─ 422 insufficient_leave_balance / overlapping_leave_request /
                 │        duplicate_leave_request / past_leave_start_date / invalid_leave_date_range
                 │        → friendly error; state is cleared either way (submit() always clears
                 │        state, success or failure — a rejected application isn't stale, it's over,
                 │        and /apply_leave starts a clean one)
                 └─ 201 → "Leave request submitted" confirmation, showing the new request's id
```

**Where the free-text steps get routed.** `webhook/update_router.py`'s message routing checks, in order: is an OTP verification pending (`auth/account_linking.py`) — checked first since it's the older, narrower flow — then is an Apply Leave conversation active (`ctx.leave_application.is_active()`); only if neither is true does plain text fall through to "I didn't understand that." Free text arriving while the conversation is mid-calendar (start/end date step) doesn't attempt to parse it as a date at all anymore — it nudges the employee back to the calendar buttons instead (`handlers/leave_handlers.py`'s `handle_apply_leave_free_text`). Reason is still genuinely free text and mirrors `link_handler.handle_otp_reply`'s precedent exactly.

**Why `callback_prefix`, not `callback`.** A leave type id or leave request id is only known at runtime, so its callback_data (`leave:apply:type:<uuid>`, `leave:cancel:select:<uuid>`, `leave:cancel:confirm:<uuid>`) can't be registered as a fixed string ahead of time — the calendar's own callback_data (`cal:<purpose>:<action>:<yyyymm>[:<day>]`, §3c) is the same story. `registry.callback_prefix()` (§6) matches on a static prefix and hands the handler the full `callback_data` string to parse the suffix from — `update_router.py`'s dispatch logic needed no changes to support any of this, it already just calls `registry.get_callback(data)`.

**Cancel Leave only offers requests worth cancelling.** `handle_cancel_leave_start` filters to `pending`/`approved` requests before building the button list (`_CANCELLABLE_STATUSES` in `leave_handlers.py`) — a display-only filter mirroring the backend's own allowed-from states for cancellation (`LeaveRequest.cancel`); the backend re-enforces the real rule when Confirm is tapped regardless.

## 3c. The reusable inline calendar (`formatting/calendar_keyboard.py` + `handlers/calendar_widget.py`)

Leave's start/end date steps are the first, but not the only intended, consumer of this — the brief was to build a date picker any future HR module (Attendance corrections, Payroll effective dates, ...) can reuse without touching this file or `webhook/update_router.py`. The split, matching this document's usual formatting-vs-dispatch separation:

- **`formatting/calendar_keyboard.py`** — pure, stateless. `build_calendar_keyboard(purpose, year, month)` returns one month's `InlineKeyboardMarkup` (a tappable month/year caption row, weekday headers, day-number buttons Monday-first, a Prev/Today/Next row, a Cancel row) built entirely from the standard library `calendar` module — deliberately no third-party calendar package. `build_month_picker_keyboard(purpose, year)` returns the second view the caption row opens: a year-only Prev/Next row plus all 12 months of that year as buttons, so reaching a month many pages away (e.g. December next year) is two taps — Next-year, then the month — instead of paging Next one month at a time. `parse_calendar_callback(data)` decodes a button's callback_data back into `(purpose, action, year, month, day)`, returning `None` (never raising) for anything that doesn't look like this widget's own data. `shift_month(year, month, delta)` is the pure month-arithmetic day-grid Prev/Next relies on. `MIN_YEAR`/`MAX_YEAR` (1970–2100) bound how far either view's navigation can page — the stdlib `calendar` module doesn't itself reject year 0 or negative years, so without an explicit limit repeated Prev taps would page backward forever into nonsensical dates.
- **`handlers/calendar_widget.py`** — the dispatch half, registered once via `@registry.callback_prefix("cal:")`. A consuming module calls `register once, at import time`:
  ```python
  @calendar_widget.on_date_selected("leave.apply.start", prompt="📅 Select your *From date* ...")
  async def _on_start_date_picked(ctx, value: date | None) -> None:
      ...  # value is None if the picker was cancelled
  ```
  and kicks a calendar off with `await calendar_widget.start_calendar_flow(ctx, purpose="leave.apply.start", anchor=some_date)`. Everything else — Prev/Next paging on either view, opening/closing the month picker, the "Today" quick-pick, Cancel (edits the message to "❌ Cancelled.", clears its keyboard, then still calls the registered handler with `None` so the owning module can clean up its own state) — is handled generically, with zero knowledge of what "leave.apply.start" means. `purpose` strings use `.`/`_` internally, never `:` (reserved as `calendar_keyboard.py`'s own callback_data field separator — enforced by an assertion, not just convention).
- **`prompt` can be a plain string, or an async function of `HandlerContext`** (`Callable[[HandlerContext], Awaitable[str]]`), resolved fresh every time that purpose's view is rendered — navigating months, opening the month picker, all of it. Leave's end-date purpose uses this: its prompt reads the conversation's own state and echoes back whatever From date was already picked ("✅ *From date:* 2026-09-01 ... now select your *To date*"), so an employee paging around the end-date calendar never loses track of what they've already chosen. A plain string behaves exactly like a callable that always returns it — most purposes don't need anything dynamic.
- **Every navigation/cancel/view-switch action edits the existing message** (`HandlerContext.edit_message`, a small helper alongside `reply()`) — never sends a new one, so paging through months or years doesn't leave a trail of messages in the chat.

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
| `/leave_balance` | Yes | Leave balance by type, current year |
| `/apply_leave` | Yes | Guided multi-step Apply Leave conversation — see §3b |
| `/leave_history` | Yes | Paginated own leave request history |
| `/cancel_leave` | Yes | Pick a pending/approved request to cancel, with confirmation |
| `/leave_types` | Yes | List of active leave types (no menu button — see §3b) |
| `/leave_request <id>` | Yes | Single request detail (no menu button — see §3b) |
| `/help` | No | Static command list |

The persistent Reply Keyboard (shown in place of the phone's own keyboard once linked) is built **from the same command registry** the slash commands are registered in — see §6 — not a second, hand-maintained button list.

## 6. Open/Closed extensibility (`handlers/registry.py`)

The brief calls for a menu system "open for future HR modules" (Leave, Attendance, Payroll, Approvals — per the roadmap). Leave (§3b) is the first module built on this mechanism, and adding it required zero edits to `webhook/update_router.py`, `formatting/keyboards.build_main_menu_keyboard()`, or any existing handler file — only new files (`handlers/leave_handlers.py`, `api_client/endpoints/leave.py`, `auth/leave_application.py`, `formatting/leave_formatter.py`) plus additive changes to `handlers/context.py` (new required fields) and `webhook/server.py` (wiring the new dependencies into the composition root). The registration mechanism itself:

```python
# handlers/leave_handlers.py — a real command
from src.handlers.registry import registry

@registry.command("leave_balance", menu_label="💰 Leave Balance", menu_order=30)
async def handle_leave_balance(ctx):
    ...

# a callback whose data carries a runtime-only id (a leave type, a leave request)
@registry.callback_prefix("leave:apply:type:")
async def handle_apply_leave_type_selected(ctx):
    ...  # ctx.update.callback_data is the full "leave:apply:type:<uuid>" string
```

`registry.command(...)`/`registry.callback(...)` are unchanged from earlier phases. `registry.callback_prefix(prefix)` is new (added for Leave): it registers a handler against a static prefix rather than one fixed string, for callback_data with a dynamically embedded suffix. `get_callback(data)` tries an exact match first, then the longest matching registered prefix — so a more specific prefix (`leave:cancel:select:`) always wins over a broader one (`leave:`) if both were ever registered, and an exact-string callback always wins over any prefix. `webhook/update_router.py`'s dispatch logic (`_route_callback`) needed no changes to support this — it already just calls `registry.get_callback(data)`.

`formatting/keyboards.build_main_menu_keyboard()` reads `registry.menu_entries()`, so a new button appears automatically, ordered by `menu_order`. A command registered without a `menu_label` (like `/start`, or Leave's `/leave_types` and `/leave_request`) simply never appears as a button.

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

**Leave (§3b) is built; Attendance/Payroll/Approvals are not.** Adding each of those never requires touching `webhook/update_router.py`'s dispatch logic or any existing handler file — see §6. The new files needed each time are `api_client/endpoints/<module>.py` and `handlers/<module>_handlers.py`, matching the backend's own module-boundary discipline (a handler for a Leave command only ever imports `endpoints/leave.py`, never another module's endpoint file). `handlers/context.py` and `webhook/server.py` do need additive edits each time — a new required field on `HandlerContext`, a new dependency wired in the composition root — as Leave's own integration demonstrates. Any future date-entry step (an Attendance correction date, a Payroll effective date, ...) doesn't need any of that groundwork repeated — `handlers/calendar_widget.py` (§3c) is already generic; a new module just picks its own `purpose` string and registers a handler.

**The next module on the roadmap is a generic Approval workflow** for HR requests (with some exceptions, e.g. leave balance requests are not approvable) — out of scope for this document until that phase's spec is provided. When it lands, it most likely needs its own Gateway commands (e.g. "my pending approvals," approve/reject inline buttons) built the same way Leave was.

**This service will need its own CI job and its own container image**, independent of the backend's release cadence — that's the entire point of it being a separate deployable (`HRMS_Architecture.md` section 2's "monorepo, three deployables" decision).

**Proactive/outbound Telegram messages** (e.g. "your leave request was approved," pushed without the employee messaging first) are out of scope for this phase — every message today is a reply to an inbound webhook update. That capability, when built, is a new outbound path (likely triggered by a domain event via the backend's `EventBus`, delivered through `telegram_client/bot_api_client.py`'s existing `send_message`), not a change to anything described in this document.
