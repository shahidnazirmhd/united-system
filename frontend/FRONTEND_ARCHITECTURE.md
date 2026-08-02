# United HRMS Frontend — Architecture (Phase 10–11)

This document explains _why_ the foundation is structured the way it is,
and — most importantly — exactly how to add a new feature module on top of
it later without changing anything in this phase's code. Phase 11 (Login)
is the first real tenant of the pattern Section 6 describes — where this
document originally said "worked example," it's now also "worked, for
real."

## 1. Guiding principles

The backend (`../backend`) follows Clean Architecture, SOLID, and the
Repository Pattern strictly (see `../HRMS_Architecture.md`). A frontend SPA
doesn't have the same layers (no database, no repositories in the backend
sense), but the same underlying discipline translates directly:

- **Separation of concerns by layer, not by convenience.** `app/` (composition:
  providers, router, error handling) never contains presentation markup.
  `layouts/` never contains business logic or data fetching. `lib/api/`
  never renders anything. `components/ui/` never knows what an "Employee"
  or a "Leave request" is.
- **Dependency direction points inward, toward the reusable core.** A future
  feature module (`src/modules/leave`) is allowed to import from `lib/`,
  `components/`, `hooks/`, `types/` — but nothing in `lib/`, `components/`,
  `app/`, or `layouts/` is ever allowed to import from `src/modules/*`. This
  is the same Dependency Inversion rule the backend's application layer
  applies to its infrastructure layer, just pointed at "foundation vs.
  feature module" instead of "domain vs. framework." `src/lib/auth/`
  (Section 2) is the one deliberate case study in this rule: session state
  is a cross-cutting concern both `app/router`'s guards AND
  `src/modules/auth`'s login feature need, so it lives in the foundation
  layer both can depend on, rather than either depending on the other.
- **Open/Closed in practice, not just in principle.** Adding a new dashboard
  module means adding new files and a small number of one-line registrations
  (one route, one nav entry) — it never means editing `Sidebar.tsx`,
  `DashboardLayout.tsx`, `AppProviders.tsx`, or any config file. Section 6
  below shows this concretely.
- **Single Responsibility per file.** Every component in this foundation
  does exactly one job — `PageHeader` renders a header, `ThemeToggle` toggles
  a theme, `httpClient.ts` makes HTTP calls. None of them also validate
  input, format business data, or make decisions about routing.
- **No premature business logic.** This phase builds the shell, deliberately
  empty of anything Employee/Leave/Approval-specific — see `src/modules/README.md`.

## 2. Folder-by-folder rationale

### `src/app/` — the composition root

Nothing in the rest of the app should construct a `QueryClient`, a
`BrowserRouter`, or catch a top-level error itself — `app/providers`,
`app/router`, and `app/error` are the ONLY places that happens. `App.tsx`
composes exactly two things: `AppProviders` and `AppRouter`. This means:

- Adding a new cross-cutting concern (i18n, feature flags, an analytics
  provider) is a one-line addition to `AppProviders.tsx`'s nesting, never a
  change scattered across the app.
- The router (`app/router/routes.tsx`) is the single source of truth for
  what URL renders what — no component anywhere else decides routing.

### `src/layouts/` — three reusable shells, nothing else

Exactly the three the brief asked for:

- **`AuthLayout`** — centered card treatment for unauthenticated flows. Wraps
  `src/modules/auth`'s real `LoginPage` as of Phase 11; a future phase's
  forgot-password/OTP pages render inside it the same way, via the same
  `<Outlet />`. The layout itself still contains no auth logic — it's
  `app/router/PublicOnlyRoute.tsx` guarding the route, not the layout,
  deciding who gets to see it.
- **`DashboardLayout`** — the authenticated app shell: `Sidebar` (desktop,
  persistent) + a Sheet-based mobile equivalent, `Topbar`, and a scrollable
  content area. Every dashboard-module route nests under it.
- **`MinimalLayout`** — bare shell (brand mark + content) for standalone
  pages: 404, route-level errors, and any future maintenance/legal page.

None of the three contain business logic, data fetching, or knowledge of
which module is currently active — `Sidebar` renders whatever
`layouts/DashboardLayout/navigation.ts` tells it to, and nothing more.

### `src/components/ui/` vs `src/components/common/`

- **`ui/`** is shadcn/ui's own generated code (Button, Card, Input, Sheet,
  DropdownMenu, ...) — copy-paste components you own outright, not a
  package dependency. `components.json` is configured so
  `npx shadcn@latest add <component>` drops any future component straight
  into this folder using the same conventions already established here.
- **`common/`** is _this application's_ reusable pieces built from those
  primitives — `PageHeader`, `EmptyState`, `ErrorState`, `PageLoader`,
  `Logo`, `ThemeToggle`. A future module's `EmployeeListPage` should reach
  for `EmptyState`/`ErrorState`/`PageHeader` rather than rebuilding them.

### `src/lib/api/` — the only path to the backend

- **`httpClient.ts`** — the one axios instance. Attaches the JWT (once one
  exists — see `authToken.ts`) and normalizes every failure (backend error
  envelope, network failure, anything else) into a single `ApiError` type.
  No feature module should ever import `axios` directly.
- **`queryClient.ts`** — the one `QueryClient`, with retry/staleness
  defaults sane for an internal HR tool (see the file's own comments for
  why each default was chosen).
- **`queryKeys.ts`** — the query-key factory convention (Section 6 shows it
  in use).
- **`types.ts`** — the envelope types (`ApiSuccessResponse`/`ApiErrorResponse`/
  `ApiError`) mirroring the backend's own response shape exactly (see
  `../backend/shared_kernel/api/response.py` and any `*_API.md` in the repo
  root) — every future module's API functions return/throw these same
  types, never a module-invented shape.
- **`endpoints.ts`** — base path segments only (`/employees`, `/leave`,
  `/approvals`, ...). Actual request functions belong inside each module,
  not here — this file staying tiny is intentional.

As of Phase 11, `httpClient.ts` also owns silent token refresh: a 401 (other
than from `/auth/login/` or `/auth/token/refresh/` itself) triggers exactly
one refresh attempt — concurrent 401s share a single in-flight refresh
promise rather than each rotating the single-use refresh token out from
under the others — and the original request is retried once with the new
access token. A refresh that itself fails clears both tokens and emits
`lib/auth/sessionEvents`'s "session expired" event; it does not redirect
directly, since httpClient runs outside the router and outside React. See
the next section for what does react to that event.

### `src/lib/auth/` — session state, not the login feature itself

This folder answers exactly one question for the rest of the app: "is
there currently a valid session?" It deliberately does not fetch a user
profile, does not call `/auth/login/`, and does not know about routes.

- **`AuthProvider.tsx` / `useAuth.ts` / `auth-context.ts`** — the same
  three-way split as `app/providers`'s `ThemeProvider` (component / hook /
  context each in their own file, so neither trips
  `react-refresh/only-export-components`). `AuthProvider` initializes
  `isAuthenticated` from whatever token is already in storage
  (`lib/api/authToken.ts`'s `hasValidAccessToken()`, a local JWT-`exp`
  check — never a network call), and subscribes to `sessionEvents` so a
  silent-refresh failure updates state immediately.
- **`useSignOut.ts`** — the one place that calls `POST /auth/logout/`
  (best-effort — local state clears either way) and then calls
  `useAuth().logout()`. Used by `UserMenu`.
- **`sessionEvents.ts`** — a tiny dependency-free pub-sub. It exists to
  break what would otherwise be a real circular import: `httpClient.ts`
  (which has no React) is the thing that discovers a session died, but only
  `AuthProvider` is allowed to own React state about it.

Both `app/router`'s `ProtectedRoute`/`PublicOnlyRoute` and
`src/modules/auth`'s login flow depend on this folder — it never depends on
either of them. That one-way arrow is what section 1's "dependency
direction" bullet means in practice, not just in the abstract.

### `src/config/env.ts` — the only file that reads `import.meta.env`

Validated with `zod` at import time, so a missing/malformed environment
variable fails loudly at startup with a clear message, instead of causing a
confusing `undefined` somewhere deep in a component three renders later.

### `src/hooks/`, `src/utils/`, `src/types/`

Cross-cutting, module-agnostic helpers only. The moment something is
specific to one module's domain (an `Employee` type, a `useLeaveBalance`
hook), it belongs inside that module under `src/modules/<module>`, not
here — keeping these three folders from becoming a dumping ground is a
deliberate, ongoing discipline, not just a starting convention.

### `src/modules/` — one real module so far

`src/modules/auth/` (Login, Phase 11) is the first tenant, following the
exact shape `src/modules/README.md` describes (`api/`, `components/`,
`hooks/`, `pages/`, plus a `validation/` folder this module added for its
zod schema — the README's shape is a starting convention, not a rigid
contract; add a folder if a module genuinely needs one). Its public surface
is `index.ts`, exporting only `LoginPage` — `api/authApi.ts`,
`hooks/useLoginMutation.ts`, and `validation/loginSchema.ts` are internal
and nothing outside the module imports them directly. Every other future
module (Employees, Leave, ...) still starts from zero — see Section 6.

## 3. Theming system

Light/Dark/System, implemented as:

1. `src/index.css` defines every color as an HSL CSS variable, twice — once
   under `:root` (light) and once under `.dark` (dark). Tailwind's
   `darkMode: ["class"]` (`tailwind.config.ts`) means adding/removing the
   `.dark` class on `<html>` is the entire mechanism — no JS-computed
   styles, no flash-of-wrong-theme beyond what a `<script>` in `index.html`
   would prevent (not needed yet at this phase's scale; revisit if a
   flash-of-unstyled-theme becomes a real, observed problem).
2. `app/providers/ThemeProvider.tsx` resolves `"system"` via
   `matchMedia("(prefers-color-scheme: dark)")`, persists the user's choice
   to `localStorage`, and applies the resolved class.
3. Every component styles itself with semantic Tailwind classes
   (`bg-background`, `text-foreground`, `border-border`, ...) that resolve
   through those CSS variables — never a hardcoded color. This is exactly
   why shadcn/ui components (and any new one added via the CLI later) pick
   up the theme automatically with no extra work.

## 4. Error handling — two distinct layers, on purpose

- **`ErrorBoundary` + `GlobalErrorFallback`** (`app/error/`) — a React class
  component catching any render-time crash anywhere in the tree, including
  outside the router (e.g. inside a provider). This is the last-resort net;
  if you see this screen, something is badly wrong.
- **`RouteErrorBoundary`** — wired as every top-level route's
  `errorElement`. Handles routing-specific failures (a thrown `Response`,
  a 404) distinctly from an unexpected exception, and renders inside
  `MinimalLayout` so the user still sees consistent app chrome.

A future module's own data-fetching errors should NOT rely on either of
these — use TanStack Query's `isError` state and render `ErrorState`
(`components/common/ErrorState.tsx`) inline, so one failed panel doesn't
take down the whole page.

## 5. Path aliases

One alias only: `@/*` → `src/*`, configured identically in
`tsconfig.app.json`, `vite.config.ts`, and `vitest.config.ts` (three places
because each tool resolves modules independently — the editor/type-checker,
the bundler, and the test runner). Deliberately not a dozen granular
aliases (`@components`, `@hooks`, `@lib`, ...) — one alias is easier to keep
in sync across all three config files and is the more common convention;
revisit only if the codebase grows large enough that `@/components/...`
imports genuinely become a readability problem, which is not the case at
this phase's size.

## 6. Adding a new module — worked example (Leave)

This is the concrete procedure the brief asked this document to describe.
Nothing below requires touching a single file from this phase. `src/modules/auth`
(Phase 11) followed this same procedure for real, with two differences
worth calling out where they happen below: it added a `validation/` folder
(step 1) for its zod schema, and its "page" (step 4) renders a form and
calls a mutation instead of a query, since login is a write, not a read —
see `src/modules/auth/hooks/useLoginMutation.ts` for the mutation
equivalent of step 3 below.

1. **Create the module folder**, following `src/modules/README.md`'s shape:

   ```
   src/modules/leave/
   ├── api/
   │   └── leaveRequests.ts       # functions built on lib/api/httpClient
   ├── components/
   │   └── LeaveRequestCard.tsx
   ├── hooks/
   │   └── useLeaveRequests.ts    # TanStack Query hooks
   ├── pages/
   │   └── LeaveListPage.tsx
   ├── types.ts
   └── index.ts
   ```

2. **API functions** call `httpClient` directly and return typed data —
   never the raw envelope:

   ```ts
   // src/modules/leave/api/leaveRequests.ts
   import { httpClient, API_ENDPOINTS } from "@/lib/api";
   import type { ApiSuccessResponse } from "@/lib/api";
   import type { LeaveRequest } from "@/modules/leave/types";

   export async function fetchLeaveRequests(): Promise<LeaveRequest[]> {
     const response = await httpClient.get<ApiSuccessResponse<LeaveRequest[]>>(
       `${API_ENDPOINTS.leave}/requests/`,
     );
     return response.data.data;
   }
   ```

3. **Query keys**, using the shared factory:

   ```ts
   // src/modules/leave/hooks/useLeaveRequests.ts
   import { useQuery } from "@tanstack/react-query";
   import { createQueryKeyFactory } from "@/lib/api";
   import { fetchLeaveRequests } from "@/modules/leave/api/leaveRequests";

   export const leaveKeys = createQueryKeyFactory("leave");

   export function useLeaveRequests() {
     return useQuery({ queryKey: leaveKeys.lists(), queryFn: fetchLeaveRequests });
   }
   ```

4. **The page**, using the existing common components:

   ```tsx
   // src/modules/leave/pages/LeaveListPage.tsx
   import { PageHeader, ErrorState, EmptyState, PageLoader } from "@/components/common";
   import { useLeaveRequests } from "@/modules/leave/hooks/useLeaveRequests";

   export function LeaveListPage() {
     const { data, isPending, isError, refetch } = useLeaveRequests();

     if (isPending) return <PageLoader />;
     if (isError) return <ErrorState onRetry={() => refetch()} />;
     if (data.length === 0) return <EmptyState title="No leave requests yet" />;

     return (
       <div>
         <PageHeader title="Leave Management" />
         {/* render data.map(...) */}
       </div>
     );
   }
   ```

5. **Wire it into the router** — replace the placeholder route in
   `app/router/routes.tsx`:
   ```tsx
   const LeaveListPage = lazy(() =>
     import("@/modules/leave/pages/LeaveListPage").then((m) => ({ default: m.LeaveListPage })),
   );
   // ...
   { path: ROUTE_PATHS.dashboard.leave.slice(1), element: withSuspense(LeaveListPage) },
   ```
   The sidebar entry (`layouts/DashboardLayout/navigation.ts`) already
   points at this same path from Phase 10 — no change needed there.

That's the entire procedure. `DashboardLayout`, `Sidebar`, `AppProviders`,
`httpClient`, and every config file stay exactly as this phase left them.

## 7. What's explicitly out of scope so far

Phase 11 closed the authentication gap Phase 10 deliberately left open
(login, JWT storage + silent refresh, protected/public-only routes,
sign-out). What's still out of scope, by design:

- A real user-profile fetch (`GET /auth/me/`) — `UserMenu` still shows a
  generic "Signed-in user" label rather than the authenticated user's real
  name/email/roles. Nothing currently needs that data; wiring it means a
  `useCurrentUser` query in a future phase, most naturally added alongside
  whichever module first needs to display or gate on the user's identity
  (e.g. role-based nav visibility).
- Password reset / forgot-password screens — `IDENTITY_API.md`'s
  `password-reset/request` and `password-reset/confirm` endpoints exist on
  the backend with no frontend screen yet.
- Any other business module's pages, API calls, or components (Employees,
  Leave, Approvals, Attendance, Overtime, Business Trips, Asset Requests,
  Notifications).
- Server-driven data anywhere outside auth — every non-auth placeholder page
  still shows static content by design.
