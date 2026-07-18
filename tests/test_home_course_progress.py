import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.course import Course
from app.models.course_structure import CourseChapter, StudentSectionProgress
from app.models.learning_profile import StudentLearningContext
from app.services.home_service import HomeService


class HomeCourseProgressTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Course.__table__.create(self.engine)
        CourseChapter.__table__.create(self.engine)
        StudentSectionProgress.__table__.create(self.engine)
        StudentLearningContext.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.service = HomeService(self.db)
        self.context = StudentLearningContext(
            id="context-1",
            student_id="7",
            course_id="course-1",
            course_name="测试课程",
            status="active",
        )
        self.db.add_all(
            [
                Course(course_id="course-1", name="测试课程"),
                self.context,
                CourseChapter(
                    id="chapter-1",
                    course_id="course-1",
                    level=1,
                    title="第一章",
                    sort_order=1,
                ),
            ]
        )
        for index in range(1, 4):
            self.db.add(
                CourseChapter(
                    id=f"section-{index}",
                    course_id="course-1",
                    parent_id="chapter-1",
                    level=2,
                    title=f"小节 {index}",
                    sort_order=index,
                )
            )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_completed_context_does_not_override_real_section_progress(self):
        self.context.status = "completed"
        self.db.add(
            StudentSectionProgress(
                student_id="7",
                course_id="course-1",
                section_id="section-1",
                progress=0.5,
                status="learning",
            )
        )
        self.db.commit()
        self.assertEqual(self.service._estimate_progress(self.context), 0.1667)

    def test_context_without_section_progress_returns_zero(self):
        self.assertEqual(self.service._estimate_progress(self.context), 0.0)

    def test_progress_matches_overview_average_across_all_sections(self):
        self.db.add_all(
            [
                StudentSectionProgress(
                    student_id="7",
                    course_id="course-1",
                    section_id="section-1",
                    progress=1.0,
                    status="completed",
                ),
                StudentSectionProgress(
                    student_id="7",
                    course_id="course-1",
                    section_id="section-2",
                    progress=1.2,
                    status="completed",
                ),
                StudentSectionProgress(
                    student_id="7",
                    course_id="course-1",
                    section_id="section-3",
                    progress=0.75,
                    status="learning",
                ),
            ]
        )
        self.db.commit()

        self.assertEqual(self.service._estimate_progress(self.context), 0.9167)

    def test_untracked_sections_are_counted_as_zero(self):
        self.db.add(
            StudentSectionProgress(
                student_id="7",
                course_id="course-1",
                section_id="section-1",
                progress=1.0,
                status="completed",
            )
        )
        self.db.commit()

        self.assertEqual(self.service._estimate_progress(self.context), 0.3333)

    def test_progress_does_not_mix_students_or_courses(self):
        self.db.add(
            StudentSectionProgress(
                student_id="8",
                course_id="course-1",
                section_id="section-1",
                progress=1.0,
                status="completed",
            )
        )
        self.db.commit()

        self.assertEqual(self.service._estimate_progress(self.context), 0.0)


if __name__ == "__main__":
    unittest.main()
