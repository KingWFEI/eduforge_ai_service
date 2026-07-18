from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.resource_generation.common.reviewers import reviewer_for
from app.agents.resource_generation.planner.service import ResourcePlanner
from app.agents.resource_generation.router import ResourceGeneratorRouter
from app.agents.resource_generation.state import ResourceGenerationState
from app.core.config import settings
from app.models.course import Course
from app.models.course_structure import CourseChapter, KnowledgeChunk, KnowledgePoint, StudentSectionProgress
from app.models.resource_agent import AgentTask, LearningResource, ResourceGenerationTask
from app.models.student_profile import StudentProfile


logger = logging.getLogger("app.agents.resource_generation.graph")


class ResourceGenerationGraphService:
    def __init__(self, db: Session, router: ResourceGeneratorRouter | None = None):
        self.db = db
        self.router = router or ResourceGeneratorRouter()
        self.planner = ResourcePlanner()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ResourceGenerationState)
        graph.add_node("parse_request", self._parse_request)
        graph.add_node("load_student_profile", self._load_student_profile)
        graph.add_node("load_learning_state", self._load_learning_state)
        graph.add_node("load_course_structure", self._load_course_structure)
        graph.add_node("build_retrieval_plan", self._build_retrieval_plan)
        graph.add_node("retrieve_course_knowledge", self._retrieve_course_knowledge)
        graph.add_node("plan_resource", self._plan_resource)
        graph.add_node("route_resource_generator", self._route_resource_generator)
        graph.add_node("review_resource", self._review_resource)
        graph.add_node("persist_artifacts", self._persist_artifacts)
        graph.add_node("save_resource", self._save_resource)
        graph.add_node("complete_task", self._complete_task)
        graph.add_edge(START, "parse_request")
        graph.add_edge("parse_request", "load_student_profile")
        graph.add_edge("load_student_profile", "load_learning_state")
        graph.add_edge("load_learning_state", "load_course_structure")
        graph.add_edge("load_course_structure", "build_retrieval_plan")
        graph.add_edge("build_retrieval_plan", "retrieve_course_knowledge")
        graph.add_edge("retrieve_course_knowledge", "plan_resource")
        graph.add_edge("plan_resource", "route_resource_generator")
        graph.add_edge("route_resource_generator", "review_resource")
        graph.add_conditional_edges(
            "review_resource",
            lambda state: "retry" if state.get("needs_retry") else "continue",
            {"retry": "route_resource_generator", "continue": "persist_artifacts"},
        )
        graph.add_edge("persist_artifacts", "save_resource")
        graph.add_edge("save_resource", "complete_task")
        graph.add_edge("complete_task", END)
        return graph.compile()

    def run(self, task_id: str) -> dict[str, Any]:
        task = self.db.get(ResourceGenerationTask, task_id)
        if task is None:
            raise RuntimeError("资源生成任务不存在")
        agent_task_id = "agent_" + uuid.uuid4().hex[:20]
        self.db.add(AgentTask(
            id=agent_task_id,
            task_type="resource_generate",
            related_task_id=task.id,
            student_id=task.student_id,
            course_id=task.course_id,
            status="running",
            progress=0,
            input_json={"task_id": task.id},
        ))
        task.started_at = datetime.now(timezone.utc)
        self.db.commit()
        initial: ResourceGenerationState = {"task_id": task.id, "agent_task_id": agent_task_id, "errors": [], "retry_count": task.retry_count or 0}
        try:
            final = self.graph.invoke(initial)
            agent_task = self.db.get(AgentTask, agent_task_id)
            if agent_task:
                agent_task.status = final.get("status", "completed")
                agent_task.progress = final.get("progress", 100)
                agent_task.output_json = {"resource_ids": final.get("resource_ids", [])}
                self.db.commit()
            return {"resource_ids": final.get("resource_ids", []), "agent_task_id": agent_task_id, "status": final.get("status")}
        except Exception as exc:
            self.db.rollback()
            self._cleanup_task_artifacts(task.id)
            task = self.db.get(ResourceGenerationTask, task_id)
            if task:
                task.status = "failed"
                task.error_code = "RESOURCE_GENERATION_FAILED"
                task.error_message = str(exc)
                task.failed_step = task.current_step
                task.retryable = int((task.retry_count or 0) < settings.RESOURCE_GENERATION_MAX_RETRIES)
                task.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            agent_task = self.db.get(AgentTask, agent_task_id)
            if agent_task:
                agent_task.status = "failed"
                agent_task.error_message = str(exc)
                self.db.commit()
            raise

    def _parse_request(self, state: ResourceGenerationState) -> dict:
        task = self.db.get(ResourceGenerationTask, state["task_id"])
        types = list(task.resource_types_json or [])
        if task.resource_type:
            types = [task.resource_type]
        if not types:
            raise ValueError("资源类型为空")
        return self._progress(state, "queued", 2, "解析资源生成请求", {
            "student_id": task.student_id,
            "course_id": task.course_id,
            "chapter_id": task.chapter_id,
            "section_id": task.section_id,
            "knowledge_point_ids": list(task.knowledge_point_ids_json or []),
            "requested_resource_type": types[0],
            "requested_resource_types": types,
            "generation_scope": task.generation_scope or "course",
            "user_request": task.user_request or task.goal or "",
            "goal": task.goal or "",
            "difficulty": task.difficulty or "基础",
        })

    def _load_student_profile(self, state: ResourceGenerationState) -> dict:
        profile = self.db.query(StudentProfile).filter(StudentProfile.student_id == state["student_id"]).first()
        data = self._orm_dict(profile, [
            "major", "grade", "learning_goals_json", "coding_level", "math_level", "course_level",
            "learning_preferences_json", "weaknesses_json", "cognitive_style_json", "summary",
        ])
        return self._progress(state, "loading_profile", 8, "读取学生画像", {"student_profile": data})

    def _load_learning_state(self, state: ResourceGenerationState) -> dict:
        query = self.db.query(StudentSectionProgress).filter(
            StudentSectionProgress.student_id == state["student_id"],
            StudentSectionProgress.course_id == state["course_id"],
        )
        if state.get("section_id"):
            query = query.filter(StudentSectionProgress.section_id == state["section_id"])
        rows = query.all()
        data = [{"section_id": row.section_id, "progress": row.progress, "status": row.status} for row in rows]
        return self._progress(state, "loading_profile", 14, "读取学习进度与薄弱点", {"learning_state": {"sections": data}})

    def _load_course_structure(self, state: ResourceGenerationState) -> dict:
        course = self.db.query(Course).filter(Course.course_id == state["course_id"]).first()
        if course is None:
            raise ValueError("课程不存在")
        chapter_rows = self.db.query(CourseChapter).filter(CourseChapter.course_id == state["course_id"]).order_by(CourseChapter.level, CourseChapter.sort_order).all()
        point_rows = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == state["course_id"]).order_by(KnowledgePoint.sort_order).all()
        points_by_chapter: dict[str, list[dict]] = {}
        for point in point_rows:
            points_by_chapter.setdefault(str(point.chapter_id or ""), []).append(self._orm_dict(point, ["id", "chapter_id", "name", "description", "difficulty", "prerequisites_json", "sort_order"]))
        chapters = [
            {**self._orm_dict(chapter, ["id", "parent_id", "level", "title", "description", "sort_order"]), "knowledge_points": points_by_chapter.get(str(chapter.id), [])}
            for chapter in chapter_rows
        ]
        section = next((item for item in chapters if str(item["id"]) == str(state.get("section_id"))), {})
        chapter_id = state.get("chapter_id") or section.get("parent_id") or (section.get("id") if section.get("level") == 1 else None)
        if not chapter_id and chapters:
            chapter_id = next((item["id"] for item in chapters if item.get("level") == 1), chapters[0]["id"])
        current = next((item for item in chapters if str(item["id"]) == str(chapter_id)), {})
        child_ids = {str(item["id"]) for item in chapters if str(item.get("parent_id") or "") == str(chapter_id)}
        current_points = [point for item in chapters if str(item["id"]) == str(chapter_id) or str(item["id"]) in child_ids for point in item.get("knowledge_points") or []]
        target_ids = set(state.get("knowledge_point_ids") or [])
        targets = [point for point in point_rows if str(point.id) in target_ids]
        if not targets and state.get("section_id"):
            targets = [point for point in point_rows if str(point.chapter_id) == str(state["section_id"])]
        target_dicts = [self._orm_dict(point, ["id", "chapter_id", "name", "description", "difficulty", "prerequisites_json"]) for point in targets]
        patch = {
            "chapter_id": str(chapter_id) if chapter_id else None,
            "course_structure": {"course": {"id": course.course_id, "name": course.name, "description": course.description}, "chapters": chapters},
            "current_chapter_context": current,
            "current_section_context": section,
            "current_chapter_knowledge_points": current_points,
            "target_knowledge_points": target_dicts,
            "cross_chapter_context": [item for item in chapters if str(item["id"]) != str(chapter_id) and str(item.get("parent_id") or "") != str(chapter_id)],
        }
        return self._progress(state, "loading_course", 22, "加载整门课程结构", patch)

    def _build_retrieval_plan(self, state: ResourceGenerationState) -> dict:
        plan = {"current_section_top_k": 8, "current_chapter_top_k": 6, "cross_chapter_top_k": 5, "requires_course_structure": True}
        return self._progress(state, "planning", 30, "构建分层检索计划", {"retrieval_plan": plan})

    def _retrieve_course_knowledge(self, state: ResourceGenerationState) -> dict:
        plan = state["retrieval_plan"]
        current_ids = {str(state.get("chapter_id") or ""), str(state.get("section_id") or "")}
        chunks: list[KnowledgeChunk] = []
        if any(current_ids):
            chunks.extend(self.db.query(KnowledgeChunk).filter(
                KnowledgeChunk.course_id == state["course_id"], KnowledgeChunk.deleted.is_(False), KnowledgeChunk.chapter_id.in_(current_ids)
            ).order_by(KnowledgeChunk.chunk_index).limit(plan["current_section_top_k"] + plan["current_chapter_top_k"]).all())
        existing = {item.id for item in chunks}
        cross = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.course_id == state["course_id"], KnowledgeChunk.deleted.is_(False), ~KnowledgeChunk.id.in_(existing or {""})
        ).order_by(KnowledgeChunk.chunk_index).limit(plan["cross_chapter_top_k"]).all()
        chunks.extend(cross)
        data = [self._orm_dict(item, ["id", "document_id", "chapter_id", "knowledge_point_id", "section", "content", "page_no", "chunk_index"]) for item in chunks]
        for item in data:
            item["chunk_id"] = item.pop("id")
            item["section_id"] = item.get("chapter_id")
        refs = [{key: item.get(key) for key in ("chunk_id", "document_id", "chapter_id", "section_id", "knowledge_point_id")} for item in data]
        return self._progress(state, "retrieving", 42, "分层检索课程知识", {"retrieved_chunks": data, "source_references": refs})

    def _plan_resource(self, state: ResourceGenerationState) -> dict:
        plans: dict[str, dict] = {}
        for resource_type in state["requested_resource_types"]:
            plans[resource_type] = self.planner.plan({**state, "requested_resource_type": resource_type}).model_dump(mode="json")
        return self._progress(state, "planning", 50, "生成结构化资源计划", {"resource_plans": plans, "resource_plan": plans[state["requested_resource_type"]]})

    def _route_resource_generator(self, state: ResourceGenerationState) -> dict:
        types = state["requested_resource_types"]
        if types == ["video"]:
            status, step = "searching_external", "搜索并筛选公开视频"
        elif "ppt" in types:
            status, step = "rendering_html", "生成并检查互动教学课件"
        else:
            status, step = "generating_content", "生成个性化学习资源"
        self._progress(state, status, 65, step)
        resources = [self.router.generate(resource_type, state) for resource_type in types]
        artifacts = {item["resource_id"]: item.get("artifacts") for item in resources if item.get("artifacts")}
        return {"generated_resources": resources, "draft_resource": resources[0] if resources else {}, "generation_artifacts": artifacts, "status": status, "progress": 72, "current_step": step}

    def _review_resource(self, state: ResourceGenerationState) -> dict:
        self._progress(state, "reviewing", 84, "执行分类型质量与安全审核")
        results = []
        failed = []
        for resource in state.get("generated_resources") or []:
            result = reviewer_for(resource["type"]).review(resource, state)
            results.append(result.model_dump())
            if not result.passed:
                failed.append(result)
        retry_count = state.get("retry_count", 0)
        if failed:
            retry_count += 1
            if retry_count > settings.RESOURCE_GENERATION_MAX_RETRIES:
                raise RuntimeError("资源审核超过最大重试次数：" + "；".join(issue for result in failed for issue in result.issues))
            task = self.db.get(ResourceGenerationTask, state["task_id"])
            task.retry_count = retry_count
            self.db.commit()
        return {
            "review_results": results,
            "review_result": results[0] if results else {},
            "final_resources": [] if failed else state.get("generated_resources", []),
            "final_resource": {} if failed or not state.get("generated_resources") else state["generated_resources"][0],
            "needs_retry": bool(failed),
            "retry_count": retry_count,
        }

    def _persist_artifacts(self, state: ResourceGenerationState) -> dict:
        for artifact in (state.get("generation_artifacts") or {}).values():
            for path_value in (artifact or {}).values():
                path = Path(path_value).resolve()
                base = settings.GENERATED_RESOURCE_DIR.resolve()
                if base not in path.parents or not path.is_file():
                    raise RuntimeError("生成产物路径无效或越界")
        return self._progress(state, "checking_html", 90, "确认生成产物与安全边界")

    def _save_resource(self, state: ResourceGenerationState) -> dict:
        self._progress(state, "saving", 95, "保存资源与来源信息")
        resource_ids: list[str] = []
        artifacts: dict[str, Any] = {}
        try:
            for item, review in zip(state.get("final_resources") or [], state.get("review_results") or []):
                if item.get("status") == "no_suitable_result":
                    continue
                content = item.get("content_json") or {}
                resource = LearningResource(
                    id=item["resource_id"], student_id=state["student_id"], course_id=state["course_id"],
                    chapter_id=state.get("chapter_id"), section_id=state.get("section_id"),
                    knowledge_point_id=(state.get("knowledge_point_ids") or [None])[0],
                    title=item.get("title") or "未命名资源", type=item["type"], difficulty=state.get("difficulty"),
                    description=item.get("overview"), reason=state.get("user_request"), content_text=item.get("content_text"),
                    content_json=content, source=item.get("source"), review_status="auto_passed", safety_score=review.get("score"),
                    hallucination_risk="low", generated_by_task_id=state["task_id"], generation_task_id=state["task_id"],
                    generation_scope=state.get("generation_scope"), overview=item.get("overview"), source_type=item.get("source_type"),
                    generation_mode=item.get("generation_mode"), external_provider=item.get("external_provider"),
                    external_id=item.get("external_id"), file_url=item.get("file_url"), preview_url=item.get("preview_url"),
                    source_references_json=item.get("source_references"), review_score=review.get("score"), status="completed",
                )
                self.db.add(resource)
                resource_ids.append(resource.id)
                if item.get("artifacts"):
                    artifacts[resource.id] = item["artifacts"]
            task = self.db.get(ResourceGenerationTask, state["task_id"])
            task.result_resource_ids_json = resource_ids
            task.artifacts_json = artifacts
            self.db.commit()
        except Exception:
            self.db.rollback()
            self._cleanup_task_artifacts(state["task_id"])
            raise
        return {"resource_ids": resource_ids}

    def _complete_task(self, state: ResourceGenerationState) -> dict:
        resources = state.get("final_resources") or []
        no_result = bool(resources) and all(item.get("status") == "no_suitable_result" for item in resources)
        status = "no_suitable_result" if no_result else "completed"
        task = self.db.get(ResourceGenerationTask, state["task_id"])
        task.status = status
        task.progress = 100
        task.current_step = "未找到合适公开视频" if no_result else "资源生成完成"
        task.completed_at = datetime.now(timezone.utc)
        task.error_message = resources[0].get("reason") if no_result else None
        self.db.commit()
        return {"status": status, "progress": 100, "current_step": task.current_step}

    def _progress(self, state: ResourceGenerationState, status: str, progress: int, step: str, patch: dict | None = None) -> dict:
        task = self.db.get(ResourceGenerationTask, state["task_id"])
        task.status, task.progress, task.current_step = status, progress, step
        self.db.commit()
        result = {"status": status, "progress": progress, "current_step": step}
        if patch:
            result.update(patch)
        return result

    @staticmethod
    def _orm_dict(instance, fields: list[str]) -> dict:
        if instance is None:
            return {}
        return {field: getattr(instance, field, None) for field in fields}

    @staticmethod
    def _cleanup_task_artifacts(task_id: str) -> None:
        if not task_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in task_id):
            return
        target = (settings.GENERATED_RESOURCE_DIR / "ppts" / task_id).resolve()
        base = (settings.GENERATED_RESOURCE_DIR / "ppts").resolve()
        if base in target.parents and target.is_dir():
            shutil.rmtree(target)
