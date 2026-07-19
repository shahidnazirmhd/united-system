# United HRMS — Complete Enterprise Folder Structure

This expands the folder structure sketched in `HRMS_Architecture.md` (§2–§3) into the full, concrete tree: all nine backend modules (the eight from `PROJECT_SPEC.md` plus `identity`), the full frontend module set, and the complete Telegram Gateway. No architectural decision from the previous document is changed — this is elaboration, not revision. One gap is filled in that the previous document left implicit (how new modules get wired into routing without touching existing ones); it's called out below as an addition, not a correction, since it doesn't contradict anything already decided.

No code is included, per your instruction — only directories, filenames, and what each is responsible for.

---

## 0. Before the tree: one addition, explained

The architecture doc established that modules must be addable "without modifying existing modules," but didn't specify how a new module's URLs, migrations, and Celery task routes get registered without editing `config/urls.py` by hand each time (which would technically mean touching a shared file, if not another module, every time a module is added). This isn't a flaw serious enough to require changing anything already decided — it's a missing implementation detail, so it's added here as `config/module_registry.py`: a single explicit list of active module names, which `config/urls.py`, Celery's autodiscovery, and Django's `INSTALLED_APPS` all read from. Adding a ninth module still means one line in one config file — unavoidable in Django, since apps must be registered somewhere — but zero lines in any *other module's* code. This preserves the Open/Closed guarantee at the only point where it was previously underspecified.

---

## 1. Backend Folder Structure

```
backend/
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── staging.py
│   │   ├── production.py
│   │   └── test.py
│   ├── module_registry.py
│   ├── celery.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── identity/
│   ├── employees/
│   ├── leave/
│   ├── attendance/
│   ├── payroll/
│   ├── performance/
│   ├── recruitment/
│   ├── approvals/
│   └── notifications/
│
├── platform/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── api/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── manage.py
├── pyproject.toml
└── requirements/
    ├── base.txt
    ├── local.txt
    └── production.txt
```

### 1.1 `config/`

The Django project shell — the only place in the backend allowed to know that *all* modules exist simultaneously. `settings/base.py` holds shared configuration; `local.py`, `staging.py`, `production.py` override per environment; `test.py` configures the fast in-memory/sqlite-free settings used by CI. `module_registry.py` is the single source of truth for which apps are active — `urls.py` iterates it to include each module's `interface/urls.py` under its namespace, and Celery's `celery.py` uses the same list for task autodiscovery, so a new module never requires touching Celery config either. `asgi.py`/`wsgi.py` are the standard Django entrypoints (ASGI kept available for future websocket use, e.g. live notification push, without a later migration).

### 1.2 `apps/` — the nine bounded contexts

Every module below shares the identical four-layer skeleton established in the architecture doc. Rather than repeat the same explanation nine times, the full breakdown is given once for `employees/`, and each subsequent module lists only what's specific to it — its domain concepts and its use cases — since the folder *purpose* at each layer is identical by design (that consistency is itself the point: a reviewer who understands one module's layout understands all nine).

#### `apps/identity/`

```
apps/identity/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── events.py
│   ├── exceptions.py
│   └── repositories.py
├── application/
│   ├── use_cases/
│   │   ├── authenticate_user.py
│   │   ├── issue_token_pair.py
│   │   ├── refresh_token.py
│   │   ├── revoke_token.py
│   │   ├── assign_role.py
│   │   └── link_telegram_account.py
│   ├── dtos.py
│   └── ports.py
├── infrastructure/
│   ├── models.py
│   ├── repositories.py
│   ├── jwt_service.py
│   ├── token_blocklist.py
│   ├── adapters.py
│   └── migrations/
├── interface/
│   ├── serializers.py
│   ├── viewsets.py
│   ├── permissions.py
│   └── urls.py
└── tests/
    ├── unit/
    └── integration/
```

`domain/entities.py` holds `User`, `Role`, `Permission` as plain Python classes — deliberately not Django's `AbstractUser`, since that would tie the domain model to Django's auth machinery. `value_objects.py` holds things like `Email` and `HashedPassword` that carry their own validation. `events.py` defines `UserAuthenticated`, `RoleAssigned`, `TokenRevoked`, `TelegramAccountLinked` — other modules never import identity's models directly; they react to these events or call its use cases. `repositories.py` declares the `UserRepository` interface only — no implementation.

`application/use_cases/` is one file per user-facing action; each is a single class with an `execute()` method taking a DTO and returning a DTO, so a viewset, a Celery task, and (later) a management command can all call the identical code path. `ports.py` is empty or near-empty for identity specifically, since identity is depended *on* by every other module rather than depending on them.

`infrastructure/jwt_service.py` and `token_blocklist.py` are called out separately from the generic `repositories.py`/`adapters.py` pair because token signing and revocation are identity-specific technical concerns, not generic persistence — keeping them named explicitly (rather than folded into a generic "services.py") makes them easy to find during a security review.

`interface/permissions.py` here is special: it defines the **base** RBAC permission classes (`IsAuthenticated`, `HasRole`, `HasPermission`) that every other module's own `interface/permissions.py` imports and composes with module-specific object-level rules. This is the one place identity's interface layer is deliberately imported by other modules — it's a stable, narrow contract (permission classes), not a backdoor into identity's data.

#### `apps/employees/`

Same four-layer skeleton. `domain/entities.py`: `Employee`, `Department`, `JobTitle`, `ReportingLine`. `application/use_cases/`: `onboard_employee.py`, `update_employee_profile.py`, `assign_manager.py`, `transfer_department.py`, `offboard_employee.py`, `get_employee_directory.py`. `application/ports.py` declares `EmployeeQueryPort` — the interface *other* modules (Leave, Payroll, Attendance) depend on to resolve "who is this employee, who is their manager" without importing Employee's models. This makes `employees/` the most-depended-upon module after `identity/`, which is expected — HR data naturally centers on the employee record — but the dependency only flows one direction, through this one published port.

#### `apps/leave/`

`domain/entities.py`: `LeaveRequest`, `LeaveBalance`, `LeavePolicy`. `application/use_cases/`: `submit_leave_request.py`, `approve_leave_request.py`, `reject_leave_request.py`, `cancel_leave_request.py`, `get_leave_balance.py`, `accrue_monthly_leave.py`. `application/ports.py` declares `EmployeeQueryPort` (consumed, implemented against `employees/`) and `ApprovalWorkflowPort` (consumed, implemented against `approvals/`). `infrastructure/tasks.py` holds the Celery task wrapping `accrue_monthly_leave` for scheduled execution.

#### `apps/attendance/`

`domain/entities.py`: `Timesheet`, `CheckInEvent`, `Shift`, `OvertimeRecord`. `application/use_cases/`: `record_check_in.py`, `record_check_out.py`, `get_monthly_timesheet.py`, `compute_overtime.py`. `application/ports.py` declares `AttendanceQueryPort` — this is the port *published outward* for Payroll to consume, so it lives here even though it's Payroll that depends on it (the convention: a port interface is declared in the module that *implements* the underlying data, and consumed via an adapter in the module that *needs* it — see the Payroll entry below).

#### `apps/payroll/`

The most rule-heavy module, per the architecture doc's own risk assessment. `domain/entities.py`: `Payslip`, `PayrollRun`, `SalaryStructure`, `TaxRule`, `Deduction`. `domain/value_objects.py` gets particular use here: `Money` (from `platform/domain/`, reused, not redefined), `TaxBracket`, `PayPeriod`. `application/use_cases/`: `run_payroll.py`, `generate_payslip.py`, `apply_tax_rules.py`, `approve_payroll_run.py`. `application/ports.py` declares `AttendanceQueryPort` and `EmployeeQueryPort` as *consumed* interfaces (implemented in `infrastructure/adapters.py` by calling into `attendance/` and `employees/` application layers). `infrastructure/tasks.py` holds the long-running `run_payroll` Celery task and routes it to the dedicated `payroll` queue described in the architecture doc's scaling strategy. `infrastructure/encryption.py` is added here specifically — not a shared pattern across modules — to field-level encrypt bank account and tax ID data at rest, per the security strategy.

#### `apps/performance/`

`domain/entities.py`: `PerformanceReview`, `Goal`, `Feedback`, `RatingScale`. `application/use_cases/`: `create_review_cycle.py`, `submit_self_assessment.py`, `submit_manager_review.py`, `finalize_review.py`. `application/ports.py` declares `EmployeeQueryPort` (consumed) and `ApprovalWorkflowPort` (consumed, if review finalization routes through the generic approval engine).

#### `apps/recruitment/`

`domain/entities.py`: `JobOpening`, `Candidate`, `Application`, `Offer`. `application/use_cases/`: `post_job_opening.py`, `submit_application.py`, `schedule_interview.py`, `extend_offer.py`, `convert_candidate_to_employee.py`. That last use case is the one deliberate seam into `employees/` — recruitment ends with a handoff, implemented via `EmployeeQueryPort`'s write-side counterpart or a dedicated `EmployeeOnboardingPort`, kept as narrow as the conversion event itself requires.

#### `apps/approvals/`

The generic, reusable engine referenced throughout the architecture doc. `domain/entities.py`: `ApprovalChain`, `ApprovalStep`, `ApprovalPolicy`, `ApprovalDecision` — deliberately modeled with no knowledge of "leave" or "payroll" as concepts; a chain just wraps a `subject_type`/`subject_id` pair. `application/use_cases/`: `start_approval_chain.py`, `record_decision.py`, `escalate_pending_approval.py`. This module has **no `ports.py` consuming other modules** — it's driven entirely by subscribing to domain events (`LeaveRequested`, review-finalization-requested, etc.) published by whichever module needs an approval, and it publishes `ApprovalGranted`/`ApprovalRejected` back out. `infrastructure/event_subscriptions.py` is the one infrastructure file unique to this module's shape — the explicit registry of which incoming events this module listens for, which is also where a new module's approval need gets wired in (one line here, again touching only `approvals/`'s own file, not the new module's).

#### `apps/notifications/`

`domain/entities.py`: `NotificationTemplate`, `NotificationLog`, `Channel`. `application/use_cases/`: `send_notification.py`, `render_template.py`. Structured identically to Approvals: driven by subscribing to domain events from every other module (`infrastructure/event_subscriptions.py` again), with `infrastructure/channels/` holding one adapter per delivery mechanism — `email_channel.py`, `push_channel.py`, `telegram_channel.py` (this last one calls the Telegram Bot API to *push* a message into an already-linked chat; it is not the Telegram Gateway and holds no inbound webhook logic — that distinction matters and is why it's a thin outbound adapter here rather than living in `telegram_gateway/`).

### 1.3 `platform/` — the shared kernel

```
platform/
├── domain/
│   ├── base_entity.py
│   ├── value_objects.py
│   └── domain_event.py
├── application/
│   ├── base_use_case.py
│   ├── unit_of_work.py
│   └── event_bus.py
├── infrastructure/
│   ├── django_unit_of_work.py
│   ├── redis_cache.py
│   ├── event_bus_impl.py
│   ├── celery_dispatcher.py
│   └── base_models.py
└── api/
    ├── base_viewset.py
    ├── error_envelope.py
    ├── pagination.py
    ├── exception_handler.py
    └── throttling.py
```

This is the one package every module is *allowed* to depend on (the exception to "modules don't import each other's internals"), because everything here is a technical concern, not a business one — no HR knowledge lives in `platform/`. `domain/base_entity.py` gives every module's entities a common identity/equality contract; `domain/value_objects.py` holds genuinely cross-module concepts like `Money` and `DateRange` so Payroll and Leave don't each invent their own. `application/unit_of_work.py` and `event_bus.py` are interfaces only, matching the same dependency-inversion pattern used everywhere else — their Django/Redis-backed implementations live in `infrastructure/`. `api/exception_handler.py` is what makes "no business logic in views" enforceable system-wide: it's the single place that maps a raised domain exception (e.g., `InsufficientLeaveBalance`) to a structured HTTP 4xx response, so no individual module's viewset ever writes its own `try/except` translating business errors into HTTP status codes.

### 1.4 `tests/`

Root-level tests are reserved for **cross-module** verification — the one place it's legitimate to exercise two modules together (e.g., "submitting a leave request actually reaches the Approval engine and a notification gets queued"). Per-module `unit/` and `integration/` tests (inside each `apps/<module>/tests/`) never test another module; anything that requires two modules working together belongs here instead, which keeps the module-internal test suites honest about not depending on each other.

### 1.5 `requirements/`

Split by environment for the same reason `settings/` is split — `production.txt` deliberately excludes dev tooling (debug toolbar, ipython) that would otherwise bloat the production image and expand its attack surface, tying back to the security strategy's container-hygiene point.

---

## 2. Frontend Folder Structure

```
frontend/
├── src/
│   ├── modules/
│   │   ├── identity/
│   │   ├── employees/
│   │   ├── leave/
│   │   ├── attendance/
│   │   ├── payroll/
│   │   ├── performance/
│   │   ├── recruitment/
│   │   ├── approvals/
│   │   └── notifications/
│   │
│   ├── shared/
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   └── layout/
│   │   ├── lib/
│   │   │   ├── api-client.ts
│   │   │   ├── auth/
│   │   │   └── query-client.ts
│   │   ├── types/
│   │   ├── hooks/
│   │   └── constants/
│   │
│   ├── app/
│   │   ├── routes.tsx
│   │   ├── providers.tsx
│   │   └── layout.tsx
│   │
│   ├── main.tsx
│   └── vite-env.d.ts
│
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

### 2.1 `modules/` — one folder per backend bounded context

The frontend mirrors the backend's module boundary on purpose: it makes "which backend module does this screen talk to" visually obvious, and it lets a frontend engineer working on Payroll never need to open the Leave folder. Each module folder (`modules/leave/` shown as the representative example) contains:

```
modules/leave/
├── api/
│   └── leaveApi.ts
├── components/
├── hooks/
│   ├── useLeaveBalance.ts
│   └── useSubmitLeaveRequest.ts
├── pages/
│   ├── LeaveRequestPage.tsx
│   └── LeaveHistoryPage.tsx
├── store/
└── types.ts
```

`api/` holds the module's typed HTTP call functions and nothing else — no components import `axios`/`fetch` directly, they only import from here, which is what makes swapping the HTTP client later a one-file change. `hooks/` wraps those API calls in TanStack Query hooks (`useQuery`/`useMutation`), which is the chosen **server-state** management approach — an HR app's client state is overwhelmingly "data that lives on the server and needs caching/revalidation," which is exactly what React Query is built for, rather than a heavier global store. `components/` holds presentation components used only within this module; anything reused by two or more modules gets promoted to `shared/components/`, never duplicated. `pages/` are route-level components composed from `components/` and `hooks/`. `store/` is intentionally sparse — used only for genuine client-only UI state local to the module (e.g., a multi-step leave request wizard's current step) via a small Zustand slice or `useReducer`; it does not duplicate server state that `hooks/` already owns, since caching the same data in two places is a bug generator. `types.ts` holds module-specific UI types that aren't part of the API contract (e.g., form state shapes), as distinct from the generated API types in `shared/types/`.

`modules/identity/` is the one module with a slightly different shape — it owns the login page, the Telegram-account-linking confirmation page, and the auth token refresh hook, but has no `store/` of its own since auth state (current user, token validity) is genuinely global and lives in `shared/lib/auth/` instead, described below.

### 2.2 `shared/`

`components/ui/` holds shadcn/ui primitives exactly as generated (button, dialog, table, etc.) — never hand-edited beyond shadcn's own customization mechanism, so upgrades stay clean. `components/layout/` holds the app shell — sidebar, header, navigation — which is where each module registers its nav entry (again, ideally via a small registry pattern analogous to the backend's `module_registry.py`, so adding a module's nav link doesn't mean editing a shared `Sidebar.tsx` switch statement by hand — flagged here as the frontend's equivalent of the same OCP gap addressed in §0).

`lib/api-client.ts` is the single configured HTTP client instance (base URL, JSON handling) that every module's `api/*.ts` file imports — this is the frontend's equivalent of the backend's `platform/`: a shared technical concern, not a business one. `lib/auth/` holds token storage and the refresh-token interceptor logic — the one genuinely global piece of client state in the app, deliberately kept out of any single module's `store/`. `lib/query-client.ts` configures the single TanStack Query client instance shared app-wide.

`types/` holds the OpenAPI-generated TypeScript types described in the architecture doc's API strategy — machine-generated, not hand-maintained, and imported by every module's `api/` layer to keep frontend and backend contracts from drifting apart silently. `hooks/` (top-level) holds genuinely generic hooks with no module affiliation (`useDebounce`, `useMediaQuery`); anything with business meaning belongs in a module's own `hooks/`, not here. `constants/` holds cross-cutting constants (date formats, role names) — not business rules, which stay server-side per the "no business logic outside the backend domain layer" principle extended to the frontend.

### 2.3 `app/`

`routes.tsx` aggregates each module's `pages/` into the router — the frontend's analogue of the backend's `config/urls.py` reading `module_registry.py`. `providers.tsx` wires up the query client, auth context, and theming providers once at the root. `layout.tsx` composes `shared/components/layout/` into the actual app shell.

---

## 3. Telegram Gateway Folder Structure

```
telegram_gateway/
├── src/
│   ├── webhook/
│   │   ├── server.py
│   │   ├── update_router.py
│   │   └── security.py
│   │
│   ├── telegram_client/
│   │   ├── bot_api_client.py
│   │   └── types.py
│   │
│   ├── api_client/
│   │   ├── hrms_client.py
│   │   └── endpoints/
│   │       ├── employees.py   # profile reads AND Telegram linking — both apps.employees
│   │       ├── leave.py
│   │       ├── attendance.py
│   │       ├── payroll.py
│   │       └── approvals.py
│   │
│   ├── auth/
│   │   └── account_linking.py   # "awaiting OTP" conversation state only — no token storage
│   │
│   ├── handlers/
│   │   ├── start_handler.py
│   │   ├── link_handler.py
│   │   ├── leave_handlers.py
│   │   ├── attendance_handlers.py
│   │   ├── payroll_handlers.py
│   │   ├── approvals_handlers.py
│   │   └── help_handler.py
│   │
│   ├── formatting/
│   │   ├── leave_formatter.py
│   │   ├── attendance_formatter.py
│   │   ├── payroll_formatter.py
│   │   └── common.py
│   │
│   ├── config.py
│   └── main.py
│
├── tests/
├── requirements.txt
└── Dockerfile
```

### 3.1 `webhook/`

`server.py` is the single HTTP entrypoint Telegram's servers call on every incoming message — the only inbound network surface this service exposes. `security.py` verifies Telegram's secret-token header on every request before anything else runs, rejecting forged webhook calls at the door. `update_router.py` inspects the parsed update (command text, or ongoing conversation state) and dispatches to the correct file in `handlers/` — this router is the Gateway's *only* piece of branching logic, and it branches purely on "which handler," never on business rules, matching the same thin-interface-layer discipline used in Django's viewsets.

### 3.2 `telegram_client/`

`bot_api_client.py` wraps outbound calls to the Telegram Bot API (send message, edit message, answer callback query) — it has no knowledge of HR data, it just knows how to talk to Telegram. `types.py` holds the shapes of Telegram's own update/message payloads, kept separate from `api_client/` (below) so Telegram's wire format and the HRMS's wire format are never confused with each other.

### 3.3 `api_client/` — the only path to HR data

This is the folder that makes "no database access from Telegram Gateway" true as a structural fact rather than a promise: it contains HTTP client code and nothing else — no ORM import is possible because none is a dependency of this service at all. `hrms_client.py` is the base HTTP client — it attaches one static shared secret (`X-Internal-Service-Key`) at construction, to every request, rather than a per-employee bearer JWT (Employee & Telegram Authentication refactor: employees using Telegram are never issued a JWT at all, so there is no per-employee token for this client to carry). `endpoints/` holds one file per backend module the Gateway actually needs to call — deliberately mirroring the backend's module names, so a handler for a leave command only ever imports `endpoints/leave.py`, keeping the Gateway's own internal structure aligned with the module boundary it's consuming, even though it has no modules of its own. `endpoints/employees.py` covers both profile reads and Telegram linking, since both are exclusively an `apps.employees` concern now.

### 3.4 `auth/`

`account_linking.py` implements the two-step linking flow (employee code, then OTP) and is the only file in this service holding any state of its own — a transient "awaiting OTP" flag per Telegram user, in this service's own Redis, TTL-matched to the backend's OTP lifetime. There is no token store and no session manager: the backend stores the Telegram user id directly on the `Employee` record, so there is nothing per-employee for this service to persist, encrypt, or refresh. Whether an account is linked is always asked of the backend fresh (`get_link_status`), never cached here.

### 3.5 `handlers/`

One file per command family, matching the backend module it talks to (`leave_handlers.py` calls only `api_client/endpoints/leave.py`, never another module's endpoint file) — this is the Gateway-side enforcement of the same "no cross-module reach-across" discipline the backend uses, applied to a service that has clients instead of modules. Each handler function does exactly what a DRF viewset action does: parse the incoming command/arguments, call the relevant `api_client` function, hand the JSON result to `formatting/`, send the formatted message back via `telegram_client`. No handler computes a leave balance, applies a tax rule, or makes any decision the backend hasn't already made — consistent with "no business logic in views," extended here to "no business logic in handlers."

### 3.6 `formatting/`

Pure functions translating HRMS API JSON responses into Telegram message text/markup (Markdown, inline keyboards). This is deliberately isolated from `handlers/` so the same formatter can be reused across multiple commands (e.g., a leave-request confirmation and a leave-history listing both use `leave_formatter.py`), and so a change in how leave data is *displayed* in chat never requires touching the handler logic that fetches it.

### 3.7 `config.py` / `main.py`

`config.py` holds environment-driven settings only (Telegram bot token, HRMS API base URL, webhook secret) — no HR configuration, since this service has no HR concerns to configure. `main.py` wires the webhook server, client instances, and handler registry together at process start.

---

## Summary of what stays consistent, and why it matters going forward

Every module, on both backend and frontend, follows the same internal shape, and the Telegram Gateway follows an analogous shape adapted to its role as a pure client. That repetition is deliberate: it means Phase 2 (Leave + Attendance + Approval, per the roadmap) is executed by copying a known-good skeleton nine times, not by re-deriving the pattern per module — and it means a code reviewer can check "did this PR add an import that crosses a module boundary it shouldn't" almost mechanically, since any such import will look structurally wrong against every other module in the tree.
