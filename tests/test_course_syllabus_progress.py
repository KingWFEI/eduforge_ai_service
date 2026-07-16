import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.course import Course
from app.models.course_structure import CourseChapter, CourseDocument, KnowledgePoint, StudentSectionProgress
from app.models.exercise import ExerciseSet
from app.models.resource_agent import LearningResource
from app.services.course_syllabus_service import get_course_syllabus


class CourseSyllabusProgressTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Course.__table__.create(self.engine)
        CourseChapter.__table__.create(self.engine)
        CourseDocument.__table__.create(self.engine)
        KnowledgePoint.__table__.create(self.engine)
        StudentSectionProgress.__table__.create(self.engine)
        LearningResource.__table__.create(self.engine)
        ExerciseSet.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_current_section_follows_chapter_then_section_order(self):
        db = self.Session()
        db.add(Course(course_id="course_001", name="C 语言"))
        rows = [
            CourseChapter(id="ch_1", course_id="course_001", title="第 1 章", level=1, sort_order=1),
            CourseChapter(id="ch_2", course_id="course_001", title="第 2 章", level=1, sort_order=2),
            CourseChapter(id="sec_1_1", course_id="course_001", parent_id="ch_1", title="1.1", level=2, sort_order=1),
            CourseChapter(id="sec_1_2", course_id="course_001", parent_id="ch_1", title="1.2", level=2, sort_order=2),
            CourseChapter(id="sec_2_1", course_id="course_001", parent_id="ch_2", title="2.1", level=2, sort_order=1),
            CourseChapter(id="sec_2_2", course_id="course_001", parent_id="ch_2", title="2.2", level=2, sort_order=2),
        ]
        db.add_all(rows)
        db.add(
            StudentSectionProgress(
                student_id="7",
                course_id="course_001",
                section_id="sec_1_1",
                progress=1.0,
                status="completed",
            )
        )
        db.commit()

        data = get_course_syllabus(db=db, course_id="course_001", student_id="7")

        self.assertEqual(data["current_chapter_id"], "ch_1")
        self.assertEqual(data["current_section_id"], "sec_1_2")

    def test_current_section_moves_to_next_chapter_after_chapter_completed(self):
        db = self.Session()
        db.add(Course(course_id="course_001", name="C 语言"))
        rows = [
            CourseChapter(id="ch_1", course_id="course_001", title="第 1 章", level=1, sort_order=1),
            CourseChapter(id="ch_2", course_id="course_001", title="第 2 章", level=1, sort_order=2),
            CourseChapter(id="sec_1_1", course_id="course_001", parent_id="ch_1", title="1.1", level=2, sort_order=1),
            CourseChapter(id="sec_1_2", course_id="course_001", parent_id="ch_1", title="1.2", level=2, sort_order=2),
            CourseChapter(id="sec_2_1", course_id="course_001", parent_id="ch_2", title="2.1", level=2, sort_order=1),
        ]
        db.add_all(rows)
        db.add_all(
            [
                StudentSectionProgress(
                    student_id="7",
                    course_id="course_001",
                    section_id="sec_1_1",
                    progress=1.0,
                    status="completed",
                ),
                StudentSectionProgress(
                    student_id="7",
                    course_id="course_001",
                    section_id="sec_1_2",
                    progress=1.0,
                    status="completed",
                ),
            ]
        )
        db.commit()

        data = get_course_syllabus(db=db, course_id="course_001", student_id="7")

        self.assertEqual(data["current_chapter_id"], "ch_2")
        self.assertEqual(data["current_section_id"], "sec_2_1")


if __name__ == "__main__":
    unittest.main()
