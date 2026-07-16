import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.course import Course
from app.models.course_structure import CourseChapter
from app.models.exercise import SectionExerciseAnswer, SectionExerciseSubmission
from app.schemas.exercise import SectionExerciseSubmitRequest
from app.services.section_exercise_service import get_latest_section_exercise, submit_section_exercise
from app.utils.response import AppException, ErrorCode


class SectionExerciseSubmitTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Course.__table__.create(self.engine)
        CourseChapter.__table__.create(self.engine)
        SectionExerciseSubmission.__table__.create(self.engine)
        SectionExerciseAnswer.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_submit_section_exercise_persists_summary_and_answers(self):
        db = self.Session()
        db.add(Course(course_id="course_001", name="C 语言"))
        db.add(
            CourseChapter(
                id="sec_001",
                course_id="course_001",
                title="1.1 入门",
                level=2,
            )
        )
        db.commit()

        payload = SectionExerciseSubmitRequest(
            answers=[
                {"exercise_id": "ex_001", "type": "choice", "user_answer": "A", "is_correct": True},
                {"exercise_id": "ex_002", "type": "fill_blank", "user_answer": ["main"], "is_correct": False},
            ]
        )
        data = submit_section_exercise(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
            payload=payload,
        )

        self.assertEqual(data["total"], 2)
        self.assertEqual(data["correct"], 1)
        self.assertEqual(data["incorrect"], 1)
        self.assertEqual(data["score"], 50)
        self.assertTrue(data["submit_id"].startswith("sub_"))
        self.assertEqual(db.query(SectionExerciseSubmission).count(), 1)
        self.assertEqual(db.query(SectionExerciseAnswer).count(), 2)

    def test_submit_section_exercise_requires_existing_section(self):
        db = self.Session()
        payload = SectionExerciseSubmitRequest(
            answers=[
                {"exercise_id": "ex_001", "type": "choice", "user_answer": "A", "is_correct": True},
            ]
        )

        with self.assertRaises(AppException) as ctx:
            submit_section_exercise(
                db=db,
                current_user=SimpleNamespace(id=7),
                course_id="missing_course",
                section_id="missing_section",
                payload=payload,
            )

        self.assertEqual(ctx.exception.code, ErrorCode.NOT_FOUND)

    def test_get_latest_section_exercise_returns_none_without_submission(self):
        db = self.Session()
        db.add(Course(course_id="course_001", name="C 语言"))
        db.add(
            CourseChapter(
                id="sec_001",
                course_id="course_001",
                title="1.1 入门",
                level=2,
            )
        )
        db.commit()

        data = get_latest_section_exercise(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
        )

        self.assertIsNone(data)

    def test_get_latest_section_exercise_returns_latest_submission_with_answers(self):
        db = self.Session()
        db.add(Course(course_id="course_001", name="C 语言"))
        db.add(
            CourseChapter(
                id="sec_001",
                course_id="course_001",
                title="1.1 入门",
                level=2,
            )
        )
        db.commit()
        first_payload = SectionExerciseSubmitRequest(
            answers=[
                {"exercise_id": "ex_001", "type": "choice", "user_answer": "A", "is_correct": False},
            ]
        )
        latest_payload = SectionExerciseSubmitRequest(
            answers=[
                {"exercise_id": "ex_002", "type": "choice", "user_answer": "B", "is_correct": True},
                {"exercise_id": "ex_003", "type": "true_false", "user_answer": False, "is_correct": True},
            ]
        )

        submit_section_exercise(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
            payload=first_payload,
        )
        latest = submit_section_exercise(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
            payload=latest_payload,
        )
        data = get_latest_section_exercise(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
        )

        self.assertEqual(data["submit_id"], latest["submit_id"])
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["correct"], 2)
        self.assertEqual(data["incorrect"], 0)
        self.assertEqual(data["score"], 100)
        self.assertEqual([item["exercise_id"] for item in data["answers"]], ["ex_002", "ex_003"])
        self.assertIsNotNone(data["submitted_at"])


if __name__ == "__main__":
    unittest.main()
