# United HRMS — Frontend

Enterprise React frontend for United HRMS. **Phase 10** built the
architectural foundation — providers, routing, theming, layouts, a reusable
UI kit, and the API client structure. **Phase 11** added the first real
feature on top of it: Login, with JWT auth (access + refresh, silent
refresh on expiry), protected/public-only routing, and sign-out. See
[`FRONTEND_ARCHITECTURE.md`](./FRONTEND_ARCHITECTURE.md) for how Login was
built and how each future module (Employees, Leave, Approvals, Attendance,
Overtime, Business Trips, Asset Requests, Notifications, ...) plugs into
this foundation the same way, without structural changes.

For setup, running, building, linting, formatting, and testing instructions,
see [`TESTING_GUIDE.md`](./TESTING_GUIDE.md).

## Tech stack

| Concern            | Choice                                |
| ------------------ | ------------------------------------- |
| Framework          | React 18 + TypeScript                 |
| Build tool         | Vite                                  |
| Styling            | Tailwind CSS                          |
| Component kit      | shadcn/ui (Radix UI primitives + CVA) |
| Routing            | React Router (data router)            |
| Server state       | TanStack Query                        |
| HTTP client        | axios                                 |
| Env validation     | zod                                   |
| Testing            | Vitest + React Testing Library        |
| Linting/formatting | ESLint (flat config) + Prettier       |

## Quick start

```bash
cp .env.example .env
npm install
npm run dev
```

Then open http://localhost:5173.

## Scripts

| Command                 | What it does                                                     |
| ----------------------- | ---------------------------------------------------------------- |
| `npm run dev`           | Start the Vite dev server with HMR                               |
| `npm run build`         | Type-check (`tsc -b`) then produce a production build in `dist/` |
| `npm run preview`       | Serve the production build locally                               |
| `npm run typecheck`     | Type-check only, no build output                                 |
| `npm run lint`          | Lint the whole project (fails on any warning)                    |
| `npm run lint:fix`      | Lint and auto-fix what's fixable                                 |
| `npm run format`        | Format the whole project with Prettier                           |
| `npm run format:check`  | Check formatting without writing changes                         |
| `npm run test`          | Run the test suite once                                          |
| `npm run test:watch`    | Run the test suite in watch mode                                 |
| `npm run test:ui`       | Run tests with Vitest's interactive UI                           |
| `npm run test:coverage` | Run the test suite with a coverage report                        |

## Folder structure (high level)

```
src/
├── app/            # Composition root: providers, router, error boundaries
├── layouts/         # Reusable page shells: AuthLayout, DashboardLayout, MinimalLayout
├── pages/           # Route-level placeholder pages (non-auth modules)
├── components/
│   ├── ui/          # shadcn/ui primitives (button, card, input, ...)
│   └── common/       # App-level reusable components (PageHeader, EmptyState, PasswordInput, ...)
├── modules/
│   └── auth/          # Login (Phase 11) — the first real feature module; see FRONTEND_ARCHITECTURE.md §6
├── lib/
│   ├── api/            # HTTP client (incl. silent token refresh), TanStack Query setup, query-key factory
│   ├── auth/            # Session state (AuthProvider/useAuth/useSignOut) — see FRONTEND_ARCHITECTURE.md §2
│   └── utils.ts          # shadcn's `cn()` helper
├── hooks/                  # Reusable hooks
├── utils/                   # General-purpose helpers (dates, storage)
├── types/                    # Cross-cutting shared types
├── config/                    # Typed, validated environment access
└── test/                       # Test setup (Vitest + Testing Library)
```

Full rationale for every one of these decisions — and exactly how to add a
new feature module — is in `FRONTEND_ARCHITECTURE.md`.

## What's intentionally NOT here yet

Login (Phase 11) is real. Still deliberately not here: a fetched user
profile (`UserMenu` shows a generic label, not the signed-in user's real
name), password reset screens, a dashboard with real data, or any
Employee/Leave/Approval/Attendance/Overtime/Business Trip/Asset
Request/Notification pages. Those are separate, later phases.
