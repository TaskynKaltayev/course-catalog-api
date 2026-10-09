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
