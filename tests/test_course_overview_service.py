import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.course import Course
from app.models.course_structure import CourseChapter, SectionRecommendation, StudentSectionProgress
from app.models.evaluation import WeakPointRecord
from app.models.exercise import SectionExerciseSubmission
from app.models.other import StudyRecord
from app.services.course_overview_service import get_course_overview


class CourseOverviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Course.__table__.create(self.engine)
        CourseChapter.__table__.create(self.engine)
        StudentSectionProgress.__table__.create(self.engine)
        SectionRecommendation.__table__.create(self.engine)
        SectionExerciseSubmission.__table__.create(self.engine)
        StudyRecord.__table__.create(self.engine)
        WeakPointRecord.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_overview_returns_current_chapter_section_ids(self):
        db = self.Session()
        db.add(Course(course_id="course_001", name="C 语言"))
        db.add_all(
            [
                CourseChapter(id="ch_1", course_id="course_001", title="第 1 章", level=1, sort_order=1),
                CourseChapter(id="ch_2", course_id="course_001", title="第 2 章", level=1, sort_order=2),
                CourseChapter(id="sec_1_1", course_id="course_001", parent_id="ch_1", title="1.1", level=2, sort_order=1),
                CourseChapter(id="sec_1_2", course_id="course_001", parent_id="ch_1", title="1.2", level=2, sort_order=2),
                CourseChapter(id="sec_2_1", course_id="course_001", parent_id="ch_2", title="2.1", level=2, sort_order=1),
            ]
        )
        db.add(
            StudentSectionProgress(
                student_id="7",
                course_id="course_001",
                section_id="sec_1_1",
                progress=1.0,
                status="completed",
            )
        )
        db.add(
            WeakPointRecord(
                id="wp_001",
                student_id="7",
                course_id="course_001",
                knowledge_point="指针",
                wrong_count=2,
            )
        )
        db.commit()

        data = get_course_overview(db=db, course_id="course_001", student_id="7")

        self.assertEqual(data["continue_learning"]["chapter_id"], "ch_1")
        self.assertEqual(data["continue_learning"]["section_id"], "sec_1_2")
        self.assertEqual(data["continue_learning"]["section_ids"], ["sec_1_1", "sec_1_2"])
        self.assertEqual(data["progress"]["total_chapters"], 2)
        self.assertEqual(data["progress"]["total_progress"], 0.3333)
        self.assertEqual(data["ai_suggestion"]["weak_points"], ["指针"])
        self.assertTrue(data["recommended_resources"])


if __name__ == "__main__":
    unittest.main()
