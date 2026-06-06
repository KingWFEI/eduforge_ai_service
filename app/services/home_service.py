import uuid
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.learning_profile import (
    StudentDomainCompetency,
    StudentLearningContext,
    StudentLearningProfile,
)

# 注意：
# 如果你的课程模型文件不是 app.models.course，
# 后面报错时，把这里改成你真实的课程模型导入路径。
from app.models.course import Course


class HomeService:
    """
    阶段 3：首页课程服务。

    主要负责：
    1. 获取当前学生已选择课程列表。
    2. 添加课程到首页。
    3. 从首页移除课程。

    当前版本基于三层画像模型：
    - student_learning_profiles：综合学习画像
    - student_learning_contexts：学生课程学习上下文
    - student_domain_competencies：课程/领域能力画像
    """

    def __init__(self, db: Session):
        self.db = db

    def get_home_courses(self, student_id: str) -> Dict[str, Any]:
        """
        获取学生首页课程列表。

        数据来源：
        - student_learning_contexts：学生已选择课程
        - student_domain_competencies：课程薄弱点、掌握情况
        - student_learning_profiles：综合学习偏好、可用时间
        """

        contexts = (
            self.db.query(StudentLearningContext)
            .filter(
                StudentLearningContext.student_id == student_id,
                StudentLearningContext.status == "active",
            )
            .order_by(StudentLearningContext.updated_at.desc())
            .all()
        )

        if not contexts:
            return {
                "selected_courses": [],
                "max_home_display": 3,
            }

        learning_profile = (
            self.db.query(StudentLearningProfile)
            .filter(StudentLearningProfile.student_id == student_id)
            .first()
        )

        selected_courses = []

        for context in contexts:
            competency = self._get_course_competency(
                student_id=student_id,
                course_id=context.course_id,
                course_name=context.course_name,
            )

            course = self._get_course(context.course_id)

            selected_courses.append(
                {
                    "course_id": self._display_course_id(context.course_id, course),
                    "course_name": self._display_course_name(context, course),
                    "progress": self._estimate_progress(context),
                    "today_suggestion": self._build_today_suggestion(
                        context=context,
                        competency=competency,
                        learning_profile=learning_profile,
                    ),
                    "today_topic": self._build_today_topic(
                        context=context,
                        competency=competency,
                    ),
                    "today_estimated_time": self._build_today_estimated_time(
                        context=context,
                        learning_profile=learning_profile,
                    ),
                    "study_hours": self._estimate_study_hours(context),
                    "average_accuracy": self._estimate_average_accuracy(competency),
                    "cover_color": self._get_course_cover_color(course),
                    "last_study_at": context.updated_at or context.started_at,
                }
            )

        return {
            "selected_courses": selected_courses,
            "max_home_display": 3,
        }

    def add_home_course(
        self,
        student_id: str,
        course_id: Union[int, str],
    ) -> Dict[str, Any]:
        """
        添加课程到学生首页。

        逻辑：
        1. 查课程是否存在。
        2. 查 student_learning_contexts 是否已有记录。
        3. 如果没有，创建 active 上下文。
        4. 如果之前 removed，就恢复为 active。
        """

        course = self._get_course(course_id)

        if not course:
            raise ValueError("课程不存在")

        course_status = getattr(course, "status", "active")

        if course_status != "active":
            raise ValueError("课程不可添加")

        real_course_id = self._get_course_business_id(course)
        course_name = self._get_course_name(course)

        context = (
            self.db.query(StudentLearningContext)
            .filter(
                StudentLearningContext.student_id == student_id,
                StudentLearningContext.course_id == real_course_id,
            )
            .first()
        )

        if context:
            context.status = "active"
            context.course_name = course_name
        else:
            context = StudentLearningContext(
                id="ctx_" + uuid.uuid4().hex[:12],
                student_id=student_id,
                course_id=real_course_id,
                course_name=course_name,
                learning_goals_json=[],
                time_budget_json=None,
                status="active",
            )
            self.db.add(context)

        self.db.commit()
        self.db.refresh(context)

        return {
            "course_id": self._display_course_id(context.course_id, course),
            "course_name": context.course_name,
            "status": context.status,
        }

    def remove_home_course(
        self,
        student_id: str,
        course_id: Union[int, str],
    ) -> Dict[str, Any]:
        """
        从首页移除课程。

        注意：
        不删除课程本身。
        只把 student_learning_contexts.status 改成 removed。
        """

        real_course_id = self._normalize_course_id(course_id)

        context = (
            self.db.query(StudentLearningContext)
            .filter(
                StudentLearningContext.student_id == student_id,
                StudentLearningContext.course_id == real_course_id,
            )
            .first()
        )

        # 如果用户传的是数字 ID，有可能 context.course_id 存的是课程业务 ID。
        # 所以再尝试通过 Course 查一次真实 course_id。
        if not context:
            course = self._get_course(course_id)

            if course:
                real_course_id = self._get_course_business_id(course)

                context = (
                    self.db.query(StudentLearningContext)
                    .filter(
                        StudentLearningContext.student_id == student_id,
                        StudentLearningContext.course_id == real_course_id,
                    )
                    .first()
                )

        if not context:
            raise ValueError("当前学生未添加该课程")

        context.status = "removed"

        self.db.commit()
        self.db.refresh(context)

        return {
            "course_id": course_id,
            "status": context.status,
        }

    def _get_course_competency(
        self,
        student_id: str,
        course_id: Optional[str],
        course_name: Optional[str],
    ) -> Optional[StudentDomainCompetency]:
        """
        获取某门课程对应的能力画像。

        兼容：
        - domain_type = course
        - domain_id = course_id
        - domain_name = course_name
        """

        query = self.db.query(StudentDomainCompetency).filter(
            StudentDomainCompetency.student_id == student_id
        )

        conditions = []

        if course_id:
            conditions.append(StudentDomainCompetency.domain_id == course_id)

        if course_name:
            conditions.append(StudentDomainCompetency.domain_name == course_name)

        conditions.append(StudentDomainCompetency.domain_type == "course")
        conditions.append(StudentDomainCompetency.domain_type == "课程")

        return (
            query.filter(or_(*conditions))
            .order_by(StudentDomainCompetency.last_updated.desc())
            .first()
        )

    def _get_course(self, course_id: Union[int, str]):
        """
        兼容查询课程。

        你的项目里 course_id 可能是：
        - 数字 id
        - 字符串 course_id，例如 course_ai_basic
        """

        course_id_str = str(course_id)

        # 1. 优先按 Course.course_id 查
        if hasattr(Course, "course_id"):
            course = (
                self.db.query(Course)
                .filter(Course.course_id == course_id_str)
                .first()
            )

            if course:
                return course

        # 2. 如果传的是数字，再按 Course.id 查
        if course_id_str.isdigit() and hasattr(Course, "id"):
            course = (
                self.db.query(Course)
                .filter(Course.id == int(course_id_str))
                .first()
            )

            if course:
                return course

        return None

    def _normalize_course_id(self, course_id: Union[int, str]) -> str:
        return str(course_id)

    def _get_course_business_id(self, course) -> str:
        """
        获取课程业务 ID。

        优先使用 course.course_id。
        如果没有，就使用 id。
        """

        if hasattr(course, "course_id") and getattr(course, "course_id"):
            return str(getattr(course, "course_id"))

        return str(getattr(course, "id"))

    def _get_course_name(self, course) -> str:
        """
        获取课程名称。

        兼容 name / course_name 两种字段。
        """

        if hasattr(course, "name") and getattr(course, "name"):
            return getattr(course, "name")

        if hasattr(course, "course_name") and getattr(course, "course_name"):
            return getattr(course, "course_name")

        return "未命名课程"

    def _display_course_id(self, context_course_id: Optional[str], course):
        """
        首页返回给前端的 course_id。

        如果 Course 有数字 id，优先返回数字 id，贴合新版阶段 3 文档。
        如果没有，就返回字符串 course_id。
        """

        if course and hasattr(course, "id") and getattr(course, "id") is not None:
            return getattr(course, "id")

        return context_course_id

    def _display_course_name(self, context: StudentLearningContext, course) -> str:
        if context.course_name:
            return context.course_name

        if course:
            return self._get_course_name(course)

        return "未命名课程"

    def _estimate_progress(self, context: StudentLearningContext) -> float:
        """
        估算课程进度。

        当前 student_learning_contexts 没有 progress 字段，
        所以先根据 status 做最小可运行估算。

        后面如果你增加学习记录或学习路径表，
        再把这里替换成真实进度计算。
        """

        if context.status == "completed":
            return 1.0

        if context.status == "active":
            return 0.0

        return 0.0

    def _build_today_topic(
        self,
        context: StudentLearningContext,
        competency: Optional[StudentDomainCompetency],
    ) -> Optional[str]:
        """
        生成今日主题。

        优先从课程能力画像的薄弱点中取第一个。
        """

        weaknesses = []

        if competency and competency.weaknesses_json:
            weaknesses = competency.weaknesses_json

        if isinstance(weaknesses, list) and len(weaknesses) > 0:
            return weaknesses[0]

        if context.course_name:
            return context.course_name

        return None

    def _build_today_suggestion(
        self,
        context: StudentLearningContext,
        competency: Optional[StudentDomainCompetency],
        learning_profile: Optional[StudentLearningProfile],
    ) -> str:
        """
        生成今日学习建议。

        优先根据薄弱点生成。
        """

        topic = self._build_today_topic(context, competency)

        if topic:
            preferences = []

            if learning_profile and learning_profile.learning_preferences_json:
                preferences = learning_profile.learning_preferences_json

            if isinstance(preferences, list) and "图解讲解" in preferences:
                return f"先用图解方式复习“{topic}”，再完成基础练习。"

            if isinstance(preferences, list) and "代码案例" in preferences:
                return f"先完成“{topic}”相关代码案例，再做练习巩固。"

            return f"今天建议先学习“{topic}”。"

        return "今天建议先完成当前课程的基础学习任务。"

    def _build_today_estimated_time(
        self,
        context: StudentLearningContext,
        learning_profile: Optional[StudentLearningProfile],
    ) -> Optional[str]:
        """
        生成今日预计学习时间。

        优先使用课程上下文 time_budget_json，
        其次使用综合画像 available_time_json。
        """

        context_time = self._extract_time_budget(context.time_budget_json)

        if context_time:
            return context_time

        if learning_profile:
            profile_time = self._extract_time_budget(
                learning_profile.available_time_json
            )

            if profile_time:
                return profile_time

        return "30 分钟"

    def _extract_time_budget(self, value) -> Optional[str]:
        """
        兼容不同 JSON 格式的时间预算。

        支持：
        "每天 45 分钟"
        {"daily_minutes": 45}
        {"text": "每天 45 分钟"}
        {"label": "45 分钟"}
        """

        if not value:
            return None

        if isinstance(value, str):
            return value.replace("每天", "").strip()

        if isinstance(value, dict):
            if value.get("daily_minutes"):
                return f"{value.get('daily_minutes')} 分钟"

            if value.get("text"):
                return str(value.get("text")).replace("每天", "").strip()

            if value.get("label"):
                return str(value.get("label")).replace("每天", "").strip()

        return None

    def _estimate_study_hours(self, context: StudentLearningContext) -> float:
        """
        当前表里没有 study_hours 字段，先返回 0。
        后续接学习记录表后再真实统计。
        """

        return 0.0

    def _estimate_average_accuracy(
        self,
        competency: Optional[StudentDomainCompetency],
    ) -> float:
        """
        估算当前课程平均正确率。

        当前没有练习提交统计时，
        先根据 competency.confidence 或 competency_level 给一个展示值。
        """

        if not competency:
            return 0.0

        if competency.confidence is not None:
            value = float(competency.confidence)

            if value > 1:
                value = value / 100

            return round(max(0.0, min(value, 1.0)), 2)

        level = competency.competency_level or ""

        if level in ["较好", "熟练", "advanced"]:
            return 0.85

        if level in ["一般", "中等", "normal"]:
            return 0.7

        if level in ["较弱", "入门", "beginner", "weak"]:
            return 0.5

        return 0.0

    def _get_course_cover_color(self, course) -> Optional[str]:
        """
        获取课程卡片颜色。

        如果课程表没有 cover_color 字段，则返回默认颜色。
        """

        if course and hasattr(course, "cover_color"):
            color = getattr(course, "cover_color")

            if color:
                return color

        return "#625BFF"