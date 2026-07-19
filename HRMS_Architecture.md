# United HRMS — Enterprise Architecture

Backend: Django 5 + DRF · PostgreSQL · Redis · Celery
Frontend: React + TypeScript + Vite + Tailwind + shadcn/ui
Clients: Web App, Telegram Bot
Principles: Clean Architecture, Domain-Driven Design, SOLID, Repository Pattern, Open/Closed

---

## 1. Overall Architecture

### 1.1 The core decision: Backend as a Platform, not an App

The single most important architectural decision here is that **Django is not "the app" — it is one interface layer sitting on top of a framework-independent domain core.** Everything else in this document follows from that decision.

The reason is in the requirements themselves: "Telegram is NOT part of HR. Telegram is only another client." If business logic lived inside Django views, or worse, inside DRF serializers, the Telegram bot would have no legal way to reuse it — it would either duplicate the logic (violating DRY and creating drift risk between two implementations of "can this employee request leave") or it would be forced to call the same HTTP API a browser calls, which is fine for reads but awkward and slow for anything requiring rich validation error handling in a chat UI. Clean Architecture solves this by making both problems moot: the domain logic lives in a layer neither Django nor Telegram owns, and *both* clients consume it through a stable boundary — REST for the web frontend, REST for Telegram too (see §7), but with a Telegram-specific adapter converting HR domain results into chat message envelopes.

### 1.2 Layering (Clean Architecture, applied per-module)

Each business module (Employee, Leave, Attendance, Payroll, Performance, Recruitment, Approval, Notification) is a **bounded context** in the DDD sense, and each is internally structured in four concentric layers, dependencies always pointing inward:

**Domain layer (innermost, zero framework dependencies).** Entities, value objects, domain events, domain services, and repository *interfaces* (abstract base classes / Protocols) live here. This layer imports nothing from Django, DRF, Celery, or any third-party package except the Python standard library and perhaps a validation library. This is what makes the business logic testable without a database and portable if, five years from now, the framework changes.

**Application layer (use cases).** Orchestrates domain objects to fulfill a use case: `SubmitLeaveRequestUseCase`, `ApprovePayrollRunUseCase`. This layer depends on domain interfaces, never on concrete Django ORM models. It is where transactions are coordinated and where domain events get dispatched (e.g., "LeaveApproved" triggers a notification, without the leave module knowing anything about Telegram or email).

**Infrastructure layer.** Concrete implementations: Django ORM models, repository implementations that satisfy the domain's repository interfaces, Celery task definitions, Redis cache adapters, external API clients. This is where Django actually gets used. Because the domain and application layers only ever talk to *interfaces*, the ORM could be swapped for something else without touching business logic — that's the Open/Closed Principle at the architecture level, not just the class level.

**Interface layer (outermost).** Django views/DRF viewsets, serializers, URL routing, and the Telegram Gateway's command handlers. This layer's only job is protocol translation: HTTP request in, use case call, HTTP response out. **No decision-making happens here.** A view is not permitted to contain an `if` statement that changes business outcome — that's the "never mix business logic into Django Views" rule from the project's standing instructions, enforced structurally rather than by convention.

### 1.3 Why DDD on top of Clean Architecture, and not just Clean Architecture alone

Clean Architecture tells you *how to layer* a module. DDD tells you *where module boundaries go* and *what a module is allowed to know about another module*. Without DDD discipline, "Clean Architecture per module" degenerates into eight copies of the same four folders with no rule about how Payroll is allowed to ask Attendance "how many hours did this employee work this month" without Payroll reaching into Attendance's database tables directly.

The rule adopted here: **modules communicate only through each other's public application-layer interfaces (in-process) or domain events — never through direct ORM access across module boundaries, and never through shared database tables.** Concretely, if Payroll needs attendance data, it depends on an `AttendanceQueryService` interface that the Attendance module publishes and implements; Payroll never imports `attendance.models`. This is the practical meaning of "every module must be independent" from the project spec — independence isn't physical (separate repos/services), it's a dependency-direction and data-ownership discipline within a single deployable.

### 1.4 Modular monolith, not microservices — and why

Given eight modules, Telegram, Celery, and "enterprise" in the brief, it's tempting to reach for microservices. That would be the wrong call at this stage, for three concrete reasons:

First, HR data is deeply relational and transactional — leave balances affect payroll, attendance affects leave accrual, approvals cut across modules. Splitting these into separate databases now means implementing distributed transactions or eventual consistency for problems that a single PostgreSQL instance with proper module boundaries solves for free.

Second, a modular monolith enforced by the layering rules above gives almost all the benefit people want from microservices — independent, testable, swappable modules — without the operational cost of running eight services, eight deployment pipelines, and a service mesh, none of which this team currently needs.

Third, and most importantly, **this architecture doesn't foreclose microservices later.** Because each module's application layer is the only door in, and cross-module calls go through explicit interfaces rather than shared ORM state, a module that later needs independent scaling (Payroll during month-end runs, for example) can be extracted into its own service by replacing its in-process interface implementation with an HTTP or message-queue client — a mechanical refactor, not a rewrite. This is the Open/Closed Principle applied at the system level: open for extension into a distributed system, closed against needing to modify the modules themselves to get there.

### 1.5 High-level component view

```
                         ┌─────────────────────┐
                         │   React + TS SPA     │
                         │ (Vite, Tailwind,     │
                         │  shadcn/ui)           │
                         └──────────┬───────────┘
                                    │ HTTPS / REST + JWT
                                    │
        ┌───────────────────┐      │      ┌────────────────────────┐
        │  Telegram Bot API  │      │      │   Nginx / API Gateway   │
        └─────────┬──────────┘      │      │  (TLS, rate limiting)  │
                  │ webhook          │      └───────────┬────────────┘
                  ▼                  ▼                   ▼
        ┌────────────────────┐            ┌──────────────────────────────┐
        │  Telegram Gateway    │  REST +   │        Django 5 + DRF          │
        │  Service (own        │  JWT      │  (interface → application →   │
        │  container, stateless)├──────────►│   domain → infrastructure)    │
        │  NO DB ACCESS         │           │                                │
        └────────────────────┘            └───────┬─────────────┬──────────┘
                                                     │             │
                                          ┌──────────▼───┐   ┌─────▼─────┐
                                          │  PostgreSQL   │   │   Redis    │
                                          │ (system of     │   │ (cache,   │
                                          │  record)       │   │  broker,  │
                                          └────────────────┘   │  sessions)│
                                                                └─────┬─────┘
                                                                      │
                                                            ┌─────────▼──────────┐
                                                            │  Celery Workers      │
                                                            │  (payroll runs,      │
                                                            │  notifications,      │
                                                            │  scheduled jobs)     │
                                                            └──────────────────────┘
```

The critical line in that diagram is that the Telegram Gateway has **no arrow to PostgreSQL.** It only ever talks to the Django REST API. **Superseded by the Employee & Telegram Authentication refactor:** this section originally described the Gateway obtaining a JWT via a delegated-user flow, the same mechanism the web frontend uses. That design was replaced — employees linked via Telegram are never issued a `User` account or a JWT at all (Identity authentication is HR-staff-only); the Gateway instead authenticates *itself* to the backend with a single static shared secret (`X-Internal-Service-Key`), and identifies *which* employee a call is about via `telegram_user_id`, not a credential. See §7 and `TELEGRAM_GATEWAY.md`/`EMPLOYEE_API.md` for the current design. The "no arrow to PostgreSQL" enforcement itself is unaffected.

---

## 2. Folder Structure

A monorepo is used here deliberately: one repository, three deployables (Django backend, React frontend, Telegram Gateway), because at this scale a monorepo keeps API contract changes atomic (backend and frontend types can be reviewed in the same PR) while the layering rules above still keep the three deployables independently releasable in principle.

```
united-hrms/
├── backend/
│   ├── config/                        # Django project (settings, root urls, wsgi/asgi, celery.py)
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   │   ├── staging.py
│   │   │   └── production.py
│   │   ├── celery.py
│   │   └── urls.py
│   │
│   ├── apps/                          # one package per bounded context / module
│   │   ├── employees/
│   │   ├── leave/
│   │   ├── attendance/
│   │   ├── payroll/
│   │   ├── performance/
│   │   ├── recruitment/
│   │   ├── approvals/
│   │   ├── notifications/
│   │   └── identity/                  # auth, JWT issuance, RBAC — supports all modules
│   │
│   ├── platform/                      # cross-cutting, framework-adjacent shared code
│   │   ├── domain/                    # shared value objects (Money, DateRange), base Entity
│   │   ├── application/               # base UseCase, UnitOfWork interface, event bus interface
│   │   ├── infrastructure/            # Django UnitOfWork impl, Redis cache client, event bus impl
│   │   └── api/                       # base viewset, standard pagination, error envelope, permissions
│   │
│   ├── tests/
│   │   ├── unit/                      # domain + application, no DB, no Django test runner needed
│   │   ├── integration/               # repository implementations against real Postgres (test DB)
│   │   └── e2e/                       # full API flow tests
│   │
│   ├── manage.py
│   ├── pyproject.toml
│   └── requirements/
│       ├── base.txt
│       ├── local.txt
│       └── production.txt
│
├── frontend/
│   ├── src/
│   │   ├── modules/                   # mirrors backend modules: employees/, leave/, payroll/...
│   │   │   └── leave/
│   │   │       ├── api/               # typed API client calls for this module only
│   │   │       ├── components/
│   │   │       ├── hooks/
│   │   │       └── pages/
│   │   ├── shared/
│   │   │   ├── components/ui/         # shadcn/ui primitives
│   │   │   ├── lib/                   # api client, query client, auth token handling
│   │   │   └── types/                 # generated API types (see §6)
│   │   ├── app/                       # routing, layout, providers
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
│
├── telegram_gateway/
│   ├── src/
│   │   ├── handlers/                  # one file per command/conversation flow
│   │   ├── api_client/                # typed client for the Django REST API — the ONLY data access
│   │   ├── formatting/                # domain-result → chat-message adapters
│   │   ├── auth/                      # account linking, token storage (not business data)
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile
│   │   ├── frontend.Dockerfile
│   │   ├── telegram.Dockerfile
│   │   └── nginx/
│   ├── docker-compose.yml             # local dev: postgres, redis, backend, celery, frontend, telegram
│   ├── docker-compose.prod.yml
│   └── k8s/                           # manifests/helm chart, added when scale requires it (§8)
│
├── docs/
│   └── architecture/                  # this document and future ADRs
│
└── .github/workflows/                 # CI: lint, type-check, test, build images
```

Two things worth calling out. The `platform/` package in the backend exists because pure Clean Architecture per-module would otherwise force each of the eight modules to reinvent its own Unit of Work and event bus — that would violate DRY without buying any independence, since these are technical concerns, not business ones, and every module needs a consistent transaction boundary and a consistent way to publish/subscribe to domain events. The `apps/identity/` module is deliberately separated from `apps/employees/` even though they seem related: authentication/authorization (who can log in, what roles they hold) is a distinct bounded context from employee HR records (who they report to, their salary band), and conflating them is a common source of accidental coupling in HR systems.

---

## 3. Module Structure

Every module under `backend/apps/<module>/` follows the identical internal skeleton — this consistency is itself a design decision: a new engineer who understands one module's layout understands all eight, and it makes the Open/Closed boundary between modules mechanically verifiable in code review (imports crossing from one module's `infrastructure/` into another module's `infrastructure/` are an automatic red flag).

```
apps/leave/
├── domain/
│   ├── entities.py            # LeaveRequest, LeaveBalance — plain Python classes, no Django
│   ├── value_objects.py       # DateRange, LeaveType
│   ├── events.py              # LeaveRequested, LeaveApproved, LeaveRejected
│   ├── exceptions.py          # InsufficientLeaveBalance, OverlappingLeaveRequest
│   └── repositories.py        # abstract LeaveRepository (Protocol/ABC) — interface only
│
├── application/
│   ├── use_cases/
│   │   ├── submit_leave_request.py
│   │   ├── approve_leave_request.py
│   │   └── get_leave_balance.py
│   ├── dtos.py                 # input/output data structures for use cases
│   └── ports.py                 # interfaces this module needs FROM others
│                                 # e.g. AttendanceQueryPort, EmployeeQueryPort — implemented
│                                 # by adapters in infrastructure/, backed by other modules' APIs
│
├── infrastructure/
│   ├── models.py                # Django ORM models (persistence detail, not the domain entity)
│   ├── repositories.py          # DjangoLeaveRepository implementing domain.repositories.LeaveRepository
│   ├── adapters.py              # implementations of application/ports.py, calling into other
│   │                             # modules' public application services (in-process function calls)
│   ├── tasks.py                  # Celery tasks (e.g. accrue_monthly_leave)
│   └── migrations/
│
├── interface/
│   ├── serializers.py           # DRF serializers — translate DTOs <-> JSON, no logic
│   ├── viewsets.py               # thin: parse request -> call use case -> serialize response
│   ├── permissions.py            # DRF permission classes for this module
│   └── urls.py
│
└── tests/
    ├── unit/                     # domain + application, mocked repositories
    └── integration/
```

The reason `models.py` (infrastructure) is separate from `entities.py` (domain) rather than using Django models directly as the domain entities — the common shortcut in most Django projects — deserves explanation, since it's the single biggest deviation from typical Django practice in this whole design. A Django Model is inescapably coupled to the ORM, to `save()`, to `Meta`, to query managers; using it as a domain entity means the domain layer *is* Django, and Clean Architecture stops being real, it's just folder names. Keeping them separate costs a mapping step (repository implementations translate `LeaveRequestModel` ↔ `LeaveRequest` entity), but it buys the ability to unit-test approval logic, leave balance math, and payroll calculation rules with zero database, zero Django test runner, and sub-second test execution — which matters a great deal for a domain as rule-heavy as payroll and leave accrual, where correctness bugs are expensive and business rules change often (new leave policies, new tax rules).

**Cross-module dependency rule, worked example.** Payroll needs to know how many overtime hours an employee logged. Payroll's `application/ports.py` declares `AttendanceQueryPort.get_overtime_hours(employee_id, period) -> Decimal`. Payroll's `infrastructure/adapters.py` implements that port by calling Attendance's public application-layer function `attendance.application.use_cases.get_overtime_hours.execute(...)` directly in-process (both modules run in the same Django process today). Payroll never imports `attendance.infrastructure.models`. If Attendance is later extracted to its own service, only the adapter changes — from a direct function call to an HTTP client call — and nothing in Payroll's domain or application layer is touched. That is SOLID's Dependency Inversion Principle and the Open/Closed Principle working together at module-boundary scale, not just class scale.

**The Notification and Approval modules are special-cased slightly**, because they are inherently cross-cutting. Approval implements a generic, reusable approval-chain engine (works for leave, expense claims, recruitment offers) driven by domain events rather than being called directly — Leave publishes `LeaveRequested`, Approval subscribes and drives the workflow, then publishes `ApprovalGranted`/`ApprovalRejected`, which Leave subscribes to in turn to finalize state. This event-driven coupling (rather than direct calls) is intentional: it means adding a ninth module with its own approval need requires zero changes to the Approval module — pure Open/Closed. Notification works the same way: every module publishes domain events: it never calls Notification directly. Notification's own infrastructure decides whether an event becomes an email, a push notification, or a Telegram message, keeping the "how do we notify" concern entirely out of the eight business modules.

---

## 4. Communication Diagram

Three request flows illustrate how the pieces talk to each other and why the rules in §1 and §7 exist.

**A. Web frontend reads/writes HR data.**
`React SPA → HTTPS/JSON+JWT → Nginx (TLS, rate limit) → DRF viewset (interface layer) → use case (application layer) → domain entity + repository interface → Django ORM repository impl (infrastructure) → PostgreSQL.` Response is serialized back through the same chain. Redis is consulted by the application layer for cacheable reads (e.g., org chart, leave policy lookup) before hitting Postgres.

**B. Telegram user requests leave balance.**
`Telegram user → Telegram Bot API webhook → Telegram Gateway service (interface only, stateless) → same DRF REST endpoint the web frontend uses, authenticated as that user via a linked JWT → ... same chain as A ... → response → Gateway formats JSON into a chat message → sent back via Bot API.` The Gateway is architecturally just a second frontend: it does not get a shortcut into the domain layer or the database. This is what makes "Telegram is only another client" true in practice, not just in a diagram's intent.

**C. Payroll run (asynchronous, long-running).**
`HR admin triggers "Run Payroll" → DRF viewset → use case validates request → enqueues Celery task via `platform/infrastructure` task dispatcher → returns 202 Accepted with a job id immediately → Celery worker picks up task → executes PayrollRunUseCase (same application layer code path, called from infrastructure instead of interface) → writes results via repository → publishes `PayrollRunCompleted` domain event → Notification module reacts → pushes completion messages via web (websocket/poll) and Telegram.` Note the use case is invoked identically whether triggered synchronously from a view or asynchronously from a Celery task — this only works because the application layer never assumes it's running inside an HTTP request/response cycle, another payoff of the layering discipline.

---

## 5. Database Design Strategy

**Single PostgreSQL instance, module-owned schemas, no cross-module foreign keys at the database level.** Each module gets its own Postgres schema (`leave.*`, `payroll.*`, `attendance.*`) inside one database. This is the database-level enforcement of module independence: Postgres will physically reject a query that tries to join `payroll.payslip` directly to `attendance.timesheet` with a raw FK, forcing that relationship through application code (the port/adapter pattern from §3) instead of an implicit database join. It costs a small amount of query convenience; it buys a hard guarantee that "module independence" isn't just a code-review convention that erodes over time — the schema boundary makes violations fail at migration time.

Where a genuine reference across modules is unavoidable (e.g., every module's tables need to reference "employee"), the referenced id is stored as a **plain UUID column, not a database foreign key**, and referential integrity for that link is enforced in application code (the referencing module resolves the employee through `EmployeeQueryPort`, not through joins). UUIDs rather than auto-increment integers are used for all primary keys system-wide specifically because they are safe to generate client-side or in Celery workers without a round trip to get a value from the database, and because they don't leak sequential business volume (e.g., "how many employees does this company have") through the API, which matters once Payroll and Recruitment data start being exposed via API to a Telegram bot.

**Migrations are owned per-app** (Django's default `apps/<module>/infrastructure/migrations/`), applied together in one deploy, but tracked and reviewable independently — this again mirrors the eventual-extraction path: a module extracted to its own service takes its migration history with it cleanly.

**Auditability.** HR and payroll data is compliance-sensitive by nature (who approved this leave, who changed this salary, when). Rather than bolting on an audit log later, every module's core aggregate root (LeaveRequest, Payslip, PerformanceReview) carries `created_at`, `created_by`, `updated_at`, `updated_by`, and state transitions are captured as immutable domain events persisted in an `event_log` table per module (event sourcing lite — not full event sourcing, since that's more complexity than this system needs, but persisted events give a genuine audit trail and enable the Notification module's subscription mechanism from §3 for free).

**Read/write split, prepared for but not built on day one.** The application layer's repository interfaces make no assumption about a single database connection, which means read replicas can be introduced later (heavy Payroll reporting queries routed to a replica) purely as an infrastructure-layer change — repository implementations pick a connection based on read vs. write — without touching use cases.

**Soft deletes over hard deletes** for HR records specifically (`is_active` / `terminated_at` rather than row deletion), because HR and payroll data typically has statutory retention requirements (tax records, dispute evidence) that hard deletion would violate; this is enforced by a shared base model in `platform/infrastructure`.

---

## 6. API Strategy

**REST, versioned from day one (`/api/v1/...`), because there are already two clients (web, Telegram) that cannot deploy in lockstep with backend changes** — a Telegram Gateway container and a React build are independently deployable artifacts per §2, so an unversioned API would force synchronized releases across three deployables, defeating the purpose of separating them.

**Resource shape follows the module boundary, not the database schema.** Endpoints are named after the domain's ubiquitous language (`/api/v1/leave/requests/`, `/api/v1/payroll/runs/{id}/payslips/`) rather than mirroring table names, and the JSON returned is built from application-layer DTOs, not directly from ORM serialization — this is what stops a database schema change from becoming an uncontrolled API breaking change, and what stops "no business logic in views" from being violated by smuggling logic into a serializer's `to_representation`.

**DRF viewsets are intentionally thin** — each action does exactly three things: deserialize the request into a use case's input DTO, call the use case, serialize the result. Validation that is purely about shape (is this a valid date, is this field required) belongs in the DRF serializer; validation that is a business rule (can this employee request more leave than their balance) belongs in the domain/application layer and is surfaced back through a domain exception that the interface layer translates into a structured 4xx error — never the other way around. This split is what makes "never mix business logic into Django Views" enforceable rather than aspirational.

**Standard error envelope and pagination**, defined once in `platform/api/`, used by every module — this is the DRY counterpart to the module independence rule: cross-cutting *technical* concerns are shared, cross-cutting *business* concerns are not.

**Authentication: JWT (access + refresh), via `djangorestframework-simplejwt` or equivalent, issued by `apps/identity/`.** Access tokens are short-lived (e.g., 15 minutes) and carry role/permission claims; refresh tokens are longer-lived and rotated on use. This is the auth mechanism for the web frontend and any other HR-staff-facing client. **The Telegram Gateway does not use it** (superseded — see §7): employees reached via Telegram never hold a JWT, since Identity only ever authenticates HR staff/administrators/managers, not individual employees self-serving through the bot.

**API contract sharing with the frontend.** The DRF API schema is exported (drf-spectacular or similar, OpenAPI 3) and TypeScript types are generated from it into `frontend/src/shared/types/` as a build step — this removes an entire class of frontend/backend drift bugs and is cheap given the monorepo layout from §2.

**Open/Closed at the API level:** new modules or new actions are added as new endpoints under a module's own URL namespace; existing endpoints are not modified to add unrelated behavior. Versioning (`v2`) is the escape hatch for genuine breaking changes, used sparingly.

---

## 7. Telegram Gateway Strategy

This is where "Telegram is NOT part of HR. Telegram is only another client" gets its sharpest architectural treatment, because it's the constraint most tempting to violate for convenience (it would genuinely be *faster* to let the bot read straight from Postgres for a simple balance check) and the one most costly to violate later (any direct DB access from the gateway becomes a second, undocumented consumer of the schema that blocks future refactors).

**The Telegram Gateway is its own deployable, own container, own codebase directory (`telegram_gateway/`), with exactly one outbound data dependency: the Django REST API.** It holds no ORM, no database driver, no Postgres credentials at all — this isn't just policy, it's enforced by simply never installing `psycopg`/Django in that container's dependencies, so a violation would fail to even import, not just fail code review.

**Employee linking, not an identity system at all.** A Telegram user links their Telegram account to their existing `Employee` record once (via a one-time OTP emailed to every address the employee has on file — `work_email` always, plus `personal_email` too if set — confirmed in the bot), after which the backend stores the Telegram user id directly on that `Employee` row — there is no JWT, no refresh token, and nothing for the Gateway to store per employee at all (superseded the original "Gateway holds an encrypted refresh token" design). Every subsequent request simply presents the same `telegram_user_id` again. The Gateway authenticates itself to the backend with one static shared secret (`X-Internal-Service-Key`, checked by `HasInternalServiceKey`), never a per-employee credential — see `TELEGRAM_GATEWAY.md`/`EMPLOYEE_API.md`. This deliberately does not extend RBAC to Telegram: an employee talking to the bot only ever sees their own record, never anyone else's, so there is no role/permission decision to make at this boundary the way there is for the web app's HR-staff users.

**Webhook over long polling** for the production bot (Telegram calls the Gateway's HTTPS endpoint on new messages) — lower latency, no wasted always-on polling connection, and it fits naturally behind the same Nginx/TLS termination as the rest of the system. Long polling is acceptable for local development only, where exposing a public webhook URL is inconvenient.

**Command/conversation handlers stay in the interface layer of the Gateway, mirroring DRF viewsets' thinness.** A `/leave balance` command handler parses the Telegram update, calls the leave-balance REST endpoint, and formats the JSON response into chat markup — it does not compute the balance itself. This means a bug fix or rule change in leave-balance calculation, made once in the Leave module's domain layer, is instantly correct for both the web app and Telegram with no Gateway code change — the entire reason this constraint exists in the first place.

**Rate limiting and abuse protection** for the Gateway-facing endpoints uses a dedicated throttle scope (`TelegramLinkRateThrottle`, IP/caller-based since there's no JWT subject to key on for this traffic) at the DRF throttling layer, plus Telegram's own per-chat flood limits and the Gateway's own soft per-chat rate limiter ahead of that. The internal-service-key check (§7, §9) is a separate control from rate limiting — it establishes *that* the caller is the Gateway, not how much traffic it's allowed to send.

**Async-heavy interactions (e.g., "generate my payslip PDF") go through the same Celery flow as the web app** (§4, flow C): the Gateway calls the same "start job" endpoint, gets a job id, and either polls a status endpoint or (preferably) is notified via the Notification module's event subscription once the job completes, then pushes the result proactively into the chat — no logic differs from how a web client would be asked to handle the same long-running operation.

---

## 8. Scaling Strategy

**Django/DRF is stateless and horizontally scaled behind a load balancer** — sessions live in Redis, not in-process memory, and JWT auth means no server-side session affinity is needed at all, so any number of backend replicas can serve any request. This is a direct payoff of choosing JWT over session-cookie auth in §6.

**Celery workers are split into dedicated queues by workload shape, not one shared pool**: a `default` queue for fast, latency-sensitive tasks (single notification sends), a `payroll` queue with fewer, higher-memory workers for month-end payroll runs, and a `reports` queue for long-running exports — because a single undifferentiated worker pool means a slow payroll run blocks a time-sensitive "leave approved" notification from being sent, which is a real user-facing regression in an HR tool people check daily. Queue routing is a Celery configuration concern, entirely in `infrastructure/`, invisible to the application layer.

**Redis serves three distinct roles — cache, Celery broker/result backend, and session/token blocklist — and is scaled/monitored as such**, potentially split into separate logical databases or even separate Redis instances if contention appears between, say, cache eviction pressure and broker throughput during a payroll run. Because each role is accessed through its own adapter in `platform/infrastructure`, splitting them physically later is a configuration change, not a code change.

**PostgreSQL scaling path**: vertical scaling and connection pooling (PgBouncer) first, since HR system load is bursty (month-end payroll, annual review cycles) rather than constantly high; read replicas next for reporting/analytics load specifically, routed at the repository layer as noted in §5; only if a specific module's write load genuinely outgrows a shared instance (Attendance, if biometric-device check-ins scale into the millions/day, is the most likely candidate) does that module's schema get extracted into its own database — which the schema-per-module boundary from §5 makes mechanically straightforward.

**The modular monolith → service extraction path is the long-term scaling strategy**, not a rewrite: because module boundaries are already enforced by schema separation (Postgres) and port/adapter interfaces (application layer), any single module that needs independent scaling, independent deployment cadence, or a different tech stack (Payroll's tax-calculation engine might eventually warrant this) is extracted by replacing its in-process adapter with a network client, standing up its own container/deployment, and pointing its schema at its own database instance. This is explicitly why §1.4 rejected microservices *now* rather than rejecting them *permanently*.

**Frontend and static assets** are scaled trivially — the Vite build output is static and served via CDN/Nginx, entirely decoupled from backend scaling.

**Containerization**: `docker-compose` for local development (all services, one command) as already shown in §2; production moves to the same images orchestrated by Kubernetes (or ECS/equivalent) once replica counts and independent scaling per-service (web pods vs. Celery payroll-queue pods vs. Telegram Gateway pods, each scaled on its own metric) justify the added operational complexity over docker-compose. The Dockerfiles being defined per-deployable from day one (§2) means this transition doesn't require re-architecting the containers, only the orchestration layer around them.

---

## 9. Security Strategy

**Authentication and token strategy.** JWT access tokens (short-lived, ~15 min) plus rotating refresh tokens, issued only by `apps/identity/`, as established in §6 — for HR-staff-facing clients (the web app). Refresh tokens are stored server-side in a revocation-capable structure (Redis-backed denylist keyed by token id) so that "log out everywhere" is a real operation, not just client-side token deletion. **The Telegram Gateway is authenticated separately** (superseded — see §7): a single static shared secret (`X-Internal-Service-Key`) rather than a JWT, since employees reached via Telegram hold no token to revoke in the first place — "revoke a compromised Telegram-linked account" is instead just unlinking (`POST /telegram/unlink/`), which clears the stored `telegram_user_id`.

**Authorization: RBAC + object-level permissions, defined once, applied everywhere.** Roles (Employee, Manager, HR Admin, Payroll Admin, Recruiter) and permissions are modeled in `apps/identity/`, exposed as DRF permission classes reused by every module's viewset, and enforced identically regardless of client — the same permission check gates a payslip view whether the request came from the React app or the Telegram Gateway, because both go through the same viewset. Object-level checks (a manager can approve *their team's* leave, not anyone's) live in the application layer, not the permission class, since "is this the requester's manager" is a business rule, not a coarse role check.

**Least privilege for the Telegram Gateway specifically**: it holds no HR database credentials (§7) and no per-employee credential of any kind — its one shared secret (`X-Internal-Service-Key`) only proves "this caller is the Gateway," and every Gateway-facing endpoint still requires the caller to supply which employee it's asking about, scoped to that employee's own record only. The Gateway process itself has no elevated "service account" privilege beyond that single narrow permission class (`HasInternalServiceKey`), which is checked per-request like any other DRF permission — not a standing, unaudited trust relationship.

**Secrets management**: no secrets in source control or Docker images; environment-injected at deploy time via the platform's secret store (e.g., Docker/K8s secrets, or a dedicated vault in production), with `config/settings/production.py` reading exclusively from environment variables, never hardcoded values — `local.py`/`.env.example` are the only place example/dummy values appear.

**Data protection**: TLS termination at the edge (Nginx) for all three client-facing surfaces (web, API, Telegram webhook); PII and compensation data encrypted at rest at the database/volume level; payroll-specific fields (bank account numbers, tax IDs) additionally field-level encrypted in the Payroll module's infrastructure layer, since a database-level breach shouldn't trivially expose bank details even if it exposes names and emails.

**Auditability as a security control, not just compliance**: the per-module event log from §5 doubles as a security audit trail — who viewed/changed what, when, from which client — queryable independently of the operational tables.

**Rate limiting and input validation**: DRF throttling classes per endpoint class (stricter on auth endpoints and payroll actions than on read-only employee directory lookups), and all external input (from both the SPA and the Telegram Gateway) validated at the DRF serializer boundary before it ever reaches application-layer use cases — the use case layer trusts its DTOs are well-formed but never trusts them to be business-valid, which is re-checked by domain rules regardless of which client sent the request. This double validation (shape at the interface layer, rules at the domain layer) is deliberate defense in depth, not redundancy.

**Dependency and container hygiene**: pinned dependency versions, automated vulnerability scanning in CI (`.github/workflows/`), and minimal base images for each of the three Dockerfiles, particularly the Telegram Gateway's, since it is the most externally-exposed, least-trusted-input surface in the system (arbitrary user text from Telegram chat) and should have the smallest possible attack surface as a result.

---

## 10. Development Roadmap

The roadmap is sequenced to de-risk the architecture itself early — proving the layering and the Telegram-as-a-client constraint work end-to-end on one thin module before investing in all eight — rather than sequenced by business priority alone.

**Phase 0 — Foundations (infrastructure, no business features).**
Repository scaffolding per §2; `platform/` shared kernel (base entity, Unit of Work, event bus, base DRF viewset/error envelope); `docker-compose` local environment (Postgres, Redis, backend, Celery, frontend); CI pipeline (lint, type-check, test); `apps/identity/` with JWT issuance and role model. Exit criterion: an empty module can be scaffolded end-to-end and a "hello world" use case is callable from a DRF endpoint, from a test, and from a Celery task.

**Phase 1 — Employee module + one vertical slice through every layer, including Telegram.**
Build `apps/employees/` fully (domain through interface), then immediately build the thinnest possible Telegram Gateway feature against it (`/whoami` or `/profile` returning the employee's own record). This phase's real purpose is proving the Telegram-as-a-client constraint and the identity-linking flow (§7) work before Leave, Attendance, and Payroll — which all depend on Employee — are built on top of it. Exit criterion: a Telegram-linked user and a web-logged-in user get identical, correctly-authorized answers from the same backend code path.

**Phase 2 — Leave + Attendance + Approval.**
These three are sequenced together because Leave depends on Approval (event-driven, §3) and both Leave and Payroll (later) depend on Attendance data. Building the generic Approval engine here, driven by Leave as its first consumer, validates that it's genuinely generic before Recruitment and Payroll also lean on it in later phases. Telegram gets leave-balance and leave-request commands added here, again exercising the read *and* write path through the Gateway.

**Phase 3 — Payroll.**
The highest-risk module (compliance-sensitive, rule-heavy, depends on Attendance and Leave for inputs), deliberately scheduled after those dependencies are stable rather than in parallel with them. This is also where the Celery `payroll` queue, field-level encryption for bank/tax data (§9), and the async job pattern (§4 flow C, §7) get built out fully.

**Phase 4 — Performance + Recruitment.**
Lower-coupling modules (Recruitment in particular barely touches the others until an offer is accepted and a Recruitment→Employee handoff occurs) — scheduled later because they're lower risk to the core architecture and can absorb any process/timeline slippage from Phase 3 without blocking payroll, which is usually the business-critical path in a real HR rollout.

**Phase 5 — Notification hardening + reporting/read replicas + hardening pass.**
Notification exists in skeletal form from Phase 1 onward (every module already publishes events), but this phase builds out its full channel matrix (email, push, Telegram proactive messages) and adds the read-replica routing from §5 for reporting load, once real usage patterns are known rather than guessed upfront.

**Phase 6 — Production scaling cutover.**
Move from docker-compose to Kubernetes/orchestrated deployment (§8) only once real load data justifies it, with per-service scaling metrics defined per component (web pods, per-queue Celery pods, Telegram Gateway pods). This is deliberately last: premature Kubernetes adoption before there's real traffic to justify it would slow down Phases 1–5 for no benefit.

Each phase ends with the same exit gate: unit tests for the domain/application layers (no DB), integration tests for repositories (real Postgres), and an end-to-end test proving both the web API path and the Telegram path produce identical, correctly-authorized results for that phase's features — the roadmap's own verification step doubles as continuous proof that the "Telegram is only a client" and "no business logic in views" rules are holding, not just documented.
