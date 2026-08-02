# Temporary Cloud Demo Deployment (2-3 days)

This is a throwaway deployment for showing the system to your manager remotely — not a real production rollout. It's built to be torn down afterward (see the last section). Everything here is free, no credit card required anywhere in this guide.

## What we're deploying, and why this shape

The full local stack (`infra/docker-compose.yml`) is: Postgres, two Redis instances, the Django backend, Celery worker + beat, and the Telegram Gateway. For a 2-3 day demo we can trim this:

- **Celery worker/beat are skipped entirely.** There are zero real background tasks defined anywhere in the backend today (confirmed by grep — `task_routes` is deliberately empty, staged for Phase 9). Not deploying them loses nothing.
- **Two managed free services replace self-hosted Postgres/Redis**: Render's free PostgreSQL, and two free Upstash Redis databases (one for the backend's cache/Celery-broker/JWT-blocklist vars, one for the Gateway's own conversation-state Redis — mirroring the existing "Gateway gets its own isolated Redis" design in docker-compose).
- **Render** hosts both the Django backend and the Telegram Gateway as two separate free Docker web services. The reason to pick Render specifically: free web services get an HTTPS `*.onrender.com` URL automatically, and Telegram *requires* HTTPS for webhooks — this sidesteps needing to buy/configure a domain or TLS certificate yourself.

One real constraint this plan works around: **Render's free tier has no shell/SSH access and no pre-deploy command** (both paid-only). So there's no way to `exec` into the container and run `manage.py migrate` by hand. To handle this I added two small, deploy-only files (nothing about your local dev setup changes):

- `infra/docker/backend.render.Dockerfile` — same production image as `backend.Dockerfile`, but its start command runs `migrate` and a new `seed_demo_data` management command before starting gunicorn, every time the container boots (both are idempotent, so this is safe to repeat on every restart).
- `backend/apps/identity/management/commands/seed_demo_data.py` — idempotently creates one Department and one Admin user from environment variables, so you get a working login without ever needing a shell.

Also fixed one real (pre-existing, not demo-specific) settings bug while at it: `backend/config/settings/base.py` now sets `SECURE_PROXY_SSL_HEADER`, which any deployment behind a reverse proxy (Render, Railway, Fly, nginx — not just this one) needs, or `SECURE_SSL_REDIRECT=True` in `production.py`/`staging.py` causes an infinite redirect loop.

---

## Phase 1 — Create your Telegram bot (2 minutes)

1. In Telegram, message **@BotFather**.
2. Send `/newbot`, give it a name and a unique username ending in `bot`.
3. BotFather replies with a token like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. Save it — this is `TELEGRAM_GATEWAY_BOT_TOKEN`.

## Phase 2 — Generate the secrets you'll need

Run these locally (or in this Cowork sandbox) and save the output — you'll paste them into Render shortly:

```bash
python3 -c "import secrets; print('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(50))"
python3 -c "import secrets; print('INTERNAL_SERVICE_API_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN=' + secrets.token_urlsafe(32))"
```

`INTERNAL_SERVICE_API_KEY` and `TELEGRAM_GATEWAY_INTERNAL_API_KEY` (gateway side) **must be the exact same value** — it's the shared secret the Gateway uses to authenticate to the backend.

## Phase 3 — Two free Redis databases (Upstash)

1. Go to upstash.com → sign up free (GitHub/Google/email, no card).
2. **Create Database** → name it `hrms-backend-redis` → any nearby region → Redis. Once created, open its connection details — Upstash shows an example like `redis-cli --tls -u redis://default:<password>@<host>:6379`, i.e. scheme `redis://` plus a *separate* `--tls` flag, because that's how `redis-cli` specifically takes it. **Our code doesn't have a separate TLS flag — it only looks at the URL scheme.** So take that string and manually change `redis://` to `rediss://` (double s) before using it anywhere below: `rediss://default:<password>@<host>:6379`. Getting this wrong is the single most common mistake in this whole guide — Upstash's free databases only accept TLS connections, so a plain `redis://` URL connects, gets its first bytes rejected, and dies immediately (you'll see `redis.exceptions.ConnectionError: Connection closed by server` in the logs if this happens).
3. **Create Database** again → name it `hrms-gateway-redis` → same steps → same `redis://` → `rediss://` fix → copy that URL too.

You now have two `rediss://` URLs. Keep them labeled — they go to different services.

## Phase 4 — Render: account + free Postgres

1. Go to render.com → sign up free.
2. **New** → **PostgreSQL** → name `hrms-db` → free plan → Create.
3. Once it's up, open it and copy the **Internal Database URL** (starts with `postgres://` — internal is faster and free-bandwidth-friendly since the backend service will also live on Render).

## Phase 5 — Deploy the backend

1. **New** → **Web Service** → connect the `united-system` GitHub repo.
2. Runtime: **Docker**. Set:
   - **Dockerfile Path**: `infra/docker/backend.render.Dockerfile`
   - **Docker Build Context Directory**: `backend`
   - Plan: **Free**
3. Before the first deploy, add environment variables. Use **Add from .env** and paste the contents of the repo's root `.env.example`, then override these:

   | Key | Value |
   |---|---|
   | `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
   | `DJANGO_SECRET_KEY` | the value generated in Phase 2 |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | *(leave as `localhost,127.0.0.1` for now — see step 4 below)* |
   | `DATABASE_URL` | the Internal Database URL from Phase 4 |
   | `DB_SSL_MODE` | `require` |
   | `REDIS_CACHE_URL` | the `hrms-backend-redis` Upstash URL |
   | `CELERY_BROKER_URL` | same `hrms-backend-redis` URL |
   | `CELERY_RESULT_BACKEND` | same `hrms-backend-redis` URL |
   | `REDIS_TOKEN_BLOCKLIST_URL` | same `hrms-backend-redis` URL |
   | `INTERNAL_SERVICE_API_KEY` | the value generated in Phase 2 |
   | `PORT` | `8000` |
   | `DEMO_ADMIN_EMAIL` | your email |
   | `DEMO_ADMIN_PASSWORD` | a password you choose for this demo login |
   | `DEMO_DEPARTMENT_NAME` | `Demo` *(optional — this is the default)* |
   | `DEMO_DEPARTMENT_CODE` | `DEMO` *(optional — this is the default)* |

   Leave `SMTP_HOST` blank — with no SMTP configured, OTP codes for Telegram linking just get logged instead of emailed, which is fine for a demo (see Phase 8). If you'd rather have real emails, set real SMTP creds here (e.g. a Gmail account with an App Password) and skip the "read the OTP from logs" step later.

4. Click **Create Web Service**. First build takes a few minutes. Once deployed, Render shows you the service's URL, e.g. `https://hrms-backend-xxxx.onrender.com`. **Go back into Environment**, set `ALLOWED_HOSTS` to that exact hostname (no `https://`, no trailing slash — just `hrms-backend-xxxx.onrender.com`), and save (this triggers a redeploy).
5. Watch the **Logs** tab during this redeploy. You should see the `migrate` output, then something like:
   ```
   Seeded department 'Demo' (DEMO), id=<uuid>
   Seeded Admin '<your email>' (id=<uuid>).
   ```
   **Copy that department `id` (UUID) — you'll need it in Phase 8.**
6. Sanity check: `curl https://hrms-backend-xxxx.onrender.com/health/` should return a 200.

## Phase 6 — Deploy the Telegram Gateway

1. **New** → **Web Service** → same repo.
2. Runtime: **Docker**. Set:
   - **Dockerfile Path**: `infra/docker/telegram.Dockerfile`
   - **Docker Build Context Directory**: `telegram_gateway`
   - Plan: **Free**
3. **Add from .env** using `telegram_gateway/.env.example`, then override:

   | Key | Value |
   |---|---|
   | `TELEGRAM_GATEWAY_BOT_TOKEN` | the BotFather token from Phase 1 |
   | `TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN` | the value generated in Phase 2 |
   | `TELEGRAM_GATEWAY_WEBHOOK_PATH` | `/webhook/telegram` |
   | `TELEGRAM_GATEWAY_HRMS_API_BASE_URL` | `https://hrms-backend-xxxx.onrender.com` *(your backend's URL, no trailing slash)* |
   | `TELEGRAM_GATEWAY_INTERNAL_API_KEY` | **the exact same value** as the backend's `INTERNAL_SERVICE_API_KEY` |
   | `TELEGRAM_GATEWAY_REDIS_URL` | the `hrms-gateway-redis` Upstash URL |
   | `TELEGRAM_GATEWAY_HRMS_API_TIMEOUT_SECONDS` | `60` *(generous, to tolerate the backend cold-starting — see Phase 9)* |
   | `TELEGRAM_GATEWAY_ENVIRONMENT` | `production` |
   | `PORT` | `8080` |

4. Create. Once deployed, note this service's URL too, e.g. `https://hrms-gateway-xxxx.onrender.com`.
5. Sanity check: `curl https://hrms-gateway-xxxx.onrender.com/healthz` should return a 200.

## Phase 7 — Register the Telegram webhook

Nothing in the repo does this automatically — one manual call:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://hrms-gateway-xxxx.onrender.com/webhook/telegram", "secret_token": "<TELEGRAM_GATEWAY_WEBHOOK_SECRET_TOKEN>"}'
```

Expect `{"ok":true,"result":true,"description":"Webhook was set"}`. Verify any time with:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

## Phase 8 — Create a demo Employee and link Telegram

1. Log in as the seeded Admin:
   ```bash
   curl -X POST https://hrms-backend-xxxx.onrender.com/api/v1/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email":"<DEMO_ADMIN_EMAIL>","password":"<DEMO_ADMIN_PASSWORD>"}'
   ```
   Copy `access_token` from the response.
2. Create an Employee record for yourself (using the department `id` you copied in Phase 5, step 5):
   ```bash
   curl -X POST https://hrms-backend-xxxx.onrender.com/api/v1/employees/ \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{"first_name":"Shahid","last_name":"Nazir","work_email":"shahidnazirmhd@gmail.com","department_id":"<department uuid>","job_title":"Engineer","employment_type":"FULL_TIME","date_of_joining":"2026-07-24"}'
   ```
   The response includes an `employee_code` like `EMP-000001` — that's what you send to the bot next.
3. In Telegram, open a chat with your bot, send `/start`, then `/link EMP-000001` (your actual code).
4. The bot replies that it emailed an OTP to your `work_email`. Since `SMTP_HOST` is blank, it won't actually arrive by email — instead, open the **backend service's Logs** tab on Render and look for the OTP code in the log line for that request. Send that code back to the bot to finish linking.
5. Try the demo commands: `/leave_types`, `/leave_balance`, `/apply_leave` (the full calendar-picker flow), `/leave_history`.

## Phase 9 — Right before the actual call with your manager

Both Render free services spin down after 15 minutes idle and take 30-60 seconds to wake on the next request. A minute or two before the call:

```bash
curl https://hrms-backend-xxxx.onrender.com/health/
curl https://hrms-gateway-xxxx.onrender.com/healthz
```

This wakes both up so the first thing your manager does isn't a 30-second stall. If the call runs long and things go idle again mid-demo, the same delay can recur on the next tap/message — just mention it's a free-tier trait, not a bug, if it comes up.

## What to actually show

- **Postman**: import `United_HRMS.postman_collection.json`, point its base-URL variable at `https://hrms-backend-xxxx.onrender.com`, log in, run a few requests live.
- **Telegram**: your manager can message the bot directly (share the bot's `@username`), or you drive it live — `/apply_leave` end-to-end is the best "wow" moment (the inline calendar, the From/To indicator, cancel/history).

## Teardown (after 2-3 days)

1. Telegram: `curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook"` (stops Telegram from trying to reach a URL you're about to delete).
2. Render: delete both web services and the Postgres database (each has a "Delete" option in its Settings tab).
3. Upstash: delete both Redis databases.
4. Optional repo cleanup — none of this is required (nothing here affects local dev or the real prod compose file), but if you'd rather not carry deploy-only files around: `infra/docker/backend.render.Dockerfile` and `backend/apps/identity/management/commands/seed_demo_data.py` can be deleted (or just left — say the word if you want me to remove them once you're done demoing).

## Troubleshooting

- **Backend redirect-loops (`ERR_TOO_MANY_REDIRECTS`)**: shouldn't happen — this is exactly what the `SECURE_PROXY_SSL_HEADER` fix (see "What we're deploying, and why this shape" above) prevents. If you see it anyway, double check `DJANGO_SETTINGS_MODULE=config.settings.production` is actually set.
- **`ImproperlyConfigured: ALLOWED_HOSTS must be explicitly set`**: you haven't done Phase 5 step 4 yet, or set it to `*`.
- **Gateway can't reach backend / timeouts**: check `TELEGRAM_GATEWAY_HRMS_API_BASE_URL` has no trailing slash and matches the backend's real onrender.com URL, and that both `INTERNAL_SERVICE_API_KEY`/`TELEGRAM_GATEWAY_INTERNAL_API_KEY` match exactly.
- **`setWebhook` succeeds but bot never responds**: check the gateway's Logs tab for `invalid_webhook_secret` type errors (secret token mismatch) or connection errors reaching Upstash.
