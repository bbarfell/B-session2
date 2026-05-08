"""Student enrollment dashboard using a thin Streamlit UI layer.

This app uses a service-like EnrollmentManager to keep the UI layer small and
separate from backend persistence. The session starts with a fixed student
session for Maya Patel and routes between a dashboard and a selected class
page using st.session_state.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

DB_PATH = Path(__file__).with_name("enrollment.db")

COURSE_SEEDS = [
    {
        "course_id": "C101",
        "name": "Introduction to Information Systems",
        "instructor": "Dr. R. Singh",
        "enrollment_key": "INFO100",
    },
    {
        "course_id": "C202",
        "name": "Data Analytics Fundamentals",
        "instructor": "Prof. A. Chen",
        "enrollment_key": "DATA202",
    },
    {
        "course_id": "C303",
        "name": "Cloud Computing Basics",
        "instructor": "Ms. J. Wood",
        "enrollment_key": "CLOUD303",
    },
]

STUDENT_SESSION = {
    "user_id": "u100",
    "name": "Maya Patel",
    "email": "maya.patel@example.edu",
    "role": "student",
}


class EnrollmentManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._create_schema()
        self._seed_initial_data()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _create_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS courses (
                    course_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    enrollment_key TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enrollments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    enrolled_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(student_id, course_id)
                )
                """
            )

    def _seed_initial_data(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO students (student_id, name, email, role) VALUES (?, ?, ?, ?)",
                (
                    STUDENT_SESSION["user_id"],
                    STUDENT_SESSION["name"],
                    STUDENT_SESSION["email"],
                    STUDENT_SESSION["role"],
                ),
            )

            course_count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
            if course_count == 0:
                conn.executemany(
                    "INSERT INTO courses (course_id, name, instructor, enrollment_key) VALUES (?, ?, ?, ?)",
                    [
                        (course["course_id"], course["name"], course["instructor"], course["enrollment_key"])
                        for course in COURSE_SEEDS
                    ],
                )

    def get_course(self, course_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT course_id, name, instructor FROM courses WHERE course_id = ?",
                (course_id,),
            ).fetchone()

        if row:
            return {"course_id": row[0], "name": row[1], "instructor": row[2]}
        return None

    def get_course_by_key(self, enrollment_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT course_id, name, instructor FROM courses WHERE enrollment_key = ?",
                (enrollment_key.strip().upper(),),
            ).fetchone()

        if row:
            return {"course_id": row[0], "name": row[1], "instructor": row[2]}
        return None

    def get_student_enrollments(self, student_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.course_id, c.name, c.instructor
                FROM enrollments e
                JOIN courses c ON e.course_id = c.course_id
                WHERE e.student_id = ? AND e.active = 1
                ORDER BY c.course_id
                """,
                (student_id,),
            ).fetchall()

        return [
            {"course_id": row[0], "name": row[1], "instructor": row[2]}
            for row in rows
        ]

    def enroll_student(self, student_id: str, enrollment_key: str) -> dict[str, Any]:
        normalized_key = enrollment_key.strip().upper()
        if not normalized_key:
            return {"success": False, "message": "Enrollment key cannot be blank."}

        course = self.get_course_by_key(normalized_key)
        if not course:
            return {"success": False, "message": "Invalid enrollment key."}

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT active FROM enrollments WHERE student_id = ? AND course_id = ?",
                (student_id, course["course_id"]),
            ).fetchone()

            if existing and existing[0] == 1:
                return {"success": False, "message": "You are already enrolled in this course."}

            if existing:
                conn.execute(
                    "UPDATE enrollments SET active = 1, enrolled_at = ? WHERE student_id = ? AND course_id = ?",
                    (datetime.now().isoformat(), student_id, course["course_id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO enrollments (student_id, course_id, enrolled_at, active) VALUES (?, ?, ?, 1)",
                    (student_id, course["course_id"], datetime.now().isoformat()),
                )

        return {"success": True, "message": f"Successfully enrolled in {course['name']}"}

    def unenroll_student(self, student_id: str, course_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE enrollments SET active = 0 WHERE student_id = ? AND course_id = ? AND active = 1",
                (student_id, course_id),
            )

            if result.rowcount == 0:
                return {"success": False, "message": "Unable to unenroll. Enrollment not found."}

        return {"success": True, "message": "You have been unenrolled from the course."}


def initialize_session_state() -> None:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "dashboard"
    if "role" not in st.session_state:
        st.session_state["role"] = STUDENT_SESSION["role"]
    if "current_student" not in st.session_state:
        st.session_state["current_student"] = STUDENT_SESSION.copy()
    if "selected_course_id" not in st.session_state:
        st.session_state["selected_course_id"] = ""
    if "feedback" not in st.session_state:
        st.session_state["feedback"] = ""
    if "feedback_type" not in st.session_state:
        st.session_state["feedback_type"] = "success"


def set_feedback(message: str, kind: str = "success") -> None:
    st.session_state["feedback"] = message
    st.session_state["feedback_type"] = kind


def show_feedback() -> None:
    if st.session_state.get("feedback"):
        if st.session_state["feedback_type"] == "warning":
            st.warning(st.session_state["feedback"])
        else:
            st.success(st.session_state["feedback"])
        st.session_state["feedback"] = ""
        st.session_state["feedback_type"] = "success"


def go_to_dashboard() -> None:
    st.session_state["current_page"] = "dashboard"
    st.session_state["selected_course_id"] = ""


def go_to_class(course_id: str) -> None:
    st.session_state["current_page"] = "class_detail"
    st.session_state["selected_course_id"] = course_id


def handle_enroll(manager: EnrollmentManager, student_id: str, enroll_key: str) -> None:
    result = manager.enroll_student(student_id, enroll_key)
    if result["success"]:
        set_feedback(result["message"], "success")
    else:
        set_feedback(result["message"], "warning")
    st.rerun()


def handle_unenroll(manager: EnrollmentManager, student_id: str, course_id: str) -> None:
    result = manager.unenroll_student(student_id, course_id)
    if result["success"]:
        set_feedback(result["message"], "success")
    else:
        set_feedback(result["message"], "warning")
    st.rerun()


def render_dashboard(manager: EnrollmentManager) -> None:
    student = st.session_state["current_student"]
    st.title(f"Welcome, {student['name']}!")
    show_feedback()

    with st.expander("Join a New Course"):
        enroll_key = st.text_input("Enrollment key", key="dashboard_enroll_key")
        if st.button("Enroll", key="dashboard_enroll_button"):
            handle_enroll(manager, student["user_id"], enroll_key)

    enrollments = manager.get_student_enrollments(student["user_id"])
    st.markdown("### Your Active Enrollments")

    if not enrollments:
        st.info("You have no active enrollments. Use the enrollment key above to join a new course.")
        return

    for enrollment in enrollments:
        with st.container():
            cols = st.columns([4, 1, 1])
            cols[0].markdown(
                f"**{enrollment['name']}**\n"
                f"Instructor: {enrollment['instructor']}\n"
                f"Course ID: {enrollment['course_id']}"
            )
            if cols[1].button(
                "Go to Class",
                key=f"go_to_{enrollment['course_id']}",
            ):
                go_to_class(enrollment["course_id"])
                st.rerun()

            if cols[2].button(
                "Unenroll",
                key=f"unenroll_{enrollment['course_id']}",
            ):
                handle_unenroll(manager, student["user_id"], enrollment["course_id"])


def render_class_detail(manager: EnrollmentManager) -> None:
    course_id = st.session_state.get("selected_course_id", "")
    course = manager.get_course(course_id)

    if not course:
        st.warning("The selected course could not be found.")
        if st.button("Back to Dashboard"):
            go_to_dashboard()
            st.rerun()
        return

    st.title(course["name"])
    st.write(f"**Instructor:** {course['instructor']}")
    st.write(f"**Course ID:** {course['course_id']}")
    st.write("\n")

    if st.button("Back to Dashboard"):
        go_to_dashboard()
        st.rerun()


def main() -> None:
    initialize_session_state()
    manager = EnrollmentManager(DB_PATH)

    if st.session_state["role"] != "student":
        st.error("Access denied. Student role required.")
        return

    if st.session_state["current_page"] == "dashboard":
        render_dashboard(manager)
    elif st.session_state["current_page"] == "class_detail":
        render_class_detail(manager)
    else:
        go_to_dashboard()
        st.rerun()


if __name__ == "__main__":
    main()