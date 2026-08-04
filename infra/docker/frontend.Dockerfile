# syntax=docker/dockerfile:1

# ---- deps stage: install node_modules once, reused by both the `local`
# (Vite dev server) and `build` (production bundle) stages below ----
FROM node:20-alpine AS deps

WORKDIR /app

# package-lock.json is committed — `npm ci` installs the exact locked
# tree, the same reproducibility guarantee backend.Dockerfile's
# `pip wheel -r requirements/production.txt` gives on the Python side.
COPY package.json package-lock.json ./
RUN npm ci

# ---- local stage: deps + full source, Vite's own dev server (HMR) ----
# Used only by infra/docker-compose.yml (local dev) via `target: local` —
# never docker-compose.prod.yml, mirroring backend.Dockerfile's
# local/production split for the same reason: dev tooling (Vite's dev
# server, unminified source, HMR websocket) has no business in a deployed
# image. docker-compose.yml bind-mounts ../frontend over the COPY below
# for live-reload editing; the COPY only makes `target: local` usable
# standalone (`docker run` with no compose, CI, etc.).
FROM deps AS local

COPY . .

EXPOSE 5173

# --host is required for the dev server to be reachable from outside the
# container — Vite's dev server binds to 127.0.0.1 only by default, which
# is unreachable through Docker's port mapping.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- build stage: compiles the production static bundle ----
FROM deps AS build

# Vite inlines every VITE_-prefixed variable into the compiled JS at BUILD
# time (see frontend/src/config/env.ts's docstring — it's read via
# `import.meta.env`, resolved by esbuild's define pass during `vite
# build`). Unlike the backend/gateway images, there is no runtime env_file
# for an already-compiled static bundle to read later, so these must
# arrive as build args instead. docker-compose.prod.yml supplies them from
# the root .env file's own "Frontend (production build args)" section.
ARG VITE_API_BASE_URL
ARG VITE_APP_NAME
ARG VITE_APP_ENV
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_NAME=${VITE_APP_NAME} \
    VITE_APP_ENV=${VITE_APP_ENV}

COPY . .
RUN npm run build

# ---- production stage: nginx serving the static bundle only ----
# Deliberately does not proxy /api/* to the backend — the frontend already
# talks to the backend directly via VITE_API_BASE_URL (browser-to-backend,
# same as local dev), so this container's only job is serving the compiled
# SPA. See nginx.conf's own docstring for why that file lives in this
# directory rather than infra/docker/nginx/.
FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
