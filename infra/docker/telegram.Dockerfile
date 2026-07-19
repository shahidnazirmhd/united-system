# syntax=docker/dockerfile:1
#
# Mirrors backend.Dockerfile's centralized-in-infra/docker/ convention
# (HRMS_Architecture.md section 2's approved top-level tree lists this file
# alongside backend.Dockerfile/frontend.Dockerfile) rather than living
# inside telegram_gateway/ itself.
#
# Minimal base image deliberately chosen: per HRMS_Architecture.md section 8,
# this service is "the most externally-exposed, least-trusted-input surface
# in the system (arbitrary user text from Telegram chat)" and should have
# the smallest possible attack surface as a result — no build tooling ships
# in the final image, and requirements.txt contains no ORM/database driver
# at all (see telegram_gateway/requirements.txt's own docstring).
FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system gateway && useradd --system --gid gateway --create-home gateway

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

USER gateway

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
