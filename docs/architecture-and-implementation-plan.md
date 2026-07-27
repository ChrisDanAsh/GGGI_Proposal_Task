# CTAF Climate Technology Proposal Portal — Architecture and Implementation Plan

---
Document version: 1.0

Date created: 27/07/26

Assignment reference: INT_CTL015_E1

Status: specification — not yet implemented

---

> **This document is the single source of truth for the build.** It
> serves two purposes at once: it is the implementation
> specification, and it is the documentation of how the finished
> code works. Every module below is specified to the point where
> implementation is transcription rather than design — no decision
> is deferred to implementation time.
>
> It supersedes [climate-proposal-app-plan.md](climate-proposal-app-plan.md),
> which remains in this folder as the earlier working document that
> established the layered approach and the technology choices.

---

## Contents

- [1. Goal and purpose](#1-goal-and-purpose)
- [2. Architecture overview](#2-architecture-overview)
- [3. Scope and phased rollout](#3-scope-and-phased-rollout)
- [4. Module specifications](#4-module-specifications)
- [5. File architecture](#5-file-architecture)
- [6. Test plan](#6-test-plan)
- [7. Future works and potential add-ons](#7-future-works-and-potential-add-ons)

---

## 1. Goal and purpose

CTAF (Climate Technology Accelerator Fund) receives climate
technology project proposals from institutions across GGGI member
countries. Today the assignment describes those submissions arriving
without a structured intake path — there is no form that enforces a
consistent shape on a proposal, no store that holds submissions for
later review, and no view that lets a reviewer see what has come in
or narrow it down by country or technology type.

This project builds that intake tool: a small web application where
a proposal is entered through a structured form, validated, stored
in Postgres, and then browsed, filtered, opened, edited, and
deleted.

**What the assignment requires** (INT_CTL015_E1, §Requirements):

1. **Submission form** with six fields — project name (text,
   required), target country (dropdown, ≥5 countries), climate
   technology category (dropdown, 5 fixed options), estimated budget
   in USD (number, required), planned start date (date), and project
   summary (multi-line, max 300 characters).
2. **Validation** — block submission on an empty required field with
   a clear error message; budget must be a positive number; the
   summary must respect its character limit and show a live counter.
3. **Storage and list view** — persist submissions, display them all
   in a table on a separate list page, and filter that page by
   country or by category.
4. **Basic CRUD** — clicking a list item opens a detail view; delete
   with a confirmation prompt; edit is optional but welcomed.

**Four properties this design targets beyond the bare requirements**,
each traceable to the assignment's evaluation criteria:

- **The full path works end to end** (Functionality, 40%). Form →
  validation → storage → list → detail → edit → delete, with
  filtering, all reachable from the browser with no manual steps.
- **Frontend and backend are separated in a way that can be
  observed, not just asserted** (Code Quality, 25%). The application
  is split into five layers — templates, routes, schemas, services,
  repository — each of which talks only to the layer directly below.
  A read-only JSON API sits beside the server-rendered pages on top
  of the *same* service and repository calls. Its primary reason for
  existing is to leave the door open for a React frontend without a
  later refactor (§2.3); that it costs twenty lines rather than a
  rewrite is also the observable demonstration that the business
  logic is not tangled into the web page.
- **Validation cannot be bypassed** (Code Quality, 25%). Browser
  attributes (`required`, `min`, `maxlength`, `type`) give fast
  feedback to a person using the form normally. A Pydantic schema on
  the server re-checks every rule, because anything running in the
  browser can be disabled from developer tools or skipped entirely
  by a command-line request.
- **A reviewer can run it from a clean clone** (Documentation, 15%).
  `docker compose up` starts Postgres and the application together,
  creates the database if it is missing, applies migrations, and
  seeds ten realistic proposals, so the app is never first seen as an
  empty table. There is no manual setup step to be forgotten — no
  `.env` to write, no `createdb` to run.

**Scope boundary.** There are no user accounts, no authentication,
and no per-user visibility rules. The assignment asks for *all*
submitted proposals to be displayed and never mentions logins, so
proposals are treated as one shared collection. A nullable
`owner_id` column is created now against a possible future — see
§4.5.

**What "done" means.** The application is complete when: the six
tests derived from the requirements plus the wider suite in §6 pass;
`docker compose up` from a fresh clone of the repository serves a
seeded, working app on `localhost:8000`; and the README, the AI-usage
note, and the screen recording called for in the assignment's *What
to Submit* section exist.

---

## 2. Architecture overview

### 2.1 The shape of the system

Two programs run side by side. One is the Python application: it
listens on a network port, waits for messages from browsers, and
sends replies. The other is Postgres: a separate program that stores
data on disk and answers queries. They talk over a network
connection, which is why the application never needs to know where
Postgres physically is — only the address in `DATABASE_URL`.

Inside the Python program the code is split into five layers. Each
layer has one job and calls only the layer directly beneath it. The
value of the arrangement is that when something breaks you know
which file to open, and when you add a feature you know where it
goes.

| Layer | Its one job | Knows about |
|---|---|---|
| Templates | Turn Python objects into the HTML a person sees | Jinja, HTML |
| Routes | Receive a request, call one service function, return a reply | HTTP, forms, redirects |
| Schemas | Check that incoming data is valid and convert it to real types | Pydantic, field rules |
| Services | Apply the rules about proposals | Nothing about HTTP or SQL |
| Repository | Read and write the database | SQLAlchemy, queries |

The direction of knowledge matters as much as the direction of
calls. A service function does not know a web page exists — it
raises `DuplicateProposalError` and lets the route decide what the
person sees. The repository does not know what a proposal *means* —
it only knows how to store and fetch one. This is what makes the
service layer testable in milliseconds without a web server, and
what makes the JSON API cost twenty lines rather than a rewrite.

### 2.2 Component diagram

```text
                          ┌──────────────────────────┐
                          │        BROWSER           │
                          │  HTML forms · CSS · a    │
                          │  little vanilla JS       │
                          │  (character counter and  │
                          │   delete confirmation,   │
                          │   external files only)   │
                          └────────────┬─────────────┘
                                       │ HTTP
                                       ▼
                          ┌──────────────────────────┐
                          │  UVICORN (ASGI server)   │
                          │  listens on :8000        │
                          └────────────┬─────────────┘
                                       ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                    FASTAPI APPLICATION                         │
   │                        app/main.py                             │
   │   mounts /static · includes both routers · 404 handler         │
   └───────┬───────────────────────────────────────────┬───────────┘
           │                                           │
           ▼                                           ▼
 ┌───────────────────────┐                 ┌───────────────────────┐
 │  WEB ROUTES           │                 │  JSON API ROUTES      │
 │  app/web/proposals.py │                 │  app/api/proposals.py │
 │                       │                 │                       │
 │  GET  /proposals/new  │                 │  GET /api/proposals   │
 │  POST /proposals      │                 │  GET /api/proposals/  │
 │  GET  /proposals      │                 │           {id}        │
 │  GET  /proposals/{id} │                 │  GET /api/countries   │
 │  GET  /…/{id}/edit    │                 │                       │
 │  POST /proposals/{id} │                 │  → serialised by      │
 │  POST /…/{id}/delete  │                 │    ProposalRead,      │
 │                       │                 │    CountryOut         │
 │                       │                 │  → auto-documented    │
 │                       │                 │    at /docs           │
 │                       │                 │  → the seam a React   │
 │                       │                 │    frontend would use │
 └───────┬───────────────┘                 └───────────┬───────────┘
         │                                             │
         │ renders                                     │
         ▼                                             │
 ┌───────────────────────┐                             │
 │  TEMPLATES + STATIC   │                             │
 │  app/templates/       │                             │
 │    base.html          │                             │
 │    form.html          │                             │
 │    list.html          │                             │
 │    detail.html        │                             │
 │    error.html         │                             │
 │  app/static/          │                             │
 │    style.css          │                             │
 │    counter.js         │                             │
 │    confirm-delete.js  │                             │
 │  (no inline event     │                             │
 │   handlers anywhere)  │                             │
 └───────────────────────┘                             │
         │                                             │
         │ both routers validate through…              │
         ▼                                             ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  SCHEMAS — app/schemas/proposal.py                             │
   │  ProposalCreate · ProposalUpdate · ProposalRead                │
   │  field rules: min_length, max_length, gt=0, enum membership    │
   │  format_errors() → {field: human message} for the form         │
   └───────────────────────────┬───────────────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  SERVICES — app/services/proposal.py                           │
   │  create · get · list · update · delete                         │
   │  rules: unique project name (case-insensitive, live rows only) │
   │  raises DuplicateProposalError / ProposalNotFoundError         │
   │  knows nothing about HTTP or SQL                               │
   └───────────────────────────┬───────────────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  REPOSITORY — app/db/repository.py                             │
   │  every query in the application lives here                     │
   │  every read filters deleted_at IS NULL                         │
   └───────────────────────────┬───────────────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  SQLALCHEMY — app/db/models.py · app/db/session.py             │
   │  Proposal ORM model · engine · SessionLocal · get_db()         │
   │  app/db/bootstrap.py — creates the database itself if absent   │
   │  parameterised SQL → SQL injection structurally impossible     │
   └───────────────────────────┬───────────────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  POSTGRES 16 (separate container)                              │
   │  table: proposals                                              │
   │  indexes on country, category, deleted_at                      │
   │  schema managed by Alembic — migrations/                       │
   └───────────────────────────────────────────────────────────────┘

  Reference data, read by schemas · templates · API · seed:
    app/domain/constants.py          Category enum + cached country loader
    app/domain/data/gggi_members.txt 54 GGGI member states, curated from
                                     the official 2026-03-12 listing.
                                     The loader is the seam for §7's
                                     move into a countries SQL table.

  Supporting, outside the request path:
    scripts/seed.py       10 realistic proposals, idempotent
    scripts/entrypoint.sh ensure database → migrate → seed → uvicorn
    docker-compose.yml    db + app, app waits on db healthcheck
    tests/                pytest against a self-creating test database
```

### 2.3 Why there are two front doors

**The reason the JSON API exists is to leave the door open for a
React frontend.** Everything else it provides is a side benefit.

The application built here is server-rendered: when a browser asks
for `/proposals`, the server queries the database, pours the rows
into an HTML template, and sends back a finished page. That is the
right choice for a form and a filterable table — it is one process
rather than two, validation errors are re-rendered by one function
instead of being reimplemented in JavaScript, and the whole thing
keeps working if a script fails to load.

But it is not the right choice forever. The moment the interface
wants to be genuinely interactive — a dashboard that updates without
a reload, drag-and-drop reordering, a richer editing experience —
a browser-side framework earns its cost. That architecture inverts
the last step:

```text
Server-rendered (what is built here)        React SPA (the future option)
────────────────────────────────────        ────────────────────────────
Browser asks for /proposals                 Browser asks for /
Server queries the database                 Server sends a page and a JS bundle
Server renders the full HTML                JS starts, asks for /api/proposals
Browser displays it. Done.                  Server queries, sends JSON
                                            JS builds the HTML in the browser
                                            Browser displays it
```

A React frontend consumes JSON. If the JSON endpoints do not exist,
the day someone wants that frontend they must first work out which
parts of the route functions were presentation and which were logic,
and disentangle them. Because `/api/proposals` exists now and is
already correct, that day costs only the frontend: the schemas, the
service functions, and the repository are reused unchanged, and the
only server-side work is adding the write endpoints (`POST`, `PUT`,
`DELETE`), each of which is a handful of lines calling service
functions that are already written and already tested.

Twenty lines today, to avoid a refactor later. That is the whole
argument.

**Two things follow at no extra cost.** First, FastAPI generates an
interactive API browser at `/docs` from the type annotations alone —
worth showing in the screen recording. Second, and more useful
during review: two independent doors reaching the same data is the
*observable* demonstration that the layering is real. Any code
structure can be claimed to be well separated; a second door that
took twenty lines rather than a rewrite is evidence.

`GET /proposals` and `GET /api/proposals` do the same work and then
diverge on the last step only:

```text
                        Postgres
                            │
                  ProposalRepository.list(country, category)
                            │
                  services.list_proposals(...)
                            │
                [ list of Python Proposal objects ]
                       ╱              ╲
                  Jinja2            Pydantic
                     │                  │
            finished HTML page      JSON text
                     │                  │
             a person reads it   a program reads it
```

The HTML path never produces JSON, and the JSON path never produces
HTML. Neither is an input to the other — they are siblings sharing
every step above the fork. It is worth being explicit that JSON is
*not* an intermediate step on the way to HTML: converting a Python
object to JSON flattens it to text, and building HTML from that text
would mean parsing it back into objects, two conversions to arrive
where the code already was. Jinja reads the Python objects directly.
Putting JSON in the middle would also lose type fidelity, since JSON
has no date type and no exact decimal type, so `start_date` and
`budget_usd` would go out as strings and come back needing re-parsing.

### 2.4 End-to-end flows

Each table below traces one complete journey through the stack.
These are the paths the test suite in §6 exercises and the paths the
screen recording should demonstrate.

#### Flow A — submitting a valid proposal

| # | Step | Layer | Detail |
|---|---|---|---|
| 1 | Person opens `/proposals/new` | Route | `form.html` rendered with `mode="create"`, empty `values`, empty `errors` |
| 2 | Browser paints the form | Template | Country and category `<select>` options come from Jinja globals seeded in `app/web/templates.py`; `counter.js` binds to the summary textarea |
| 3 | Person types; the counter updates | Browser | `input` event handler rewrites the used, limit, and remaining counts. No network traffic |
| 4 | Person clicks Submit | Browser | `required`, `type="number"`, `min="0.01"`, `maxlength="300"` are checked by the browser first — an incomplete form never leaves the machine |
| 5 | `POST /proposals` arrives | Route | Six `Form(...)` parameters collected into a raw dict, all still strings |
| 6 | Raw dict validated | Schema | `ProposalCreate(**raw)`. Strings stripped; `""` start date coerced to `None`; budget parsed to `Decimal`; country and category checked against the enums |
| 7 | Rule applied | Service | `create_proposal` calls `repo.exists_with_name(...)`; no match, so it proceeds |
| 8 | Row written | Repository | `Proposal(id=uuid4(), **data)` added and flushed |
| 9 | Transaction committed | Session | `get_db()` commits as the request finishes; `expire_on_commit=False` keeps the object readable |
| 10 | Reply sent | Route | `303 See Other` → `Location: /proposals`. Not a page — see below |
| 11 | Browser follows the redirect | Browser | `GET /proposals` runs Flow C; the new row is at the top |

**Why step 10 is a redirect and not a page.** If the POST returned
HTML directly, the browser's address bar would still point at the
POST. Pressing refresh would re-submit the form and create a
duplicate. Redirecting means refresh merely re-fetches a harmless
list page. Status `303 See Other` is used rather than `302` because
303 tells the browser explicitly to follow up with a `GET`.

#### Flow B — submission that fails validation

| # | Step | Layer | Detail |
|---|---|---|---|
| 1 | `POST /proposals` arrives with `budget_usd="-5"` | Route | Reached the server because the person disabled the browser checks, or sent the request from the command line |
| 2 | `ProposalCreate(**raw)` raises `ValidationError` | Schema | Error type `greater_than` on field `budget_usd` |
| 3 | Errors translated | Schema | `format_errors(exc)` → `{"budget_usd": "Estimated budget must be greater than zero."}` — Pydantic's raw wording is never shown to a person |
| 4 | Form re-rendered | Route | `form.html` returned with HTTP `400`, carrying `errors` **and the values already typed**, so nothing is lost |
| 5 | Person sees the message | Template | Red text directly beneath the budget input; the field gets `aria-invalid="true"` |

The same path handles a duplicate project name, except the error
originates in the service layer as `DuplicateProposalError`, the
route catches it, and the response status is `409 Conflict`.

#### Flow C — viewing and filtering the list

| # | Step | Layer | Detail |
|---|---|---|---|
| 1 | `GET /proposals?country=KE&category=smart_grid` | Route | Both parameters optional; a value not in the enums is discarded rather than erroring |
| 2 | Service called | Service | `list_proposals(repo, country="KE", category="smart_grid")` |
| 3 | Query built | Repository | `WHERE deleted_at IS NULL AND country = :country AND category = :category ORDER BY created_at DESC`. Conditions are appended only when the argument is present |
| 4 | Postgres filters | Database | Indexes on `country` and `category` are used; filtering happens in the database, not in Python |
| 5 | Table rendered | Template | `list.html` loops the rows; each project name links to `/proposals/{id}`; both dropdowns keep the current selection; an empty result renders an explanatory row, not a blank table |

#### Flow D — editing an existing proposal

Editing is the only flow that touches both a `GET` and a `POST` on
the same resource, and it is where the "one template for create and
edit" decision pays for itself.

| # | Step | Layer | Detail |
|---|---|---|---|
| 1 | Person clicks Edit on the detail page | Browser | Plain link to `/proposals/{id}/edit` — a `GET`, because opening a form changes nothing |
| 2 | Proposal fetched | Service | `get_proposal(id, repo)`; a deleted or unknown id raises `ProposalNotFoundError`, which the route turns into a `404` page |
| 3 | Stored values converted to form strings | Route | `_values_from(proposal)` — the budget formatted to two decimal places, the date as `YYYY-MM-DD` because that is the only format `<input type="date">` accepts, and `None` becoming `""` |
| 4 | Form rendered | Template | The same `form.html` as creation, with `mode="edit"`, `action="/proposals/{id}"`, and every box pre-filled. The heading reads "Edit proposal" and the button "Save changes" |
| 5 | Counter initialises correctly | Browser | `counter.js` runs `update()` on load, so an existing 180-character summary shows its remaining count immediately rather than as though the box were empty |
| 6 | Person changes a field and submits | Browser | The same native checks as creation |
| 7 | `POST /proposals/{id}` arrives | Route | The same six `Form(...)` parameters as creation, collected into the same raw dict |
| 8 | Validated | Schema | `ProposalUpdate(**raw)` — identical rules to creation. On failure the form re-renders with `mode="edit"` and `action` pointing back at this URL, status `400`, values preserved |
| 9 | Existence re-checked | Service | `update_proposal` calls `get_proposal` first, so editing something deleted in another tab meanwhile raises `ProposalNotFoundError` rather than silently writing to a dead row |
| 10 | Duplicate check, excluding self | Service | `repo.exists_with_name(name, exclude_id=proposal_id)`. Without `exclude_id` a proposal saved without renaming would be reported as a duplicate of itself |
| 11 | Fields written | Repository | `repo.update(proposal, {...})` sets each attribute and flushes. `id` and `created_at` are untouched; `updated_at` is re-stamped by the `onupdate` rule on the column |
| 12 | Reply sent | Route | `303 See Other` → `/proposals/{id}` |
| 13 | Browser follows the redirect | Browser | The detail page reappears showing the new values — the confirmation that the edit took |

Editing redirects to the **detail page** rather than the list,
because after changing something a person expects to see the thing
they changed. Creation redirects to the list, because after
submitting, seeing the new row among the others is the confirmation
that the submission worked.

#### Flow E — deleting a proposal

| # | Step | Layer | Detail |
|---|---|---|---|
| 1 | Person clicks Delete on the detail page | Browser | `confirm-delete.js` intercepts the form's `submit` event, reads the project name from `data-project-name`, and prompts; cancelling calls `preventDefault()` and stops the submission entirely. The name is handled as a string value, never as JavaScript source — §4.11.5 |
| 2 | `POST /proposals/{id}/delete` | Route | POST, not GET — a GET could be triggered by a link prefetch or a crawler |
| 3 | Service called | Service | `delete_proposal(id, repo)`; raises `ProposalNotFoundError` if already gone |
| 4 | Row marked, not removed | Repository | `deleted_at = now()`. The row stays on disk |
| 5 | Redirect | Route | `303` → `/proposals`. The proposal is absent from the list, because every read filters `deleted_at IS NULL` |

#### Flow F — the JSON door

| # | Step | Layer | Detail |
|---|---|---|---|
| 1 | `GET /api/proposals?country=KE` | API route | `country` typed as `Country | None`, so `/docs` renders it as a dropdown and an unknown code returns `422` |
| 2–4 | Service → repository → Postgres | — | Byte-for-byte the same calls as Flow C steps 2–4 |
| 5 | Serialised | Schema | `ProposalRead` with `from_attributes=True` converts each ORM object; `Decimal` and `date` become JSON strings |
| 6 | Reply sent | API route | `application/json`. No template involved at any point |

---

## 3. Scope and phased rollout

Six phases. Each ends with something observable — a page that loads,
a row in a table, a test that passes — so that a failure is always
attributable to the one thing just added. Phases are strictly
ordered; modules within a phase are ordered too, and the module
numbers in §4 follow that order exactly.

| Phase | Modules | What is built | Observable at the end |
|---|---|---|---|
| **1 — Foundation** | 1–3 | Settings loaded from the environment; the country and category vocabularies that every other layer references; the FastAPI application object with static mounting, router inclusion, a health check, and an HTML-aware 404 handler | `uvicorn app.main:app --reload` serves `/health` returning `{"status": "ok"}` |
| **2 — Persistence** | 4–7 | Database engine, per-request session, and the bootstrap that creates the database if absent; the `Proposal` ORM model; Alembic wired to the model with the first migration generated and applied; the repository holding every query in the application | `psql` shows a `proposals` table with the right columns and three indexes |
| **3 — Domain logic** | 8–10 | Pydantic schemas carrying every validation rule from the assignment, plus the error-message translator; the domain exceptions; the service functions holding the uniqueness rule | Schema and service tests pass with no web server and no browser involved |
| **4 — Web interface** | 11–13 | The five Jinja templates and the shared template environment; the hand-written stylesheet and the character-counter script; the seven HTML routes | The whole app works in a browser: submit, list, filter, open, edit, delete |
| **5 — Second door and data** | 14–15 | The three read-only JSON endpoints on the same service calls; the seeding script with ten realistic proposals | `/docs` renders an interactive API browser; `/api/proposals` returns JSON; the list page is populated on first view |
| **6 — Packaging, tests, documentation** | 16–18 | Dockerfile, Compose stack, entrypoint; the full pytest suite; README and the AI-usage note | `docker compose up` from a fresh clone serves a seeded working app; `pytest` is green |

### 3.1 What each module is

**Phase 1 — Foundation**

- **Module 1 · `app/config.py`** — one `Settings` class reading
  `DATABASE_URL` and friends from the environment, cached so the
  environment is read once per process. Environment variables rather
  than literals in code, because the database address differs
  between a laptop and a container and because passwords must never
  enter git history.
- **Module 2 · `app/domain/constants.py` +
  `app/domain/data/gggi_members.txt`** — the `Category` enum, fixed
  by the assignment, and the 54 GGGI member countries curated from
  the Institute's official March 2026 listing into a plain text
  data file with a cached loader. One definition of each, consumed by
  the schemas (validation), the templates (dropdown options and table
  labels), the API (query parameters), and the seed script. Codes are
  stored; labels are presentation. The loader is the seam that lets
  the country list move into a SQL table later without any caller
  changing.
- **Module 3 · `app/main.py`** — assembles the application: mounts
  `/static`, includes both routers, redirects `/` to `/proposals`,
  exposes `/health`, and installs the exception handler that renders
  a styled 404 page for browser requests while keeping JSON errors
  for `/api` paths.

**Phase 2 — Persistence**

- **Module 4 · `app/db/session.py` + `app/db/bootstrap.py`** — the
  engine, the session factory, and `get_db()`, the dependency that
  opens one session per request, commits on success, rolls back on
  any exception, and always closes; a half-saved proposal is
  structurally impossible. Alongside it, `ensure_database_exists()`,
  which creates the database itself when the server does not have
  one — so no `createdb` step exists to be forgotten, by a reviewer
  or by the test suite.
- **Module 5 · `app/db/models.py`** — the `proposals` table as a
  Python class. UUID primary keys so URLs do not reveal how many
  proposals exist; `NUMERIC` for money so no rounding error can
  appear; timestamps maintained by the database; `deleted_at` for
  soft delete; a nullable `owner_id` reserved for a future with user
  accounts.
- **Module 6 · `migrations/`** — Alembic pointed at the model's
  metadata, with the initial migration generated, read, and applied.
  The schema's history lives in git next to the code, so any copy of
  the database can be brought up to date by running the same
  sequence.
- **Module 7 · `app/db/repository.py`** — `ProposalRepository`, the
  only place in the codebase where a query is written. Every read
  excludes soft-deleted rows. Filters are composed conditionally so
  Postgres does the work rather than Python.

**Phase 3 — Domain logic**

- **Module 8 · `app/schemas/proposal.py` + `app/schemas/country.py`**
  — `ProposalCreate`, `ProposalUpdate`, `ProposalRead`, and
  `CountryOut`, plus `format_errors()`, which turns Pydantic's
  machine-readable error list into the field-keyed dictionary of
  plain-English messages the form displays. Every validation rule in
  the assignment lives here, and this is the copy that cannot be
  bypassed. Country validation is a membership check against the
  loader from Module 2, not an enum, so it survives the list's move
  into a database.
- **Module 9 · `app/services/errors.py`** — `DuplicateProposalError`
  and `ProposalNotFoundError`. Domain vocabulary, so a service can
  signal a problem without knowing what an HTTP status code is.
- **Module 10 · `app/services/proposal.py`** — five functions
  holding the rules: create, get, list, update, delete. They take
  validated data and a repository, and contain no HTTP and no SQL.

**Phase 4 — Web interface**

- **Module 11 · `app/templates/` + `app/web/templates.py`** — the
  shared shell, the form (used for both create and edit), the list,
  the detail page, the error page, and the configured Jinja
  environment that supplies the dropdown vocabularies and the
  formatting filters for money, dates, and labels.
- **Module 12 · `app/static/`** — one hand-written stylesheet with
  semantic class names, the live character counter, and the delete
  confirmation. Everything is vendored, so the interface renders
  identically offline and inside Docker, and a later move to a CSS
  framework or a React frontend means replacing a stylesheet rather
  than editing every template. All behaviour lives in external files:
  the templates contain no inline event handlers, for the security
  reason set out in §4.11.5.
- **Module 13 · `app/web/proposals.py`** — the seven HTML routes.
  Each takes input, calls one service function, and returns a page or
  a redirect. Any route longer than a handful of lines means logic
  has leaked out of the service layer.

**Phase 5 — Second door and data**

- **Module 14 · `app/api/proposals.py`** — `GET /api/proposals`,
  `GET /api/proposals/{id}`, and `GET /api/countries`, calling the
  identical service functions and loaders the HTML routes call and
  serialising through the schemas from Module 8. This is the seam a
  React frontend would consume (§2.3). FastAPI generates the
  interactive documentation at `/docs` from the type annotations at
  no additional cost.
- **Module 15 · `scripts/seed.py`** — ten realistic proposals spread
  across countries and categories, so filtering demonstrably does
  something and the app is never first seen empty. Idempotent, so
  running it twice is harmless.

**Phase 6 — Packaging, tests, documentation**

- **Module 16 · `Dockerfile`, `docker-compose.yml`,
  `scripts/entrypoint.sh`, `.dockerignore`, `.gitattributes`** — one
  command starts Postgres and the application, waits for the database
  to be genuinely ready, applies migrations, seeds, and serves.
- **Module 17 · `tests/`** — the full pytest suite: schema unit
  tests, service tests, HTTP integration tests, and API tests,
  running against a dedicated test database with each test isolated
  in a rolled-back transaction.
- **Module 18 · `README.md`, `docs/AI_PROMPTS.md`** — setup and run
  instructions verified from a clean clone, the design decisions
  written up, and the AI-usage note the assignment requires.

---

## 4. Module specifications

One section per module, in implementation order. Each opens with a
one-line summary, states its purpose, then specifies the
implementation completely. Where a value could reasonably have gone
more than one way, the chosen value is stated and the reason given —
nothing is left to be decided while coding.

Python version: **3.14**, the version present on the build machine.
All code is fully type-annotated. The module code in this document
uses no syntax specific to 3.12 — `X | None` unions, `Annotated`, and
`match` are all available from 3.10 onward — so targeting 3.14
changes nothing about what is written, only which interpreter runs
it.

### 4.0 Dependencies

`requirements.txt`, pinned exactly:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
jinja2==3.1.5
pydantic==2.13.4
pydantic-settings==2.14.2
sqlalchemy==2.0.41
alembic==1.14.0
psycopg[binary]==3.2.13
python-multipart==0.0.20
pytest==8.3.4
httpx==0.28.1
```

**`pydantic`, `pydantic-settings`, `psycopg[binary]`, and
`sqlalchemy` are pinned above their originally intended versions,
because installation and use on this machine proved it necessary —
this is the resolved state, not a hypothetical.** Three separate
Python 3.14 gaps surfaced, two at install time (missing wheels) and
one only once the ORM models (Module 5) were actually exercised:

- `psycopg[binary]==3.2.3` has no `cp314` wheel; `3.2.10` is the
  earliest patch on the 3.2.x line that does. Bumped to `3.2.13`, the
  newest 3.2.x patch, keeping the change as small as possible.
- `pydantic==2.10.5` pulls in `pydantic-core==2.27.2`, a Rust
  extension with **no `cp314` wheel at any patch on that line** — not
  a stale patch but an entire minor series predating 3.14's release.
  `pip` fell back to compiling it from source, which failed at the
  link stage (`link.exe failed: exit code: 1`) for want of a working
  Rust/MSVC toolchain — nothing this project should need just to
  install a dependency. Bumped `pydantic` to `2.13.4` and
  `pydantic-settings` to `2.14.2` (the versions current at build
  time), which pull `pydantic-core==2.46.4`, confirmed to ship a
  `cp314` wheel.
- `sqlalchemy==2.0.36` installs cleanly (it has a `cp314` wheel) but
  fails at class-definition time, not at import time, so the gap
  surfaced only once Module 5 defined a real model: any `Mapped[X |
  None]` column annotation — `start_date`, `owner_id`, `deleted_at` —
  raised `TypeError: descriptor '__getitem__' requires a
  'typing.Union' object but received a 'tuple'` while SQLAlchemy
  resolved the annotation, a consequence of Python 3.14's PEP 649
  lazy-annotation evaluation that 2.0.36 does not yet handle.
  Bisected against the published patch releases: `2.0.40` still
  fails, `2.0.41` is the first patch that resolves it. Bumped to
  `2.0.41` rather than the newest `2.0.x` patch, keeping the change as
  small as possible, consistent with the other two entries here.

Before installing on another machine, re-verify with
`pip index versions <package>` and a `pip download --no-deps
<package>==<version>` dry run for whichever Python version is
actually present, rather than assuming these exact pins remain
correct — wheel availability is a function of *when* a package was
published relative to a Python release, and both shift over time. If
a gap appears again, the fallback that avoids chasing pins
indefinitely is to create the virtual environment against Python 3.12
or 3.13 specifically (`py -3.12 -m venv .venv`), where every version
in this file already has full wheel coverage.

Notes on three of these, which are easy to omit and produce
confusing failures:

- **`python-multipart`** — FastAPI cannot read HTML form bodies
  without it. Its absence produces a runtime error only when the
  first form is submitted, not at startup.
- **`psycopg[binary]`** — the version 3 driver. The `[binary]` extra
  ships pre-compiled wheels, so no C toolchain is needed on Windows.
  The URL scheme is `postgresql+psycopg://`, not `postgresql://`,
  which would select the older psycopg2.
- **`httpx`** — required by Starlette's `TestClient`, used
  throughout §6.

Versions are pinned rather than left open so that the reviewer's
install resolves to exactly what was developed against.

---

### 4.1 Module 1 — `app/config.py`

**Summary**: a single cached `Settings` object holding every value
that differs between environments.

**Purpose**: the database address on a laptop is not the address
inside Docker, and a password must never be written into a file that
git tracks. Both problems are solved by reading configuration from
the environment. Caching the result means the environment is parsed
once per process rather than on every request, and gives tests a
single place to override.

**Implementation**

- New file `app/config.py`:

  ```python
  from functools import lru_cache

  from pydantic_settings import BaseSettings, SettingsConfigDict


  class Settings(BaseSettings):
      """Application settings, read from the environment or a .env file."""

      model_config = SettingsConfigDict(
          env_file=".env",
          env_file_encoding="utf-8",
          extra="ignore",
      )

      database_url: str = "postgresql+psycopg://ctaf:ctaf@localhost:5432/ctaf"
      app_name: str = "CTAF Proposal Portal"
      debug: bool = False


  @lru_cache
  def get_settings() -> Settings:
      """Return the process-wide settings object, parsed once."""
      return Settings()
  ```

- Field-to-variable mapping is automatic and case-insensitive:
  `database_url` reads `DATABASE_URL`, `debug` reads `DEBUG`.
- `extra="ignore"` means unrelated environment variables present on
  the machine do not cause a validation error.

**On `database_url` having a default.** A configuration value with no
default fails loudly when it is missing, which is normally the right
behaviour. Here the opposite is chosen deliberately: the default is
the local development URL, so a person who clones the repository and
runs `uvicorn app.main:app` gets a working application without first
having to create a `.env` file. Docker Compose sets `DATABASE_URL`
explicitly and therefore never sees the default. The trade-off — a
missing variable silently using local development settings instead of
erroring — is acceptable because nothing here is deployed anywhere
that a wrong default could reach. `.env.example` remains committed as
documentation of what can be overridden, and copying it to `.env` is
still the recommended path; it is simply no longer a prerequisite.

Together with the database bootstrap in §4.4.2, the effect is that a
fresh machine with Postgres running needs no manual setup at all: no
`.env`, no `createdb`, no `alembic upgrade` typed by hand.
- New file `.env.example`, committed:

  ```
  # Copy to .env and adjust. .env is never committed.
  DATABASE_URL=postgresql+psycopg://ctaf:ctaf@localhost:5432/ctaf
  DEBUG=false
  ```

- New file `.gitignore`:

  ```
  .env
  .venv/
  __pycache__/
  *.py[cod]
  .pytest_cache/
  .coverage
  htmlcov/
  *.egg-info/
  .idea/
  .vscode/
  ```

- New file `app/__init__.py`, empty. Every package directory created
  in this plan (`app/`, `app/db/`, `app/domain/`, `app/schemas/`,
  `app/services/`, `app/web/`, `app/api/`, `scripts/`, `tests/`) gets
  an empty `__init__.py` so imports resolve from the project root.

---

### 4.2 Module 2 — `app/domain/constants.py` and `app/domain/data/gggi_members.txt`

**Summary**: the category vocabulary as a fixed Python enum, and the
country vocabulary as a curated data file with a cached loader.

**Purpose**: the same vocabularies appear in the form dropdowns, the
validation rules, the filter dropdowns, the table cells, the API
query parameters, and the seed data. Defining each once means a
change happens in exactly one place. Storing short codes rather than
display text means the wording shown to a person can change without
a database migration and without invalidating stored rows.

The two vocabularies are deliberately implemented differently,
because they are different kinds of thing:

- **Categories are fixed by the assignment.** Five values, named in
  the brief, changing only if the brief changes. That is a code
  constant, so `Category` is a Python enum.
- **Countries are reference data that changes on its own schedule.**
  GGGI admits new members regularly — four joined during 2025 alone.
  A list like that does not belong hard-coded in a Python file. It
  is held in a plain text data file now, and §7 describes its move
  into a `countries` SQL table. **The loader function is the seam
  that makes that move cheap**: today its body reads a file, later it
  runs a query, and no caller changes.

#### 4.2.1 The country data file

- New file `app/domain/data/gggi_members.txt`.
- **Provenance**: curated from *GGGI Assembly Member States and
  Membership Dates*, the official Global Green Growth Institute
  listing dated **12 March 2026**, published at
  `https://gggi.org/wp-content/uploads/2026/03/20260312_Assembly-States-and-Membership-Dates.pdf`.
  The source URL and retrieval date are recorded in the file's header
  comment so the list can be re-verified later.
- **Format**: one record per line, three pipe-delimited fields —
  ISO 3166-1 alpha-2 code, display name, GGGI accession date in
  ISO format. Lines beginning `#` and blank lines are ignored.

  ```
  # GGGI Assembly Member States, with accession dates.
  # Source: https://gggi.org/wp-content/uploads/2026/03/20260312_Assembly-States-and-Membership-Dates.pdf
  # Retrieved: 2026-07-27. Official list dated 2026-03-12.
  # Format: ISO-3166-1-alpha-2 | display name | accession date (YYYY-MM-DD)
  # Note: the official list also includes OECS (Organisation of Eastern
  # Caribbean States), a regional integration organisation rather than a
  # country. It is omitted here because this field is a target *country*.
  DK|Denmark|2012-10-18
  GY|Guyana|2012-10-18
  KI|Kiribati|2012-10-18
  PH|Philippines|2012-11-08
  KR|Republic of Korea|2012-12-29
  VN|Viet Nam|2013-01-11
  KH|Cambodia|2013-03-24
  QA|Qatar|2013-03-24
  PG|Papua New Guinea|2013-04-10
  AE|United Arab Emirates|2013-05-29
  GB|United Kingdom|2013-06-27
  ET|Ethiopia|2013-08-04
  NO|Norway|2013-09-25
  FJ|Fiji|2014-04-25
  JO|Jordan|2014-05-10
  MN|Mongolia|2014-07-20
  CR|Costa Rica|2014-10-18
  ID|Indonesia|2014-10-26
  AU|Australia|2014-11-16
  MX|Mexico|2014-11-19
  VU|Vanuatu|2014-12-07
  SN|Senegal|2014-12-09
  HU|Hungary|2016-02-13
  TH|Thailand|2016-02-28
  RW|Rwanda|2016-09-11
  PE|Peru|2016-10-19
  LA|Lao PDR|2017-10-07
  PY|Paraguay|2018-09-13
  TO|Tonga|2018-12-17
  LK|Sri Lanka|2019-01-13
  UZ|Uzbekistan|2019-03-09
  BF|Burkina Faso|2019-04-14
  UG|Uganda|2019-08-28
  AO|Angola|2019-11-23
  EC|Ecuador|2019-11-23
  KG|Kyrgyz Republic|2020-05-15
  CI|Côte d'Ivoire|2020-09-24
  CO|Colombia|2021-04-14
  NI|Nicaragua|2021-10-16
  PK|Pakistan|2021-11-11
  TM|Turkmenistan|2022-03-06
  BH|Bahrain|2022-03-18
  NP|Nepal|2022-10-23
  KZ|Kazakhstan|2022-12-16
  ZM|Zambia|2023-07-23
  SV|El Salvador|2023-09-28
  TG|Togo|2023-11-04
  TJ|Tajikistan|2024-12-06
  KE|Kenya|2025-04-18
  BJ|Benin|2025-08-27
  DZ|Algeria|2025-08-28
  MA|Morocco|2025-11-14
  SB|Solomon Islands|2025-12-24
  LU|Luxembourg|2026-03-12
  ```

  **54 countries**, from 55 entries in the source once OECS is
  excluded. The file is written UTF-8 — Côte d'Ivoire needs it — and
  is stored in accession order, matching the source document, so the
  two can be diffed line by line when the list is next refreshed.
  The dropdown sorts by display name at render time; see below.

**Decisions fixed here**

- **OECS is omitted.** Entry 34 of the official list is the
  Organisation of Eastern Caribbean States, a regional integration
  organisation with no ISO 3166-1 country code. The form field is
  "Target Country", so a regional body does not belong in it. The
  omission is recorded in the file's header rather than left silent,
  so a future reader comparing against the source does not think a
  line was lost.
- **The accession date is carried even though nothing uses it yet.**
  It is in the source, it costs one field, and it is the natural
  column to have when the list becomes a table. Dropping it now would
  mean re-curating later.
- **Pipe-delimited, not CSV.** No country name in the list contains
  a pipe, so no quoting or escaping rules are needed and the parser
  is one `split("|")`. Côte d'Ivoire contains no comma either, but
  pipes remove the question entirely.
- **A `.txt` file rather than JSON or YAML.** It is reference data a
  person may need to edit by hand, it is diff-friendly, and it needs
  no parser beyond the standard library. JSON would add punctuation
  noise to 54 lines; YAML would add a dependency.

#### 4.2.2 `app/domain/constants.py`

```python
from datetime import date
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

DATA_DIR = Path(__file__).resolve().parent / "data"
COUNTRIES_FILE = DATA_DIR / "gggi_members.txt"


class Category(str, Enum):
    """The five climate technology categories from the assignment."""

    RENEWABLE_ENERGY = "renewable_energy"
    MRV = "mrv"
    SMART_GRID = "smart_grid"
    CLIMATE_RISK_MAPPING = "climate_risk_mapping"
    OTHER = "other"


CATEGORY_LABELS: dict[Category, str] = {
    Category.RENEWABLE_ENERGY: "Renewable Energy",
    Category.MRV: "Carbon Measurement (MRV)",
    Category.SMART_GRID: "Smart Grid",
    Category.CLIMATE_RISK_MAPPING: "Climate Risk Mapping",
    Category.OTHER: "Other",
}

CATEGORY_CHOICES: list[tuple[str, str]] = [
    (category.value, CATEGORY_LABELS[category]) for category in Category
]


class CountryRecord(NamedTuple):
    """One GGGI member country."""

    code: str
    name: str
    joined: date | None


@lru_cache(maxsize=1)
def load_countries() -> tuple[CountryRecord, ...]:
    """Read the curated GGGI member list, sorted by display name.

    The single seam between the rest of the application and where the
    country list physically lives. Today it parses a text file; when
    the list moves into a `countries` table this body becomes a query
    and no caller changes.
    """
    if not COUNTRIES_FILE.exists():
        raise FileNotFoundError(f"Country data file not found: {COUNTRIES_FILE}")

    records: list[CountryRecord] = []
    for line_number, raw in enumerate(
        COUNTRIES_FILE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            raise ValueError(
                f"{COUNTRIES_FILE.name} line {line_number}: "
                f"expected 3 pipe-separated fields, got {len(parts)}"
            )
        code, name, joined_raw = parts
        if len(code) != 2 or not code.isalpha() or code != code.upper():
            raise ValueError(
                f"{COUNTRIES_FILE.name} line {line_number}: "
                f"{code!r} is not an uppercase ISO 3166-1 alpha-2 code"
            )
        joined = date.fromisoformat(joined_raw) if joined_raw else None
        records.append(CountryRecord(code=code, name=name, joined=joined))

    if not records:
        raise ValueError(f"{COUNTRIES_FILE.name} contains no country records")

    return tuple(sorted(records, key=lambda record: record.name))


@lru_cache(maxsize=1)
def country_choices() -> list[tuple[str, str]]:
    """Ordered (code, display name) pairs for rendering <select> options."""
    return [(record.code, record.name) for record in load_countries()]


@lru_cache(maxsize=1)
def country_codes() -> frozenset[str]:
    """Every valid country code, for validation."""
    return frozenset(record.code for record in load_countries())


def country_label(code: str) -> str:
    """Display name for a stored country code; the code itself if unknown."""
    for record in load_countries():
        if record.code == code:
            return record.name
    return code


def category_label(code: str) -> str:
    """Display name for a stored category code; the code itself if unknown."""
    try:
        return CATEGORY_LABELS[Category(code)]
    except ValueError:
        return code
```

**Decisions fixed here**

- **The country list is data, not code**, and reaches the rest of the
  application only through `load_countries()`, `country_choices()`,
  and `country_codes()`. Nothing else opens the file, so §7's move to
  a SQL table rewrites three function bodies and touches nothing
  else.
- **There is no `Country` enum.** An enum is a compile-time
  vocabulary, and the point of this module is that the vocabulary is
  loaded at runtime. Building an enum dynamically from the file would
  work today and break the moment the list comes from a database that
  cannot be queried at import time. Country validation is therefore a
  membership check against `country_codes()` — see §4.8.
- **`@lru_cache` on the three loaders** means the file is read once
  per process. It is file-content caching, not a results cache, and
  it also gives tests a documented way to force a re-read via
  `load_countries.cache_clear()`.
- **Sorted by display name for the dropdown**, so a person scanning
  54 options finds a country where they expect it. The *file* stays
  in accession order so it diffs cleanly against the source document;
  the two orderings serve different readers and the sort is one line.
- **The parser validates as it reads and raises on a malformed
  line**, naming the file and line number. A typo in reference data
  should fail at startup with a precise message, not produce a
  dropdown that is silently missing a country.
- **Category members are declared in the assignment's own order**, so
  the form matches the brief exactly. Categories are *not* sorted
  alphabetically — "Other" belongs last, where the brief puts it.
- **`str, Enum` rather than plain `Enum`** for `Category`, so a member
  compares equal to its string value. This lets a template write
  `{% if value == "smart_grid" %}` and lets a member reach a
  SQLAlchemy filter without `.value`.
- **The label lookups return the raw code for an unknown value**
  rather than raising. A proposal stored against a country later
  removed from the file must still render rather than crash the whole
  list page.

---

### 4.3 Module 3 — `app/main.py`

**Summary**: the application object — mounts, routers, root redirect,
health check, and the HTML-aware error handler.

**Purpose**: one file that a reader can open to see the whole
application's surface. It composes the pieces and owns nothing else.

**Implementation**

- New file `app/main.py`:

  ```python
  from pathlib import Path

  from fastapi import FastAPI, Request
  from fastapi.responses import JSONResponse, RedirectResponse, Response
  from fastapi.staticfiles import StaticFiles
  from starlette.exceptions import HTTPException as StarletteHTTPException

  from app.api import proposals as api_proposals
  from app.config import get_settings
  from app.web import proposals as web_proposals
  from app.web.templates import templates

  STATIC_DIR = Path(__file__).resolve().parent / "static"

  settings = get_settings()

  app = FastAPI(
      title=settings.app_name,
      description=(
          "CTAF climate technology project proposal intake. "
          "The browser interface is served from /proposals; "
          "the read-only JSON API is documented below."
      ),
      version="1.0.0",
      docs_url="/docs",
      redoc_url=None,
  )

  app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
  app.include_router(web_proposals.router)
  app.include_router(api_proposals.router)


  @app.get("/", include_in_schema=False)
  def root() -> RedirectResponse:
      """Send the bare domain to the list page."""
      return RedirectResponse(url="/proposals", status_code=307)


  @app.get("/health", include_in_schema=False)
  def health() -> dict[str, str]:
      """Liveness probe used by the container and by smoke tests."""
      return {"status": "ok"}


  @app.exception_handler(StarletteHTTPException)
  def http_exception_handler(
      request: Request, exc: StarletteHTTPException
  ) -> Response:
      """Render HTML errors for browser routes; keep JSON for the API."""
      if request.url.path.startswith("/api"):
          return JSONResponse(
              status_code=exc.status_code, content={"detail": exc.detail}
          )
      return templates.TemplateResponse(
          request=request,
          name="error.html",
          context={"status_code": exc.status_code, "detail": exc.detail},
          status_code=exc.status_code,
      )
  ```

**Decisions fixed here**

- **`STATIC_DIR` is derived from `__file__`**, not written as the
  relative string `"app/static"`. A relative path resolves against
  the working directory, which differs between a laptop, a test
  runner, and a container, and produces a startup crash that is
  tedious to diagnose.
- **`/` redirects with `307`, not `302`.** For a `GET` the two are
  equivalent, but 307 preserves the method, so the behaviour cannot
  change if the root ever accepts something other than `GET`.
- **`redoc_url=None`.** One documentation UI (`/docs`) is enough;
  the second adds a route with no purpose here.
- **`include_in_schema=False`** on `/` and `/health` keeps the
  generated API documentation limited to the actual API.
- **The exception handler branches on the path prefix.** A person
  who mistypes a proposal URL gets a styled page consistent with the
  rest of the site; a program calling `/api/...` gets the JSON error
  shape it expects. Registering the handler on Starlette's
  `HTTPException` rather than FastAPI's catches errors raised inside
  Starlette itself, such as an unmatched route.
- **`templates.TemplateResponse(request=..., name=..., context=...)`**
  uses the keyword form throughout the codebase. The older positional
  form with `request` inside the context dict is deprecated in
  current Starlette and emits warnings.
- **Router inclusion order** — the web router is included before the
  API router. They share no path prefix, so order is not functionally
  significant; it is fixed here only for consistency.
- **Build order note.** During Phase 1 this file exists without the
  two router imports and without the exception handler, since the
  modules do not yet exist; the health route alone proves the setup
  works. The imports and handler are added in Phases 4 and 5 as their
  modules land. The listing above is the final state.

---

### 4.4 Module 4 — `app/db/session.py` and `app/db/bootstrap.py`

#### 4.4.1 `app/db/session.py`

**Summary**: the engine, the session factory, and the per-request
session dependency.

**Purpose**: a *session* is one conversation with the database.
Opening one when a request arrives and closing it when the request
ends — committing if everything succeeded, rolling back if anything
raised — is what makes a half-written proposal impossible. Centralising
this means no route ever writes transaction handling by hand.

**Implementation**

- New file `app/db/session.py`:

  ```python
  from collections.abc import Iterator

  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session, sessionmaker

  from app.config import get_settings

  engine = create_engine(
      get_settings().database_url,
      pool_pre_ping=True,
      future=True,
  )

  SessionLocal = sessionmaker(
      bind=engine,
      autoflush=False,
      autocommit=False,
      expire_on_commit=False,
  )


  def get_db() -> Iterator[Session]:
      """Yield one database session per request.

      Commits when the request handler returns normally, rolls back if
      it raised, and always closes the connection.
      """
      db = SessionLocal()
      try:
          yield db
          db.commit()
      except Exception:
          db.rollback()
          raise
      finally:
          db.close()
  ```

**Decisions fixed here**

- **`pool_pre_ping=True`** issues a trivial check before handing out
  a pooled connection. Without it, the first request after Postgres
  restarts — which happens routinely with `docker compose restart` —
  fails with a stale-connection error.
- **`expire_on_commit=False`** is the single most consequential
  setting in this file. By default SQLAlchemy marks every attribute
  stale after a commit, so reading `proposal.project_name` afterwards
  triggers a fresh `SELECT` — and if the session is already closed,
  raises `DetachedInstanceError`. Since `get_db()` commits *after*
  the route has built its response, templates would routinely hit
  that error. Disabling expiry keeps loaded values readable.
- **`autoflush=False`** makes writes explicit. The repository flushes
  where a flush is genuinely needed (to populate defaults) rather
  than SQLAlchemy issuing surprise writes mid-query.
- **The commit lives in `get_db()`, not in the repository.** One
  request is one transaction. A repository method that committed by
  itself would make a multi-step operation impossible to roll back as
  a unit.
- **The engine is created at import time** from `get_settings()`.
  Connections are lazy, so importing this module does not require a
  reachable database — which matters for `alembic` and for test
  collection.

#### 4.4.2 `app/db/bootstrap.py`

**Summary**: creates the database itself if it does not yet exist.

**Purpose**: `alembic upgrade head` creates *tables*, but it cannot
create the *database* those tables live in — it has to connect to
something before it can do anything, and connecting to a database
that does not exist fails. Normally the gap is closed by a person
typing `createdb ctaf`, which is one more instruction in a README
that can be missed. Closing it in code means a fresh Postgres server
needs no manual preparation: start the application and the database,
the schema, and the seed data all appear.

**Implementation**

- New file `app/db/bootstrap.py`:

  ```python
  import logging

  from sqlalchemy import create_engine, text
  from sqlalchemy.engine import make_url

  logger = logging.getLogger(__name__)


  def ensure_database_exists(database_url: str) -> bool:
      """Create the target database if the server does not already have it.

      Connects to the server's default `postgres` maintenance database,
      checks pg_catalog, and issues CREATE DATABASE when absent.

      Returns True if a database was created, False if it already existed.
      Raises if the server itself is unreachable — that is a real problem
      and must not be swallowed.
      """
      url = make_url(database_url)
      target = url.database
      if not target:
          raise ValueError(f"No database name in URL: {database_url}")

      admin_url = url.set(database="postgres")
      admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
      try:
          with admin_engine.connect() as connection:
              exists = connection.scalar(
                  text("SELECT 1 FROM pg_database WHERE datname = :name"),
                  {"name": target},
              )
              if exists:
                  return False
              connection.execute(text(f'CREATE DATABASE "{target}"'))
              logger.info("Created database %s", target)
              return True
      finally:
          admin_engine.dispose()
  ```

- Called from exactly three places:
  1. `scripts/entrypoint.sh` (§4.16.2), before `alembic upgrade head`.
  2. `scripts/seed.py` is unaffected — by the time it runs the
     database exists.
  3. `tests/conftest.py` (§4.17), so `ctaf_test` is created
     automatically rather than by a documented manual step.

**Decisions fixed here**

- **It connects to the `postgres` maintenance database**, which every
  Postgres server has, because there is nowhere else to stand while
  asking whether a database exists.
- **`isolation_level="AUTOCOMMIT"` is required, not stylistic.**
  Postgres refuses to run `CREATE DATABASE` inside a transaction
  block, and SQLAlchemy opens one by default. Without this the call
  fails with `CREATE DATABASE cannot run inside a transaction block`.
- **The database name is interpolated into the statement**, which is
  the one place in this codebase where a value is not a bound
  parameter — Postgres does not accept a parameter in that position.
  The name is quoted with double quotes and comes from the
  application's own configuration rather than from user input, so
  there is no injection surface. This exception is called out here
  precisely because "never build SQL by string" is otherwise an
  absolute rule in this project.
- **It checks before creating** rather than catching a
  "already exists" error, so a normal start produces no error at all
  in the logs and the function can report which case occurred.
- **An unreachable server still raises.** The function's job is a
  missing *database*, not a missing *server*; hiding a connection
  failure here would turn a clear error into a confusing one further
  along.
- **It does not run at application import or startup.** Creating
  databases is a deployment action, and every worker process
  importing the app would race. The entrypoint runs it once before
  anything else starts.

---

### 4.5 Module 5 — `app/db/models.py`

**Summary**: the `proposals` table expressed as a Python class.

**Purpose**: SQLAlchemy writes the SQL from this description. Two
things follow. The editor catches a misspelled column name before the
code runs. And every value reaches the database as a bound parameter
rather than as text spliced into a query string, which makes SQL
injection — typing `'; DROP TABLE proposals; --` into the project
name box — structurally impossible rather than a thing to remember to
defend against.

**Implementation**

- New file `app/db/models.py`:

  ```python
  import uuid
  from datetime import date, datetime
  from decimal import Decimal

  from sqlalchemy import Date, DateTime, Numeric, String, Text, func
  from sqlalchemy.dialects.postgresql import UUID as PgUUID
  from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


  class Base(DeclarativeBase):
      """Declarative base; Alembic reads Base.metadata to autogenerate."""


  class Proposal(Base):
      """One climate technology project proposal."""

      __tablename__ = "proposals"

      id: Mapped[uuid.UUID] = mapped_column(
          PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
      )
      project_name: Mapped[str] = mapped_column(String(200), nullable=False)
      country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
      category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
      budget_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
      start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
      summary: Mapped[str] = mapped_column(Text, nullable=False)
      owner_id: Mapped[uuid.UUID | None] = mapped_column(
          PgUUID(as_uuid=True), nullable=True
      )
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True),
          server_default=func.now(),
          onupdate=func.now(),
          nullable=False,
      )
      deleted_at: Mapped[datetime | None] = mapped_column(
          DateTime(timezone=True), nullable=True, index=True
      )

      def __repr__(self) -> str:
          return f"<Proposal {self.id} {self.project_name!r}>"
  ```

**Column decisions**

| Column | Type | Why this type |
|---|---|---|
| `id` | `UUID` | A long random identifier rather than 1, 2, 3. Sequential integers in URLs disclose how many proposals exist and invite guessing at neighbouring records. Generated in Python via `default=uuid.uuid4` so the value is known before the row is written. |
| `project_name` | `VARCHAR(200)` | Bounded at the database, matching the schema's `max_length=200`. A length the database enforces is one that survives a bug in the application. |
| `country` | `CHAR-width VARCHAR(2)`, indexed | The ISO code, not the display name, so wording can change without touching stored data. Indexed because it is filtered on. |
| `category` | `VARCHAR(32)`, indexed | Stored as a plain string rather than a native Postgres `ENUM` type. A native enum means an `ALTER TYPE` migration to add a category, and psycopg-level friction; a string plus the Pydantic enum gives the same guarantee with none of that. Indexed because it is filtered on. |
| `budget_usd` | `NUMERIC(15, 2)` | Money is never a float. Binary floating point stores 0.1 approximately, and the error compounds across arithmetic. `NUMERIC` stores the exact decimal. 15 digits with 2 after the point allows up to 9,999,999,999,999.99 — far beyond any plausible project budget. |
| `start_date` | `DATE`, nullable | The assignment does not mark it required, so it is genuinely optional. |
| `summary` | `TEXT`, `NOT NULL` | Unbounded at the database; the 300-character limit is a rule of the application, not of storage, and is enforced by the schema. The field is **optional** (§4.8), and an absent summary is stored as the empty string rather than `NULL`, so there is exactly one representation of "no summary". |
| `owner_id` | `UUID`, nullable | Empty today. If user accounts are added later there would be no way to reconstruct who created rows written before the column existed. Adding it now costs one nullable column and keeps that door open. |
| `created_at` | `TIMESTAMPTZ` | `server_default=func.now()` — the database stamps it, so the value cannot drift with an application server's clock. |
| `updated_at` | `TIMESTAMPTZ` | `onupdate=func.now()` — SQLAlchemy re-stamps it on every `UPDATE` this application issues. |
| `deleted_at` | `TIMESTAMPTZ`, nullable, indexed | `NULL` means live. Indexed because *every single read* filters on it. |

**On soft delete.** Deleting sets `deleted_at` to the current time
rather than removing the row. Every read excludes non-null
`deleted_at`, so to a user the proposal has vanished; on disk it is
intact, so an accidental deletion is recoverable and there is a
record of what happened. This is standard practice for anything a
person might regret deleting, and it is why the delete route is
described as a delete throughout the interface while never issuing a
SQL `DELETE`.

**On uniqueness.** No `UNIQUE` constraint is placed on
`project_name`. The rule is *"no two live proposals share a name"*,
and a plain unique index would also collide with soft-deleted rows,
making a name unusable forever after its proposal was deleted. The
rule is therefore enforced in the service layer against live rows
only — see §4.10. A partial unique index
(`WHERE deleted_at IS NULL`) would express this in the database and
is listed in §7 as a future addition.

---

### 4.6 Module 6 — `migrations/` (Alembic)

**Summary**: the database's schema history as a folder of small
numbered Python scripts.

**Purpose**: the table exists in the database with a fixed set of
columns. When a column is later added to the Python class, the
database does not know about it and saving breaks. Alembic compares
the classes to the live database, writes a script describing the
difference, and records which scripts have been applied. Because the
scripts are committed to git alongside the code, any copy of the
database — a colleague's, the container's, the test database — is
brought up to date by running the same sequence.

**Implementation**

1. Run `alembic init migrations` from the project root. This creates
   `alembic.ini` and the `migrations/` directory containing `env.py`,
   `script.py.mako`, and an empty `versions/`.

2. Edit `alembic.ini`:
   - Set `script_location = migrations`.
   - **Delete the value of `sqlalchemy.url`**, leaving
     `sqlalchemy.url =`. The URL is supplied from `Settings` in
     `env.py` instead, so the connection string exists in exactly one
     place and no credential is written into a tracked file.

3. Replace the configuration section of `migrations/env.py` with:

   ```python
   from logging.config import fileConfig

   from alembic import context
   from sqlalchemy import engine_from_config, pool

   from app.config import get_settings
   from app.db.models import Base

   config = context.config
   config.set_main_option("sqlalchemy.url", get_settings().database_url)

   if config.config_file_name is not None:
       fileConfig(config.config_file_name)

   target_metadata = Base.metadata
   ```

   The rest of the generated `run_migrations_offline()` and
   `run_migrations_online()` functions are left untouched.

4. Ensure Alembic can import the `app` package. Add to
   `alembic.ini`, under `[alembic]`:

   ```
   prepend_sys_path = .
   ```

   Newer Alembic templates include this already; confirm rather than
   assume, since without it `from app.config import ...` fails when
   `alembic` runs from the project root.

5. With Postgres running, generate the first migration:

   ```
   alembic revision --autogenerate -m "create proposals table"
   ```

6. **Read the generated script before applying it.** The expected
   content is one `op.create_table("proposals", ...)` with all eleven
   columns, followed by three `op.create_index` calls for `country`,
   `category`, and `deleted_at`. Anything else means `env.py` is
   pointed at the wrong metadata or at a database that already has
   objects in it.

   > Alembic reliably detects added and removed columns but gets
   > *renames* wrong, because a rename is indistinguishable from a
   > drop plus an add. Every autogenerated script is reviewed before
   > it is applied.

7. Apply it: `alembic upgrade head`.

8. Confirm with `psql`:

   ```sql
   \d proposals
   ```

   Eleven columns and three indexes plus the primary key.

**Decisions fixed here**

- **The migration file is committed**, including the generated
  revision identifier. The reviewer's database is built by replaying
  it, not by `Base.metadata.create_all()`, so the committed migration
  is the one path that is actually exercised.
- **`create_all()` is used in exactly one place** — the test fixture
  in §4.17, where speed matters more than replaying history, and
  where the schema under test comes from the same `Base.metadata`
  that generated the migration.
- **Migrations are applied by the container entrypoint** (§4.16), not
  by application startup code. Schema changes belong to deployment,
  not to request handling; running them at import time would mean
  every worker process racing to migrate the same database.

---

### 4.7 Module 7 — `app/db/repository.py`

**Summary**: one class containing every database query in the
application.

**Purpose**: if queries are scattered through routes and services,
changing anything about how data is stored means hunting through the
whole codebase. Holding them in one class means one file to open —
and it is what makes the soft-delete rule enforceable, because
"every read filters `deleted_at IS NULL`" is a claim that can be
verified by reading a single file.

**Implementation**

- New file `app/db/repository.py`:

  ```python
  from datetime import datetime, timezone
  from typing import Any
  from uuid import UUID

  from sqlalchemy import func, select
  from sqlalchemy.orm import Session

  from app.db.models import Proposal


  class ProposalRepository:
      """Every query against the proposals table.

      All reads exclude soft-deleted rows. Methods flush but never
      commit; the transaction is owned by get_db().
      """

      def __init__(self, db: Session) -> None:
          self.db = db

      def add(self, proposal: Proposal) -> Proposal:
          """Insert a proposal and return it with database defaults populated."""
          self.db.add(proposal)
          self.db.flush()
          self.db.refresh(proposal)
          return proposal

      def get(self, proposal_id: UUID) -> Proposal | None:
          """Fetch one live proposal, or None if absent or deleted."""
          stmt = select(Proposal).where(
              Proposal.id == proposal_id,
              Proposal.deleted_at.is_(None),
          )
          return self.db.scalars(stmt).one_or_none()

      def list(
          self,
          country: str | None = None,
          category: str | None = None,
      ) -> list[Proposal]:
          """List live proposals, newest first, optionally filtered."""
          stmt = select(Proposal).where(Proposal.deleted_at.is_(None))
          if country:
              stmt = stmt.where(Proposal.country == country)
          if category:
              stmt = stmt.where(Proposal.category == category)
          stmt = stmt.order_by(Proposal.created_at.desc(), Proposal.id.desc())
          return list(self.db.scalars(stmt))

      def exists_with_name(
          self,
          project_name: str,
          exclude_id: UUID | None = None,
      ) -> bool:
          """Whether a live proposal already uses this name, case-insensitively."""
          stmt = select(func.count()).select_from(Proposal).where(
              func.lower(Proposal.project_name) == project_name.strip().lower(),
              Proposal.deleted_at.is_(None),
          )
          if exclude_id is not None:
              stmt = stmt.where(Proposal.id != exclude_id)
          return bool(self.db.scalar(stmt))

      def update(self, proposal: Proposal, fields: dict[str, Any]) -> Proposal:
          """Apply changed fields to a proposal already attached to the session."""
          for name, value in fields.items():
              setattr(proposal, name, value)
          self.db.flush()
          self.db.refresh(proposal)
          return proposal

      def soft_delete(self, proposal: Proposal) -> None:
          """Mark a proposal deleted without removing the row."""
          proposal.deleted_at = datetime.now(timezone.utc)
          self.db.flush()
  ```

**Decisions fixed here**

- **Filters are composed conditionally.** When `country` is absent,
  the condition is simply not added — Postgres does the filtering,
  using the indexes, instead of every row being loaded into Python
  and filtered there.
- **The tie-break `Proposal.id.desc()`** is appended to the ordering.
  Ten seeded rows can share a `created_at` value to microsecond
  precision, and without a tie-break the list order would vary
  between page loads, which would make list-ordering assertions in
  §6 flaky.
- **`exists_with_name` is case-insensitive** via `func.lower(...)` on
  both sides. Two proposals called "Solar Mini-Grid" and "solar
  mini-grid" are the same proposal as far as a reviewer is concerned.
  It also strips the incoming name, matching the schema's stripping,
  so trailing whitespace cannot be used to sidestep the rule.
- **`exclude_id`** exists for editing: saving a proposal without
  changing its name must not report the proposal as a duplicate of
  itself.
- **`exists_with_name` counts rather than fetching.** Only the answer
  to a yes/no question is needed; loading the row would be wasted
  work.
- **`get` returns `None` rather than raising.** Deciding that a
  missing proposal is an error is a domain judgement, so it belongs
  in the service layer, which raises `ProposalNotFoundError`. This
  keeps the repository purely mechanical.
- **`update` takes a plain `dict` rather than `**kwargs`.** The
  caller has a dictionary from `model_dump()`; passing it as a
  dictionary avoids a name in the data silently colliding with a
  parameter name.
- **`flush()` then `refresh()`, never `commit()`.** Flush sends the
  `INSERT` so database defaults are computed; refresh reads back
  `created_at` and `updated_at`. Commit belongs to `get_db()`, so
  one request remains one transaction.
- **No `hard_delete` method.** Nothing in the application removes a
  row. Purging is an administrative act, described in §7.

---

### 4.8 Module 8 — `app/schemas/proposal.py`

**Summary**: Pydantic classes describing valid data, plus the
translator that turns validation failures into messages a person can
read.

**Purpose**: everything arriving from a browser is text. `"50000"` is
a string, not a number; `"banana"` may arrive where a budget was
expected; an empty date field arrives as `""` rather than as nothing
at all. Something must check and convert before the rest of the code
touches the values, and it must do so in a way that cannot be
circumvented. The browser's `required` and `maxlength` attributes run
on someone else's computer and can be deleted from developer tools in
seconds; this file is the check that always runs.

**Implementation**

- New file `app/schemas/proposal.py`:

  ```python
  from datetime import date, datetime
  from decimal import Decimal
  from typing import Annotated, Any
  from uuid import UUID

  from pydantic import (
      AfterValidator,
      BaseModel,
      ConfigDict,
      Field,
      ValidationError,
      field_validator,
  )

  from app.domain.constants import Category, country_codes


  def _known_country(code: str) -> str:
      """Reject a country code that is not a current GGGI member."""
      normalised = code.strip().upper()
      if normalised not in country_codes():
          raise ValueError("Unknown country code")
      return normalised


  CountryCode = Annotated[str, AfterValidator(_known_country)]


  class ProposalBase(BaseModel):
      """Fields and rules shared by creation and editing."""

      model_config = ConfigDict(str_strip_whitespace=True)

      project_name: str = Field(min_length=1, max_length=200)
      country: CountryCode
      category: Category
      budget_usd: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
      start_date: date | None = None
      summary: str = Field(default="", max_length=300)

      @field_validator("start_date", mode="before")
      @classmethod
      def _empty_string_is_no_date(cls, value: Any) -> Any:
          """An untouched date input posts "", which means 'not provided'."""
          if isinstance(value, str) and not value.strip():
              return None
          return value

      @field_validator("budget_usd", mode="before")
      @classmethod
      def _normalise_budget(cls, value: Any) -> Any:
          """Strip thousands separators and surrounding spaces before parsing."""
          if isinstance(value, str):
              return value.strip().replace(",", "")
          return value


  class ProposalCreate(ProposalBase):
      """Validated payload for creating a proposal."""


  class ProposalUpdate(ProposalBase):
      """Validated payload for editing a proposal. Same rules as creation."""


  class ProposalRead(BaseModel):
      """What the JSON API returns."""

      model_config = ConfigDict(from_attributes=True)

      id: UUID
      project_name: str
      country: str
      category: str
      budget_usd: Decimal
      start_date: date | None
      summary: str
      created_at: datetime
      updated_at: datetime


  _ERROR_MESSAGES: dict[tuple[str, str], str] = {
      ("project_name", "missing"): "Project name is required.",
      ("project_name", "string_too_short"): "Project name is required.",
      ("project_name", "string_too_long"): "Project name must be 200 characters or fewer.",
      ("country", "missing"): "Select a target country.",
      ("country", "value_error"): "Select a target country from the list.",
      ("country", "string_type"): "Select a target country from the list.",
      ("category", "missing"): "Select a climate technology category.",
      ("category", "enum"): "Select a climate technology category from the list.",
      ("budget_usd", "missing"): "Estimated budget is required.",
      ("budget_usd", "decimal_parsing"): "Estimated budget must be a number.",
      ("budget_usd", "greater_than"): "Estimated budget must be greater than zero.",
      ("budget_usd", "decimal_max_places"): "Estimated budget may have at most 2 decimal places.",
      ("budget_usd", "decimal_whole_digits"): "Estimated budget is too large.",
      ("budget_usd", "decimal_max_digits"): "Estimated budget is too large.",
      ("start_date", "date_parsing"): "Planned start date must be a valid date.",
      ("start_date", "date_from_datetime_parsing"): "Planned start date must be a valid date.",
      ("start_date", "date_type"): "Planned start date must be a valid date.",
      ("summary", "string_too_long"): "Project summary must be 300 characters or fewer.",
  }

  _FALLBACK_MESSAGES: dict[str, str] = {
      "project_name": "Please check the project name.",
      "country": "Please choose a target country.",
      "category": "Please choose a climate technology category.",
      "budget_usd": "Please enter a valid budget in USD.",
      "start_date": "Please enter a valid start date.",
      "summary": "Please check the project summary.",
  }


  def format_errors(exc: ValidationError) -> dict[str, str]:
      """Turn a ValidationError into {field name: one plain-English message}.

      Only the first error per field is kept — the form shows one
      message beneath each input.
      """
      messages: dict[str, str] = {}
      for error in exc.errors():
          location = error.get("loc") or ()
          field = str(location[0]) if location else "_form"
          if field in messages:
              continue
          key = (field, str(error.get("type", "")))
          messages[field] = _ERROR_MESSAGES.get(
              key,
              _FALLBACK_MESSAGES.get(field, "This value is not valid."),
          )
      return messages
  ```

**How each assignment rule maps to this file**

| Assignment rule | Expressed as |
|---|---|
| Project name required | `min_length=1` plus `str_strip_whitespace=True`, so `"   "` is rejected rather than stored as blank |
| Target country from a list of ≥5 | typed as `CountryCode`, an `Annotated[str, AfterValidator(...)]` checking membership in `country_codes()`; anything outside the 54 GGGI members fails with error type `value_error` |
| Category from the five given options | typed as `Category`; same mechanism |
| Budget required and positive | `Decimal` with `gt=0`; missing, non-numeric, zero, and negative each produce a distinct error type and therefore a distinct message |
| Start date optional | `date | None = None` plus the `""` → `None` coercion |
| Summary at most 300 characters | `max_length=300`, and nothing more — see the requiredness table below |

**Which fields are required, and on whose authority**

The assignment marks exactly two fields required. Everything else is
a judgement call, so each one is recorded here rather than left
implicit in the code:

| Field | Required? | Authority |
|---|---|---|
| `project_name` | **Yes** | The assignment: *"Project Name (text, required)"* |
| `budget_usd` | **Yes** | The assignment: *"Estimated Budget in USD (number, required)"* |
| `country` | **Yes** | *Design decision.* Not marked required in the brief, but the brief separately requires *"a filter on the list page by Country or by Technology Category"*. A proposal stored with no country cannot be reached by that filter and cannot be excluded by it either — it becomes a row that is visible unfiltered and invisible the moment anyone filters. Requiring the field is what makes the filtering requirement coherent. |
| `category` | **Yes** | *Design decision*, same reasoning as `country`. |
| `start_date` | **No** | The assignment lists it as *"Planned Start Date (date)"* with no required marker, and a planned date is genuinely often unknown at submission. |
| `summary` | **No** | The assignment lists it as *"Project Summary (multi-line text, max 300 characters)"*. It constrains the maximum and says nothing about a minimum. The field is therefore optional, and the only rule enforced is the 300-character ceiling. |

The principle behind that table: where the brief is explicit it is
followed exactly, and where a field is unmarked it stays optional
unless leaving it optional would break another stated requirement —
as it would for the two filter dropdowns. Requiring a field the brief
did not require is an assumption, so any such case is argued above
rather than silently encoded.

**Decisions fixed here**

- **The country is re-checked on the server even though the form
  offers a dropdown.** A `<select>` is not a gate. It is HTML the
  server sent to someone else's computer, and it constrains only the
  people who use it as intended: right-click, Inspect, change
  `value="KE"` to `value="ZZ"`, submit — ten seconds, no tools
  installed. A request sent with `curl` has no dropdown in it at all.
  This is the same argument the plan already makes for `maxlength`
  and `required`, and a dropdown deserves it more rather than less,
  precisely because it *feels* like it has already foreclosed the
  possibility.

  The form is also not the main reason. A country code reaches the
  application from four places and only one of them is a dropdown:
  the form (`POST /proposals`), the filter query string
  (`GET /proposals?country=…`, typed by hand), the JSON API
  (`GET /api/proposals?country=…`, called by a program), and
  `scripts/seed.py` (a Python literal — which is where the India
  error in §4.15 was caught).

  What skipping the check would cost is worth being concrete about,
  because it is not a crash. A row stored with `country="ZZ"`
  renders fine: `country_label` falls back to the raw code, so the
  table shows a proposal labelled "ZZ". No filter option matches it,
  because the dropdown only offers real members. The row is visible
  in the unfiltered list and unreachable by every filter. Invalid
  input is transient; invalid *data* is permanent, and this is the
  variety that hides.

- **The validation costs almost nothing, because the module had to
  exist regardless.** `load_countries()` and `country_choices()` are
  needed to populate the dropdown at all — Jinja must be handed a
  list to loop over. `country_codes()` is six lines reusing the list
  already in memory. Validation is a free rider on a module built for
  presentation, which is also why the dropdown and the validator can
  never disagree about what a valid country is: there is one list.

- **`country` is validated by function, not by enum type**, because
  the country list is runtime data loaded from a file (§4.2) and will
  later come from a table. `AfterValidator` runs the same membership
  check wherever the type is used, and the check reads its list
  through `country_codes()`, so the move to SQL changes nothing here.
  The validator also upper-cases the code, so a hand-written `ke`
  from a command-line request is accepted and stored as `KE`.
- **A raised `ValueError` inside `AfterValidator` surfaces as error
  type `value_error`**, which is the key `format_errors` maps. This
  differs from an enum field's `enum` type, and getting it wrong
  means the country message silently falls through to the generic
  fallback — worth verifying with test S-16.
- **`str_strip_whitespace=True` is set at model level** rather than
  as a per-field validator. It applies to `project_name` and
  `summary`. On `project_name` it is what makes `min_length=1` mean
  "has actual content" rather than "has any characters at all". On
  `summary` it normalises a textarea containing only whitespace to
  `""`, so there is one representation of "no summary" rather than
  two.
- **`summary` defaults to `""`, not to `None`.** The column stays
  `NOT NULL` and an absent summary is stored as the empty string.
  Allowing both `NULL` and `""` in a text column creates two ways to
  say the same thing, and then every read has to check for both. One
  empty value is simpler, and `str_strip_whitespace` guarantees
  whitespace collapses into it.
- **The budget pre-validator strips commas.** A person typing
  `250,000` is entering a plausible budget, and rejecting it as
  unparseable would be needlessly hostile. Stripping the separator
  before parsing is a small kindness that costs two lines.
- **The date pre-validator is mandatory, not cosmetic.** An untouched
  `<input type="date">` posts an empty string. Without this
  coercion, every proposal submitted without a start date would be
  rejected with an unintelligible date-parsing error — and the field
  is explicitly optional.
- **`format_errors` maps `(field, error_type)` pairs**, not field
  names alone. `""`, `"abc"`, `"0"`, and `"-5"` in the budget box are
  four different mistakes and deserve four different messages;
  keying on the field alone could only produce one.
- **A two-level fallback.** An unmapped error type falls back to a
  per-field message, and an unknown field to a generic one. Pydantic's
  own `msg` is never shown, because its wording ("Input should be
  greater than 0") reads as a machine talking to a machine.
- **Only the first error per field is kept.** The form renders one
  message beneath each input; a list would complicate the template
  for no gain.
- **`ProposalUpdate` is a distinct class** even though it currently
  adds nothing to `ProposalBase`. It is the natural home for any rule
  that eventually differs between creating and editing, and its
  presence makes the route signatures self-documenting.
- **`ProposalRead` restates its fields rather than inheriting.** It
  is a different shape — it has `id` and timestamps, and its
  `country` and `category` are plain strings, because the API returns
  the stored code and a consumer should not have to know the Python
  enum. Inheriting would drag the input rules into an output model
  where they mean nothing.
- **`ProposalRead` omits `deleted_at` and `owner_id`.** Deleted rows
  are never returned, so the field would always be null; `owner_id` is
  unused. Neither belongs in a public response shape.

**Also in this module — `app/schemas/country.py`**

One small model, used only by `GET /api/countries` (§4.14):

```python
from datetime import date

from pydantic import BaseModel


class CountryOut(BaseModel):
    """A GGGI member country as returned by the API."""

    code: str
    name: str
    joined: date | None
```

It lives in its own file rather than in `proposal.py` because it
describes a different thing, and because when the country list moves
into a SQL table (§7) this is the shape that table's rows will be
serialised as.

---

### 4.9 Module 9 — `app/services/errors.py`

**Summary**: the two exceptions the domain can raise.

**Purpose**: a service function must be able to say "that name is
already taken" without knowing that a web page exists or that HTTP has
a status code numbered 409. Defining the failure in domain vocabulary
lets the route decide the presentation, and lets a future caller — a
spreadsheet importer, a command-line tool — decide differently.

**Implementation**

- New file `app/services/errors.py`:

  ```python
  from uuid import UUID


  class ProposalError(Exception):
      """Base class for every proposal rule violation."""


  class DuplicateProposalError(ProposalError):
      """Raised when a live proposal already uses the requested name."""

      def __init__(self, project_name: str) -> None:
          self.project_name = project_name
          super().__init__(
              f"A proposal named {project_name!r} already exists."
          )


  class ProposalNotFoundError(ProposalError):
      """Raised when the requested proposal does not exist or was deleted."""

      def __init__(self, proposal_id: UUID) -> None:
          self.proposal_id = proposal_id
          super().__init__(f"No proposal with id {proposal_id}.")
  ```

**Decisions fixed here**

- **A shared `ProposalError` base** so a caller may catch every
  domain failure with one `except` clause.
- **Each exception keeps the offending value as an attribute.** The
  route needs `project_name` to attach the message to the right form
  field; digging it back out of the formatted string would be
  fragile.
- **`ProposalNotFoundError` is raised, not returned as `None`.** A
  route that forgets to check a returned `None` renders a page with a
  missing proposal and fails confusingly further along; an
  unhandled exception fails immediately and visibly.

---

### 4.10 Module 10 — `app/services/proposal.py`

**Summary**: five functions holding every rule about proposals.

**Purpose**: some logic is neither about the shape of a field nor
about the database. "No two live proposals may share a name" is a
rule about *this application*, and it needs a home that is not
tangled up with web code. Keeping it here means it can be tested in
a fraction of a second without a web server, and called from
somewhere other than a web page later without modification.

**Implementation**

- New file `app/services/proposal.py`:

  ```python
  from uuid import UUID, uuid4

  from app.db.models import Proposal
  from app.db.repository import ProposalRepository
  from app.schemas.proposal import ProposalCreate, ProposalUpdate
  from app.services.errors import DuplicateProposalError, ProposalNotFoundError


  def create_proposal(
      data: ProposalCreate, repo: ProposalRepository
  ) -> Proposal:
      """Create a proposal, rejecting a name already in live use."""
      if repo.exists_with_name(data.project_name):
          raise DuplicateProposalError(data.project_name)
      proposal = Proposal(
          id=uuid4(),
          project_name=data.project_name,
          country=data.country,
          category=data.category.value,
          budget_usd=data.budget_usd,
          start_date=data.start_date,
          summary=data.summary,
      )
      return repo.add(proposal)


  def get_proposal(proposal_id: UUID, repo: ProposalRepository) -> Proposal:
      """Fetch one live proposal or raise ProposalNotFoundError."""
      proposal = repo.get(proposal_id)
      if proposal is None:
          raise ProposalNotFoundError(proposal_id)
      return proposal


  def list_proposals(
      repo: ProposalRepository,
      country: str | None = None,
      category: str | None = None,
  ) -> list[Proposal]:
      """List live proposals, newest first, optionally filtered."""
      return repo.list(country=country, category=category)


  def update_proposal(
      proposal_id: UUID, data: ProposalUpdate, repo: ProposalRepository
  ) -> Proposal:
      """Edit a proposal, rejecting a name another live proposal uses."""
      proposal = get_proposal(proposal_id, repo)
      if repo.exists_with_name(data.project_name, exclude_id=proposal_id):
          raise DuplicateProposalError(data.project_name)
      return repo.update(
          proposal,
          {
              "project_name": data.project_name,
              "country": data.country,
              "category": data.category.value,
              "budget_usd": data.budget_usd,
              "start_date": data.start_date,
              "summary": data.summary,
          },
      )


  def delete_proposal(proposal_id: UUID, repo: ProposalRepository) -> None:
      """Soft-delete a proposal."""
      proposal = get_proposal(proposal_id, repo)
      repo.soft_delete(proposal)
  ```

**Decisions fixed here**

- **Nothing about HTTP and nothing about SQL appears in this file.**
  That is the test of whether the layer is doing its job.
- **Fields are assigned explicitly rather than via
  `**data.model_dump()`.** `category` is an enum member and must be
  unwrapped to `.value` before reaching its string column, while
  `country` is already a plain validated string; an explicit list
  makes that asymmetry visible and means a new schema field cannot
  silently flow into the model without a deliberate edit here.
- **`update_proposal` calls `get_proposal` first**, so editing a
  deleted or non-existent proposal raises `ProposalNotFoundError`
  rather than the duplicate check running against nothing.
- **The duplicate check in `update_proposal` passes
  `exclude_id`**, so saving a proposal without renaming it does not
  report the proposal as a duplicate of itself.
- **`delete_proposal` fetches before deleting**, so deleting twice —
  a double-clicked button, a re-submitted form — produces a clean
  404 rather than silently doing nothing.
- **`list_proposals` is a thin pass-through today.** It exists so
  that the routes depend on the service layer uniformly; when
  pagination or sorting arrives, it changes here and no route moves.

---

### 4.11 Module 11 — `app/templates/` and `app/web/templates.py`

**Summary**: five Jinja templates and the configured environment that
renders them.

**Purpose**: the list page must show every proposal in a table, and
how many there will be is unknowable in advance. A template lets the
shape of a row be written once and repeated per proposal. Configuring
the environment in one module means the country and category
vocabularies and the formatting rules for money and dates are defined
once rather than repeated in every route.

#### 4.11.1 `app/web/templates.py`

```python
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.domain.constants import (
    CATEGORY_CHOICES,
    category_label,
    country_choices,
    country_label,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _money(value: Decimal | None) -> str:
    """Render a budget as USD with thousands separators."""
    if value is None:
        return "—"
    return f"${value:,.2f}"


def _date_display(value: date | None) -> str:
    """Render a date as 05 Mar 2026, or an em dash when absent."""
    if value is None:
        return "—"
    return value.strftime("%d %b %Y")


def _date_input(value: date | None) -> str:
    """Render a date as YYYY-MM-DD for <input type="date">."""
    if value is None:
        return ""
    return value.isoformat()


templates.env.globals["country_choices"] = country_choices()
templates.env.globals["category_choices"] = CATEGORY_CHOICES
templates.env.globals["app_name"] = "CTAF Proposal Portal"
templates.env.filters["country_label"] = country_label
templates.env.filters["category_label"] = category_label
templates.env.filters["money"] = _money
templates.env.filters["date_display"] = _date_display
templates.env.filters["date_input"] = _date_input
```

**Decisions fixed here**

- **`TEMPLATES_DIR` is derived from `__file__`**, for the same
  working-directory reason as `STATIC_DIR` in §4.3.
- **The dropdowns are populated from the curated vocabulary, not
  from `SELECT DISTINCT` over the proposals.** A filter list built
  from the stored data would hide a country until a proposal existed
  for it and would change shape as rows come and go. The GGGI member
  list is stable and matches the submission form exactly.
- **`country_choices()` is called once at import**, since it is
  `@lru_cache`d and the file does not change while the process runs.
  When the list moves to a SQL table (§7) this line becomes a
  per-request call or an explicitly refreshed cache; it is noted here
  because it is the one place the current design assumes the
  vocabulary is static for the process lifetime.
- **Two separate date filters.** A person reads `05 Mar 2026`; an
  `<input type="date">` requires `2026-03-05` and silently renders
  blank given anything else. Conflating them would leave the edit
  form's date box mysteriously empty.
- **Autoescaping is on** — Jinja2Templates enables it for `.html` by
  default. Every value interpolated into a page is HTML-escaped, so a
  project summary containing `<script>` is displayed as text rather
  than executed. This is the cross-site-scripting defence and it is
  never disabled; `|safe` appears nowhere in these templates.
- **Autoescaping is sufficient only because no template contains an
  inline event handler.** HTML escaping is the correct escaping for
  an HTML context, and the wrong escaping for a JavaScript one — an
  `onsubmit` or `onclick` attribute is an escape hatch out of the
  guarantee above, because the HTML parser decodes entities before
  the JavaScript parser reads what remains. The rule for this
  codebase is therefore absolute: **no `on…=` attributes anywhere**.
  Values needed by scripts travel as `data-` attributes and are read
  with `getAttribute()`. §4.11.5 works through the concrete attack
  this prevents; tests W-27 and W-28 enforce it.

#### 4.11.2 `app/templates/base.html`

The shared shell every other template extends.

- `<!DOCTYPE html>`, `<html lang="en">`, `<meta charset="utf-8">`,
  `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- `<title>{% block title %}{{ app_name }}{% endblock %}</title>`.
- `<link rel="stylesheet" href="/static/style.css">`.
- `<header class="site-header">` containing the app name linking to
  `/proposals`, and a `<nav>` with two links: **All proposals**
  (`/proposals`) and **New proposal** (`/proposals/new`).
- `<main class="container">{% block content %}{% endblock %}</main>`.
- `<footer class="site-footer">` with a single line naming the
  assignment reference.
- `{% block scripts %}{% endblock %}` immediately before `</body>`,
  so page-specific scripts load after the markup they operate on.

#### 4.11.3 `app/templates/form.html`

One template serving both creation and editing, because an edit form
is the same form with the boxes already filled in.

**Context it is rendered with**, in every case:

| Variable | Type | Meaning |
|---|---|---|
| `mode` | `"create"` or `"edit"` | Chooses the heading and the button label |
| `action` | `str` | The URL the form posts to |
| `values` | `dict[str, str]` | What to put in each box — submitted values on a failed attempt, existing values when editing, empty on a fresh form |
| `errors` | `dict[str, str]` | Field name → message; empty on a fresh form |
| `proposal` | `Proposal | None` | Present only when editing; used for the Cancel link |

**Structure**

- Extends `base.html`.
- `<h1>` reads "Submit a proposal" or "Edit proposal" from `mode`.
- `<form method="post" action="{{ action }}" class="proposal-form">`.

  **The form carries no `novalidate` attribute.** `novalidate` is a
  boolean HTML attribute: the browser disables native validation
  whenever the attribute is *present*, regardless of what it is set
  to. `novalidate="false"` therefore switches validation off just as
  effectively as `novalidate` alone — the string `"false"` is never
  read. Writing it would silently defeat every `required`, `min`,
  `step`, and `maxlength` check specified below, leaving the server
  checks in §4.8 as the only line of defence and making the form
  behave nothing like this document describes. The attribute must be
  **absent**, not set to a falsy value.
- Six field groups, each following an identical pattern:

  ```html
  <div class="field{% if errors.project_name %} field-invalid{% endif %}">
    <label for="project_name">Project name <span class="required">*</span></label>
    <input type="text" id="project_name" name="project_name"
           value="{{ values.project_name | default('') }}"
           maxlength="200" required
           {% if errors.project_name %}aria-invalid="true"
           aria-describedby="project_name-error"{% endif %}>
    {% if errors.project_name %}
      <p class="field-error" id="project_name-error">{{ errors.project_name }}</p>
    {% endif %}
  </div>
  ```

- The `<span class="required">*</span>` marker appears in the label
  of the four required fields only — `project_name`, `country`,
  `category`, `budget_usd` — and is absent from `start_date` and
  `summary`. A legend beneath the heading reads
  "<span class="required">*</span> Required field", so the asterisk
  is explained rather than assumed. The markers must agree with the
  `required` attributes and with §4.8's requiredness table; a label
  promising a field is optional while the input refuses to submit
  without it is worse than either alone.

- The six fields and their input attributes, exactly:

  | Field | Element | Attributes |
  |---|---|---|
  | `project_name` | `<input type="text">` | `required`, `maxlength="200"` |
  | `country` | `<select>` | `required`; a disabled, selected, valueless placeholder `<option>` reading "Select a country"; then `{% for code, label in country_choices %}` with `selected` when `values.country == code` |
  | `category` | `<select>` | `required`; same placeholder pattern; options from `category_choices` |
  | `budget_usd` | `<input type="number">` | `required`, `min="0.01"`, `step="0.01"`, `inputmode="decimal"` |
  | `start_date` | `<input type="date">` | no `required` — the field is optional |
  | `summary` | `<textarea>` | `maxlength="300"`, `rows="5"`, `id="summary"` — **no `required`**, the field is optional; followed by `<p class="counter" id="summary-counter">0 / 300 · 300 remaining</p>` |

- Submit button labelled "Submit proposal" or "Save changes"
  depending on `mode`.
- A Cancel link beside it: to `/proposals` when creating, to
  `/proposals/{{ proposal.id }}` when editing.
- `{% block scripts %}<script src="/static/counter.js" defer></script>{% endblock %}`.

**Decisions fixed here**

- **The browser attributes duplicate the server rules on purpose.**
  They give immediate, native feedback with no code and no round
  trip. They are not the enforcement — §4.8 is — and the README says
  so explicitly. **This includes the two dropdowns**: a `<select>`
  restricts what is convenient to submit, not what is possible to
  submit, and §4.8 sets out at length why the country and category
  are re-checked on arrival.
- **`min="0.01"` rather than `min="0"`**, because the rule is that
  the budget must be *positive*, and `min="0"` would let zero pass
  the browser's check only to be rejected by the server.
- **`step="0.01"`** matches the column's two decimal places, so the
  number spinner cannot produce a value the server will reject.
- **The placeholder `<option>` carries `disabled selected value=""`**,
  so a dropdown that has not been touched fails the `required` check
  rather than silently defaulting to whichever country happens to be
  first.
- **`values` is a dictionary of strings, not a `Proposal`.** After a
  failed submission there is no `Proposal` — validation is what
  failed. One shape for both cases means one template rather than
  two branches through every field.
- **The counter's initial text is written into the HTML**, and
  `counter.js` corrects it on load. If scripting is unavailable the
  page still renders sensibly instead of showing an empty element.
  The number of countries in the dropdown is not stated anywhere in
  the markup, so the file in §4.2.1 remains the single source.

#### 4.11.4 `app/templates/list.html`

**Context**: `proposals` (list), `selected_country` (`str | None`),
`selected_category` (`str | None`).

**Structure**

- `<h1>Proposals</h1>` and a count line: "Showing N proposals",
  with " (filtered)" appended when either filter is active.
- A filter form, `<form method="get" action="/proposals"
  class="filters">`:
  - `<select name="country">` — first option `value=""` reading "All
    countries"; then `country_choices`, with `selected` where
    `selected_country == code`.
  - `<select name="category">` — first option `value=""` reading "All
    categories"; then `category_choices`, same pattern.
  - `<button type="submit">Apply filters</button>`.
  - A "Clear" link to `/proposals`, rendered only when a filter is
    active.
- `<table class="proposal-table">` with a `<thead>` of: Project name,
  Country, Category, Budget (USD), Start date, Submitted.
- `<tbody>` looping `proposals`:
  - Project name as `<a href="/proposals/{{ p.id }}">`, satisfying
    "clicking an item opens a detail view".
  - `{{ p.country | country_label }}`, `{{ p.category | category_label }}`,
    `{{ p.budget_usd | money }}` in a right-aligned cell,
    `{{ p.start_date | date_display }}`,
    `{{ p.created_at | date_display }}`.
- `{% else %}` on the loop renders a single full-width row: "No
  proposals match these filters." when a filter is set, otherwise
  "No proposals yet — submit the first one." with a link to
  `/proposals/new`.
- The table is wrapped in `<div class="table-scroll">` so it scrolls
  horizontally on a narrow screen rather than forcing the page to.

**Decisions fixed here**

- **The filter form is `GET`, not `POST`.** A filtered view then has
  its own URL, which can be bookmarked, shared, and reloaded, and
  the back button behaves correctly. This is what filtering means on
  the web.
- **Both filters submit together in one form**, so they compose:
  Kenya *and* Smart Grid narrows to the intersection. The assignment
  requires filtering by country *or* category; supporting both at
  once is strictly more useful and costs nothing, since the
  repository already appends conditions independently.
- **The empty state is explicit and differs by cause.** A blank table
  leaves a reviewer unsure whether the app is broken or the filter
  simply matched nothing.

#### 4.11.5 `app/templates/detail.html`

**Context**: `proposal`.

**Structure**

- `<h1>{{ proposal.project_name }}</h1>`.
- A `<dl class="detail-list">` with every field: Country, Category,
  Estimated budget, Planned start date, Submitted, Last updated,
  and the summary.
- The summary is rendered as
  `{% if proposal.summary %}<p class="summary-text">{{ proposal.summary }}</p>{% else %}<p class="summary-text empty">No summary provided.</p>{% endif %}`.
  Both `start_date` and `summary` are optional (§4.8), so both have
  an explicit absent state — the date filter already renders an em
  dash, and the summary says so in words because a lone em dash
  under a "Project summary" heading reads as a rendering fault
  rather than as an empty field.
- An actions row:
  - `<a class="button" href="/proposals/{{ proposal.id }}/edit">Edit</a>`.
  - The delete form. The project name travels as a **data
    attribute**, never as JavaScript source:

    ```html
    <form method="post"
          action="/proposals/{{ proposal.id }}/delete"
          class="delete-form"
          data-project-name="{{ proposal.project_name }}">
      <button type="submit" class="button button-danger">Delete</button>
    </form>
    ```
  - `<a href="/proposals">Back to list</a>`.
- `{% block scripts %}<script src="/static/confirm-delete.js" defer></script>{% endblock %}`.

**Decisions fixed here**

- **Delete is a `POST` with a confirmation, never a link.** A `GET`
  can be fired by a browser prefetching a link or by a crawler
  following it, and would delete the proposal with nobody having
  clicked anything.
- **The project name is passed as a `data-` attribute and the
  handler lives in an external script. It is never interpolated into
  inline JavaScript.** This is a security requirement, not a style
  preference, and the reasoning is worth stating in full because the
  unsafe version looks safe.

  The obvious way to write this prompt is an inline handler, and it
  is exploitable:

  ```html
  <!-- VULNERABLE — do not write this -->
  onsubmit="return confirm('Delete “{{ proposal.project_name }}”? …');"
  ```

  Jinja's autoescaping is on, and it escapes `'` to `&#39;`, so this
  appears protected. It is not, because **the HTML parser decodes
  character references in an attribute value before the JavaScript
  parser sees the result.** A proposal named `'); alert(1); //`
  produces:

  ```text
  stored value : '); alert(1); //
  Jinja emits  : onsubmit="return confirm('Delete “&#39;); alert(1); //”? …');"
  HTML decodes : return confirm('Delete “'); alert(1); //”? …');
  JS executes  :                          ^ string terminated, alert(1) runs
  ```

  The attacker cannot escape the attribute itself — `"` becomes
  `&#34;`, and attribute delimiters are matched before entities are
  decoded — but they do not need to. Arbitrary JavaScript running in
  the page's origin is already the whole prize. Since the application
  has no authentication, anyone may submit such a proposal, and the
  payload fires for any person who clicks Delete on it.

  **Why the data-attribute version is safe.** `data-project-name` is
  an ordinary HTML attribute, and HTML escaping is exactly the
  correct escaping for that context: `"` → `&#34;` makes attribute
  breakout impossible, and the decoded result is a plain string
  value. `getAttribute()` then returns that value **as data**. There
  is no point at which the name is parsed as code, because there is
  no JavaScript source context for it to occupy. The rule this
  encodes: escaping is context-dependent, and HTML escaping is not
  JavaScript escaping — so the fix is to remove the JavaScript
  context rather than to escape harder.

  **This is the one context autoescaping does not cover**, which is
  why §4.11.1 can otherwise say `|safe` appears nowhere and treat
  autoescaping as the XSS defence. An inline event handler is an
  escape hatch out of that guarantee, so the codebase contains no
  inline event handlers at all — see test W-27.

- **A confirmation prompt is a courtesy, not a control.** It runs in
  the browser and can be bypassed like anything else there. What
  actually makes an accidental deletion survivable is that deletes
  are soft (§4.5): the row is marked, never removed, so even an
  unconfirmed delete is recoverable.
- **The summary is rendered inside `<p>` with `white-space:
  pre-line`** in the stylesheet, so line breaks a submitter typed
  survive to the page while the value stays HTML-escaped.

#### 4.11.6 `app/templates/error.html`

**Context**: `status_code`, `detail`.

- `<h1>{{ status_code }}</h1>`, the `detail` text beneath it, and a
  link back to `/proposals`. Extends `base.html`, so a wrong URL
  produces a page that still looks like the application rather than
  a bare JSON object.

---

### 4.12 Module 12 — `app/static/`

**Summary**: one hand-written stylesheet and two small scripts.

**Purpose**: the interface has to be legible in a screen recording
and must render identically offline and inside Docker, so nothing is
fetched from a CDN. Writing the CSS by hand keeps the class names in
the markup semantic (`proposal-table`, `field-error`), which means a
later move to a CSS framework or a React frontend replaces one file
rather than editing every template.

#### 4.12.1 `app/static/style.css`

Approximately 150 lines, organised in this order:

1. **Custom properties** on `:root` — `--ink: #16241f`,
   `--ink-soft: #5b6b64`, `--accent: #1f7a5a`, `--accent-dark:
   #155c43`, `--danger: #b3261e`, `--surface: #ffffff`, `--page:
   #f4f6f5`, `--line: #d9e0dd`, `--radius: 6px`. A restrained green
   palette, appropriate to the domain and legible at recording
   resolution.
2. **Reset** — `*, *::before, *::after { box-sizing: border-box }`,
   `body { margin: 0 }`.
3. **Base typography** — a system font stack (`-apple-system,
   "Segoe UI", Roboto, Helvetica, Arial, sans-serif`), `line-height:
   1.55`, `color: var(--ink)`, `background: var(--page)`. A system
   stack means no web font to download and no layout shift.
4. **Layout** — `.container { max-width: 68rem; margin: 0 auto;
   padding: 1.5rem 1.25rem }`.
5. **Header and footer** — `.site-header` with a white surface, a
   bottom border, and the nav laid out with flexbox; the current
   page's nav link is not specially marked (there are only two).
6. **Forms** — `.field { margin-bottom: 1.1rem }`; labels are block
   elements at `600` weight; inputs, selects, and textareas share
   `width: 100%`, `padding: 0.55rem 0.7rem`, `border: 1px solid
   var(--line)`, `border-radius: var(--radius)`, and a focus ring of
   `outline: 2px solid var(--accent); outline-offset: 1px`.
7. **Error state** — `.field-invalid input, .field-invalid select,
   .field-invalid textarea { border-color: var(--danger) }`;
   `.field-error { color: var(--danger); font-size: 0.875rem;
   margin: 0.35rem 0 0 }`; `.required { color: var(--danger) }`.
8. **Counter** — `.counter { font-size: 0.85rem; color:
   var(--ink-soft); text-align: right; margin: 0.3rem 0 0;
   font-variant-numeric: tabular-nums }`. One rule, no state
   variants: the counter shows the remaining count continuously, so
   there is nothing for a colour change to add. Tabular figures stop
   the text jiggling as digits change width while typing.
9. **Buttons** — `.button` and `button` share padding
   `0.55rem 1.1rem`, `border-radius: var(--radius)`, no border,
   `background: var(--accent)`, white text, `cursor: pointer`, and a
   `:hover` of `var(--accent-dark)`. `.button-danger` overrides the
   background to `var(--danger)`. `.actions { display: flex; gap:
   0.75rem; align-items: center; margin-top: 1.5rem }` so the Edit
   link, the delete form, and the back link sit on one row, with
   `.delete-form { margin: 0 }` so the form adds no spacing of its
   own as a flex item.
10. **Table** — `.table-scroll { overflow-x: auto }`;
    `.proposal-table { width: 100%; border-collapse: collapse;
    background: var(--surface) }`; `th, td { padding: 0.65rem 0.75rem;
    text-align: left; border-bottom: 1px solid var(--line) }`;
    `thead th { background: #eef2f0; font-size: 0.8rem;
    text-transform: uppercase; letter-spacing: 0.04em }`;
    `tbody tr:hover { background: #f8faf9 }`; `.numeric { text-align:
    right; font-variant-numeric: tabular-nums }` so budget digits
    align in a column.
11. **Filters** — `.filters { display: flex; flex-wrap: wrap; gap:
    0.75rem; align-items: flex-end; margin-bottom: 1.25rem }`; the
    selects inside it are `width: auto; min-width: 12rem`.
12. **Detail list** — `.detail-list` as a two-column grid
    (`grid-template-columns: max-content 1fr; gap: 0.5rem 1.5rem`);
    `dt` at `600` weight in `var(--ink-soft)`; `.summary-text {
    white-space: pre-line }`; `.summary-text.empty { color:
    var(--ink-soft); font-style: italic }` for the "No summary
    provided." state.
13. **Responsive** — a single `@media (max-width: 40rem)` block
    stacking the header nav and setting `.filters` to
    `flex-direction: column; align-items: stretch`.

No CSS framework, no CDN link, no build step. The file is served
directly by the `StaticFiles` mount.

#### 4.12.2 `app/static/counter.js`

```javascript
/* Live character counter for the project summary textarea. */
document.addEventListener("DOMContentLoaded", function () {
  var textarea = document.getElementById("summary");
  var counter = document.getElementById("summary-counter");
  if (!textarea || !counter) {
    return;
  }

  var limit = parseInt(textarea.getAttribute("maxlength"), 10) || 300;

  function update() {
    var used = textarea.value.length;
    counter.textContent =
      used + " / " + limit + " · " + (limit - used) + " remaining";
  }

  textarea.addEventListener("input", update);
  update();
});
```

**Decisions fixed here**

- **It runs entirely in the browser and sends nothing.** The counter
  watches the textarea and updates a number; no network traffic is
  involved.
- **`update()` is called once on load**, not only on input, so an
  edit form opened with an existing 180-character summary shows
  `180 / 300 · 120 remaining` immediately rather than starting from
  zero.
- **The limit is read from the `maxlength` attribute** rather than
  hard-coded, so the number appears in exactly one place — the
  template — and cannot drift out of step with what the browser
  enforces.
- **The remaining count is shown continuously, and there is no
  warning state.** A colour change near the limit is a common
  addition, meant to explain why the browser stops accepting
  keystrokes at 300. It is unnecessary here: a number counting down
  to zero in real time already tells the person how much room is
  left, at every moment rather than only near the end. Adding a
  colour would introduce a second mechanism conveying the same fact,
  plus a state to style and test, for nothing.
- **Guard clauses return early** when the elements are absent, so the
  script is harmless on pages that have no textarea.
- **`defer` on the `<script>` tag** plus the `DOMContentLoaded`
  listener — either alone would suffice; both together mean the
  script cannot run before its elements exist regardless of how the
  tag is later moved.

#### 4.12.3 `app/static/confirm-delete.js`

```javascript
/* Confirmation prompt for delete forms.
   The project name arrives as a data attribute and is treated as a
   string value — it is never interpolated into JavaScript source.
   See §4.11.5 for why that distinction matters. */
document.addEventListener("DOMContentLoaded", function () {
  var forms = document.querySelectorAll(".delete-form");

  Array.prototype.forEach.call(forms, function (form) {
    form.addEventListener("submit", function (event) {
      var name = form.getAttribute("data-project-name") || "this proposal";
      var message =
        'Delete "' + name + '"? This cannot be undone from the interface.';
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
});
```

**Decisions fixed here**

- **The name reaches JavaScript through `getAttribute()`**, which
  returns a string. Concatenating that string into `message` builds a
  *value*, never source that gets parsed. This is the whole point of
  the change described in §4.11.5.
- **`event.preventDefault()` rather than `return false`.**
  `return false` inside an `addEventListener` callback does nothing
  at all — it only cancels in the old inline-handler style, which is
  precisely the style being removed here. Using the wrong one would
  make the prompt appear and then delete the proposal regardless of
  the answer.
- **A fallback of `"this proposal"`** if the attribute is missing, so
  a template edit that drops it degrades to a generic prompt rather
  than showing the word `null` to a person.
- **`querySelectorAll` with a class rather than an id**, so a future
  list page with a delete button on every row works with no change.
  `Array.prototype.forEach.call` handles the `NodeList` without
  assuming a modern iterable.
- **A separate file from `counter.js`.** They load on different
  pages — the counter on the form, this on the detail page — and each
  is bound to elements the other page does not have. Keeping them
  apart means neither runs where it has nothing to do.
- **If JavaScript is unavailable the form still submits**, without a
  prompt. That is the correct degradation: the delete is soft, so it
  is recoverable, and blocking deletion entirely without JavaScript
  would be worse than confirming without it.

---

### 4.13 Module 13 — `app/web/proposals.py`

**Summary**: the seven HTML routes.

**Purpose**: something must receive the incoming request and decide
what happens. Each route does three things and stops: take the input,
call one service function, return a page or a redirect. A route
longer than a few lines means logic has crept in that belongs in the
service layer.

**Implementation**

- New file `app/web/proposals.py`.

- Router: `router = APIRouter(tags=["proposals"], include_in_schema=False)`.
  The HTML routes are excluded from the generated documentation,
  which describes the JSON API.

- Every route takes `request: Request` and
  `db: Session = Depends(get_db)`.

- **A shared helper** for rebuilding the form context, so the three
  places that re-render a failed form do not drift apart:

  ```python
  def _form_context(
      *,
      mode: str,
      action: str,
      values: dict[str, str],
      errors: dict[str, str] | None = None,
      proposal: Proposal | None = None,
  ) -> dict[str, object]:
      return {
          "mode": mode,
          "action": action,
          "values": values,
          "errors": errors or {},
          "proposal": proposal,
      }
  ```

- **A shared helper** for collecting the posted form into a raw dict,
  since create and edit post identical fields:

  ```python
  def _raw_form(
      project_name: str,
      country: str,
      category: str,
      budget_usd: str,
      start_date: str,
      summary: str,
  ) -> dict[str, str]:
      return {
          "project_name": project_name,
          "country": country,
          "category": category,
          "budget_usd": budget_usd,
          "start_date": start_date,
          "summary": summary,
      }
  ```

**The seven routes, in declaration order**

| # | Method and path | Behaviour |
|---|---|---|
| 1 | `GET /proposals` | Reads optional `country` and `category` query parameters as `str | None`. Each is checked for membership in its enum; a value that is not a member is treated as absent rather than raising, so a hand-edited URL degrades to the unfiltered list. Calls `list_proposals(...)`. Renders `list.html` with `proposals`, `selected_country`, `selected_category`. |
| 2 | `GET /proposals/new` | Renders `form.html` via `_form_context(mode="create", action="/proposals", values={})`. |
| 3 | `POST /proposals` | Six `Form(...)` parameters, all typed `str` with `""` defaults. Builds the raw dict; attempts `ProposalCreate(**raw)`. On `ValidationError`, re-renders `form.html` with `errors=format_errors(exc)` and `values=raw`, status **400**. On `DuplicateProposalError`, re-renders with `errors={"project_name": str(exc)}` and `values=raw`, status **409**. On success, returns `RedirectResponse("/proposals", status_code=303)`. |
| 4 | `GET /proposals/{proposal_id}` | `proposal_id: UUID`. Calls `get_proposal(...)`; catches `ProposalNotFoundError` and raises `HTTPException(404, "Proposal not found.")`. Renders `detail.html`. |
| 5 | `GET /proposals/{proposal_id}/edit` | Fetches the proposal the same way, converts it to the string-keyed `values` dict via `_values_from(proposal)`, renders `form.html` via `_form_context(mode="edit", action=f"/proposals/{proposal_id}", values=..., proposal=proposal)`. |
| 6 | `POST /proposals/{proposal_id}` | Same six form parameters. Validates with `ProposalUpdate`. `ValidationError` → re-render, status 400, `action` pointing back at this URL and `mode="edit"`. `DuplicateProposalError` → re-render, status 409. `ProposalNotFoundError` → `HTTPException(404)`. On success, `RedirectResponse(f"/proposals/{proposal_id}", status_code=303)`. |
| 7 | `POST /proposals/{proposal_id}/delete` | Calls `delete_proposal(...)`; `ProposalNotFoundError` → `HTTPException(404)`. On success, `RedirectResponse("/proposals", status_code=303)`. |

- **`_values_from(proposal)`** converts a stored proposal into the
  string dictionary the form expects:

  ```python
  def _values_from(proposal: Proposal) -> dict[str, str]:
      return {
          "project_name": proposal.project_name,
          "country": proposal.country,
          "category": proposal.category,
          "budget_usd": f"{proposal.budget_usd:.2f}",
          "start_date": proposal.start_date.isoformat() if proposal.start_date else "",
          "summary": proposal.summary,
      }
  ```

**Decisions fixed here**

- **Declaration order is load-bearing.** `GET /proposals/new` must be
  declared *before* `GET /proposals/{proposal_id}`. FastAPI matches
  in declaration order, and with the dynamic route first the literal
  string `new` would be parsed as a UUID and produce a `422` instead
  of the form. The table above is the required order.
- **Every redirect is `303 See Other`**, not `302`. 303 instructs the
  browser explicitly to follow up with a `GET`, which is exactly the
  post/redirect/get behaviour intended, whereas 302's method
  handling is historically ambiguous.
- **Creation redirects to the list; editing redirects to the
  detail page.** After submitting, seeing the new proposal in the
  table is the confirmation that the flow worked; after editing,
  returning to the page just edited is what a person expects.
- **Form parameters are typed `str` with `""` defaults, never
  `Optional[...]` or `Decimal`.** If FastAPI coerced the budget
  itself, a non-numeric value would produce FastAPI's own `422` JSON
  error page and the person would lose everything they typed.
  Accepting raw strings routes *every* failure through
  `format_errors`, so the form always re-renders with messages and
  preserved values.
- **The re-rendered form carries `values=raw`** — the values the
  person actually typed, not the empty form. Losing six fields of
  input because one was wrong is the single most irritating thing a
  web form can do.
- **Status codes are meaningful**: `400` for a malformed submission,
  `409` for a name that conflicts with an existing proposal, `404`
  for a proposal that is not there. The page rendered is the same
  form either way; the status makes the outcome legible to anything
  that is not a browser.
- **Filter parameters are sanitised, not validated.** Typing
  `?country=ZZ` shows the unfiltered list rather than an error, which
  is the friendlier behaviour for a URL a person can edit. The JSON
  API takes the opposite position — see §4.14 — because a program
  passing a bad code has a bug and should be told.
- **`ProposalNotFoundError` is converted to `HTTPException(404)`**
  in the route, never raised through it. Translating a domain error
  into an HTTP status is the route's job, which is exactly why the
  service does not do it.

---

### 4.14 Module 14 — `app/api/proposals.py`

**Summary**: three read-only JSON endpoints on the same service calls
the HTML routes use.

**Purpose**: the HTML routes and these endpoints reach identical
service and repository functions and diverge only on the final step —
Jinja renders a page, Pydantic renders JSON. That the second door
costs twenty lines is the observable demonstration that the business
logic is not embedded in the web page. It also produces the
interactive documentation at `/docs` from the type annotations alone,
and it is the seam a React or mobile frontend would plug into later
without a single server-side change.

**Implementation**

- New file `app/api/proposals.py`:

  ```python
  from uuid import UUID

  from fastapi import APIRouter, Depends, HTTPException, Query
  from sqlalchemy.orm import Session

  from app.db.repository import ProposalRepository
  from app.db.session import get_db
  from app.domain.constants import Category, country_codes, load_countries
  from app.schemas.country import CountryOut
  from app.schemas.proposal import ProposalRead
  from app.services.errors import ProposalNotFoundError
  from app.services.proposal import get_proposal, list_proposals

  router = APIRouter(prefix="/api", tags=["proposals"])


  @router.get("/proposals", response_model=list[ProposalRead])
  def api_list_proposals(
      country: str | None = Query(
          default=None,
          min_length=2,
          max_length=2,
          description=(
              "Filter by ISO 3166-1 alpha-2 code of a GGGI member country, "
              "e.g. KE. See GET /api/countries for the full list."
          ),
      ),
      category: Category | None = Query(
          default=None, description="Filter by climate technology category."
      ),
      db: Session = Depends(get_db),
  ) -> list[ProposalRead]:
      """List all live proposals, newest first, optionally filtered."""
      if country is not None:
          country = country.strip().upper()
          if country not in country_codes():
              raise HTTPException(
                  status_code=422,
                  detail=f"Unknown country code: {country}",
              )
      proposals = list_proposals(
          ProposalRepository(db),
          country=country,
          category=category.value if category else None,
      )
      return [ProposalRead.model_validate(p) for p in proposals]


  @router.get("/countries", response_model=list[CountryOut])
  def api_list_countries() -> list[CountryOut]:
      """The GGGI member countries a proposal may target."""
      return [
          CountryOut(code=record.code, name=record.name, joined=record.joined)
          for record in load_countries()
      ]


  @router.get("/proposals/{proposal_id}", response_model=ProposalRead)
  def api_get_proposal(
      proposal_id: UUID,
      db: Session = Depends(get_db),
  ) -> ProposalRead:
      """Fetch one live proposal by id."""
      try:
          proposal = get_proposal(proposal_id, ProposalRepository(db))
      except ProposalNotFoundError:
          raise HTTPException(status_code=404, detail="Proposal not found.")
      return ProposalRead.model_validate(proposal)
  ```

**Decisions fixed here**

- **Read-only.** The assignment does not ask for an API at all, so
  the endpoints exist to open the seam for a React frontend (§2.3)
  rather than to become a second write path that would double the
  validation and test surface for no requirement. The write endpoints
  are described in §7 as the work a frontend would actually require.
- **`GET /api/countries` exists because the country list is no longer
  a compile-time constant.** A React frontend has to populate its own
  country dropdown, and hard-coding 54 entries into a JavaScript
  bundle would immediately duplicate the data file. Exposing the
  curated list makes it fetchable, and the endpoint survives the move
  to a SQL table unchanged because it reads through
  `load_countries()`.
- **`category` is typed as its enum but `country` is a plain
  string.** The asymmetry is deliberate and follows §4.2: the
  category vocabulary is fixed in code, so `/docs` can render it as a
  dropdown; the country vocabulary is runtime data, so it is
  validated by membership check instead. The cost is that `/docs`
  shows a free-text box for `country` rather than a dropdown, which
  is why the parameter description points at `GET /api/countries`.
- **An unknown country code returns `422`**, unlike the HTML list
  route, which silently ignores it. A program passing a bad code has
  a bug and should be told; a person editing a URL is better served
  by seeing the unfiltered list.
- **`response_model` is declared even though the return type
  annotation says the same thing.** It is what drives the schema
  shown in `/docs`, and it guarantees the response is filtered to
  exactly `ProposalRead`'s fields.
- **`ProposalRead.model_validate(...)` is called explicitly** rather
  than relying on FastAPI's implicit conversion, making the ORM →
  schema step visible at the call site.
- **The prefix is `/api`**, so nothing here can ever collide with an
  HTML route, and §4.3's exception handler can branch on the path to
  decide between a JSON error and an HTML error page.

---

### 4.15 Module 15 — `scripts/seed.py`

**Summary**: ten realistic proposals, inserted idempotently.

**Purpose**: without seed data, whoever opens the app sees an empty
table and two dropdowns that appear to do nothing. Ten proposals
spread across countries and categories make filtering demonstrably
work, and give the screen recording something to show in its first
five seconds.

**Implementation**

- New file `scripts/seed.py`.

- Module-level constant `SEED_PROPOSALS`, a list of ten dictionaries.
  These are the exact values, fixed here so the demo and the README
  screenshots are reproducible:

  | Project name | Country | Category | Budget USD | Start date |
  |---|---|---|---|---|
  | Lake Turkana Solar Mini-Grid Expansion | KE | renewable_energy | 2450000.00 | 2026-03-01 |
  | Nairobi Distribution Network Smart Metering | KE | smart_grid | 1180000.00 | 2026-05-15 |
  | Rift Valley Flood Exposure Atlas | ET | climate_risk_mapping | 640000.00 | 2026-01-20 |
  | Addis Ababa Industrial Emissions MRV Platform | ET | mrv | 890000.00 | *(none)* |
  | Kigali Rooftop Solar Cooperative | RW | renewable_energy | 375000.00 | 2026-07-01 |
  | Mekong Delta Saltwater Intrusion Mapping | VN | climate_risk_mapping | 1520000.00 | 2026-02-10 |
  | Java Geothermal Wellhead Pilot | ID | renewable_energy | 4300000.00 | 2026-09-01 |
  | Luzon Typhoon Grid Resilience Upgrade | PH | smart_grid | 2760000.00 | 2026-04-05 |
  | Gobi Desert Utility-Scale Solar Corridor | MN | renewable_energy | 3100000.00 | 2026-06-12 |
  | Andean Glacier Retreat Monitoring Network | PE | climate_risk_mapping | 725000.00 | 2026-08-18 |

  Each entry also carries a `summary` of 120–280 characters written
  in the register of a real funding application — one or two
  sentences naming what is built, where, and what it delivers. All
  ten are under the 300-character limit, and one is deliberately near
  it (about 290 characters) so the character counter has something
  interesting to show.

  Countries used: KE ×2, ET ×2, RW, VN, ID, PH, MN, PE — eight
  distinct countries, two of them repeated so that filtering by
  country returns more than one row and the result is visibly a
  filter rather than a coincidence. Categories used:
  renewable_energy ×4, climate_risk_mapping ×3, smart_grid ×2,
  mrv ×1. `other` is deliberately unused, so filtering by it
  demonstrates the empty state.

  **Every code above must appear in `gggi_members.txt`** — check
  rather than assume, since plausible-looking codes are easy to reach
  for and GGGI membership is not the set of countries one would
  guess. India, for instance, is not a member. Because `seed.py`
  validates through `ProposalCreate`, a wrong code fails loudly on
  the first `docker compose up` instead of silently inserting a row
  the application considers invalid — which is precisely why the
  script does not write to the session directly.

- `main()`:

  ```python
  def main() -> None:
      db = SessionLocal()
      try:
          repo = ProposalRepository(db)
          created = 0
          for entry in SEED_PROPOSALS:
              if repo.exists_with_name(entry["project_name"]):
                  continue
              data = ProposalCreate(**entry)
              create_proposal(data, repo)
              created += 1
          db.commit()
          print(f"Seed complete: {created} created, "
                f"{len(SEED_PROPOSALS) - created} already present.")
      except Exception:
          db.rollback()
          raise
      finally:
          db.close()


  if __name__ == "__main__":
      main()
  ```

- Run with `python -m scripts.seed`.

**Decisions fixed here**

- **The script goes through `ProposalCreate` and
  `create_proposal`**, not straight to `session.add()`. The seed data
  is therefore validated by the same rules a person's submission
  faces, so a typo in this file fails loudly rather than inserting a
  row the application considers invalid.
- **It is idempotent by name check.** The container entrypoint runs
  it on every start, so running it twice must be harmless.
- **It manages its own session** rather than borrowing `get_db()`,
  which is a request-scoped generator dependency and not meaningful
  outside a request.
- **It prints a summary line.** During `docker compose up` that line
  is the confirmation in the logs that the database is populated.
- **Start dates are in 2026**, forward of the document date, so the
  data reads as a live pipeline rather than a historical archive. One
  entry has no start date at all, exercising the optional field on
  both the list page and the detail page.

---

### 4.16 Module 16 — Containerisation

**Summary**: `Dockerfile`, `docker-compose.yml`,
`scripts/entrypoint.sh`, `.dockerignore`, `.gitattributes`.

**Purpose**: one command must start Postgres and the application
together, apply migrations, seed, and serve — from a clean clone, on
a machine that has only Docker. This is what makes the reviewer's
first experience "it worked" rather than a support conversation.

#### 4.16.1 `Dockerfile`

```dockerfile
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/code

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "/code/scripts/entrypoint.sh"]
```

**Decisions fixed here**

- **`requirements.txt` is copied and installed before the rest of the
  source.** Docker caches each layer; installing dependencies first
  means editing a template does not reinstall FastAPI.
- **`PYTHONUNBUFFERED=1`** so log output appears in
  `docker compose up` immediately rather than being held in a buffer
  — which otherwise makes a crash look like a silent hang.
- **`PYTHONPATH=/code`** so `app` and `scripts` import cleanly
  regardless of how the process is invoked.
- **`CMD ["sh", "/code/scripts/entrypoint.sh"]`, not
  `["./scripts/entrypoint.sh"]`.** The latter requires the file's
  executable bit, which Windows checkouts do not preserve and which
  produces a `permission denied` that is easy to misread as a Docker
  problem. Invoking `sh` explicitly sidesteps the issue entirely.
- **`python:3.14-slim`, not `alpine`.** Alpine's musl libc means
  several Python packages build from source instead of installing a
  wheel, turning a fast build into a slow one for a small image
  saving.
- **The image version matches the host's development interpreter
  (§4.0) rather than being pinned independently.** The container is
  already decoupled from whatever else is installed on the host — that
  is the point of containerising — but the *version of Python itself*
  is worth keeping identical between local development and the
  container regardless, so that a difference in behaviour between
  `uvicorn app.main:app --reload` on the host and
  `docker compose up` cannot be a Python-version discrepancy hiding
  underneath it. If the host venv is later created against a pinned
  3.12 or 3.13 (per §4.0's fallback, should a `psycopg[binary]` wheel
  be unavailable for 3.14), this line changes to match.

#### 4.16.2 `scripts/entrypoint.sh`

```sh
#!/usr/bin/env sh
set -e

echo "Ensuring the database exists…"
python -c "from app.config import get_settings; from app.db.bootstrap import ensure_database_exists; ensure_database_exists(get_settings().database_url)"

echo "Applying database migrations…"
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "Seeding example proposals…"
  python -m scripts.seed
fi

echo "Starting application on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- **`set -e`** aborts on the first failure, so a failed migration
  stops the container instead of starting an app against a schema
  that is not there.
- **The bootstrap runs before Alembic**, because Alembic must connect
  to the database in order to create tables in it. In the Compose
  stack Postgres has already created `ctaf` from `POSTGRES_DB`, so
  this call finds it present and returns immediately; it earns its
  place when someone points `DATABASE_URL` at a Postgres server that
  has no `ctaf` database, which is the normal case outside Docker.
- **`exec`** replaces the shell with uvicorn, so `docker compose
  stop` signals the server directly and it shuts down cleanly.
- **Seeding is behind `SEED_ON_START`**, set to `"true"` in Compose,
  so the seed can be turned off without editing the image.

#### 4.16.3 `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ctaf
      POSTGRES_PASSWORD: ctaf
      POSTGRES_DB: ctaf
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ctaf -d ctaf"]
      interval: 3s
      timeout: 3s
      retries: 20

  app:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg://ctaf:ctaf@db:5432/ctaf
      SEED_ON_START: "true"
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

**Decisions fixed here**

- **`condition: service_healthy`, not a bare `depends_on`.** A plain
  dependency waits only for the container to *start*, and Postgres
  takes a few seconds more to accept connections. Without the
  healthcheck, the app's first `alembic upgrade` intermittently fails
  with "connection refused" — the single most common cause of a
  Compose stack that works on the author's machine and not on the
  reviewer's.
- **The host `5432` is published** so `psql` and a locally run
  `pytest` can reach the database while the stack is up.
- **`db` is the hostname inside the Compose network**, which is why
  the app's `DATABASE_URL` says `@db:5432` while `.env.example` says
  `@localhost:5432`. This is exactly the difference environment
  variables exist to absorb.
- **Development credentials are in the file in plain text.** They are
  `ctaf`/`ctaf`, they reach a throwaway local container, and there is
  no production deployment in scope. The README states this
  explicitly so it cannot be mistaken for carelessness.
- **A named volume `pgdata`** so data survives `docker compose down`.
  `docker compose down -v` is documented in the README as the way to
  start over.

#### 4.16.4 `.dockerignore`

```
.git
.venv
__pycache__
*.py[cod]
.pytest_cache
.env
docs
*.md
htmlcov
.coverage
```

Keeps the build context small and — critically — keeps a local
`.env` pointing at `localhost` from being copied into the image,
where it would override the Compose-supplied `DATABASE_URL` and make
the container unable to find the database.

#### 4.16.5 `.gitattributes`

```
* text=auto eol=lf
*.sh text eol=lf
```

Development is on Windows. Without this, `entrypoint.sh` is committed
with CRLF line endings, and Linux `sh` reads the trailing carriage
return as part of the command, failing with an error message that
mentions a filename with an invisible `\r` in it. This one file
prevents a genuinely baffling failure.

---

### 4.17 Module 17 — `tests/`

**Summary**: the pytest suite and its fixtures.

**Purpose**: so that changing something in the last hour of work
reveals immediately whether something from the first hour broke,
rather than the reviewer discovering it. The suite covers the
assignment's stated rules directly, so it doubles as evidence that
each requirement is met.

**Implementation of the fixtures** — the tests themselves are
enumerated in §6.

- New file `tests/conftest.py`:

  ```python
  import os
  from collections.abc import Iterator

  import pytest
  from fastapi.testclient import TestClient
  from sqlalchemy import create_engine, text
  from sqlalchemy.engine import Connection, Engine
  from sqlalchemy.orm import Session

  from app.db.bootstrap import ensure_database_exists
  from app.db.models import Base
  from app.db.repository import ProposalRepository
  from app.db.session import get_db
  from app.main import app

  TEST_DATABASE_URL = os.getenv(
      "TEST_DATABASE_URL",
      "postgresql+psycopg://ctaf:ctaf@localhost:5432/ctaf_test",
  )


  @pytest.fixture(scope="session")
  def engine() -> Iterator[Engine]:
      """Session-wide engine with the test database and schema created once."""
      ensure_database_exists(TEST_DATABASE_URL)
      eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
      Base.metadata.drop_all(eng)
      Base.metadata.create_all(eng)
      yield eng
      Base.metadata.drop_all(eng)
      eng.dispose()


  @pytest.fixture()
  def connection(engine: Engine) -> Iterator[Connection]:
      conn = engine.connect()
      yield conn
      conn.close()


  @pytest.fixture()
  def db_session(connection: Connection) -> Iterator[Session]:
      """One test = one transaction, always rolled back."""
      transaction = connection.begin()
      session = Session(
          bind=connection,
          join_transaction_mode="create_savepoint",
          expire_on_commit=False,
      )
      yield session
      session.close()
      transaction.rollback()


  @pytest.fixture()
  def repo(db_session: Session) -> ProposalRepository:
      return ProposalRepository(db_session)


  @pytest.fixture()
  def client(db_session: Session) -> Iterator[TestClient]:
      """TestClient whose requests share the test's transaction."""

      def _override_get_db() -> Iterator[Session]:
          yield db_session
          db_session.flush()

      app.dependency_overrides[get_db] = _override_get_db
      with TestClient(app) as test_client:
          yield test_client
      app.dependency_overrides.clear()
  ```

**Decisions fixed here**

- **A separate database, `ctaf_test`.** Tests drop and recreate every
  table at session start; pointing them at the development database
  would destroy the seeded data. The name is overridable via
  `TEST_DATABASE_URL`.
- **The test database creates itself.** `ensure_database_exists`
  (§4.4.2) runs before the engine is built, so `pytest` works against
  a Postgres server that has never heard of `ctaf_test` — no
  `createdb` step in the README, and nothing to forget. It is the
  same function the container entrypoint uses, so the path is
  exercised by every test run rather than only at deployment.
- **The schema is built with `create_all`, not by running Alembic.**
  It is faster, and both come from the same `Base.metadata`. The
  migration itself is exercised by the Compose stack, which is where
  it actually matters.
- **`join_transaction_mode="create_savepoint"`** is the mechanism
  that makes isolation work. Routes call `db.commit()` through
  `get_db`; without this setting that commit would end the outer
  transaction and the fixture's rollback would have nothing left to
  undo, leaking rows between tests. With it, the session's commits
  land on savepoints inside the fixture's transaction, and the final
  rollback discards everything.
- **`get_db` is overridden rather than the engine swapped.** The
  route, service, repository, and template code under test is
  byte-for-byte what runs in production; only where the session comes
  from differs.
- **The override yields the same session it flushes**, so writes made
  inside a request are visible to assertions made after it in the
  same test.
- **`TestClient` is used as a context manager**, so startup and
  shutdown events fire as they do in a real run.
- **`follow_redirects=False` is passed per-request** wherever a test
  asserts on a redirect, so the `303` and its `Location` header can
  be inspected rather than transparently followed.

---

### 4.18 Module 18 — Documentation

**Summary**: `README.md` and `docs/AI_PROMPTS.md`.

**Purpose**: documentation is 15% of the assessment, and the AI-usage
note is an explicitly required submission item. The README is also
the thing that determines whether the reviewer ever sees the app
running.

#### 4.18.1 `README.md`

Sections, in order:

1. **What this is** — two sentences naming CTAF, the assignment
   reference, and what the app does.
2. **Screenshot** — the list page, committed to `docs/img/`. It is
   the fastest way to convey what was built.
3. **Quick start with Docker** — the primary path:

   ```
   git clone <url> && cd GGGI_Proposal_Task
   docker compose up --build
   ```

   Then: open `http://localhost:8000`, which redirects to the list
   page already showing ten seeded proposals. Also names
   `http://localhost:8000/docs` for the API browser. States that the
   first build takes a couple of minutes and that migrations and
   seeding run automatically.
4. **Running without Docker** — for a reader who already has a
   Postgres server: create a virtual environment, `pip install -r
   requirements.txt`, then `sh scripts/entrypoint.sh` — or the three
   commands it runs, spelled out. No `.env` is needed unless the
   Postgres credentials differ from the defaults, and no `createdb`
   is needed because §4.4.2 creates the database. Stated plainly as
   the secondary path; Postgres is required either way.
5. **Running the tests** — `pytest -q`. The test database is created
   automatically; the only prerequisite is a reachable Postgres.
6. **How it is put together** — the layer table from §2.1, the
   component diagram from §2.2, and the route table. Enough for a
   reader to navigate the code without opening every file.
7. **Design decisions** — the ones worth defending, each in a short
   paragraph:
   - *Proposals are shared, not per-user.* The assignment mentions no
     accounts and asks for all proposals to be displayed, so the app
     treats them as one shared collection. A nullable `owner_id`
     exists so per-user scoping could be added later without
     rebuilding the table.
   - *The country list is data, not code.* All 54 GGGI member states
     are curated from the Institute's official listing of 12 March
     2026 into `app/domain/data/gggi_members.txt`, read through one
     cached loader. Membership changes several times a year, so the
     list does not belong hard-coded; the loader is the seam that
     lets it move into a database table later without any caller
     changing.

     **Verifying the list is current.** The file header records the
     source URL and the edition date it was curated from. GGGI
     publishes a fresh PDF at `gggi.org` when membership changes;
     compare its entry count and final rows against the file, which
     is deliberately kept in accession order so new members append at
     the end and a diff is a single line.
   - *Deletes are soft.* Records are marked, not removed, so an
     accidental deletion is recoverable and there is a record of what
     happened.
   - *Validation happens twice, deliberately.* Browser attributes for
     fast feedback; Pydantic on the server because anything in the
     browser can be bypassed.
   - *Postgres rather than a JSON file.* A file breaks when two
     people submit at once, cannot be queried for filtering, and
     enforces no types. All three matter here.
   - *A JSON API alongside the pages.* It exists so a React frontend
     can be added later without disentangling logic from the page
     rendering — the endpoints are the seam such a frontend plugs
     into. That two doors reach the same data through the same
     service calls is also the observable evidence that the layering
     is real.
   - *Money is `NUMERIC`, not a float.* Binary floating point stores
     decimal fractions approximately; budgets must be exact.
   - *No inline event handlers.* Jinja's autoescaping protects HTML
     contexts, but an `onsubmit` or `onclick` attribute is a
     JavaScript context, where HTML escaping does not protect
     anything — the HTML parser decodes entities before the script is
     parsed. Values scripts need travel as `data-` attributes and are
     read with `getAttribute()`, so user text is always handled as
     data and never as code.
   - *Development credentials are in `docker-compose.yml` in plain
     text*, reaching a throwaway local container. Nothing here is
     deployed.
8. **What I would add with more time** — a short paragraph pointing
   at §7 of this document.
9. **AI-prompt usage note** — a link to `docs/AI_PROMPTS.md`.

#### 4.18.2 `docs/AI_PROMPTS.md`

**Authored by hand, outside this plan.** The assignment asks for a
5–10 line note covering two or three key prompts used during
development and whether the output was used as-is or modified, and
why. That is a first-hand account of how the work actually happened,
so it is not specified here and not generated. The file is listed in
§5 and linked from the README; its contents are written separately.

---

## 5. File architecture

Final state of the repository. Every file listed is created by this
plan; nothing else is required.

```
GGGI_Proposal_Task/
│
├── app/
│   ├── __init__.py
│   ├── main.py                  FastAPI app: mounts, routers, root, health, 404 handler
│   ├── config.py                Settings read from the environment, cached
│   │
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── constants.py         Category enum; cached country loader and labels
│   │   └── data/
│   │       └── gggi_members.txt 54 GGGI member states, curated from the
│   │                            official 2026-03-12 listing
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py           Engine, SessionLocal, get_db dependency
│   │   ├── bootstrap.py         Creates the database itself if absent
│   │   ├── models.py            Base and the Proposal ORM model
│   │   └── repository.py        ProposalRepository — every query in the app
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── proposal.py          ProposalCreate/Update/Read, format_errors
│   │   └── country.py           CountryOut
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── errors.py            DuplicateProposalError, ProposalNotFoundError
│   │   └── proposal.py          create · get · list · update · delete
│   │
│   ├── web/
│   │   ├── __init__.py
│   │   ├── templates.py         Jinja environment, globals, filters
│   │   └── proposals.py         The seven HTML routes
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── proposals.py         The three JSON endpoints
│   │
│   ├── templates/
│   │   ├── base.html            Shared shell: header, nav, footer, blocks
│   │   ├── form.html            Create and edit, with per-field errors
│   │   ├── list.html            Filter form and the proposals table
│   │   ├── detail.html          One proposal, edit link, delete form
│   │   └── error.html           Styled 404 and other HTTP errors
│   │
│   └── static/
│       ├── style.css            ~150 hand-written lines, no framework
│       ├── counter.js           Live character counter
│       └── confirm-delete.js    Delete confirmation, bound by class
│
├── migrations/
│   ├── env.py                   Points Alembic at Settings and Base.metadata
│   ├── script.py.mako
│   └── versions/
│       └── <rev>_create_proposals_table.py
│
├── scripts/
│   ├── __init__.py
│   ├── seed.py                  Ten realistic proposals, idempotent
│   └── entrypoint.sh            migrate → seed → uvicorn (LF endings)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              engine, connection, db_session, repo, client
│   ├── test_constants.py        Country file parsing and loader behaviour
│   ├── test_schemas.py          Field rules in isolation
│   ├── test_services.py         Rules and soft delete, no HTTP
│   ├── test_web_routes.py       Full request/response through the pages
│   └── test_api.py              The JSON endpoints
│
├── docs/
│   ├── CTAF_Coding_Assignment.pdf
│   ├── climate-proposal-app-plan.md
│   ├── architecture-and-implementation-plan.md   ← this document
│   ├── AI_PROMPTS.md            written by hand, not specified here
│   └── img/
│       └── list-page.png
│
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── .dockerignore
├── .gitattributes
├── .gitignore
├── .env.example
├── requirements.txt
└── README.md
```

**Route reference**

| URL | Method | Purpose | Success response |
|---|---|---|---|
| `/` | GET | Entry point | `307` → `/proposals` |
| `/health` | GET | Liveness | `200` `{"status": "ok"}` |
| `/proposals` | GET | List, optionally filtered | `200` HTML |
| `/proposals/new` | GET | Empty form | `200` HTML |
| `/proposals` | POST | Validate and create | `303` → `/proposals` |
| `/proposals/{id}` | GET | Detail view | `200` HTML |
| `/proposals/{id}/edit` | GET | Form, pre-filled | `200` HTML |
| `/proposals/{id}` | POST | Validate and save the edit | `303` → `/proposals/{id}` |
| `/proposals/{id}/delete` | POST | Soft delete | `303` → `/proposals` |
| `/api/proposals` | GET | List as JSON | `200` JSON array |
| `/api/proposals/{id}` | GET | One proposal as JSON | `200` JSON object |
| `/api/countries` | GET | The 54 GGGI member countries as JSON | `200` JSON array |
| `/docs` | GET | Interactive API documentation | `200` HTML |

---

## 6. Test plan

Run with `pytest -q` against the `ctaf_test` database. Every test
uses the fixtures in §4.17, so each runs inside a transaction that is
rolled back afterwards and no test can see another's rows.

The six tests the assignment's requirements imply directly are marked
**[REQ]**. They are the ones a reviewer would write from the brief
alone; the rest exist because the code has more surface than the
brief describes.

### 6.1 Country data tests — `tests/test_constants.py`

The country list is now data rather than code, so it needs the tests
data gets: that it parses, that it is complete, and that malformed
input fails loudly.

| ID | Scenario | Expected |
|---|---|---|
| C-1 | `load_countries()` against the shipped file | Returns 54 records; every code is two uppercase letters; no duplicates |
| C-2 | Spot-check membership | `DK` and `GY` (the founding 2012 accessions) and `SB` and `LU` (the most recent) are all present; `IN` is absent, since India is not a GGGI member |
| C-3 | Ordering | `country_choices()` is sorted by display name; the file itself is in accession order |
| C-4 | `country_codes()` | A `frozenset` of 54 codes, matching `load_countries()` |
| C-5 | `country_label("KE")` / `country_label("ZZ")` | `"Kenya"` / `"ZZ"` — unknown codes return the code, not an exception |
| C-6 | Non-ASCII handling | `country_label("CI")` returns `"Côte d'Ivoire"` with the accent intact, proving the UTF-8 read |
| C-7 | Caching | Two calls to `load_countries()` return the identical object; `Path.read_text` is invoked once |
| C-8 | Malformed line — two fields instead of three | `ValueError` naming the file and the line number |
| C-9 | Malformed line — a three-letter code | `ValueError` naming the offending code |
| C-10 | A file of only comments and blank lines | `ValueError` reporting no records, not an empty dropdown |
| C-11 | Missing file | `FileNotFoundError` naming the expected path |

C-8 through C-11 use a temporary file with `COUNTRIES_FILE`
monkeypatched and `load_countries.cache_clear()` called first and
last, so the real list is not poisoned for other tests.

### 6.2 Schema tests — `tests/test_schemas.py`

No database, no web server. These run in milliseconds.

| ID | Scenario | Expected |
|---|---|---|
| S-1 | A fully populated valid payload | `ProposalCreate` constructs; `budget_usd` is a `Decimal`; `start_date` is a `date` |
| S-2 **[REQ]** | `project_name=""` | `ValidationError`; `format_errors` → `{"project_name": "Project name is required."}` |
| S-3 | `project_name="   "` | Rejected — stripping happens before the length check |
| S-4 | `project_name` of 201 characters | Rejected with the 200-character message |
| S-5 **[REQ]** | `budget_usd="-5"` | Rejected with "must be greater than zero" |
| S-6 | `budget_usd="0"` | Rejected with the same message — zero is not positive |
| S-7 | `budget_usd="banana"` | Rejected with "must be a number" |
| S-8 | `budget_usd=""` | Rejected with "must be a number", not an unhandled error |
| S-9 | `budget_usd="250,000"` | **Accepted**, parsed as `Decimal("250000")` |
| S-10 **[REQ]** | `summary` of 301 characters | Rejected with the 300-character message |
| S-11 | `summary` of exactly 300 characters | Accepted — the boundary is inclusive |
| S-12 | `summary=""` | **Accepted**; the field is `""`. The assignment does not mark the summary required — see §4.8 |
| S-12b | `summary` omitted entirely | **Accepted**; the field defaults to `""` |
| S-12c | `summary="   "` | Accepted and normalised to `""`, so whitespace and absence have one representation |
| S-13 | `start_date=""` | Accepted; the field is `None` |
| S-14 | `start_date` omitted entirely | Accepted; the field is `None` |
| S-15 | `start_date="not-a-date"` | Rejected with the date message |
| S-16 | `country="ZZ"` | Rejected; `format_errors` → "Select a target country from the list." — confirms the `value_error` key is mapped rather than falling through to the fallback |
| S-16b | `country="IN"` | Rejected — India is not a GGGI member, so a plausible-looking ISO code is still refused |
| S-16c | `country="ke"` | **Accepted**, normalised and stored as `"KE"` |
| S-17 | `category="nuclear"` | Rejected with the category message |
| S-18 | Three fields invalid at once | `format_errors` returns exactly three keys, one message each |
| S-19 | `ProposalRead.model_validate(proposal_orm_object)` | Succeeds; no `deleted_at` or `owner_id` in the dump |

### 6.3 Service tests — `tests/test_services.py`

Database, but no HTTP.

| ID | Scenario | Expected |
|---|---|---|
| V-1 **[REQ]** | `create_proposal` with valid data | Returns a `Proposal` with a UUID `id`, populated `created_at`, and `deleted_at` of `None`; `repo.list()` contains it |
| V-2 | Create, then create again with the same name | `DuplicateProposalError`; the exception carries `project_name` |
| V-3 | Create "Solar Grid", then create "solar grid" | `DuplicateProposalError` — the check is case-insensitive |
| V-4 | Create, soft-delete, then create with the same name again | **Succeeds** — the rule constrains live proposals only |
| V-5 | `get_proposal` with an unknown UUID | `ProposalNotFoundError` |
| V-6 | `get_proposal` for a soft-deleted proposal | `ProposalNotFoundError` |
| V-7 **[REQ]** | Three proposals across KE, KE, ET; `list_proposals(country="KE")` | Exactly the two Kenyan rows |
| V-8 | Filter by category | Only that category's rows |
| V-9 | Both filters together | Only rows matching both |
| V-10 | A filter matching nothing | Empty list, no error |
| V-11 | `list_proposals()` with no filters | Every live proposal, newest first |
| V-12 **[REQ]** | `delete_proposal`, then `list_proposals()` | The proposal is absent from the list |
| V-13 | After `delete_proposal`, query the row directly | The row still exists and `deleted_at` is set — the delete is soft |
| V-14 | `delete_proposal` twice | Second call raises `ProposalNotFoundError` |
| V-15 | `update_proposal` changing budget and summary | Values change; `id` and `created_at` do not; `updated_at` advances |
| V-16 | `update_proposal` keeping the same name | Succeeds — a proposal is not a duplicate of itself |
| V-17 | `update_proposal` taking another live proposal's name | `DuplicateProposalError` |
| V-18 | `update_proposal` on a deleted proposal | `ProposalNotFoundError` |

### 6.4 Web route tests — `tests/test_web_routes.py`

Full requests through `TestClient`, exercising route, schema,
service, repository, and template together.

| ID | Scenario | Expected |
|---|---|---|
| W-1 | `GET /health` | `200`, `{"status": "ok"}` |
| W-2 | `GET /` without following redirects | `307`, `Location: /proposals` |
| W-3 | `GET /proposals/new` | `200`; the body contains all six field names, all 54 country options, and all five category options |
| W-4 **[REQ]** | `POST /proposals` with valid form data, redirects not followed | `303`, `Location: /proposals`; the proposal is then present in the database |
| W-5 | Follow the redirect from W-4 | `200`; the project name appears in the list page body |
| W-6 **[REQ]** | `POST /proposals` with `project_name=""` | `400`; the body contains "Project name is required."; no row is created |
| W-7 **[REQ]** | `POST /proposals` with `budget_usd="-100"` | `400`; the body contains "greater than zero" |
| W-8 **[REQ]** | `POST /proposals` with a 301-character summary | `400`; the body contains "300 characters or fewer" |
| W-9 | A failed POST that had four valid fields | The re-rendered body contains the four submitted values — nothing typed is lost |
| W-10 | `POST /proposals` with a name already in use | `409`; the body contains "already exists" |
| W-11 | `POST /proposals` with `start_date=""` | `303`; the stored proposal has `start_date` of `None` |
| W-11b | `POST /proposals` with `summary=""` | `303`; the proposal is created with an empty summary — the field is optional |
| W-11c | `GET /proposals/{id}` for a proposal with no summary | `200`; the body contains "No summary provided." and no empty gap |
| W-12 **[REQ]** | `GET /proposals?country=KE` with mixed rows seeded | `200`; Kenyan project names present, others absent |
| W-13 | `GET /proposals?category=smart_grid` | Only that category's rows appear |
| W-14 | `GET /proposals?country=ZZ` | `200`; behaves as unfiltered — an invalid filter is discarded, not an error |
| W-15 | `GET /proposals` with an empty database | `200`; the body contains "No proposals yet" |
| W-16 | `GET /proposals/{id}` for an existing proposal | `200`; the summary text and the formatted budget appear |
| W-17 | `GET /proposals/{id}` for an unknown UUID | `404`; the styled error page, not a JSON body |
| W-18 | `GET /proposals/{id}` for a deleted proposal | `404` |
| W-19 | `GET /proposals/{id}/edit` | `200`; every input carries the stored value; the date input is `YYYY-MM-DD` |
| W-20 | `POST /proposals/{id}` with a changed name | `303` → `/proposals/{id}`; the stored name is updated |
| W-21 | `POST /proposals/{id}` with an invalid budget | `400`; the form re-renders in edit mode posting back to the same URL |
| W-22 **[REQ]** | `POST /proposals/{id}/delete` | `303` → `/proposals`; the proposal is gone from the list and its detail page returns `404` |
| W-23 | `POST /proposals/{id}/delete` for an unknown UUID | `404` |
| W-24 | `GET /proposals/new` | The body contains `maxlength="300"`, `min="0.01"`, `required`, and `counter.js` — the browser-side checks are actually rendered |
| W-24b | `GET /proposals/new` | The body contains **no** `novalidate` attribute. A single stray `novalidate` disables every check W-24 asserts is present, so the two are tested together |
| W-24c | `GET /proposals/new` | Exactly four `required` attributes are present, on `project_name`, `country`, `category`, and `budget_usd` — not on `start_date` or `summary`, matching §4.8's requiredness table |
| W-25 | `GET /proposals/{id}` where the summary contains `<script>alert(1)</script>` | The body contains the escaped `&lt;script&gt;`, never the raw tag — autoescaping holds in an HTML text context |
| W-27 | `GET /proposals/{id}` for a proposal named `'); alert(1); //` | The response contains **no** `onsubmit`, `onclick`, or any other `on…=` attribute, and no `<script>` block containing the project name. The name appears only inside `data-project-name="…"`. This is the regression test for the XSS described in §4.11.5 — note that W-25 passes even when this fails, because HTML escaping is correct for a `<p>` and insufficient for a JavaScript context |
| W-28 | `GET /proposals/new`, `/proposals`, `/proposals/{id}`, `/proposals/{id}/edit` | No page contains an inline event-handler attribute. Asserted across all four templates, so the rule holds as new markup is added rather than only where it was once fixed |
| W-26 | `POST /proposals` with `project_name="'; DROP TABLE proposals; --"` | `303`; the row is stored with that literal name and the table still exists — parameterisation holds |

### 6.5 API tests — `tests/test_api.py`

| ID | Scenario | Expected |
|---|---|---|
| A-1 | `GET /api/proposals` with three seeded rows | `200`; a JSON array of three objects, each with `id`, `project_name`, `country`, `category`, `budget_usd`, `start_date`, `summary`, `created_at`, `updated_at` |
| A-2 | `GET /api/proposals?country=KE` | Only Kenyan rows — the same result the HTML list produces for the same filter |
| A-3 | `GET /api/proposals?country=ZZ` | `422` — a program passing a bad code is told, unlike the forgiving HTML route |
| A-4 | `GET /api/proposals` after a soft delete | The deleted proposal is absent |
| A-5 | `GET /api/proposals/{id}` | `200`; the object matches the stored proposal |
| A-6 | `GET /api/proposals/{id}` for an unknown UUID | `404` with a JSON body `{"detail": "Proposal not found."}`, not an HTML page |
| A-7 | Any API response | No `deleted_at` and no `owner_id` field is present |
| A-8 | `GET /openapi.json` | `200`; all three `/api` paths are documented and no `/proposals` HTML path is |
| A-9 | `GET /api/countries` | `200`; 54 objects, each with `code`, `name`, `joined`; sorted by name |
| A-10 | `GET /api/countries` cross-check | Every `code` returned appears in the form's country dropdown — the two doors read the same vocabulary |

### 6.6 Manual verification checklist

Automated tests do not cover what happens in a browser. These are
performed by hand before recording the demo, and they are the
recording's shot list.

1. Open `http://localhost:8000` — it redirects to a list showing ten
   seeded proposals.
2. Filter by Kenya — the table narrows to two rows and the dropdown
   keeps its selection.
3. Filter by Kenya *and* Smart Grid — one row. Clear the filters —
   all ten return.
4. Filter by the Other category — the empty state message appears,
   not a blank table.
5. Open **New proposal**. Check the country dropdown lists all 54
   GGGI members, alphabetically. Type into the summary and watch the
   remaining count fall in real time; at zero the browser stops
   accepting keystrokes, which the counter has already made obvious.
6. Submit with the project name empty — the browser blocks it and
   shows its own message. Nothing reaches the server. **If the form
   submits instead, a stray `novalidate` attribute is the first
   thing to check.**
6b. Submit a complete proposal leaving the summary and the start date
   blank — both are optional, so it saves. Open it: the detail page
   reads "No summary provided." and an em dash for the date.
7. Fill the form correctly and submit — the list reappears with the
   new proposal at the top.
8. Submit again with the same project name — the form returns with
   "already exists" beneath the name field and every other value
   still filled in.
9. Click a project name — the detail page shows every field, with
   the budget formatted and the date readable.
10. Click **Edit**, change the budget, save — the detail page returns
    showing the new figure.
11. Click **Delete** — the confirmation prompt names the proposal.
    Cancel: nothing happens, and the proposal is still there. Delete:
    the list returns without it.
11b. Submit a proposal named `'); alert(1); //`, open it, and click
    Delete. The prompt must show that text **as the proposal's name**
    and no dialog other than the confirmation may appear. If an
    `alert` fires, an inline event handler has crept back in — see
    §4.11.5.
12. Visit the deleted proposal's URL directly — the styled 404 page.
13. Visit `/api/proposals` — JSON, and it does not include the
    deleted proposal. Visit `/api/countries` — the 54 members.
14. Visit `/docs` — the interactive API browser; run
    `GET /api/proposals` from it with a country filter.
15. Narrow the browser window — the header stacks, the filters
    stack, and the table scrolls horizontally rather than the page.

### 6.7 Clean-clone verification

Performed last, and **not** in the working directory. The working
directory holds files and settings the README does not mention, and
that is the most common reason a working project fails on someone
else's machine.

1. Clone the repository into a completely new folder.
2. Follow the README's Docker quick start exactly as written,
   changing nothing.
3. Confirm the stack builds, migrations apply, seeding reports ten
   created, and `localhost:8000` serves the populated list.
4. Run through the §6.6 checklist in that clone.
5. Any step that required knowledge not in the README is a
   documentation bug — fix the README, not the memory of it.

---

## 7. Future works and potential add-ons

Ordered roughly by ratio of value to effort. None is required by the
assignment; the first three are what a second working day would
sensibly buy.

**Move the country list from the text file into a `countries`
table.** This is the follow-on the current design was shaped around,
and §4.2 exists in the form it does specifically to make it small.
The work: an Alembic migration creating `countries` with `code`
(primary key), `name`, and `joined_on`; a data migration inserting
the 54 rows by parsing the existing text file, so the curated data
carries across rather than being retyped; a `Country` ORM model; a
`CountryRepository`; and then **three function bodies change** —
`load_countries()`, `country_choices()`, and `country_codes()` query
instead of reading. Every caller keeps working: the schema validator
already goes through `country_codes()`, the templates already go
through `country_choices()`, and `GET /api/countries` already goes
through `load_countries()`.

Two follow-on decisions arrive with it. The `proposals.country`
column becomes a real foreign key to `countries.code`, so the
database enforces what the application currently enforces alone.
And the `@lru_cache` on the loaders has to go or gain an explicit
invalidation, since the point of the move is that the list can change
while the process is running — which is also when an admin screen for
adding a country starts being worth building.

**Pagination and sorting on the list page.** Ten proposals fit on one
screen; five hundred do not. `list()` in the repository is the only
place that changes — a `limit`/`offset` pair and an `order_by`
argument — plus page controls in `list.html` and two query
parameters on the route. The layering means no other file is touched.

**Free-text search.** A search box matching against project name and
summary. Postgres full-text search (`to_tsvector` with a GIN index)
handles this natively, so it stays one more conditional clause in the
repository rather than filtering in Python.

**A partial unique index on the project name.** The uniqueness rule
currently lives only in the service layer, which means two
simultaneous submissions of the same name could both pass the check
before either commits. `CREATE UNIQUE INDEX ... ON proposals
(lower(project_name)) WHERE deleted_at IS NULL` moves the guarantee
into the database, where concurrency cannot defeat it. The service
check stays, because it produces the friendly message; the index
becomes the backstop, caught as an `IntegrityError` and translated
into the same `DuplicateProposalError`.

**User accounts and per-user scoping.** The `owner_id` column already
exists and is nullable. Adding session-based authentication, setting
`owner_id` on creation, and restricting edit and delete to the owner
or a reviewer role is a self-contained addition: a new
`app/services/auth.py`, a dependency on the routes that mutate, and
one extra condition in the repository. Nothing already written needs
rearranging — which was the point of adding the column early.

**An undelete path.** Soft delete already preserves every row, so
recovery is a query away. A "recently deleted" view with a Restore
button that clears `deleted_at` turns a safety property that
currently only exists on disk into one a person can use.

**Attachments.** Real proposals arrive with a budget spreadsheet and
a concept note. A `proposal_documents` table, object storage rather
than the database for the bytes themselves, and an upload field on
the form.

**Status workflow.** Proposals move through submitted → under review
→ approved or rejected. A `status` column with a default, a filter on
the list page, and a transition guard in the service layer. This is
where a service layer stops being tidiness and starts being
necessary, because a status transition is exactly the kind of rule
that has nowhere else sensible to live.

**CSV export.** A third front door beside HTML and JSON, streaming
`StreamingResponse` from the same `list_proposals` call — perhaps the
clearest possible demonstration of what the layering was for, since
it is a genuinely different output format reached by adding nothing
but the formatting step.

**A React frontend.** This is the addition the JSON API was built
for, and §2.3 sets out the reasoning. A React app would consume
`/api/proposals` and `/api/countries` — both already exist and are
already correct — and the only server-side work is adding the write
endpoints: `POST`, `PUT`, and `DELETE` on `/api/proposals`, each a
handful of lines calling the same service functions the HTML routes
already call. The schemas, the validation rules, the uniqueness rule,
and every query are reused unchanged.

Worth doing when the interface becomes genuinely interactive — live
updating, drag-and-drop, richer editing. Not worth doing before
then: a form and a filterable table are precisely the case where
server rendering wins, because the validation-error round trip stays
one function on the server instead of being reimplemented in
JavaScript, and the pages keep working if a script fails to load.
The point of building the seam now is that the choice can be made
later on its merits rather than being foreclosed by a refactor cost.

**Continuous integration.** A GitHub Actions workflow running `pytest`
against a Postgres service container on every push, plus `ruff` for
linting and `mypy` for type checking. Cheap, and it means the test
suite is run by something other than good intentions.

**Structured logging and error tracking.** Today an exception prints
a traceback to the container log. Structured JSON logs with a
per-request correlation id, and an error tracker such as Sentry,
are what turn "a user says it broke" into a stack trace with the
request attached.

**Rate limiting on the submission endpoint.** The form is
unauthenticated. On any public deployment that is an invitation to
fill the table with junk. A per-IP limit on `POST /proposals` is the
minimum, and a CAPTCHA the next step.

**Internationalisation.** GGGI member countries do not share a
language. Jinja supports gettext-style translation, the country
labels are already separated from the stored codes, and the layer
that would need the work — templates — is the only layer that
contains any English at all.

---

## Implementation note

On approval, the work proceeds in the phase order of §3, with each
phase ending at its observable checkpoint before the next begins.
Git is initialised at the start of Phase 1 with a commit per module,
so the history reads as the plan does.

This document is written to
`docs/architecture-and-implementation-plan.md` as the first action.
