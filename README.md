# course-catalog-api

Backend of the course catalog: FastAPI, SQLAlchemy, PostgreSQL, Alembic migrations,
GraphQL on Strawberry, and JWT login with roles (Labs 4–9, "Advanced Web Technologies").

Author: **Taskyn Kaltayev**

## How to run

You need Python 3.11 or newer and PostgreSQL 16 or newer.

Once, as the `postgres` superuser, create the role and the database:

```sql
CREATE ROLE catalog_app LOGIN PASSWORD 'change-me';
CREATE DATABASE course_catalog OWNER catalog_app;
```

Then, from the project folder, create the environment and install the dependencies:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`. It holds the database address and `SECRET_KEY`, which is empty in
the example and must be at least 32 characters: without it the application does not start.
Generate a key and paste it after `SECRET_KEY=`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Create the schema (three migrations), load the data, create the users, start the server:

```bash
alembic upgrade head
```

```bash
psql -h localhost -U catalog_app -d course_catalog -v ON_ERROR_STOP=1 -f seed.sql
```

```bash
python seed_users.py
```

```bash
fastapi dev main.py
```

REST docs: http://localhost:8000/docs. GraphiQL: http://localhost:8000/graphql.

Demo users (course passwords; a real project never publishes them):

| E-mail | Role | Password |
|--------|------|----------|
| admin@example.com | admin | admin-demo-password |
| aigerim@example.com | student (student 1) | aigerim-demo-pass |
| daniyar@example.com | student (student 2) | daniyar-demo-pass |
| asel@example.com | student (student 3) | asel-demo-password |

`seed.sql` also clears `users`: after it, always run `python seed_users.py`.

Check scripts, with the server running: `check_users.py` (4 of 4), `try_auth.py` (6 of 6),
`try_tokens.py` (9 of 9), `try_timing.py`, `try_access.py` (14 of 14), `try_errors.py` (5 of 5),
`try_graphql_access.py` (9 of 9), `try_graphql.py` (8 of 8), `try_n_plus_1.py` (4 and 4 SQL
queries), `measure.py`, and the scanners `scan_routes.py` and `scan_graphql.py`.

## Access matrix

The codes come from `python try_access.py` (14 of 14 as expected). The "—" cell: the
administrator has no student profile, so there is nobody to enroll "for yourself".

| Request | Anonymous | Student | Administrator |
|---------|-----------|---------|---------------|
| `GET /courses` | 200 | 200 | 200 |
| `GET /me` | 401 | 200 | 200 |
| `GET /enrollments` | 401 | 403 | 200 |
| `POST /enrollments`, for yourself | 401 | 201 | — |
| `POST /enrollments`, for another | 401 | 403 | 201 |

A 401 always comes with `WWW-Authenticate: Bearer` (no token or a bad one: "who are you?"); a 403
comes without it (the token is fine, the role or the owner is not: "I know you, but no").

## Open spots

Found by `scan_routes.py` and `scan_graphql.py`; not closed in this lab.

| Route or field | Verdict | How to close it |
|----------------|---------|-----------------|
| `GET /` | by design: a health message with no data | no need to close it |
| `GET /courses` | by design: the catalog is open to everyone | no need to close it |
| `GET /courses/{id}` | by design: a course page is part of the public catalog | no need to close it |
| `POST /courses/{id}/like` | a hole: an anonymous caller inflates the counter without limit | `CurrentUser`, one "like" per user (a `likes` table with a unique `(user_id, course_id)`) |
| `POST /students` | a hole: anyone creates student profiles with any name and e-mail | `AdminUser`, or create the profile together with the account at registration |
| `GET /students/{id}` | a hole: anyone reads any student's name and e-mail by trying ids | `CurrentUser` plus `can_access_student`: the student themselves or the administrator |
| `GET /students/{id}/enrollments` | a hole: anyone learns which courses any student takes | `CurrentUser` plus `can_access_student`, the same rule as for the profile |
| `GET /stats/courses` | by design: aggregated numbers per course, no personal data | no need to close it |
| GraphQL `courses` | by design: the same public catalog as `GET /courses` | no need to close it |
| GraphQL `course` | by design: the same as `GET /courses/{id}` | no need to close it |
| GraphQL `student` | a hole: the name and the courses of any student are open; only `email` is closed | `IsSelfOrAdmin` on the field, the same rule as `GET /students/{id}` |
| GraphQL `enrollments` | a hole: all enrollments of all students, which REST gives only to the administrator | `IsAdmin`, as `GET /enrollments` in REST |
| GraphQL `Course.enrollments` | a hole: through a public course anyone reaches the list of its students | `IsAdmin` on the field, or show others only the number of enrollments |
| GraphQL `Student.enrollments` | a hole: the courses of any student, as in `GET /students/{id}/enrollments` | `IsSelfOrAdmin` on the field |
| GraphQL `enroll` | a hole: an anonymous caller enrolls any student in any course; REST closed this in step 3 | move the owner check into `services.enroll` so both entrances share it |
| GraphQL `likeCourse` | a hole: the same as `POST /courses/{id}/like` | `IsAuthenticated` and one "like" per user, in the service |

## Threat table

| Where | What can break | How it is covered | How I checked |
|-------|----------------|-------------------|---------------|
| The login form | the answer or the time reveals which e-mails are registered; passwords can be guessed | `auth.authenticate` answers every failure with the same 401 `Incorrect email or password` and always runs Argon2id: for an unknown e-mail it verifies against `DUMMY_HASH` | `try_auth.py` 6 of 6; experiment 2: 94.7 vs 97.0 ms with `DUMMY_HASH`, 6.9 vs 99.1 ms without it. Guessing is not limited (see below) |
| Passwords and the key | a leaked table gives the passwords; a leaked or weak key lets anyone sign tokens | `users.password_hash` holds Argon2id (`m=65536,t=3,p=4`, its own salt per hash), never the password; `SECRET_KEY` comes from `.env`, `Field(min_length=32)` in `config.py`; `.env` is in `.gitignore`, only `.env.example` without a value is in git | `check_users.py` 4 of 4; experiment 1: no key → `Field required`, a short key → `at least 32 characters`; two hashes of one password differ, both verify |
| Token and role | a token with an edited payload, another key or issuer, `alg: none`, an expired one; a role that stays in an old token | `security.read_access_token`: `algorithms=["HS256"]`, `issuer`, `require` of `exp`, `sub`, `iss`; lifetime 15 minutes; `get_current_user` reads the user and the role from the database on every request | `try_tokens.py` 9 of 9; experiment 3: with the signature check off only 3 of 9, `alg: none` gave the administrator; experiment 4: a role changed in the database works on the next request with the same token |
| Permissions on objects | a student enrolls another student (BOLA); a route or a GraphQL field is forgotten | `can_access_student` in `POST /enrollments`, `AdminUser` on `GET /enrollments`; `IsAdmin` on `students`, `IsSelfOrAdmin` on `Student.email`, which allows `null` | `try_access.py` 14 of 14, `try_graphql_access.py` 9 of 9; experiment 5: without the owner check Aigerim enrolled Daniyar (201); experiment 6; the scanners: 8 open routes and 8 open fields (see "Open spots") |
| Cookie and Next.js | JavaScript on the page steals the token; a forged cookie opens a private page | the token lives in the `session` cookie with `httpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, `maxAge` 900; `proxy.ts` checks that the cookie exists, `verifySession()` asks the API `/me` next to the data | the browser check: `document.cookie` is empty, without a cookie `/account` → `/login`; experiment 7: a forged cookie passes `proxy.ts`, but `/me` answers 401 and the page redirects to `/login` |
| Logout and lifetime | a copied token keeps working after "Log out" | only the 15-minute `exp`; "Log out" deletes the cookie in the browser | experiment 8: after "Log out" the same token still gets 200 from `/me` |

"Log out" guarantees that this browser no longer sends the token and `/account` closes; it does
not guarantee that a copy of the token stops working before its 15 minutes run out.

Deliberately not closed:

- **Limiting login attempts.** Now guessing is limited only by the response time, about 70–100 ms
  per attempt. A counter in the process memory is lost on restart and is not shared: with four
  server processes the attacker gets four times the limit. So I would keep it in a shared store:
  Redis with `INCR` and a TTL (one fast operation per login), or a `login_attempts` table if no
  new service is wanted. A limit on the e-mail alone is bad: anyone who knows someone's address
  can block that person's login by failing on purpose, and it does not stop one password tried
  against thousands of e-mails. So the counter should key on the IP and on the pair "IP and
  e-mail", with a growing delay rather than a hard lock of the account.
- **The token after "Log out".** I would choose `token_version`: an integer in `users`, put into
  the token at login and increased at "Log out on all devices". It costs almost nothing here,
  because `get_current_user` already reads the user's row on every request: comparing one more
  number adds no query. It needs a migration with the new column and one comparison after
  decoding the token. A `jti` list needs a new table and a lookup on every request, and refresh
  tokens need a table and a second endpoint; both are heavier than this project needs.

## Experiment log

| No. | Experiment | What I saw | Cause | How I fixed it |
|-----|------------|------------|-------|----------------|
| 1 | no key, a short key; two hashes of one password | without `SECRET_KEY`: `secret_key Field required [type=missing]`; with a short one: `String should have at least 32 characters`; a hash takes about 69 ms and looks like `$argon2id$v=19$m=65536,t=3,p=4$salt$hash`; two hashes of one password differ, both verify `True`, a wrong password `False` | `Settings` validates the key when the application starts; Argon2id puts a new random salt and its parameters into every hash | put the key back into `.env`; the hashes need no fix: different strings are the point |
| 2 | login time with and without `DUMMY_HASH` | with it: unknown e-mail 94.7 ms, known 97.0 ms; without it: 6.9 ms vs 99.1 ms, about 14 times faster for an unknown e-mail | without the dummy check the server answers at once when there is no user, so the time tells whether the e-mail exists, even though the text is the same | restored the verification against `DUMMY_HASH`: 91.1 and 91.3 ms |
| 3 | nine forged tokens; signature check turned off | with the checks: 9 of 9 rejected with 401; with `verify_signature: False`: 3 of 9, the expired token, the one signed with another key, another issuer and the one without `exp` let Aigerim in, the edited payload and `alg: none` gave `admin@example.com` | without the signature the payload is just base64 text: anyone can write `sub: "1"` | restored `jwt.decode` with the key, `algorithms`, `issuer` and `require`: 9 of 9 |
| 4 | the role changes in the database, the token is the same | the administrator's token: 200 on `/enrollments`, after `role = 'student'` 403, after restoring 200; Aigerim's token: 403, after `role = 'admin'` 200, after restoring 403 | the role is not in the token: `get_current_user` reads it from `users` on every request | put the roles back; nothing to fix, this is the intended behaviour |
| 5 | the owner check in `POST /enrollments` removed | `try_access.py`: 13 of 14, the cell `201 (want 403)`; Aigerim with her own token enrolled Daniyar Bekov in `web-security` (enrollment 20) | the token only says who is calling; whether this caller may act on student 2 is a separate check (BOLA) | deleted enrollment 20, restored `can_access_student`: 14 of 14 |
| 6 | the path closed, not the field; the closed field not nullable | `email: str` without a permission: `student(2).email` gave `daniyar@example.com` to Aigerim, 7 of 9; with the permission but not nullable: `{"data": {"student": null}}` with `path ["student", "email"]`, and the whole `enrollments` answer became `null` (`path ['enrollments', 2, 'student', 'email']`), 7 of 9 | a field is reached by many paths (`student`, `enrollments → student`), so only the field itself is a safe place for the rule; a refused non-null field turns into `null` that rises to the nearest nullable parent | `email: str \| None` with `IsSelfOrAdmin`: 9 of 9, the other fields stay visible |
| 7 | a forged cookie; protection only in `proxy.ts` | without a cookie `/account` answered 307 to `/login` and the API saw no request; with `session=forged.token.value` also 307, but the API log showed `GET /me 401`; with a page that does not call `verifySession()` the forged cookie got 200 and the private page | `proxy.ts` only checks that a cookie exists and cannot tell a real one from a forgery; only the API verifies the signature | `git restore app/account/page.tsx`: `verifySession()` next to the data, the forged cookie gives 307 again |
| 8 | the token after "Log out" | after "Log out" the cookie is gone and `/account` sends to `/login`, but the same token with `curl /me` still answered 200 `{"id":2,"email":"aigerim@example.com","role":"student","studentId":1}` | the token is checked by its signature and the server keeps no list of issued tokens, so it is valid until `exp`, up to 15 minutes | not fixed in this lab: a short lifetime and `token_version` would reduce the risk of a stolen token (see the threat table) |

## Decisions

- **The role is read from the database on every request, not from the token.** It costs one
  query by primary key per request, which is also why `try_n_plus_1.py` now shows 4 instead of
  3. In return, a change of role or a deleted user takes effect at once (experiment 4), not after
  up to 15 minutes, and the token carries only `sub`, so there is nothing in it to keep in sync.
- **The closed GraphQL field allows `null`, and the permission sits on `Student.email`, not on
  the root query.** The same student is reached through `student`, `students` and
  `enrollments → student`; a rule on one root query leaves the other paths open, as experiment 6
  showed. A refused field becomes `null`, and if the field were `String!` that `null` would wipe
  out the whole student or even the whole list; with `String` only the e-mail disappears and the
  error points to it.
- **`proxy.ts` checks only that a cookie exists, while `verifySession()` stands next to the
  data.** The proxy runs before every request and must be fast, so it does not call the API: it
  cannot tell a real token from a forged string, as experiment 7 showed. Only the API can check
  the signature, so the real check happens where the data is read; the proxy only saves a
  round trip for visitors without any cookie.

## Lab 8: GraphQL

### What changed in the API

- **REST errors follow Problem Details (RFC 9457).** A rule failure arrives with the content
  type `application/problem+json` and the fields `type`, `title`, `status`, `detail` and
  `instance`; `type` names the kind of error, for example
  `https://example.com/problems/already-enrolled`. The rules live in `services.py` and raise a
  `ServiceError` with a code; `problem.py` turns the code into a status and a body. Unknown
  addresses and wrong methods also arrive as Problem Details with `type: about:blank`, and a
  405 keeps its `Allow` header. Pydantic validation errors (422) stay in FastAPI's own format.
- **`/graphql` is a second entrance to the same data.** It uses the same database session per
  request and the same services. A browser opening the address with `GET` gets GraphiQL — an
  editor with hints and schema documentation; a client sends `POST` with JSON
  `{"query": …, "variables": …}` and gets exactly the fields it asked for.
- **Mutations `enroll` and `likeCourse` return `userErrors`.** An expected rule error — a
  repeated enrollment, an unknown course or student — arrives in `data`, inside the mutation
  result, with the same code the services layer gives REST. Only unexpected failures and
  invalid queries arrive in `errors`. Both cases have status 200.
- **The `X-SQL-Queries` header** on every response counts the database queries the request
  caused. It is a measuring instrument: it made the N+1 problem visible and shows that
  DataLoaders keep GraphQL at three queries regardless of the amount of data.
- **Protection.** A query may be at most 5 levels deep and use at most 10 aliases; `limit`
  must be between 1 and 100; a student `id` must be a number. The text of unexpected internal
  errors is replaced with `Unexpected error.`, while the real cause stays in the server log.
  Introspection is controlled by the `GRAPHQL_INTROSPECTION` variable (on by default).
- **New REST routes:** `GET /students/{id}` and `GET /students/{id}/enrollments`, used by the
  REST version of the "My courses" screen.

### Example queries

The "My courses" query (in the GraphiQL Variables panel: `{"id": "2"}`):

```graphql
query MyCourses($id: ID!) {
  student(id: $id) {
    name
    enrollments {
      id
      course { title credits level }
    }
  }
}
```

```json
{
  "data": {
    "student": {
      "name": "Daniyar Bekov",
      "enrollments": [
        { "id": "3", "course": { "title": "Modern Frontend: React & Next.js", "credits": 5, "level": "intermediate" } },
        { "id": "4", "course": { "title": "Backend Foundations: FastAPI", "credits": 5, "level": "intermediate" } },
        { "id": "5", "course": { "title": "AI/LLM Integration", "credits": 5, "level": "beginner" } }
      ]
    }
  }
}
```

The `enroll` mutation (Variables: `{"input": {"courseId": "web-security", "studentId": "3"}}`):

```graphql
mutation Enroll($input: EnrollInput!) {
  enroll(input: $input) {
    enrollment { id enrolledAt course { title } }
    userErrors { code message }
  }
}
```

The first time the enrollment is created and `userErrors` is empty. The same mutation again:

```json
{
  "data": {
    "enroll": {
      "enrollment": null,
      "userErrors": [
        { "code": "ALREADY_ENROLLED", "message": "Student is already enrolled in this course" }
      ]
    }
  }
}
```

### REST vs GraphQL comparison

The "My courses" screen of student 2; numbers from `measure.py`, starting data.

| Criterion | REST | GraphQL | Source |
|-----------|------|---------|--------|
| Requests and rounds per screen | 5 requests in 2 rounds: the course codes are known only after the first round | 1 request in 1 round | `measure.py`, step 8 |
| Bytes in the responses | 1145: full courses with description, likes and the elective flag, enrollments with names and time | 339: only title, credits and level | `measure.py`, step 8 |
| SQL queries per screen | 5: the student, the enrollments, one per course | 3: the student, the enrollments, all courses in one `IN` | `measure.py`, `X-SQL-Queries` |
| SQL growth with more students | 1 per route regardless of data: the shape of the answer is known, one `JOIN` | 7 → 27 without loaders as students grew from 3 to 20; 3 → 3 with DataLoaders | `try_n_plus_1.py`, experiments 4–5 |
| Error in the query text | 404 for an unknown address, 422 for invalid parameters — the status says what went wrong | 200 with `data: null` and `errors`; the `Did you mean` hint names the right field | experiments 1 and 8 |
| Expected rule error (repeated enrollment) | 409, `application/problem+json`, `type …/already-enrolled` | 200, `userErrors[0].code = ALREADY_ENROLLED` | steps 1 and 4 |
| HTTP cache | each resource has its own `GET` address, so browsers, CDNs and proxies can cache it out of the box | everything goes through `POST /graphql`, so standard HTTP caching does not apply; it needs persisted queries or a client-side cache | lecture section 14 |
| Protection from "expensive" queries | the cost is fixed by each route; a rate limiter counts requests | the client composes the query: 12 likes fit into one `POST`, so depth, alias and argument limits are needed on the server | experiments 6 and 7 |

**Conclusion.** For a screen that combines several related objects, GraphQL clearly wins: "My
courses" took one request instead of five, one network round instead of two, 339 bytes
instead of 1145, and three SQL queries that do not grow with the number of courses. For
public, stable resources — the course list or a single course — I would stay with REST: they
map to cacheable `GET` addresses, each route has a fixed cost, and errors are visible in the
status code without parsing the body. GraphQL's flexibility has a price: N+1 appears as soon as
a resolver touches a relation (27 queries without loaders), and the server has to defend
itself against queries it never anticipated.

### Lab 8 experiment log

| # | Experiment | What I saw | Cause | How I fixed it |
|---|------------|------------|-------|----------------|
| 1 | a typo in a field name, an argument name in `snake_case` | status 200, `data: null`, `errors[0].message`: `Cannot query field 'titel' on type 'Course'. Did you mean 'title', 'level', or 'likes'?`, `locations: line 1, column 30`; for `courses(is_elective: true)` — `Unknown argument 'is_elective' on field 'Query.courses'. Did you mean 'isElective'?`. The same mistake in REST (`/courses/no-such`) gives 404 | the engine validates the query against the schema before running it and reports problems in the body, not in the status; argument names in the schema are camelCase | fixed the field and the argument names; a client has to check `errors`, because 200 guarantees nothing |
| 2 | `\| None` removed from the `course` query, a nonexistent course | the schema became `course(id: ID!): Course!`; the answer was `data: null` and `Cannot return null for non-nullable field Query.course.` with `path: ["course"]`. With two fields `a` (existing) and `b` (missing) the whole `data` was `null`, path `["b"]` — field `a` was lost too | null propagation: a `null` in a field marked `!` rises to the nearest parent that may be `null`, here the whole `data` | put `\| None` back; the same query returned `{"a": {"title": "API Design: REST vs GraphQL"}, "b": null}` |
| 3 | a mutation with the GET method | a query over `GET` returned 200 and the course; the `likeCourse` mutation over `GET` returned **400** with the plain-text body `mutations are not allowed when using GET`; likes stayed at 11 | `GET` must be safe: it can be repeated, prefetched and cached, so a link must not change data | nothing to fix: the refusal is correct; mutations are sent only with `POST` |
| 4 | `more_students.sql`: 3 and 20 students, the SQL counter | `students → enrollments → course`: **7** queries on 3 students, **27** on 20; `enrollments → course, student`: **7**, then **24**. REST `GET /courses` and `GET /enrollments` stay at 1 | lazy loading in resolvers: 1 query for the list + 1 per student for enrollments + 1 per distinct course (1 + 3 + 3 and 1 + 20 + 6); for the second query 1 + 6 courses + 17 students. GraphiQL still answers instantly, so only the counter reveals the growth | DataLoaders (step 6): 3 and 3 on any number of students |
| 5 | a DataLoader batch function that doesn't sort rows by key | the students query failed loudly: `Received wrong number of results in dataloader, expected: 3, received: 6`. The enrollments query returned **no error**, but enrollments 2, 4, 5 and 6 showed someone else's course (2: `Backend Foundations` instead of `AI/LLM Integration`, 4: `AI/LLM Integration` instead of `Backend Foundations`) | the loader hands results out by position; with `ORDER BY id DESC` the three courses came back in a different order than the three keys, the lengths matched, so nothing objected | `git restore graphql_api.py`: the `groups` dictionary matches rows to keys by value. The silent case is the dangerous one — wrong data with no error |
| 6 | six dangerous queries without protection and with it | without: the depth-6 cycle and 12 aliases ran; `limit: -1` and the 20-digit id leaked `(psycopg.errors.InvalidRowCountInLimitClause)` / `(NumericValueOutOfRange)` with SQL text and parameters; `id "abc"` leaked `invalid literal for int()`; `flood_likes.py` made 12 likes (11 → 23) with 24 SQL queries in one `POST`. With: `'Cycle' exceeds maximum operation depth of 5`, `12 aliases found. Allowed: 10`, `limit must be between 1 and 100`, `Invalid ID: 'abc'`, `Unexpected error.`; the flood was rejected with **0** SQL queries | in GraphQL the client composes the query, and by default an unhandled exception goes to `errors` with its whole text — table and column names, SQL, parameter values | `QueryDepthLimiter(5)`, `MaxAliasesLimiter(10)`, `check_limit`, `parse_id`, `MaskErrors` |
| 7 | introspection off, a typo in a field name | `{ __schema { … } }` was rejected: `GraphQL introspection has been disabled, but the requested query contained the field '__schema'`. Ordinary queries and `try_graphql.py` (8 of 8) kept working. A typo `{ cours { title } }` still answered `Did you mean 'course' or 'courses'?` | turning introspection off hides the map of the schema, not the fields: by trying typos the fields can be found one by one | put `GRAPHQL_INTROSPECTION` back to true for GraphiQL; access to data must be limited by permissions, not by hiding the schema |
| 8 | client failures: a typo, no `errors` check, the API stopped | typo: `GraphQLRequestError: Cannot query field 'titel' on type 'Course'. Did you mean …`; without the check: `TypeError: Cannot destructure property 'student' of '(intermediate value)' as it is null.`; API stopped: `TypeError: fetch failed`. The page answered 500 in all three cases | a GraphQL error arrives with status 200, so `res.ok` passes; only the `errors` check names the real cause, otherwise the page crashes on `data: null` and shows the consequence | restored `lib/graphql.ts` and the query with `git restore`; `gql` throws `GraphQLRequestError` whenever `errors` is non-empty |

Answers for experiment 6:

- **What did the client learn without protection?** From `limit: -1` and the 20-digit id — the
  driver name (psycopg), the table and column names of `courses` and `students`, the full SQL
  text and the parameter values. From `id "abc"` — that the id is converted with Python's
  `int()`. From the cycle and the aliases — that the server will execute any depth and any
  number of operations, including 12 writes in one request.
- **Why write `check_limit` and `parse_id` instead of relying on `MaskErrors`?** Because
  `Unexpected error.` hides the cause from everyone, including an honest client who just made a
  mistake. `Invalid ID: 'abc'` tells the client exactly what to fix. Cases we can foresee get a
  clear answer; only the unforeseen ones are masked.
- **What suffers if `max_depth` is lowered to 2?** "My courses" itself: `student → enrollments
  → course` has depth 3, so the main screen of the frontend would be rejected.

### Lab 8 decisions

- **The rules and their errors live in `services.py`; REST and GraphQL translate the code each
  in their own way.** If both layers checked the constraints themselves, the dictionary of
  constraint names and the `try/except` around `commit()` would exist twice and drift apart
  over time. Now there is one source of truth: a repeated enrollment is `ALREADY_ENROLLED`
  everywhere, and the layers only decide how to say it — 409 with Problem Details in REST, an
  entry in `userErrors` in GraphQL. Adding a rule means changing one function.
- **Loaders are created in `Context`, and the batch function matches rows to keys by value.**
  A loader caches results by key; a single one for the whole application would serve one
  user's data to another and would never see changes in the database. `Context` is created
  per request, so the cache lives exactly as long as the request. Matching by value is what
  experiment 5 proved: the database returns rows in any order, and a loader that trusts
  positions silently assigns other people's courses while the lengths still match.
- **The protection is two-layered: `check_limit` and `parse_id` for the expected cases,
  `MaskErrors` for everything else.** Bad arguments we can foresee deserve a precise message
  the client can act on. Everything we did not foresee — a database failure, a bug, a value
  that passes our check but breaks the database, like the 20-digit id — must not leak its
  internals, so it becomes `Unexpected error.` for the client while the full traceback stays
  in the server log for the developer.

## Lab 7: database and migrations

### Migrations

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

### Lab 7 experiment log

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

### Lab 7 decisions

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

### Migration 0002 self-check

| What to check | Result |
|---------------|--------|
| Goal and steps | Yes. One goal — give every course a required difficulty level — in three steps inside one migration: add nullable, backfill, set `NOT NULL`. Nothing unrelated is bundled in. |
| Data | Yes. The six existing rows are filled by an explicit rule (`beginner` for elective courses, `intermediate` otherwise) before the column becomes required; no row is lost or left empty. |
| Renames and drops | No renames and no drops in `upgrade()`. The column is new, so nothing existing is touched. |
| Rollback | Yes, `downgrade()` drops the column, and the `upgrade → downgrade → upgrade` cycle was run against the real database. On production this rollback would destroy any levels chosen by hand — here the values are recomputed by the rule, so it is safe. |
| Verification | Yes. `alembic upgrade 0001:0002 --sql` was read first (`BEGIN`, three statements, the `alembic_version` update, `COMMIT`), then the cycle was run, and `alembic check` reports no differences. |
| History | Yes. `alembic heads` shows a single head `0002`, and the migration is committed together with the model, the schema and the updated `seed.sql`. |
| Application | Yes. `CourseOut` gained `level`, `GET /courses` gained a `level` filter, and `seed.sql` writes the new column. Clients get one extra field in every course response; nothing they already send becomes invalid. |
