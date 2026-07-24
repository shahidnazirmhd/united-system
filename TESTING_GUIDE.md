# United HRMS — Full System Testing Guide (Phase 1–8)

This is a from-scratch runbook: clean checkout → running stack → Identity/Employee flows verified → Telegram Gateway wired up and tested against a real Telegram bot, including Phase 8's Leave Management module end to end (REST + real Telegram bot commands). Follow it top to bottom the first time; the sections are also usable independently once your stack is already running.

Tools assumed: **VS Code**, **Docker Desktop**, **Postman**, a **Telegram account** on your phone or desktop, and (for the Telegram part only) **ngrok** — Telegram's servers need a public HTTPS URL to call, and `localhost` isn't reachable from the internet.

All commands below assume your VS Code integrated terminal's working directory is the project root (`United HRMS/`, the folder containing `backend/`, `telegram_gateway/`, `infra/`, this file, etc.). Open that folder in VS Code (`File > Open Folder`), then open a terminal (`` Ctrl+` ``).

**A note on shells.** Every command below is written as a single line deliberately — no `\` line-continuations — so it works unchanged whether your VS Code terminal is Windows `cmd.exe`, PowerShell, or a bash-like shell (Git Bash/WSL/macOS/Linux). `\` continuation is bash syntax only; `cmd.exe` will try to run the backslash itself as a command (that's what happened earlier). The one place shells genuinely differ is activating a Python virtual environment (Part B2) and grepping log output — both variants are given where that comes up.

---

## Part A — One-time environment setup

1. **Create your `.env` file.**
   ```bash
   cp .env.example .env
   ```
   Open `.env` in VS Code and fill in the placeholders. For local testing, the fastest path:
   - `DJANGO_SECRET_KEY`: generate one —
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(50))"
     ```
     Paste the output in.
   - `POSTGRES_PASSWORD`: pick any password, e.g. `changeme` — just keep it consistent (it's also embedded in `DATABASE_URL` a few lines below; update both).
   - Leave every `TELEGRAM_GATEWAY_*` variable as the placeholder text for now — Part E covers those once the core stack is proven working. The core backend does not read those variables, so it won't complain.
   - `INTERNAL_SERVICE_API_KEY` (backend) and `TELEGRAM_GATEWAY_INTERNAL_API_KEY` (gateway) **must be set to the exact same value** — this is the shared secret the Gateway uses to prove to the backend that a Telegram-linking call is really coming from the Gateway, not the general internet. Part E3 generates it; a placeholder mismatch here is the single most common cause of `403` errors in Part H.

2. **Sanity-check Docker Desktop is running** (VS Code's Docker extension, if installed, shows this in the sidebar; otherwise `docker ps` should return without error).

---

## Part B — Automated tests first (fast sanity gate)

Worth doing before any manual clicking — if these fail, manual testing will just rediscover the same problem slower.

### B1. Backend (Django) test suite
The `backend` image installs `requirements/production.txt` only (no pytest — deliberately, so test/lint tooling never ships to a real deployment). `infra/docker-compose.yml` instead builds the `local` Dockerfile stage, which layers `requirements/local.txt` (pytest, pytest-django, factory-boy, ...) on top — make sure you're on a version of this repo that has that stage (`infra/docker/backend.Dockerfile` should contain a `FROM production AS local` section) and rebuild once:
```bash
docker compose -f infra/docker-compose.yml --env-file .env build backend
docker compose -f infra/docker-compose.yml --env-file .env up -d db redis
docker compose -f infra/docker-compose.yml --env-file .env run --rm backend pytest
```
Expect all tests to pass. As of Phase 8 (Leave Management), this includes `apps/leave/tests/unit/` (domain entities, `LeaveValidationService`, `LeaveBalanceService`, `LeaveRequestService` — pure application-layer tests, no database) and `apps/leave/tests/integration/test_leave_endpoints.py` (real Postgres, full HTTP stack). If anything fails, stop here and share the output before continuing.

### B2. Telegram Gateway test suite
The gateway's tests need no database and no Docker — a plain local virtual environment is fastest, and lets you use VS Code's Test Explorer too if you want.
```bash
cd telegram_gateway
python -m venv .venv
```
Activate it — **Windows cmd.exe**: `.venv\Scripts\activate.bat`; **Windows PowerShell**: `.venv\Scripts\Activate.ps1`; **macOS/Linux**: `source .venv/bin/activate`. Then:
```bash
pip install -r requirements-dev.txt
pytest
```
Expect `190 passed`. As of Phase 8, this includes `tests/unit/test_leave_application.py` (the `/apply_leave` multi-step conversation state machine), `tests/unit/test_leave_handlers.py` (every Leave command and callback, plus a full end-to-end conversation routed through `update_router.route()`), and the Leave-related additions to `test_registry.py` (the new `callback_prefix()` matching), `test_update_router.py`, and every other handler test file (each now wires a `leave=`/`leave_application=` fake into `HandlerContext`). It also includes regression tests for two profile-card bugs fixed post-launch (the "🔄 Refresh" button no longer surfaces a false "Something went wrong" when the card's content hasn't changed, and the "🔓 Unlink account" button's callback_data now actually routes to a registered handler), and the reusable inline calendar date picker that replaced free-text date entry in Apply Leave: `tests/unit/test_calendar_keyboard.py` (the pure month-grid/callback_data functions, including `build_month_picker_keyboard`'s year-paged month grid and the `label` footer row) and `tests/unit/test_calendar_widget.py` (navigation, Today, Cancel, day-selection dispatch, opening/closing the month/year picker, and dynamic per-render prompts/labels, using throwaway test purposes independent of Leave — see `TELEGRAM_GATEWAY.md` §3c). It also covers this round's UX fixes: the From/To footer-label indicator and header/footer prompt split, `past_leave_start_date` mapping to the specific "contact HR" message rather than a generic fallback, `/leave_history`'s empty-state text, and `HandlerContext.clear_reply_markup()` being called everywhere a Leave callback proceeds via a new message instead of an in-place edit. Deactivate and `cd ..` back to the project root when done (`deactivate`).

---

## Part C — Bring up the core stack

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --build db redis backend celery_worker celery_beat
```

Watch it come up:
```bash
docker compose -f infra/docker-compose.yml --env-file .env logs -f backend
```
Look for Django's dev server banner ("Starting development server at http://0.0.0.0:8000/") with no tracebacks above it. `Ctrl+C` to stop following logs (the container keeps running).

### C1. Run migrations
```bash
docker compose -f infra/docker-compose.yml --env-file .env exec backend python manage.py migrate
```
You should see a list of `Applying ... OK` lines, including the seed migrations (`0002_seed_system_roles`, `0002_seed_employee_permissions`, `0003_seed_default_departments`) and the Telegram-linking migrations (`apps.employees`'s `0004_add_telegram_linking`, which adds the `telegram_*` fields and link-token table to Employee; `apps.identity`'s `0004_drop_telegram_tables`, which removes the old Identity-side Telegram tables from an earlier phase; and `apps.employees`'s `0005_add_link_token_attempt_count`, which adds the OTP brute-force lockout counter from the post-milestone error-handling review). Phase 8 adds `apps.leave`'s three migrations: `0001_initial` (`leave_types`/`leave_balances`/`leave_requests` tables), `0002_seed_leave_permissions` (`leave.view_leave`/`leave.manage_leave`, granted to HR Admin/Manager), and `0003_seed_default_leave_types` (seeds `ANNUAL`/`SICK`/`UNPAID`). No errors.

### C2. Health check
Open `http://localhost:8000/health/` in a browser, or:
```bash
curl http://localhost:8000/health/
```
Expect `{"success": true, "data": {...}}` with every check `"ok"`.

---

## Part D — Identity + Employee flows (Postman)

### D1. Bootstrap the first HR Admin
```bash
docker compose -f infra/docker-compose.yml --env-file .env exec backend python manage.py create_admin_user --email admin@example.com --password "AdminPass123!"
```
Use exactly this email/password — it matches the Postman collection's default `admin_email`/`admin_password` variables, so nothing else needs editing. Expect: `Created HR Admin user 'admin@example.com' (id=...)`.

### D2. Import and run the Postman collection
1. Postman → **Import** → select `United_HRMS.postman_collection.json` from the project root.
2. Confirm the collection variable `base_url` is `http://localhost:8000` (Collection → Variables tab).
3. Run folders **in order**, top to bottom: `1. Health` → `2. Auth Session` → `3. Password Reset` → `4. User Management` → `5. Role Management` → `6. Employee Management`. Each request's test script auto-populates the variables the next request needs (`access_token`, `employee_id`, etc.) — you don't need to copy/paste anything between requests within a folder.
4. **One manual step**: before running `6. Employee Management`'s `Create Employee` request, fetch a seeded department id and paste it into the `department_id` collection variable:
   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env exec backend python manage.py shell -c "from apps.employees.infrastructure.models import DepartmentRecord; [print(d.code, d.id) for d in DepartmentRecord.objects.all()]"
   ```
   Pick any one (e.g. `ENG`'s id) and set it as `department_id` in Postman.
5. Every request should return the status code its name implies (the "should fail"/"Not Found"/"Duplicate" ones are deliberately testing error paths — a 4xx there is a **pass**, not a bug).

At the end of this folder, note the `employee_code` printed in the **Create Employee** response (e.g. `EMP-000001`) — you'll link this exact employee to Telegram in Part H. This employee was created with no `user_id`, and that's fine and expected: `user_id` is an optional, admin-driven link to an HR System `User` account for web-app access, completely unrelated to Telegram. Telegram linking (Part H) never touches `user_id` and never creates a `User` — it only ever sets the `telegram_*` fields directly on this `Employee` record.

### D3. Confirm self-service `/me` works too
Optional but worth doing since it's new this phase — in Postman, manually send:
```
GET {{base_url}}/api/v1/employees/me/
Authorization: Bearer {{access_token}}
```
Since the admin user isn't itself linked to an employee record via `user_id`, expect `404 employee_not_found` — that's correct (only a `User` explicitly linked to an `Employee` via `user_id` should see this succeed). Note this is a different, JWT-authenticated endpoint from the Telegram-facing profile lookup exercised in Part H (`GET /employees/telegram/profile/`, authenticated via the internal service key and keyed by `telegram_user_id` instead) — linking via Telegram in Part H does not make this endpoint start succeeding, by design (see `EMPLOYEE_API.md`'s "Telegram linking" section for why the two are intentionally separate).

### D4. Leave Management REST surface (Phase 8)
`United_HRMS.postman_collection.json`'s **`7. Leave Management`** folder covers this — run it top to bottom after folders `2`, `4`, and `6` (it needs `access_token`, `new_user_id`/`new_user_access_token`, and `department_id`, all captured by those earlier folders).

There's no dedicated "link a User to an Employee" endpoint (`user_id` is only settable at `POST /employees/` creation time), so the folder's `Create Employee Linked To New User` request creates a **second** employee (Grace Hopper) with `user_id: {{new_user_id}}` specifically so the rest of the folder can authenticate as `new_user_access_token` and exercise the real self-service Leave flow — apply, duplicate/overlap/insufficient-balance rejections, history, detail, and cancel — against an account that's actually linked, rather than the admin account (which, like `/employees/me/` in D3, 404s `employee_not_found` on every self-service Leave endpoint since it isn't linked to any Employee). The folder also confirms auto-provisioning: `My Leave Balance - As Linked Employee` checks that Grace's balance rows exist with no manual seeding step, from `apps/leave/apps.py`'s subscription to the `EmployeeCreated` event.

Full request/response shapes and every error code are documented in `LEAVE_API.md`. The Telegram-facing surface (`/leave/telegram/...`) is exercised for real in Part H2 below rather than via Postman, since it's the Gateway's job to call it, not a human's.

If everything in Parts B–D passed, the pre-existing system (Phases 1–6) plus Phase 8's Leave REST surface are confirmed working, and you can move on to the new part.

---

## Part E — Telegram Gateway: getting real credentials

This is the part that's different from anything you've configured before, so read it slowly the first time.

### E1. Create a real Telegram bot
1. Open Telegram (phone app or web.telegram.org) and search for **@BotFather**.
2. Send `/newbot`.
3. Give it a display name (anything, e.g. "United HRMS Test Bot").
4. Give it a **username** ending in `bot` (must be globally unique across all of Telegram, e.g. `united_hrms_yourname_bot`).
5. BotFather replies with a token that looks like `123456789:AAExampleTokenValueGoesHere`. **This is `TELEGRAM_GATEWAY_BOT_TOKEN`.** Copy it into `.env`.

### E2. Generate the webhook secret
Any random string works — Telegram just echoes it back so we can verify a call is really from Telegram, not a forged request:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Paste the result into `TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN` in `.env`.

### E3. Generate the internal service key
This is the shared secret that authenticates the Gateway to the backend for every Telegram-linking call (checked via the `X-Internal-Service-Key` header, `shared_kernel.api.permissions.HasInternalServiceKey`). Unlike the old per-employee token encryption scheme this replaced, it needs no third-party package — plain stdlib is enough, so there's no need to build the gateway image first:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Paste the output into **both** `INTERNAL_SERVICE_API_KEY` (backend section) **and** `TELEGRAM_GATEWAY_INTERNAL_API_KEY` (gateway section) in `.env` — they must be the identical value. A mismatch here shows up as `403` responses from every `/employees/telegram/*` call in Part H, with `HasInternalServiceKey` rejecting the Gateway's requests.

### E4. Leave the rest as-is
`TELEGRAM_GATEWAY_HRMS_API_BASE_URL=http://backend:8000` and `TELEGRAM_GATEWAY_REDIS_URL=redis://telegram_gateway_redis:6379/0` are container-to-container hostnames on the compose network — don't change these to `localhost`, they won't resolve from inside the gateway's own container.

Save `.env`.

---

## Part F — Bring up the Gateway containers

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --build telegram_gateway_redis telegram_gateway
docker compose -f infra/docker-compose.yml --env-file .env logs -f telegram_gateway
```
Expect JSON log lines ending in something like `{"event": "gateway_started", ...}` with no tracebacks. `Ctrl+C` to stop following.

Verify the health endpoint from your host machine:
```bash
curl http://localhost:8080/healthz
```
Expect `{"status": "ok"}`.

If this fails, see **Troubleshooting** at the bottom before continuing — don't move on to the ngrok/Telegram part with a broken container.

---

## Part G — Expose the Gateway to Telegram (ngrok) and register the webhook

Telegram's servers must be able to reach your machine over HTTPS. Locally, that means a tunnel.

### G1. Install and run ngrok
1. Download from [ngrok.com/download](https://ngrok.com/download), sign up for a free account, and follow their one-time `ngrok config add-authtoken <token>` setup step.
2. In a **new, separate terminal** (leave it running for your whole test session):
   ```bash
   ngrok http 8080
   ```
3. Copy the `https://xxxxxxxx.ngrok-free.app` forwarding URL it prints — this changes every time you restart ngrok on the free tier, so if you restart it, repeat Step G2 below with the new URL.

### G2. Register the webhook with Telegram
Replace `<BOT_TOKEN>`, `<NGROK_URL>`, and `<WEBHOOK_SECRET>` with your real values from `.env`. This uses Telegram's Bot API as a plain query-string GET request rather than a JSON POST body specifically to sidestep quote-escaping differences between `cmd.exe`/PowerShell/bash — one line, no embedded quotes to get wrong:
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<NGROK_URL>/webhook/telegram&secret_token=<WEBHOOK_SECRET>"
```
Expect `{"ok":true,"result":true,"description":"Webhook was set"}`.

### G3. Verify it registered correctly
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
`url` should show your ngrok URL, and `last_error_message` should be absent (if it shows an error, see Troubleshooting).

---

## Part H — Real end-to-end Telegram testing

Open a chat with your bot in the actual Telegram app (search its username) and send these one at a time, checking the response each time.

| You send | Expect |
|---|---|
| `/start` | Onboarding message ("link your Telegram account...") since you're not linked yet |
| `/link EMP-000001` (use the real employee_code from Part D2) | "✅ We've sent a one-time code..." |
| *(nothing yet — go fetch the OTP, see below)* | — |
| *(the 6-digit code)* | "🎉 You're linked, `<Your Name>`! Use the menu below to get started." plus the main menu (Reply Keyboard) appears |
| `/profile` (or tap "👤 My Profile") | A formatted profile card — name, employee ID, job title, department, etc. Company/Branch show "_Not available_" — that's correct, not a bug (see `EMPLOYEE_API.md`) |
| Tap "🔄 Refresh" under the profile card | The same card re-renders in place (edited message, not a new one) |
| `/status` (or "📋 My Status") | A terser card showing just status, e.g. "🟢 Active" |
| `/unlink` | Asks for confirmation with Yes/Cancel buttons |
| Tap "❌ Cancel" | "No changes made — you're still linked." |
| `/unlink` again, then "✅ Yes, unlink" | "🔓 Your Telegram account has been unlinked." |
| `/profile` again | "You'll need to link your account first. Send /link to get started." — proves unlink actually took effect |

### Fetching the OTP
The OTP is delivered by **email**, not SMS/push — to `work_email` always, and to `personal_email` too if the employee you created in Part D2 has one set (the Postman collection's default payload doesn't, so expect a single email/log line unless you added one yourself). Both copies carry the identical code, so either inbox works. Which of two things happens depends on whether you configured real `SMTP_*` credentials in `.env` (Part A):

- **If you left `SMTP_HOST` blank** (the default, fastest path for local testing): no real email is sent — the backend logs the message instead, via `LoggingEmailClient`. Check:
  ```bash
  docker compose -f infra/docker-compose.yml --env-file .env logs backend --tail=50
  ```
  Look for a line like `Email requested for someone@example.com — subject='Your United HRMS Telegram verification code' (would be sent via SMTP, not logged in production): Hi Jane Doe,\n\nYour one-time verification code to link your Telegram account is: 482913\n\n...`. To filter instead of scrolling — **cmd.exe**:
  ```bat
  docker compose -f infra/docker-compose.yml --env-file .env logs backend --tail=200 | findstr "verification code"
  ```
  **PowerShell**:
  ```powershell
  docker compose -f infra/docker-compose.yml --env-file .env logs backend --tail=200 | Select-String "verification code"
  ```
- **If you configured a real Gmail (or other SMTP) account** (see `.env.example`'s SMTP setup guide): the backend actually sends the email via `SmtpEmailClient` — check the employee's `work_email` inbox for a message titled "Your United HRMS Telegram verification code" instead of the logs.

### Error-path checks worth doing too
- `/link EMP-999999` (an employee code that doesn't exist) → "We couldn't find an employee with that ID..."
- Type the wrong 6-digit code after a real `/link` → "That code isn't right..." (and the pending link stays open — you can just type the correct code next without re-running `/link`)
- Type the wrong code **5 times in a row** → the 5th wrong guess still says "That code isn't right...", but even the *correct* code on the 6th attempt now gets "That code has been entered incorrectly too many times... Send /link to request a new code." — and `/link` immediately works again (it isn't blocked by a stale "already in progress" message).
- Wait 10+ minutes after `/link` before entering the code → "That code has expired. Send /link to request a new one."
- From a **second** Telegram account, run `/link` with the employee_code of an employee who's already linked to your **first** account → "This employee ID is already linked to a different Telegram account..." — and no new OTP email goes out for this rejected attempt.
- Re-run `/link` from the **same, already-linked** account (e.g. you want another copy of the code) → this is allowed, a fresh OTP is sent normally, no error.
- Send some random text with no `/link` in progress → "I didn't understand that. Type /help..."

### Confirming the link server-side
Telegram linking never creates a `User` account or a `user_id` — it only sets the `telegram_*` fields directly on the `Employee` record. Verify that in Postman:
```
GET {{base_url}}/api/v1/employees/{{employee_id}}/
Authorization: Bearer {{access_token}}
```
`is_linked_to_telegram` should now be `true`, `telegram_username` should match your Telegram username, and `telegram_linked_at` should be a recent timestamp. `user_id` should still be `null` — that's correct, not a regression (see D2's note on why the two are unrelated). You can also confirm via Django shell:
```bash
docker compose -f infra/docker-compose.yml --env-file .env exec backend python manage.py shell -c "from apps.employees.infrastructure.models import EmployeeRecord; e = EmployeeRecord.objects.get(employee_code='EMP-000001'); print(e.telegram_user_id, e.telegram_username, e.telegram_linked_at, e.user_id)"
```
`user_id` in that last column should print `None`.

---

## Part H2 — Real end-to-end Leave testing via Telegram (Phase 8)

Continue in the same chat as Part H — you should still be linked (if you ran the `/unlink` steps at the end of Part H's table, send `/link EMP-000001` and re-verify with the OTP before continuing). Full command reference, the Apply Leave flow diagram, and how the calendar picker works: `TELEGRAM_GATEWAY.md` §3b/§3c.

| You send | Expect |
|---|---|
| `/leave_balance` (or "💰 Leave Balance") | One line per active leave type — `Annual Leave: 20.00 available (0.00 used)`-style — from the auto-provisioned balances confirmed in D4.3 |
| `/leave_types` | A list of `Annual Leave`, `Sick Leave`, `Unpaid Leave` with their default annual days |
| `/apply_leave` (or "📝 Apply Leave") | An inline keyboard, one button per leave type |
| Tap **Annual Leave** | The SAME message turns into an inline calendar for the current month — short header "🏖️ *Apply Leave*" above the grid, a tappable month/year caption, a Prev/Today/Next row, then **below the day grid, right above Cancel**: "🟢 FROM DATE — tap a day to select" |
| Tap **◀ Prev** a couple of times, then **Next ▶** back | The message keeps editing in place (no new messages appear) as the grid pages between months; the "🟢 FROM DATE" row stays put at the bottom throughout |
| Tap the month/year caption (e.g. "September 2026") | The SAME message switches to the month/year picker view — a year-only ◀/▶ row, all 12 months as buttons, the "🟢 FROM DATE" row still above Cancel, and Cancel |
| Tap **▶** on the year row a couple of times, then a month button | Jumps straight to that month/year's day grid in one tap — no need to page one month at a time |
| Tap any day number (e.g. `1`) | The SAME message turns into a calendar for the To date, opened on the month your From date fell in — header text becomes "✅ *From date:* 2026-09-01" (so it's always clear what you already picked), and the row above Cancel switches to "🔵 TO DATE — tap a day to select" (a distinct color/label from the From-date step) |
| Tap the month/year caption again while picking the To date, page around, then tap a month | Both the "✅ *From date:* ..." header and the "🔵 TO DATE" indicator stay visible through the whole detour — neither is lost when switching views |
| Tap a later day number (e.g. `3`) | The SAME message becomes: "✅ *From date:* 2026-09-01\n✅ *To date:* 2026-09-03" followed by "Want to add a reason? Send it, or reply \"skip\"." — the calendar buttons are gone, and both dates are recapped |
| Send `skip` | "*Please confirm your leave application:*" summary (type, dates, "📝 Reason: _(none)_") with **Confirm**/**Cancel** buttons |
| Tap **Confirm** | The Confirm/Cancel buttons vanish from that message immediately (text stays, just no longer tappable), then: "✅ Your leave request has been submitted and is *🟡 Pending*." plus dates and a request id — note the id, you'll need it below |
| `/leave_balance` again | `Pending requests: 3 days` now reflects the days just applied for; `Available` is unchanged (the balance gate is applied at apply time, not shown as already-deducted — see `LEAVE_API.md`'s balance note) |
| `/leave_history` | Shows the request you just submitted, "🟡 Pending" |
| `/leave_request <id>` (the id from the submit confirmation) | "*Leave Request Details*" card for that one request |
| `/cancel_leave` | An inline keyboard listing your `pending`/`approved` requests |
| Tap the request you just submitted | That list's buttons vanish immediately (text stays), then: "Cancel this request?" with its summary line and its own Confirm/Abort buttons |
| Tap **Confirm** | Those Confirm/Abort buttons vanish immediately too, then: "🚫 Leave request `<id>` has been cancelled."; a repeat `/leave_history` now shows "⚫ Cancelled" |

### Calendar picker checks worth doing too
- `/apply_leave` → pick a type → on the From-date calendar, tap **Today** → the SAME message immediately becomes the To-date calendar (Today is a one-tap pick, not just a "jump to this month" button)
- Mid-calendar (either From or To date step), type and send a plain message instead of tapping a button (e.g. `2026-09-01`) → "Please use the calendar buttons above to pick a date." — the flow does **not** try to parse it, and the calendar stays exactly as it was
- On the From-date calendar, tap **❌ Cancel** → the SAME message becomes "❌ Cancelled." with no buttons, and `/apply_leave` can be started fresh immediately (state was cleared, not left dangling)
- Page **◀ Prev** far enough back (many taps) → navigation eventually stops responding to further Prev taps once it hits the picker's minimum year (1970) — proves the paging bound, not an infinite scroll
- Open the month/year picker, then page **◀** on the year row far enough back → year navigation also stops at 1970, same bound as the day-grid Prev
- Open the month/year picker, then tap **❌ Cancel** from that view → same "❌ Cancelled." behavior as cancelling from the day grid — Cancel works from either view
- Send free text (e.g. a stray word) while **not** mid-`/apply_leave`, and while not mid-OTP-linking → falls through to "I didn't understand that." (proves the free-text routing in `update_router.py` correctly falls through when neither conversation is active)

### Stale-button checks worth doing too
- `/apply_leave` twice in a row without completing the first (tap **Annual Leave** on the second `/apply_leave`'s type list, ignore the first message entirely) → go back and tap a button on the FIRST message: the buttons are simply gone from it (message text unchanged) — nothing happens, no error, no double-started conversation
- Get to the "Please confirm your leave application" step, tap **Confirm**, then immediately try tapping **Confirm** again on the (now button-less) message → nothing to tap; confirms the buttons were stripped before the submit even completed, not after
- `/cancel_leave` with two or more cancellable requests, tap one, then go back and tap a *different* request on that same original list → the original list's buttons are already gone, so this isn't tappable at all

### Leave business-rule error-path checks worth doing too
- `/apply_leave` → pick a type → pick a start date, then an end date *before* it on the following calendar → `invalid_leave_date_range`'s friendly message on Confirm
- `/apply_leave` → pick a type → pick a From date *before today* (page **◀ Prev** back a month or two, tap any day) → carry on to Confirm → "Backdated leave requests cannot be submitted through Telegram. Please contact HR department." — never a generic "Something went wrong"
- Apply for the same exact type + dates twice in a row → the second attempt gets `duplicate_leave_request`'s friendly message on Confirm
- Apply for overlapping dates under a *different* leave type while the first request is still `pending` → `overlapping_leave_request`
- Apply for more days than your remaining balance allows → `insufficient_leave_balance`
- Start `/apply_leave`, pick a type, get all the way to the confirmation summary, then tap **Cancel** there instead of Confirm → "No leave application was submitted." and `/apply_leave` can be started fresh immediately
- `/cancel_leave` when you have no `pending`/`approved` requests (e.g. right after a fresh account, or after cancelling everything) → a friendly "nothing to cancel" message, no empty keyboard shown
- `/leave_history` for an account with no leave requests at all yet → "No leave history found." — never "Something went wrong"
- `/leave_request <a made-up id>` → `leave_request_not_found`'s friendly message

---

## Part I — Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `docker compose ... exec backend` says no such service | You're not passing `-f infra/docker-compose.yml`, or the containers aren't up yet (`docker compose ... ps` to check) |
| `curl http://localhost:8080/healthz` fails / connection refused | `telegram_gateway` container isn't up or crashed on start — check `docker compose ... logs telegram_gateway` for a Python traceback, usually a missing/invalid env var (Part E) |
| `getWebhookInfo` shows a `last_error_message` about connection refused/timeout | ngrok isn't running, or you registered the webhook with an old (expired) ngrok URL — restart ngrok, re-run Part G2 with the new URL |
| Telegram never responds to `/start` at all | Check `docker compose ... logs telegram_gateway` for `webhook_signature_rejected` (means `TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN` in `.env` doesn't match what you passed to `setWebhook` in G2 — they must be identical) |
| `/link EMP-000001` replies "Something went wrong on our end" | Check `docker compose ... logs telegram_gateway` for the real error; also check `docker compose ... logs backend` — a common cause is the gateway not being able to reach `http://backend:8000` (confirm both containers are on the same compose network, i.e. both started via the same `docker compose -f infra/docker-compose.yml` invocation) |
| OTP never appears in backend logs | Confirm `link/request/` actually returned `200` in the gateway logs (`hrms_api_call` event) — if it returned `404 employee_not_found`, double check the employee_code you typed |
| Postman requests fail with connection refused | `backend` container isn't up — `docker compose ... ps` and `docker compose ... logs backend` |

---

## Part J — Resetting for a clean re-test

To wipe the database and start over (careful — this deletes all data):
```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
docker compose -f infra/docker-compose.yml --env-file .env exec backend python manage.py migrate
```
Then repeat from Part D1 (`create_admin_user`) onward. You'll also need to re-run `/unlink`-then-`/link` in Telegram if you'd previously linked, since a fresh database has no linked accounts, and re-register the webhook (Part G2) only if ngrok itself was restarted — the webhook registration lives with Telegram, not your database, so it survives a `down -v`.
