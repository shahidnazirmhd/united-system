# syntax=docker/dockerfile:1

# ---- Builder stage: compile dependencies into wheels, nothing else ----
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

# ---- Production stage: slim runtime image, no compiler/build tooling ----
FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# libpq5 (runtime client library) only — libpq-dev and build-essential from
# the builder stage never make it into this image.
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

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

# ---- Local stage: production image + test/lint/REPL tooling ----
# Used only by infra/docker-compose.yml (local dev) via `target: local` on
# the backend/celery_worker/celery_beat services — never by
# docker-compose.prod.yml, which pins `target: production` explicitly so a
# future reordering of these stages can't accidentally ship pytest/black/
# ruff into a production image (HRMS_Architecture.md section 9: minimal
# base images for internet-facing containers). This is what makes
# `docker compose -f infra/docker-compose.yml ... run --rm backend pytest`
# work — the production stage deliberately has no test tooling at all,
# since requirements/production.txt pulls only requirements/base.txt.
FROM production AS local

USER root

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/local.txt

USER appuser

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
