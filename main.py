from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from data import find_course, get_all_courses
from models import Course, Enrollment, EnrollmentIn

app = FastAPI(title="Course Catalog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ENROLLMENTS: list[Enrollment] = []


def pagination(page: int = 1, page_size: int = 20):
    return {"offset": (page - 1) * page_size, "limit": page_size}


@app.get("/")
def read_root():
    return {"message": "Course Catalog API is running"}


@app.get("/courses", response_model=list[Course])
def list_courses(
    is_elective: bool | None = None,
    sort: str = "popular",
    p: dict = Depends(pagination),
):
    courses = get_all_courses()

    if is_elective is not None:
        courses = [course for course in courses if course.is_elective == is_elective]

    if sort == "title":
        courses = sorted(courses, key=lambda course: course.title)
    else:
        courses = sorted(courses, key=lambda course: course.likes, reverse=True)

    offset = p["offset"]

    return courses[offset : offset + p["limit"]]


@app.get("/courses/{course_id}", response_model=Course)
def get_course(course_id: str):
    course = find_course(course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return course


@app.post("/courses/{course_id}/like", response_model=Course)
def like_course(course_id: str):
    course = find_course(course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    course.likes += 1

    return course


@app.post("/enrollments", response_model=Enrollment, status_code=201)
def create_enrollment(data: EnrollmentIn):
    if find_course(data.course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = Enrollment(
        id=len(ENROLLMENTS) + 1,
        course_id=data.course_id,
        student_name=data.student_name,
    )
    ENROLLMENTS.append(enrollment)

    return enrollment


@app.get("/enrollments", response_model=list[Enrollment])
def list_enrollments():
    return ENROLLMENTS
