# syntax=docker/dockerfile:1
#
# Deploy-only Dockerfile for temporary cloud hosting (e.g. Render), NOT used
# by infra/docker-compose.yml or docker-compose.prod.yml — both of those
# keep using backend.Dockerfile exactly as before, unaffected by this file.
#
# Why this exists: backend.Dockerfile is multi-stage (builder -> production
# -> local), and docker-compose selects the stage it wants via `target:`.
# Render's Docker deploys don't support `docker build --target` (no such
# option in their dashboard or render.yaml as of this writing), so pointing
# Render straight at backend.Dockerfile would silently build its LAST stage
# — "local" — shipping test/lint tooling and running `manage.py runserver`
# instead of gunicorn. This file is just backend.Dockerfile's
# builder+production stages, verbatim, with nothing after the production
# CMD — so whatever Render builds by default (the only/last stage here) is
# exactly the same production image docker-compose.prod.yml's `target:
# production` already produces locally. Delete this file once the temporary
# deployment is torn down; it's not part of the app's normal build path.
#
# The one real behavioral difference from backend.Dockerfile: the CMD below
# runs `migrate` and the demo-only `seed_demo_data` command before starting
# gunicorn, every time the container boots. A real deployment would do this
# via a pre-deploy hook or a separate one-off shell command instead of
# baking it into the start command — but Render's free tier (this file's
# whole reason for existing) has neither shell/SSH access nor a pre-deploy
# command (both are paid-only there), so the container's own start command
# is the only code Render's free tier will actually run for us. Both
# `migrate` and `seed_demo_data` are idempotent, so re-running them on every
# restart/redeploy is safe, not just expedient.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements/ requirements/
RUN pip install --upgrade pip \
    && pip wheel --wheel-dir /wheels -r requirements/production.txt

FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements/ requirements/
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements/production.txt \
    && rm -rf /wheels

COPY . .

RUN mkdir -p /app/staticfiles && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Render (and most PaaS Docker hosts) default to routing traffic to
# whatever port their own PORT env var says — set PORT=8000 on this
# service in Render's dashboard to match the fixed port below.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo_data && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
