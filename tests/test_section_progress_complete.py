import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.course import Course
from app.models.course_structure import CourseChapter, StudentSectionProgress
from app.services.section_progress_service import complete_section_learning
from app.utils.response import AppException, ErrorCode


class SectionProgressCompleteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Course.__table__.create(self.engine)
        CourseChapter.__table__.create(self.engine)
        StudentSectionProgress.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def _seed_section(self, db):
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

    def test_complete_section_creates_completed_progress(self):
        db = self.Session()
        self._seed_section(db)

        data = complete_section_learning(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
        )

        row = db.query(StudentSectionProgress).first()
        self.assertEqual(data, {"progress": 1.0})
        self.assertEqual(row.student_id, "7")
        self.assertEqual(row.course_id, "course_001")
        self.assertEqual(row.section_id, "sec_001")
        self.assertEqual(row.progress, 1.0)
        self.assertEqual(row.status, "completed")
        self.assertIsNotNone(row.last_study_at)

    def test_complete_section_updates_existing_progress(self):
        db = self.Session()
        self._seed_section(db)
        db.add(
            StudentSectionProgress(
                student_id="7",
                course_id="course_001",
                section_id="sec_001",
                progress=0.4,
                status="learning",
            )
        )
        db.commit()

        complete_section_learning(
            db=db,
            current_user=SimpleNamespace(id=7),
            course_id="course_001",
            section_id="sec_001",
        )

        rows = db.query(StudentSectionProgress).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].progress, 1.0)
        self.assertEqual(rows[0].status, "completed")

    def test_complete_section_requires_existing_section(self):
        db = self.Session()

        with self.assertRaises(AppException) as ctx:
            complete_section_learning(
                db=db,
                current_user=SimpleNamespace(id=7),
                course_id="missing_course",
                section_id="missing_section",
            )

        self.assertEqual(ctx.exception.code, ErrorCode.NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
