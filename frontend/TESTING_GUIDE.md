# United HRMS Frontend — Setup & Testing Guide (Phase 1–13 + Leave review round)

Step-by-step instructions for getting this project running, and for every
quality gate (typecheck, lint, format, test, build) available in it. Phase 10
covered the foundation itself (tooling, routing, theming, layouts) with no
business modules yet. Phase 11 added the first real one — Login. Phase 12
adds Employee Management, Department CRUD (a sub-view of Employees), and User
Management — Parts B3 and B4 below cover their manual walkthroughs, the same
way Part B2 was added for Login. The Role & Permission Management phase then
adds full Role Management (a sub-view of Users, B4.7) and extends the
Create/Edit User dialogs to optionally link an employee and assign roles
inline (B4.2). Phase 13 adds Leave Management (B5) and Approvals (B6). A
follow-up review of Phase 13 (referred to below as "the Leave review round")
then reshaped both: the Leave tab became a pure HR/Admin processing queue
(no more personal balance/apply/cancel view — that moved to Employee Details,
B3.3), the approval chain gained a second, HR/Admin-only level that must
explicitly finalize a leave after the manager's own approval (B6), and the
Employee form's Manager field became a searchable picker instead of a flat
dropdown (B3.2).

Phase 12 also needed new backend endpoints (User list/detail/edit/activate/
deactivate, Employee-to-User linking, and full Department CRUD); the Role &
Permission Management phase added Role update/delete and a permission-catalogue
endpoint, and reduced the seeded system roles to a single "Admin" role; the
Leave review round extended the generic Approval Engine to support a step
assigned by permission code, not just one named employee — see the repo
root's `IDENTITY_API.md`/`EMPLOYEE_API.md`/`APPROVALS_API.md`/`LEAVE_API.md`
for all of this, and `../TESTING_GUIDE.md` for the backend's own automated
test run (`pytest`) before testing the frontend against it.

Tools assumed: **Node.js 20.11+** and **npm** (comes with Node). Verify with:

```bash
node -v
npm -v
```

---

## Part A — One-time setup

1. From the `frontend/` folder:

   ```bash
   cp .env.example .env
   ```

   The defaults work as-is for local development as long as the backend is
   running at `http://localhost:8000` (see `../backend`'s own
   `TESTING_GUIDE.md`) — `VITE_API_BASE_URL` already points there.

2. Install dependencies:
   ```bash
   npm install
   ```
   This is also the step that will surface any dependency-resolution issue —
   if it fails, check your Node version first (`node -v` should be 20+).

---

## Part B — Running the dev server

```bash
npm run dev
```

Expect Vite's banner with a local URL, typically:

```
  VITE vX.X.X  ready in XXX ms

  ➜  Local:   http://localhost:5173/
```

Open that URL. As of Phase 11, every dashboard route sits behind
`ProtectedRoute` (`src/app/router/ProtectedRoute.tsx`), so with no session
yet you'll be redirected straight to `/auth/login` instead of seeing the
dashboard shell — see Part B2 below for the real login walkthrough. Once
logged in, you land on the dashboard home with its "Coming soon" placeholder
card (see `README.md`'s "What's intentionally NOT here yet").

### B1. Things worth clicking through manually (once logged in)

| Action                                                                                            | Expect                                                                                                                                    |
| ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Click "Employees" in the sidebar                                                                  | Navigates to the real Employee List page (Phase 12) — not a placeholder. See Part B3                                                      |
| Click "Users" in the sidebar                                                                      | Navigates to the real User List page (Phase 12) — not a placeholder. See Part B4                                                          |
| Click "Leave" in the sidebar                                                                      | Navigates to the real Leave module (Phase 13, redesigned as an HR/Admin queue in the Leave review round) — not a placeholder. See Part B5 |
| Click "Approvals" in the sidebar                                                                  | Navigates to the real Approvals module (Phase 13) — not a placeholder. See Part B6                                                        |
| Click each remaining sidebar item (Attendance, Overtime, Asset Requests, Notifications, Settings) | Each navigates to its own URL and shows a "Coming soon" placeholder with that section's title                                             |

**Business Trips (Leave review round):** removed entirely — no sidebar item, no route, no placeholder page. `ROUTE_PATHS.dashboard.businessTrips` and its `PlaceholderPage` route are both gone from `app/router/`; there is nothing left to click through for it.

**Permission-based nav/route gating (Leave review round):** "Employees," "Leave," and "Users" only appear in the sidebar if the signed-in user holds the corresponding `*.view_*`/`*.manage_*` permission (`useHasAnyPermission`, `lib/auth/usePermission.ts`) — a user with only Leave/Approval permissions (no `identity.view_users`/`identity.manage_users`) no longer sees "Users" at all. Each of those pages also self-gates on direct URL navigation (typing `/users`, `/employees/new`, etc. straight into the address bar still renders a "You don't have access to..." `EmptyState` instead of the real page if the caller lacks the permission) — defense-in-depth on top of the hidden nav item, matching the existing `LeaveDashboardPage` precedent. Within a page the caller _can_ open, row-level Edit/Deactivate/Activate actions are hidden too if the caller only holds the `view` half of a permission pair, not `manage`. Test this by logging in as a user whose only role grants `leave.manage_leave`/`approvals`-related permissions: "Users" should be absent from the sidebar, and manually navigating to `/users` should show the restricted `EmptyState`, not the User List.
| Resize the window below the `lg` breakpoint (~1024px), or open dev tools' device toolbar | The sidebar disappears and a hamburger menu button appears in the topbar |
| Click the hamburger menu on a narrow viewport | A slide-over navigation panel opens from the left with the same links; clicking a link navigates and closes the panel |
| Click the sun/moon icon in the topbar | A menu with Light / Dark / System appears; picking one immediately re-themes the whole app |
| Reload the page after picking a theme | The theme persists (stored in `localStorage` under `united-hrms-theme`) |
| Pick "System" and toggle your OS's light/dark setting | The app follows it live, no reload needed |
| Click the account icon (top-right) | The dropdown label now shows your real signed-in email and role(s) (Phase 12, `GET /auth/me/`) instead of "Signed-in user" |
| Click the account icon (top-right), then "Sign out" | The session is cleared and you're redirected back to `/auth/login` (see B2) |
| While logged out, try navigating to `/` or any dashboard URL directly | `ProtectedRoute` redirects you to `/auth/login` instead of rendering the page |
| Navigate to a nonsense URL, e.g. `/this-does-not-exist` | A "Page not found" screen renders inside the Minimal layout, with a button back to the dashboard |

---

## Part B2 — Login (Phase 11)

This is the first real, backend-integrated feature in the frontend — it
needs the Django backend actually running and reachable at whatever
`VITE_API_BASE_URL` points to (`../backend`'s own `TESTING_GUIDE.md`, Parts
A–C, gets you a running backend with at least one seeded user). Everything
below assumes that's already up.

### B2.1 Happy path

1. With no session yet, open the app — you land on `/auth/login`.
2. Enter a real user's email and password (e.g. the `existing_user` fixture
   pattern from `apps/identity/tests/integration/test_auth_endpoints.py`, or
   any account you created via the backend's `POST /api/v1/auth/users/`).
3. Click the eye icon inside the password field — the value toggles between
   masked and plain text.
4. Click "Sign in". Expect: the button switches to a disabled, spinning
   "Signing in..." state, then you're redirected to the dashboard home
   (`/`) with no page reload.
5. Open dev tools → Application → Local Storage. Expect two new keys:
   `united-hrms-access-token` and `united-hrms-refresh-token`.
6. Reload the page. You should stay on the dashboard (the session persists
   across reloads) rather than bouncing back to login.

### B2.2 Validation

| Action                                                     | Expect                                                                                             |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Click "Sign in" with both fields empty                     | "Email is required" and "Password is required" appear under each field, no network request is made |
| Type a non-email string into the Email field, then blur it | "Enter a valid email address" appears under the field                                              |
| Fix the field after an error                               | The field-level error clears once you move focus (validation mode is `onTouched`)                  |

### B2.3 Server-side errors

| Scenario                                                            | Expect                                                                                                |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Correct email, wrong password                                       | A red banner above the form: "Incorrect email or password." (backend's `invalid_credentials`, 401)    |
| A deactivated account's credentials (`is_active=False` on the user) | A red banner: "This account has been deactivated. Contact your administrator." (`inactive_user`, 401) |
| Backend not running / unreachable                                   | A red banner: "Unable to reach the server. Check your connection and try again."                      |

None of these should ever throw an unhandled error to the console or show a
blank screen — every failure path is caught and rendered as the banner
above the form, with the form itself still usable for a retry.

### B2.4 Session lifecycle

| Action                                                                                                                                                       | Expect                                                                                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| While logged in, navigate to `/auth/login` directly                                                                                                          | `PublicOnlyRoute` redirects you straight back to the dashboard — you never see the login form while authenticated                                               |
| Click "Sign out" from the account menu                                                                                                                       | `POST /auth/logout/` fires (check the Network tab), both token keys are cleared from Local Storage, and you land on `/auth/login`                               |
| Manually delete `united-hrms-access-token` from Local Storage while on a dashboard page, then navigate to another sidebar link                               | You're redirected to `/auth/login` — a missing/expired access token is treated the same as never having logged in                                               |
| Log in, wait past the access token's lifetime (`JWT_ACCESS_TOKEN_LIFETIME_MINUTES` in the backend's settings — 15 min by default), then trigger any API call | The request 401s once, httpClient silently exchanges the refresh token for a new pair behind the scenes, and the original request succeeds without you noticing |
| Repeat the above but first also delete `united-hrms-refresh-token`                                                                                           | The silent refresh has nothing to use, both tokens are cleared, and the next protected navigation redirects to `/auth/login`                                    |

---

## Part B3 — Employee Management (Phase 12)

Needs the backend's Phase 12 endpoints running (Department CRUD, at minimum —
`EMPLOYEE_API.md`) and an admin account with `employees.view_employees`/
`employees.manage_employees` (the built-in **Admin** role has both by default).

### B3.1 Employee List

1. Navigate to "Employees". Expect a search box, three filter dropdowns
   (Department, Status, Type), and a table of employees with pagination at
   the bottom. **Bugfix regression check**: every row's Department column
   should show the employee's actual department name (e.g. "General"), never
   "—" — it previously always showed "—" regardless of the employee's real
   department, because the backend's list endpoint never resolved
   `department_name` at all (see `EMPLOYEE_API.md`).
2. Type into the search box. Expect the list to refetch ~350ms after you stop
   typing (not on every keystroke) and narrow to matches on name, employee
   code, or work email.
3. Pick a Department/Status/Type filter. Expect the list to narrow
   immediately and a "Clear filters" button to appear; clicking it resets
   every filter and the search box.
4. With more than one page of results (or lower `page_size` via the backend
   temporarily to force this), click "Next"/"Previous". Expect the URL's
   underlying state to update and the table to refetch that page.
5. Click a row (not the "⋯" menu). Expect navigation to that employee's
   Detail page.
6. Open the "⋯" menu on a row. Expect "View details", "Edit", and either
   "Deactivate" (if Active) or "Activate" (if not Terminated) — no status
   action at all for a Terminated employee.

### B3.2 Create Employee

1. Click "New Employee". Fill in first/last name, work email, department,
   job title, employment type, and date of joining (the only required
   fields — EMPLOYEE_API.md's optional fields can stay blank).
2. On the Manager field (Leave review round — replaced the old dropdown),
   type part of an existing employee's name or employee code. Expect
   matching results within ~350ms of you stopping typing, each row showing
   full name and employee code. Pick one — expect the field to collapse
   into a "selected" chip showing that name/code with a clear (✕) button.
   Click the ✕ and confirm the search box reappears, manager unset.
3. Submit with the work email of an employee that already exists. Expect a
   red banner: the backend's `duplicate_work_email` message.
4. Submit with valid, unique data (with or without a manager picked). Expect
   a success toast and redirect to the new employee's Detail page.

### B3.3 Employee Details & Edit

1. On a Detail page, confirm every field EMPLOYEE_API.md documents renders
   (department/manager names resolved, not raw ids; Telegram link status
   shown).
2. If you (or a role you hold) have `leave.view_leave`/`leave.manage_leave`,
   confirm a "Leave" section renders below the main details — a Leave
   Balance card grid and a paginated Leave History table for this one
   employee (Leave review round: this replaced the old personal leave view
   that used to live on the Leave module tab — see B5 below). Click a row in
   the history table; expect navigation to that leave request's detail page.
   Without either permission, confirm the section doesn't render at all
   (no broken/error state, just absent).
3. Click "Edit". Change the job title and department, submit. Expect a
   success toast, redirect back to Detail, and the new values reflected
   there. On Edit, confirm the Manager field pre-fills as a "selected" chip
   showing the employee's current manager (if any), not an empty search box.
4. From Detail, click "Deactivate" (if Active). Expect a status badge
   change to "Suspended" with no confirmation dialog (this action has none
   by design — only User Management's activate/deactivate does, see B4).

### B3.4 Departments (sub-view)

1. From the Employee List page, click "Departments" in the header (there is
   deliberately no separate sidebar entry for this — see
   `EmployeeListPage.tsx`'s docstring).
2. Click "New Department", fill in name/code, submit. Expect it to appear in
   the list immediately.
3. Click "New Department" again and reuse an existing code (e.g. `GEN`,
   seeded by the backend). Expect a red banner: `duplicate_department_code`.
4. Click the pencil icon on a department row, change its name, toggle
   "Active" off, submit. Expect the row to update and show an "Inactive"
   badge.
5. Confirm the department picker on the Employee Create/Edit form reflects
   whatever you just created (department pickers only list active
   departments).

### B3.5 Linked user account indicator (bugfix)

1. Link an employee to a user (B4.4 below, or via an employee created with
   `user_id` set at creation time).
2. Open that employee's Detail page. Expect a badge reading "User account
   linked: Yes" next to the status badge, with the linked account's email
   shown alongside it.
3. On an employee with no linked user, expect "User account linked: No"
   and no email shown.

---

## Part B4 — User Management (Phase 12)

Needs an admin account with `identity.view_users`/`identity.manage_users`
(the built-in **Admin** role has both by default).

### B4.1 User List

1. Navigate to "Users". Expect a search box (matches email), a status
   filter, and a table of users with pagination.
2. Confirm each row shows email, roles (or "—" if none), whether it's
   linked to an employee, and an Active/Inactive badge.

### B4.2 Create & Edit User

1. Click "New User". Submit with an email that already exists. Expect a red
   banner: "A user with this email already exists."
2. Submit with a new email and a password under 10 characters. Expect a
   client-side validation error before any request is sent.
3. Still in "New User", search for and select an employee in the "Link to
   employee (optional)" field, and check one or more roles in the "Roles
   (optional)" list. Submit valid data. Expect a success toast; then open the
   new user's row and confirm it shows "Linked" and the roles you checked —
   these are three separate backend calls chained behind one submit (create,
   then link, then assign each role), so also confirm no duplicate/partial
   state resulted (e.g. re-run and reselect the same employee — it should now
   show "already linked to a different user" and be unselectable).
4. Open the "⋯" menu on a row → "Edit". Change the email, submit. Expect a
   success toast and the updated email in the list.
5. Edit a user with **no** linked employee. Expect the same employee picker
   as Create. Edit a user that **is already linked**. Expect a read-only
   "Already linked to an employee record" line instead of the picker — there
   is no unlink endpoint, so this dialog never offers to change an existing
   link.
6. Edit any user's Roles checklist: check one more role and uncheck one it
   already had, then submit. Expect a success toast, and confirm the row's
   role badges reflect exactly the new set (this exercises
   `useSyncUserRolesMutation`'s assign+revoke diff, not just assign).

### B4.3 Activate / Deactivate

1. On an Active user, open "⋯" → "Deactivate". Expect a confirmation dialog
   (unlike Employee deactivate in B3.3, this one confirms first) warning
   that existing sessions stop working immediately. Confirm it.
2. Expect the badge to flip to "Inactive". If you have that user's
   credentials handy, confirm a fresh login attempt now gets
   `inactive_user` — matching IDENTITY_API.md's "checked fresh on every
   request" note, no delay.
3. Reactivate via "⋯" → "Activate" → confirm. Expect the badge to flip back.

### B4.4 Link User to Employee

1. On a user with no linked employee ("Not linked" in the table), open "⋯" →
   "Link to employee". Expect a dialog with a search box.
2. Type part of an existing employee's name. Expect matching results within
   ~350ms, each showing name and employee code (and "already linked to a
   different user" if applicable).
3. Select an unlinked employee, click "Link employee". Expect a success
   toast, the dialog closing, and the user's row now showing "Linked".
4. Repeat, this time selecting an employee already linked to a _different_
   user. Expect a red error toast: the backend's `user_already_linked`
   message.
5. **Bugfix regression check**: if you linked the account you're currently
   logged in as, sign out and back in (or just reload). Expect the account
   menu's roles/label to keep matching, and `GET /auth/me/`'s `employee_id`
   (check via Postman, or your browser's Network tab) to now be non-null —
   before this bugfix, `employee_id` never got set at all, regardless of
   how the link was made. Employees linked _before_ this fix shipped need a
   one-time `python manage.py backfill_user_employee_links` (run from
   `backend/`, see `EMPLOYEE_API.md`) to catch up.

### B4.5 Reset Password

1. Open "⋯" → "Send password reset". Expect a confirmation dialog, then a
   toast confirming (or denying nothing — the backend's endpoint always
   replies the same way whether or not the email is registered, per
   IDENTITY_API.md).
2. If `SMTP_HOST` isn't configured on the backend, confirm the reset link
   appears in the backend's logs instead (same mechanism `../TESTING_GUIDE.md`
   Part H describes for the Telegram-linking OTP).

### B4.6 What's not automated yet

Phase 12 did not add Vitest component tests for the Employee/User/Department
UI (unlike Login's `LoginForm.test.tsx` in Phase 11) — Part B3/B4 above are
manual-only for now. A future pass should add at least one test per module
following `LoginForm.test.tsx`'s shape (mock the API module, assert
validation/error-banner behavior) before this scope is considered fully
covered by Part F below. The same applies to B4.7 and Part B5/B6 (Phase 13's
Leave Management and Approvals modules) below.

### B4.7 Role Management (Role & Permission Management phase)

Reached via the Users list page's "Manage Roles" header action — a sub-view
of Users, same placement rule as Departments under Employees (B3.4). Needs
`identity.view_roles`/`identity.manage_roles` (the built-in **Admin** role
has both by default).

1. Navigate to Users → "Manage Roles". Expect a table of roles with name,
   description, a truncated list of permission badges ("+N more" once past
   three), and a "System"/"Custom" badge — exactly one role, **Admin**,
   should show "System".
2. Click "New Role". Fill in a name, optional description, and check a few
   permissions (grouped by module — identity, employees, leave, approvals).
   Submit. Expect a success toast and the new role in the table with
   "Custom".
3. Submit a second role reusing an existing name. Expect a red banner:
   duplicate role name.
4. Click the "⋯" menu on your new role → "Edit". Change its description,
   check one more permission and uncheck another, submit. Expect the row's
   permission badges to reflect exactly the new set — this is a
   full-replace update (unchecked permissions are actually revoked, not left
   alone).
5. Edit the **Admin** role. Expect an inline note that it's a built-in
   system role but can still be edited. Confirm you _can_ save a permission
   change to it (only deletion is blocked, not editing).
6. Delete your custom role while it's still assigned to a user (assign it to
   someone first via B4.2's Edit dialog). Expect a red error toast for a
   conflict — revoke it from every user first.
7. Revoke the role from that user (Edit User → uncheck it, save), then
   delete the role again. Expect success and the row disappearing from the
   table.
8. Attempt to delete the **Admin** role. Expect a red error toast — built-in
   system roles can never be deleted, regardless of whether they're assigned
   to anyone.

---

## Part B5 — Leave Management (Phase 13; redesigned into an HR-only queue in the Leave review round)

Top-level nav item ("Leave"), same placement `layouts/DashboardLayout/navigation.ts`
already reserved back in Phase 10. **As of the Leave review round, this tab is
HR/Admin leave _processing_ only** — it never shows the logged-in user's own
leave, and there is no self-service Apply/Cancel/Dashboard surface here
anymore (an employee's own balance/history now lives on their Employee
Details page instead — see B3.3). Everything in this Part needs
`leave.manage_leave` (or, for read-only rows, `leave.view_leave`) — the
built-in **Admin** role has both by default. Log in as Admin (or a custom
role granted these) for all of B5.

### B5.1 Leave Dashboard (HR processing queue)

1. Navigate to "Leave" as a user **without** `leave.view_leave`/
   `leave.manage_leave`. Expect a graceful restricted-access empty state, not
   a crash or a blank page — matching this codebase's existing "nav item
   always visible, the page itself decides access" precedent (there is no
   separate route-level permission gate anywhere else either, e.g. Role
   Management).
2. Log in as Admin and navigate to "Leave". Expect a paginated table of
   **every employee's** leave requests (not your own), with filters for
   employee (searchable), status, leave type, and a start-date range — no
   balance cards, no "Apply for Leave" self-service button.
3. Confirm each row shows the employee's name/code alongside the request
   details — this is the `employee_name`/`employee_code` enrichment
   `GET /leave/requests/manage/` adds (see `LEAVE_API.md`).
4. Type into the employee filter. Expect the list to narrow to that
   employee's requests only, across every status.
5. Click a row. Expect navigation to the Leave Request Detail page
   (`/leave/<id>`), same detail page as before, showing the full request
   plus an "Approval status" panel (embedded from the Approvals module —
   see Part B6) listing every level reached so far (now potentially two:
   manager, then HR/Admin) and any decision comments.

### B5.2 Apply Leave on behalf of an Employee (HR/Admin)

1. From the Leave Dashboard, click "Apply for Leave". Expect an "Employee"
   picker inside the dialog (search by name/code) — there is no "apply for
   yourself" shortcut anymore since this surface is HR-only. Pick an
   employee, fill in the rest, submit. Expect success and the new request
   appearing in the queue under that employee's name.
2. Reapply for the same employee with overlapping dates. Expect a red error
   banner (overlapping request). Apply for more days than that employee's
   available balance. Expect a red error banner (insufficient balance).
3. Confirm (via `/api/docs/` or the database) that the resulting approval
   request's `requested_by_employee_id` is the picked employee, not the HR
   caller — this is what makes the employee's own Telegram notifications (if
   linked) fire identically to a self-submitted request.

### B5.3 Cancel any employee's leave (HR/Admin)

1. From the Leave Dashboard's queue, cancel a `pending`/`approved` request
   from any employee. Confirm in the dialog (reason optional). Expect
   `status: cancelled` and — if it was `approved` — the consumed balance
   restored.
2. Attempt to cancel an already-`cancelled`/`rejected` request. The button
   should not even be offered.

### B5.4 Leave application from Telegram, and an employee's own view

An employee applying via the Gateway's `/apply_leave` conversation (or an
HR/Admin applying on their behalf per B5.2) shows up in **two** places on
the web app now: the Leave Dashboard's HR-wide queue (this Part) and that
one employee's own Leave section on their Employee Details page (B3.3) —
both read the same underlying `LeaveService`/endpoints, just scoped
differently (everyone vs. one employee). Confirm: apply via Telegram, then
reload both screens and confirm the new request appears in each without a
page-specific change.

### B5.5 Leave Type Management

Reached via the Leave Dashboard's "Leave Types" header action — a sub-view
of Leave, same placement rule as Departments under Employees.

1. Navigate to Leave → "Leave Types". Expect a paginated, searchable table
   including inactive rows (unlike the plain apply-leave dropdown, which is
   always active-only).
2. Click "New Leave Type". Fill in name, code, default annual days, paid/
   requires-approval toggles. Submit. Expect a success toast and the new
   row.
3. Submit a second leave type reusing an existing code (e.g. `ANNUAL`).
   Expect a red banner: duplicate code.
4. Edit your new leave type: toggle "Active" off, submit. Expect the row's
   badge to flip to "Inactive", and confirm it no longer appears in the
   Apply Leave dialog's leave-type dropdown.
5. Re-edit it and toggle "Active" back on — confirm it reappears in the
   dropdown. There is no delete action (leave types are referenced by
   balance/request rows).

### B5.6 Leave Balance Adjustment / Opening

Reached via the Leave Dashboard's "Open Balance"/"Adjust Balance" header
actions (Admin/HR only). Both open the same dialog against the same
endpoint — only the pre-filled year/copy differs.

1. Click "Open Balance". Pick an employee, a leave type, a year with no
   existing balance row (e.g. two years from now), entitled/used/carried-
   forward days, and a reason (required). Submit. Expect a success toast
   ("Leave balance opened") and the change reflected the next time you view
   that employee's balance for that year (check via their Employee Details
   Leave section, B3.3 — there's no balance-card view on the Dashboard
   anymore).
2. Click "Adjust Balance". Pick the same employee/leave type/the _current_
   year (which already has a row), change the entitled days, and submit.
   Expect a success toast ("Leave balance adjusted").
3. Submit either dialog with a negative day value. Expect a red error
   banner (`invalid_leave_balance_adjustment`).
4. Submit with an empty reason. Expect a client-side validation message —
   every adjustment is written to an audit trail and a reason is required.

---

## Part B6 — Approvals (Phase 13; gained permission-based ("any HR/Admin") steps in the Leave review round)

Top-level nav item ("Approvals"). `IsAuthenticated` only — "My Pending
Approvals" is your own inbox, no special permission needed, matching every
other module's "your own data" precedent. Leave's approval chain is now
**two levels**: level 1 is assigned to one specific employee (the
applicant's manager, unchanged from Phase 9); level 2 is assigned to
**anyone holding `leave.manage_leave`**, not one designated person — new
this round, so B6.1/B6.2 below cover both shapes.

### B6.1 My Pending Approvals

1. Log in as the manager assigned to an employee who has a `pending` leave
   request (see B5.2 to create one). Navigate to "Approvals". Expect the
   level-1 request listed with its subject summary, current level (1), and
   status — this step still shows only for that one manager, same as
   before.
2. Log in as **any** user holding `leave.manage_leave` (e.g. Admin) once a
   request has advanced to level 2 (have the manager approve it first, per
   B6.2 step 1 below). Expect the same request to appear in **every** such
   user's pending list simultaneously — proves the step isn't tied to one
   designated person.
3. Log in as someone with no pending approvals of either kind. Expect the
   empty state ("Nothing waiting on you").

### B6.2 Decide (Approve / Reject)

1. As the manager, click "Decide" on the level-1 request. Add an optional
   comment, click "Approve". Expect a success toast, the request removed
   from _the manager's_ pending list — but **not yet marked `approved`**:
   checking the Leave Dashboard (B5.1) or the employee's Employee Details
   Leave section (B3.3) should still show `status: pending`. This is the
   Leave review round's core change — a manager's approval alone no longer
   finalizes the leave.
2. As any `leave.manage_leave` holder, open "Approvals" and confirm the same
   request now shows there at level 2. Click "Decide" → "Approve" with an
   optional comment. Expect a success toast, and now — checking the Leave
   Dashboard or Employee Details — `status: approved` with **this** HR/Admin
   user's comment visible in the "Approval status" panel (not the manager's
   comment from step 1, which shows as level 1's own decision in the same
   history).
3. As a **second** `leave.manage_leave` holder (a different user than the
   one who decided in step 2), reload "Approvals" after step 2 completes.
   Expect the request no longer listed — proves the decide-mutation's cache
   invalidation is broad enough to clear it even for users who didn't make
   the decision themselves.
4. Repeat with "Reject" at level 1 (the manager) on a different request.
   Expect `status: rejected` immediately, the request never reaching any
   HR/Admin user's pending list at all, and the employee's balance **not**
   decremented.
5. Repeat with "Reject" at level 2 (an HR/Admin user, after the manager
   approved) on a third request. Expect `status: rejected`, and confirm the
   balance was never decremented (a request rejected at any level never had
   its balance deducted).
6. Attempt to decide a request that isn't assigned to you at all — neither
   as the named level-1 approver nor as a `leave.manage_leave` holder for a
   level-2 step (e.g. by hitting the API directly with someone else's
   request id). Expect a 403 — the UI itself only ever offers "Decide" on
   requests already scoped to your own pending list, so this is a
   server-side-only check to confirm, not something reachable through the
   screen itself.

### B6.3 Approval history on Leave Request Detail

Covered by B5.1 above — the same `ApprovalHistoryPanel` this Approvals
module exports is what Leave's Detail page embeds, so decisions made here
in B6.2 show up there immediately (React Query invalidates both modules'
caches on a successful decide), listing both levels once both have been
decided.

---

## Part C — Type checking

```bash
npm run typecheck
```

Runs `tsc -b` with `--noEmit` — no output at all on success. Any type error
prints the offending file/line; fix before continuing. This is also run as
the first step of `npm run build`, so a broken build always means a type
error came first.

---

## Part D — Linting

```bash
npm run lint
```

ESLint's flat config (`eslint.config.js`) — TypeScript-aware rules, React
Hooks rules, JSX accessibility rules, all with **zero tolerance for
warnings** (`--max-warnings 0`), so a clean run prints nothing and exits 0.

To auto-fix what's mechanically fixable (mostly import ordering and a few
stylistic rules Prettier doesn't already own):

```bash
npm run lint:fix
```

---

## Part E — Formatting

```bash
npm run format:check
```

Prettier, checking every file matches its expected formatting (including
Tailwind class sorting via `prettier-plugin-tailwindcss`) without writing
anything. To actually reformat:

```bash
npm run format
```

---

## Part F — Running the test suite

```bash
npm run test
```

Expect:

```
 ✓ src/lib/utils.test.ts (3 tests)
 ✓ src/components/common/PageHeader.test.tsx (4 tests)
 ✓ src/modules/auth/components/LoginForm.test.tsx (4 tests)

 Test Files  3 passed (3)
      Tests  11 passed (11)
```

`utils.test.ts` and `PageHeader.test.tsx` exist to prove the test pipeline
itself works end to end (Vitest + jsdom + React Testing Library + the `@/`
path alias) — a plain-function test and a component-render test
respectively. `LoginForm.test.tsx` is the first real feature test: it mocks
`modules/auth/api/authApi`'s `login` function (no real network call) and
covers field rendering, client-side validation errors, the show/hide
password toggle, and the friendly-message mapping for a rejected login.
Every future module's tests should follow whichever of these shapes fits
what's being tested.

Other test commands:

```bash
npm run test:watch      # re-runs on file change
npm run test:ui         # opens Vitest's interactive browser UI
npm run test:coverage   # runs once and writes an HTML coverage report to coverage/
```

If anything fails, stop here and fix it before moving on — a broken test
pipeline this early will only get harder to debug once real modules add
their own tests on top of it.

---

## Part G — Production build

```bash
npm run build
```

This runs `tsc -b` (Part C) and then `vite build`. Expect a `dist/` folder
containing the built assets and a build summary in the terminal showing
each output file's size. No warnings about chunk size are expected yet at
this phase's scale.

Preview the production build locally:

```bash
npm run preview
```

Opens on `http://localhost:4173` by default — this serves the actual
built `dist/` output, not the dev server, so it's the closest local check to
what a real deployment would serve.

---

## Part H — Troubleshooting

| Symptom                                                                        | Likely cause / fix                                                                                                                                                                                                                              |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm install` fails on a peer dependency error                                 | Confirm `node -v` is 20 or newer; older Node versions aren't supported by this toolchain                                                                                                                                                        |
| Dev server starts but the page is blank, console shows an env validation error | `.env` is missing or a value doesn't match `.env.example`'s shape — re-copy `.env.example` and check `VITE_API_BASE_URL` is a full valid URL                                                                                                    |
| Theme doesn't persist after reload                                             | Check the browser isn't blocking `localStorage` (private/incognito mode with strict settings can do this)                                                                                                                                       |
| `npm run lint` fails with parser errors about `tsconfig`                       | Run `npm run typecheck` first — ESLint's type-aware rules need a project that already type-checks cleanly                                                                                                                                       |
| `npm run build` fails but `npm run dev` works fine                             | `vite dev` doesn't type-check by default; `npm run build`'s `tsc -b` step catches type errors dev mode would silently let through — run `npm run typecheck` to see them directly                                                                |
| Tests fail with "matchMedia is not a function"                                 | Should not happen — `src/test/setupTests.ts` stubs it for jsdom. If you see this, confirm `vitest.config.ts`'s `setupFiles` still points at that file                                                                                           |
| Login always redirects back to `/auth/login` even with correct credentials     | Check the Network tab for the actual `POST /auth/login/` response — a CORS failure or wrong `VITE_API_BASE_URL` looks identical to a bad password from the UI. Also confirm the backend is actually running (`../backend`'s `TESTING_GUIDE.md`) |
| Logged-in session is lost on every page reload                                 | Check dev tools → Application → Local Storage for `united-hrms-access-token`/`united-hrms-refresh-token` — if the browser is blocking `localStorage` (see the theme row above), the session can't persist either                                |
| Stuck in a redirect loop between `/` and `/auth/login`                         | This should not happen — `ProtectedRoute` and `PublicOnlyRoute` (`src/app/router/`) both read the same `useAuth()` state. If you see this, check that `AuthProvider` is mounted above the router in `app/providers/AppProviders.tsx`            |

---

## What's next

Phase 11 added the first real feature module (Login); Phase 12 added
Employee Management, Department CRUD, and User Management — see
`FRONTEND_ARCHITECTURE.md`'s "Adding a new module" section, which
`src/modules/employees` and `src/modules/users` both follow. Once the next
phase adds another real module (Leave, Approvals, ...), this file should
grow a new Part for that module's own manual test walkthrough, the same way
Parts B2/B3/B4 were added here — mirroring how `../TESTING_GUIDE.md` (backend

- Telegram Gateway) grows a new part per phase. Part B4.6 above also flags
  one open item worth picking up before then: Vitest coverage for the Phase 12
  modules.
