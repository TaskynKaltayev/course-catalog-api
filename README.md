# course-catalog-api

Backend of the course catalog: FastAPI, SQLAlchemy 2.1, PostgreSQL, and Alembic
migrations (Labs 4–7 of "Advanced Web Technologies").

Author: **Taskyn Kaltayev**

## How to run

You need Python 3.11 or newer and PostgreSQL 16 or newer.

Once, as the `postgres` superuser, create the role and the database:

```sql
CREATE ROLE catalog_app LOGIN PASSWORD 'change-me';
CREATE DATABASE course_catalog OWNER catalog_app;
```

Then, from the project folder:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (it holds the database address and is not in the repository),
then create the schema, load the data and start the server:

```bash
alembic upgrade head
```

```bash
psql -h localhost -U catalog_app -d course_catalog -v ON_ERROR_STOP=1 -f seed.sql
```

```bash
fastapi dev main.py
```

API documentation: http://localhost:8000/docs. The password `change-me` is for
teaching; in a real project, passwords are never put into the repository.

Checks: `python check_db.py` (connection), `python check_models.py` (models against the
database), `python try_errors.py` (error responses, with the server running).

## What changed in the API

- **The data lives in PostgreSQL.** Courses, students and enrollments are rows in three
  tables instead of Python lists; likes and enrollments survive a server restart. `data.py`
  is gone, and the Pydantic models moved to `schemas.py` so that `models.py` can hold the
  SQLAlchemy tables.
- **`POST /enrollments` takes `studentId`, not `studentName`.** An enrollment references a
  row in `students`, so a student is created first with `POST /students` and only then
  enrolled. The enrollment form of the Lab 5 frontend still sends `studentName` and will get
  422 until it is updated.
- **New routes:** `POST /students`, `GET /stats/courses` (enrollments per course, including
  courses with none). `GET /enrollments` now joins the tables and returns `courseTitle` and
  `studentName` alongside the identifiers.
- **The `level` field** was added to every course with migration 0002: `beginner` for
  elective courses, `intermediate` for the rest. `GET /courses?level=beginner` filters by it,
  next to the existing `is_elective` and `sort`.
- **Constraint violations became meaningful responses.** A taken email or a repeated
  enrollment gives 409, an unknown course or student gives 404, and a name shorter than two
  characters gives 422 from Pydantic before the request ever reaches the database. An
  unfamiliar violation is re-raised and shows up as 500, because that means a bug in the code.

## Migrations

| Command | What it does |
|---------|--------------|
| `alembic upgrade head` | applies all the missing migrations |
| `alembic downgrade -1` | rolls back the last migration |
| `alembic current` | shows the version of the database |
| `alembic history` | shows the chain of migrations |
| `alembic revision --autogenerate -m "text"` | writes a draft from models vs. database |
| `alembic check` | reports whether the models and the database have diverged |
| `alembic upgrade 0001:0002 --sql` | prints the SQL of a migration without running it |
| `alembic stamp head` | marks the database as up to date without running migrations |

## Experiment log

| # | Experiment | What I saw | Cause | How I fixed it |
|---|------------|------------|-------|----------------|
| 1 | the `uq` template in `naming_convention` changed | `check_models.py`: names only in models `['enrollments_course_id_unique', 'students_email_unique']`, names only in database `['enrollments_course_id_student_id_key', 'students_email_key']` | the template built a name the database never chose, so the models and the schema describe the same constraint under different names; Alembic would offer to recreate it and the 409 lookup in step 5 would miss | restored `%(table_name)s_%(column_0_N_name)s_key`; both lists went back to `none` |
| 2 | `min_length` removed from `StudentIn`, name `N` | 500 Internal Server Error; in the server log `IntegrityError: (psycopg.errors.CheckViolation) … violates check constraint "students_name_check"` | with the Pydantic check gone the request reached the database; the `CHECK` stopped the row, but `students_name_check` is not in `CONSTRAINT_ERRORS`, so the handler treated it as a bug and answered 500 | restored `Field(min_length=2)`: the right answer (422) comes from Pydantic, and the `CHECK` stays as insurance |
| 3 | a typo in a constraint name in the dictionary | 500 again; the log named the real constraint — `(psycopg.errors.UniqueViolation) … "students_email_key"` | the key in `CONSTRAINT_ERRORS` was `students_email_uniq`, so the lookup found nothing and the violation fell through to the "unknown" branch | restored the key; `try_errors.py` went back to 5 of 5 |
| 4 | `title` without `NOT NULL` in the database, `alembic check` | `Detected NOT NULL on column 'courses.title'`, then `FAILED: New upgrade operations detected: [('modify_nullable', …)]`; after changing the type to `varchar(100)` — `Detected type change from VARCHAR(length=100) to Text()` and `modify_type` | `alembic check` compares the models with the real schema, so a change made by hand in psql shows up as a pending migration | put `NOT NULL` and `text` back; check returned `No new upgrade operations detected.` |
| 5 | automatic migration `0002` on existing data | `IntegrityError: (psycopg.errors.NotNullViolation) column "level" of relation "courses" contains null values`, `[SQL: ALTER TABLE courses ADD COLUMN level TEXT NOT NULL]`; `alembic current` still `0001` | autogenerate compares schemas, not data: a required column without a default has no value for the six rows that already exist; the whole migration rolled back in its transaction | rewrote `upgrade()` in three steps — add the column as nullable, fill it with a `CASE`, then set `NOT NULL` |
| 6 | `import models` commented out in `env.py` | autogenerate wrote `0003_oops.py` with `op.drop_table('courses')`, `op.drop_table('enrollments')`, `op.drop_table('students')` and `drop_index` | without the import the models never register in `Base.metadata`, so Alembic saw an empty target schema and decided the three real tables were superfluous | deleted `0003_oops.py` and restored the import; applying that migration would have destroyed all the data |
| 7 | a `phone` field in the model without a migration | `Detected added column 'students.phone'`, `FAILED: New upgrade operations detected: [('add_column', …)]` | the model got ahead of the database; it works locally only until someone else runs the old schema | removed the field (in real work this is where the migration is written and committed together with the model) |
| 8 | two migrations from one revision | `alembic heads` printed `0003 (head)` and `0004 (head)`; `alembic upgrade head` refused with `Multiple head revisions are present for given argument 'head'` | two migrations declared the same parent `0002`, so the chain has two ends and Alembic cannot pick one | `alembic merge heads` created `0005` with two parents and a single head; then deleted all three experiment files, leaving `0002 (head)` |

## Decisions

- **The response is chosen by the constraint name, not by SQLSTATE, and the error is caught
  after `commit()`.** SQLSTATE is too coarse: `23505` means "some unique constraint was
  violated", and this schema has two of them — a taken email (409 about the student) and a
  repeated enrollment (409 about the course). Only `exc.orig.diag.constraint_name` says which
  one fired. The message text is worse still: it changes between PostgreSQL versions and is
  localized — on this machine the server speaks Russian. As for checking in advance with a
  `SELECT`, between that check and the `INSERT` another request can take the same email, so
  the check is stale the moment it returns; the database's own constraint is the only check
  that cannot be raced. Trying the insert and handling the refusal is both correct and one
  query cheaper.
- **A like is `UPDATE courses SET likes = likes + 1`.** The database computes the new value
  while holding the row lock. If the code read the number into Python and wrote back
  `likes + 1`, two simultaneous requests would both read 11, both write 12, and one like would
  be silently lost. `RETURNING` then hands back the committed number, so the client sees what
  is actually stored rather than its own guess.
- **Migration 0002 is split into three steps.** `ALTER TABLE … ADD COLUMN level TEXT NOT NULL`
  cannot run on a table that already holds rows: the existing six courses have no value for
  the new column, and there is no default to fall back on. Adding the column as nullable,
  filling it by an explicit rule, and only then forbidding `NULL` gets the same end state
  without a moment where the constraint is false. The rule itself is a decision about data,
  not about schema, which is exactly why autogenerate cannot write this migration for you.

## Migration 0002 self-check

| What to check | Result |
|---------------|--------|
| Goal and steps | Yes. One goal — give every course a required difficulty level — in three steps inside one migration: add nullable, backfill, set `NOT NULL`. Nothing unrelated is bundled in. |
| Data | Yes. The six existing rows are filled by an explicit rule (`beginner` for elective courses, `intermediate` otherwise) before the column becomes required; no row is lost or left empty. |
| Renames and drops | No renames and no drops in `upgrade()`. The column is new, so nothing existing is touched. |
| Rollback | Yes, `downgrade()` drops the column, and the `upgrade → downgrade → upgrade` cycle was run against the real database. On production this rollback would destroy any levels chosen by hand — here the values are recomputed by the rule, so it is safe. |
| Verification | Yes. `alembic upgrade 0001:0002 --sql` was read first (`BEGIN`, three statements, the `alembic_version` update, `COMMIT`), then the cycle was run, and `alembic check` reports no differences. |
| History | Yes. `alembic heads` shows a single head `0002`, and the migration is committed together with the model, the schema and the updated `seed.sql`. |
| Application | Yes. `CourseOut` gained `level`, `GET /courses` gained a `level` filter, and `seed.sql` writes the new column. Clients get one extra field in every course response; nothing they already send becomes invalid. |
