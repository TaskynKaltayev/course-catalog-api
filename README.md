# Course Catalog API

A FastAPI backend that serves the course catalog of the Advanced Web Technologies programme.

Author: **Taskyn Kaltayev**

## How to run

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On macOS and Linux the second command is `source .venv/bin/activate`.

Install the dependencies and start the development server:

```bash
pip install -r requirements.txt
```

```bash
fastapi dev main.py
```

The server runs at <http://127.0.0.1:8000>, the interactive documentation at
<http://127.0.0.1:8000/docs>.

## Routes

| Route | Description |
| --- | --- |
| `GET /` | health check |
| `GET /courses` | course list with filtering, sorting and pagination |
| `GET /courses/{course_id}` | a single course, or a 404 error |
| `GET /docs` | Swagger UI generated from the code |

Query parameters of `GET /courses`:

| Parameter | Values | Default |
| --- | --- | --- |
| `is_elective` | `true` / `false` | not set — all courses |
| `sort` | `popular` (by likes, descending) / `title` (alphabetically) | `popular` |
| `page` | page number | `1` |
| `page_size` | items per page | `20` |

Pagination is supplied by the `pagination` dependency through `Depends`, so the route itself
never computes the offset.

## What was verified

| Request | Result |
| --- | --- |
| `GET /` | `{"message": "Course Catalog API is running"}` |
| `GET /courses` | 6 courses, `ai-integration` first (32 likes), `api-design` last (11) |
| `GET /courses?is_elective=true` | 2 courses: `ai-integration`, `api-design` |
| `GET /courses?is_elective=false` | 4 courses: `modern-frontend`, `web-security`, `backend-fastapi`, `databases-postgresql` |
| `GET /courses?sort=title` | `ai-integration`, `api-design`, `backend-fastapi`, `modern-frontend`, `databases-postgresql`, `web-security` |
| `GET /courses?page=1&page_size=2` | `ai-integration`, `modern-frontend` |
| `GET /courses?page=2&page_size=2` | `web-security`, `backend-fastapi` |
| `GET /courses?page=3&page_size=2` | `databases-postgresql`, `api-design` |
| `GET /courses?page=4&page_size=2` | `[]` |
| `GET /courses/web-security` | 200, one course object |
| `GET /courses/nope` | 404, `{"detail": "Course not found"}` |
| `GET /docs`, `GET /redoc` | both open; `/docs` lists exactly three routes and the `Course` schema |

## Data

There is no database yet. `data.py` holds the same six courses that lived in `lib/courses.ts`
in the Next.js project, described with the Pydantic `Course` model from `models.py`.

## What changed in Lab 5

### Allowed origin

`CORSMiddleware` is attached in `main.py` with an explicit list of origins:

```python
allow_origins=["http://localhost:3000", "http://localhost:3001"]
```

CORS is a browser rule, not a server guard: the API executes a request from any origin, but only a
page served from an allowed origin is permitted by the browser to read the response. The second
address is there because port 3000 is occupied by another application on this machine and the
Next.js dev server falls back to 3001. The value is an origin — scheme, host and port, with no path
and no trailing slash.

| Request | Response |
| --- | --- |
| `curl -i -H "Origin: http://localhost:3001" /` | `access-control-allow-origin: http://localhost:3001`, `vary: Origin` |
| `curl -i -H "Origin: http://evil.example" /` | 200, no `access-control-*` headers |
| `OPTIONS /enrollments` with `Access-Control-Request-Method: POST` | 200, `access-control-allow-methods` includes POST, `access-control-max-age: 600` |

### camelCase in JSON

`models.py` defines `CamelModel` with `alias_generator=to_camel`, `validate_by_name=True` and
`validate_by_alias=True`; every model inherits from it. Python keeps `snake_case`, while JSON uses
`camelCase`, which is what the TypeScript `Course` type on the frontend expects:

```json
{ "id": "ai-integration", "title": "AI/LLM Integration", "credits": 5, "isElective": true, "likes": 32 }
```

`validate_by_name` is what lets `data.py` keep building courses by field name (`is_elective=True`).
Without it Pydantic would accept only aliases, silently drop the argument, and every course would
become non-elective.

Query parameters are not affected by the aliases: they are declared in the function signature, so
the filter is still `?is_elective=true`. A request with `?isElective=true` returns all six courses,
because FastAPI ignores an unknown parameter.

### New routes

| Route | Example |
| --- | --- |
| `POST /courses/{course_id}/like` | 200, the updated course: `{"id": "web-security", ..., "likes": 22}`; an unknown id gives 404 `{"detail": "Course not found"}` |
| `POST /enrollments` | body `{"courseId": "web-security", "studentName": "Aigerim"}` → 201 `{"courseId": "web-security", "studentName": "Aigerim", "id": 1}`; a one-letter name → 422 with `"loc": ["body", "studentName"]` and `"msg": "String should have at least 2 characters"`; an unknown course → 404 |
| `GET /enrollments` | the list of records created so far |

Likes and enrollments are kept in memory, so both reset on every server restart.
