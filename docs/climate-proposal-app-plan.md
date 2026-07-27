# Climate Technology Proposal App — Build Plan

A working document. Tick the boxes in Part 4 as you go.

---

## Contents

- [Part 1 — The big picture](#part-1--the-big-picture)
- [Part 2 — The tools](#part-2--the-tools)
- [Part 3 — The layers in detail](#part-3--the-layers-in-detail)
- [Part 4 — Building it, step by step](#part-4--building-it-step-by-step)
- [Appendix A — File layout](#appendix-a--file-layout)
- [Appendix B — Routes](#appendix-b--routes)
- [Appendix C — Database table](#appendix-c--database-table)
- [Appendix D — Decisions for the README](#appendix-d--decisions-for-the-readme)

---

## Part 1 — The big picture

You are building one Python program. It runs continuously, waits for messages from browsers, and sends messages back. Next to it runs a database, which is a separate program that stores your data on disk.

Inside your Python program, the code is split into five groups of files. Each group has one job. Programmers call these groups **layers**, because they sit in a stack and each one only talks to the one directly below it.

| Layer | Its one job |
|---|---|
| Templates | Turn data into the HTML page a person sees |
| Routes | Receive the message, decide what to do, send a reply |
| Schemas | Check that incoming data is valid |
| Services | Apply your rules about proposals |
| Repository | Read and write the database |

Below all of that sits Postgres, the database itself.

**Why split it this way:** each file stays small and does one understandable thing. When something breaks, you know which file to open. When you want to add a feature, you know where it goes. If you put everything in one big function instead, it works at first and becomes impossible to change after a few weeks.

---

## Part 2 — The tools

| Tool | What it is |
|---|---|
| Uvicorn | The program that listens on a network port and speaks HTTP. You run it; you never write code for it. |
| FastAPI | Connects a URL to one of your Python functions. Also handles validation and sending replies. |
| Pydantic | Describes what valid data looks like and rejects data that doesn't match. Comes with FastAPI. |
| Jinja2 | Lets you write HTML files with gaps in them that get filled with your data. |
| SQLAlchemy | Lets you read and write the database using Python instead of writing SQL by hand. |
| Alembic | Keeps track of changes to your database's structure over time. |
| Postgres | The database. Stores your proposals on disk. |
| Docker Compose | Starts your app and Postgres together with one command. |
| pytest | Runs your tests. |

---

## Part 3 — The layers in detail

### 3.1 Templates

**What it is:** HTML files with placeholders in them.

**Why it exists:** Your list page has to show every proposal in a table, but you don't know how many there will be. You can't write that HTML by hand. A template lets you write the shape of the table once and let Jinja repeat a row for each proposal.

```html
<table>
  {% for p in proposals %}
    <tr>
      <td><a href="/proposals/{{ p.id }}">{{ p.project_name }}</a></td>
      <td>{{ p.country }}</td>
      <td>{{ p.budget_usd }}</td>
    </tr>
  {% endfor %}
</table>
```

`{% for %}` repeats what's inside it. `{{ p.project_name }}` gets replaced with the actual name. You hand Jinja a list of proposals and it hands you back finished HTML.

**The four templates you will write:**

| File | Purpose |
|---|---|
| `base.html` | The shared shell: page header, navigation, the `<html>` and `<body>` tags. Every other template starts from this one so you don't repeat it. |
| `form.html` | The submission form. Also used for editing, because an edit form is the same form with the boxes already filled in. |
| `list.html` | The table and the filter dropdowns. |
| `detail.html` | One proposal on its own page, with the delete button. |

**The small amount of JavaScript that lives here** is the live character counter. It runs in the browser, not on your server, and sends nothing over the network. It just watches the textarea and updates a number on screen:

```javascript
textarea.addEventListener('input', () => {
  counter.textContent = textarea.value.length + " / 300";
});
```

The form inputs also carry `required`, `type="number"`, `min="0"`, and `maxlength="300"`. These are built into every browser: they stop the person submitting an incomplete form and show a message, without you writing any code.

---

### 3.2 Routes

**What it is:** Python functions, each connected to one URL.

**Why it exists:** Something has to receive the incoming message and decide what happens. This is that something.

```python
@router.get("/proposals/{proposal_id}")
def detail(proposal_id: UUID, db: Session = Depends(get_db)):
    proposal = get_proposal(proposal_id, ProposalRepository(db))
    return templates.TemplateResponse("detail.html", {"proposal": proposal})
```

The line starting with `@` tells FastAPI: when a GET request arrives for a URL shaped like `/proposals/something`, run this function and pass the `something` part in as `proposal_id`.

**`Depends(get_db)`** appears everywhere, so it's worth understanding. It means "before running this function, call `get_db()` and pass me the result." `get_db()` opens a connection to the database. This saves writing the same setup lines at the top of every route. FastAPI calls this **dependency injection** — a large name for a small idea: the function declares what it needs and FastAPI supplies it.

**Keep route functions short.** A route does three things and stops: take the input, call one service function, return a page. If a route is more than about five lines, logic has crept in that belongs in the service layer.

**After every POST, send a redirect, not a page.** A redirect is a reply saying "don't display anything, go fetch this other URL instead." The browser does it automatically. If you returned the page directly, the browser's address bar would still point at the POST, and pressing refresh would submit the form again and create a duplicate proposal. Redirecting means refresh just re-fetches a harmless list page.

---

### 3.3 Schemas

**What it is:** Python classes that describe valid data.

**Why it exists:** Everything arriving from a browser is text. `"50000"` is a string, not a number. `"banana"` might arrive where you expected a budget. Something has to check and convert the data before the rest of your code touches it.

```python
class ProposalCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=200)
    country: str
    category: Category
    budget_usd: Decimal = Field(gt=0)
    start_date: date | None = None
    summary: str = Field(max_length=300)
```

Every validation rule from the task is in that block:

- `min_length=1` — can't be empty
- `gt=0` — budget must be greater than zero
- `max_length=300` — the summary limit
- `date | None` — start date is allowed to be missing

When data arrives, Pydantic checks it against this class. If anything fails, it produces a list of exactly which fields failed and why. You use that list to show error messages next to the right boxes on the form.

**Why this exists even though the browser already checks:** the browser is on the other person's computer. They can open developer tools and delete the `maxlength` attribute, turn JavaScript off, or skip the browser entirely and send a request from the command line. None of that is difficult. The browser checks give a fast, pleasant experience to people using the form normally; this Pydantic class is the check that cannot be skipped.

---

### 3.4 Services

**What it is:** ordinary Python functions holding your rules about proposals.

**Why it exists:** Some logic isn't about the shape of a field and isn't about the database. "You can't have two proposals with the same name" is a rule about your application. It needs a home that isn't tangled up with web code.

```python
def create_proposal(data: ProposalCreate, repo: ProposalRepository) -> Proposal:
    if repo.exists_with_name(data.project_name):
        raise DuplicateProposalError(data.project_name)
    return repo.add(Proposal(id=uuid4(), **data.model_dump()))
```

Nothing about HTTP in here, nothing about SQL. It takes validated data, applies a rule, and asks the repository to save it.

**Why this matters practically:** you can test this function in a fraction of a second without starting a web server or a database. You can also call it from somewhere other than a web page later — a script that imports proposals from a spreadsheet, for example — without changing it.

If something goes wrong, raise your own error like `DuplicateProposalError`. The route catches it and decides what the person sees. The service doesn't know what a web page is, so it shouldn't decide what error message to display.

---

### 3.5 Repository

**What it is:** one Python class containing every database query in your app.

**Why it exists:** If queries are scattered across your routes and services, changing anything about how data is stored means hunting through the whole codebase. Keeping them in one file means one place to look.

```python
class ProposalRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, country=None, category=None):
        stmt = select(Proposal).where(Proposal.deleted_at.is_(None))
        if country:
            stmt = stmt.where(Proposal.country == country)
        if category:
            stmt = stmt.where(Proposal.category == category)
        return list(self.db.scalars(stmt.order_by(Proposal.created_at.desc())))
```

This is your filter feature. If the caller passes a country, an extra condition gets added to the query. If not, it's left out. Postgres does the filtering, which is far faster than loading every proposal into Python and filtering there.

`deleted_at.is_(None)` appears in every read — see soft delete in Appendix C.

---

### 3.6 The database

Postgres runs as a separate program and stores your data in a table. The table structure is in [Appendix C](#appendix-c--database-table).

**How Python talks to the table:** you describe it as a Python class in `db/models.py`.

```python
class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_name: Mapped[str]
    country: Mapped[str] = mapped_column(index=True)
    budget_usd: Mapped[Decimal]
```

SQLAlchemy uses this to write the SQL for you. Two reasons that's worth it rather than writing SQL strings yourself:

1. Your editor catches typos in column names.
2. It prevents **SQL injection** — an attack where someone types something like `'; DROP TABLE proposals; --` into a form field and it gets executed as a database command. Building SQL by joining strings together is how that happens. SQLAlchemy makes it structurally impossible.

**A session** is one conversation with the database. You open one when a request arrives, do your reads and writes, then either commit it (make changes permanent) or roll it back (undo everything). `get_db()` handles this and rolls back automatically if your code raises an error, so a half-saved proposal can't happen.

---

### 3.7 Migrations

**What it is:** Alembic, and a folder of small numbered Python files.

**Why it exists:** Your table exists in the database with a fixed set of columns. Later you add a field to the Python class. The database doesn't know about it, and saving breaks.

Alembic compares your Python classes to the actual database and writes a script describing the difference:

```python
def upgrade():
    op.add_column("proposals", sa.Column("status", sa.String(), nullable=True))
```

You run `alembic upgrade head` and the database is updated. These scripts live in git alongside your code, so any copy of the database can be brought up to date by running the same sequence. Without this, every change means writing SQL by hand and remembering to run it everywhere.

> **Read each generated script before applying it.** Alembic is good at spotting added and removed columns but gets renames wrong, because a rename looks identical to deleting one column and adding another.

---

### 3.8 Tests

**What it is:** Python functions that call your code and check the answer, run by pytest.

**Why it exists:** So that when you change something in week three, you find out immediately if you broke something from week one, instead of discovering it during the evaluation.

Six tests cover this app credibly:

1. Submitting a valid proposal saves it
2. Submitting with an empty project name is rejected
3. Submitting a negative budget is rejected
4. Submitting a summary over 300 characters is rejected
5. Filtering by country returns only that country's proposals
6. Deleting a proposal removes it from the list

---

## Part 4 — Building it, step by step

Each step should end with something you can look at. If a step doesn't work, fix it before moving on — debugging one new thing is manageable, debugging four at once is not.

### Step 1 — Get something running

- [ ] Create the project folder and a virtual environment
- [ ] `requirements.txt` with `fastapi` and `uvicorn`
- [ ] `main.py` with one route returning `{"status": "ok"}`
- [ ] Run `uvicorn app.main:app --reload`, open `localhost:8000`
- [ ] `git init` and first commit

*This proves your setup works and nothing else. Do it first anyway.*

### Step 2 — Settings

- [ ] `config.py` reading `DATABASE_URL` from the environment
- [ ] `.env.example` showing what variables are needed
- [ ] Add `.env` to `.gitignore` so real values never reach git

**Environment variables** are values set outside your program rather than written into it. The database address is different on your laptop than inside Docker, so keeping it in a variable means the same code works in both places. It also keeps passwords out of your git history.

### Step 3 — Your first page

- [ ] Add Jinja2
- [ ] Create `base.html` and one page rendering fixed text
- [ ] Add a route that returns it

*You should now see your own HTML in the browser.*

### Step 4 — The form, doing nothing

- [ ] Build `form.html` with all six fields and a submit button
- [ ] `GET /proposals/new` to show it
- [ ] `POST /proposals` that only prints what it received

*Submit the form and read what gets printed. This is the moment the whole request-and-response idea becomes real — don't rush past it.*

### Step 5 — Validation

- [ ] Write `schemas/proposal.py`
- [ ] Run incoming data through it in the POST route
- [ ] On failure, render `form.html` again with error messages **and the values the person already typed**
- [ ] Add `required`, `min="0"`, `maxlength="300"` to the inputs
- [ ] Add the character counter script

*The entire validation requirement is now finished, and there is still no database.*

### Step 6 — The database

- [ ] `docker-compose.yml` with a Postgres service; start it
- [ ] Write `db/models.py` and `db/session.py`
- [ ] `alembic init migrations`, point it at your models
- [ ] Generate and apply the first migration
- [ ] Connect with `psql` and confirm the table exists

### Step 7 — Saving

- [ ] POST route saves the proposal and redirects to `/proposals`
- [ ] List route can return a placeholder for now

*Run `SELECT * FROM proposals;` and see your row.*

### Step 8 — The list page

- [ ] Query the proposals
- [ ] Render them in a table
- [ ] Make each row link to `/proposals/{id}`

*The full cycle now works: submit a proposal, see it appear in the list.*

### Step 9 — Filtering

- [ ] Read `country` and `category` as optional values from the URL
- [ ] Pass them into the query
- [ ] Add the two dropdowns to the list page

### Step 10 — Detail, delete, edit

- [ ] Detail page fetches one proposal by id, 404 if not found
- [ ] Delete as a POST with a JavaScript `confirm()` prompt, setting `deleted_at`
- [ ] Edit reuses `form.html` pre-filled, posting to a different URL

### Step 11 — Split into layers

- [ ] Move logic out of routes into `services/proposal.py`
- [ ] Move queries into `db/repository.py`
- [ ] Routes shrink to a few lines each

*Doing this now rather than at the start is deliberate. You've seen the code work, so you can see exactly which parts belong where. Splitting before you understand the shape of the problem produces boundaries in the wrong places.*

### Step 12 — Tests

- [ ] Write the six tests from section 3.8

### Step 13 — Example data

- [ ] `scripts/seed.py` creating 8–10 realistic proposals across different countries and categories

*Without this, whoever opens your app sees an empty table and empty filters.*

### Step 14 — Packaging

- [ ] Write a `Dockerfile`
- [ ] Add your app to `docker-compose.yml` alongside Postgres
- [ ] Confirm `docker compose up` starts everything

### Step 15 — README

- [ ] How to run it
- [ ] The decisions from [Appendix D](#appendix-d--decisions-for-the-readme)

### Final check

- [ ] Clone your own repository into a **completely new folder**
- [ ] Follow your README exactly as written
- [ ] Confirm it starts and the seeded data appears

> Do not test this in the folder you've been working in. That folder has files and settings your instructions don't mention, and that's the most common reason a working project fails on someone else's machine.

---

## Appendix A — File layout

```
app/
  main.py               Starts the app, connects the routes
  config.py             Reads settings from environment variables
  db/
    session.py          Opens and closes database connections
    models.py           The Proposal table as a Python class
    repository.py       All database queries
  services/
    proposal.py         Your rules
  schemas/
    proposal.py         Validation
  web/
    proposals.py        The seven routes
  templates/            The four HTML files
  static/               CSS and the character counter script
migrations/             Alembic's scripts
tests/
scripts/seed.py         Creates example proposals
```

---

## Appendix B — Routes

| URL | Method | What it does |
|---|---|---|
| `/proposals/new` | GET | Show the empty form |
| `/proposals` | POST | Validate and save, then redirect |
| `/proposals` | GET | Show the list page |
| `/proposals/{id}` | GET | Show one proposal |
| `/proposals/{id}/edit` | GET | Show the form, filled in |
| `/proposals/{id}` | POST | Save the edit, then redirect |
| `/proposals/{id}/delete` | POST | Delete it, then redirect |

---

## Appendix C — Database table

Table name: `proposals`

| Column | Type | Why |
|---|---|---|
| `id` | UUID | A long random identifier like `f47ac10b-58cc-...`. Used instead of counting 1, 2, 3 so IDs in URLs don't reveal how many proposals exist. |
| `project_name` | TEXT | |
| `country` | TEXT | Stored as a two-letter code like `KE`, so the display name can change without touching the data. Indexed. |
| `category` | TEXT | Indexed. |
| `budget_usd` | NUMERIC | Used for money instead of a decimal number type, because decimals in computers are stored approximately and small rounding errors appear. NUMERIC stores the exact value. |
| `start_date` | DATE | Can be empty. |
| `summary` | TEXT | |
| `owner_id` | UUID | Empty for now — see below. |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |
| `deleted_at` | TIMESTAMP | Empty for a live proposal — see below. |

**Index.** A lookup structure the database builds for a column. Without one, finding all proposals where country is `KE` means checking every row one at a time. With one, the database jumps straight to the matching rows. Add them on `country` and `category`, the two columns you filter by.

**Soft delete.** When someone deletes a proposal, you don't remove the row — you set `deleted_at` to the current time, and every query that reads proposals ignores rows where `deleted_at` is filled in. To the user it has vanished. To you it's still there, so an accidental deletion is recoverable and you have a record of what happened. Standard practice for anything a person might regret deleting.

**`owner_id`.** An empty column added now against a possible future. The task doesn't ask for user accounts, so every proposal is visible to everyone. But if accounts were added later, you'd want to know who created each proposal, and there'd be no way to work that out for records already saved. Adding the empty column now costs nothing and keeps that door open.

---

## Appendix D — Decisions for the README

Write these up in your own words. They show you read the task carefully and made deliberate choices.

**Proposals are shared, not per-user.** The task doesn't mention accounts or logins, and it asks for *all* submitted proposals to be displayed. The app therefore treats proposals as one shared collection, as would suit an internal review team. A nullable `owner_id` column exists so per-user scoping could be added later without rebuilding the table.

**Deletes are soft.** Records are marked deleted rather than removed, so an accidental deletion is recoverable.

**Validation happens twice, on purpose.** The browser checks give fast feedback to people using the form normally. The server checks are the ones that actually count, because anything running in the browser can be bypassed.

**Postgres rather than a JSON file.** The task allows any storage method. A file breaks when two people submit at the same time, can't be queried for filtering, and doesn't enforce types. Postgres handles all three.

**What you'd add with more time.** Worth including — one short paragraph. User accounts, pagination on the list page, and a proper error-tracking setup are honest answers.
