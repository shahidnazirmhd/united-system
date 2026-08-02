# Feature modules

This directory is intentionally empty in Phase 10. Every future business
module (Employees, Leave, Approvals, Attendance, Overtime, Business Trips,
Asset Requests, Notifications, ...) gets its own folder here, each following
the same internal shape:

```
src/modules/<module-name>/
├── api/            # request functions built on lib/api/httpClient, one file per resource
├── components/     # module-only presentational components
├── hooks/          # module-only TanStack Query hooks (useEmployees, useCreateEmployee, ...)
├── pages/          # route-level page components (wired into app/router/routes.tsx)
├── types.ts        # this module's own domain types
└── index.ts        # the module's public surface — only what other code needs
```

See `FRONTEND_ARCHITECTURE.md`'s "Adding a new module" section at the
project root for the full convention, including how a module's page gets
wired into the router with lazy-loading, and how its query keys should be
namespaced.
