import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.code_agent import CodeAgent
from app.agents.doc_agent import DocAgent
from app.agents.exercise_agent import ExerciseAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.mindmap_agent import MindMapAgent
from app.agents.profile_agent import ProfileAgent
from app.agents.resource_designer_agent import ResourceDesignerAgent
from app.agents.safety_agent import SafetyAgent
from app.agents.video_agent import VideoAgent
from app.db.session import SessionLocal
from app.models.course_structure import KnowledgePoint
from app.models.resource_agent import (
    AgentTask,
    AgentTaskStep,
    LearningResource,
    ResourceGenerationTask,
)
from app.services.llm_service import DeepSeekService


logger = logging.getLogger("app.services.resource_generation_graph")


class ResourceGraphState(TypedDict, total=False):
    db: Session

    resource_task_id: str
    agent_task_id: str
    student_id: str
    course_id: str
    knowledge_point: str
    knowledge_point_id: Optional[str]
    goal: str
    resource_types: List[str]
    difficulty: str
    use_profile: bool

    profile: Dict[str, Any]
    knowledge_chunks: List[Dict[str, Any]]
    resource_plan: List[Dict[str, Any]]
    generated_resources: List[Dict[str, Any]]
    reviewed_resources: List[Dict[str, Any]]
    resource_ids: List[str]


class ResourceGenerationGraphService:
    """
    阶段 4：基于 LangGraph 的多智能体资源生成服务。

    这里采用“固定工作流 + 多智能体节点”的控制方式：
    Profile → Knowledge → Designer → Doc → MindMap → Exercise → Code → Video → Safety → Save
    每个节点都会写入 agent_task_steps，便于前端展示生成进度。
    """

    def __init__(self, db: Session):
        self.db = db
        self.llm_service = DeepSeekService()

        self.profile_agent = ProfileAgent(self.llm_service)
        self.knowledge_agent = KnowledgeAgent(self.llm_service)
        self.designer_agent = ResourceDesignerAgent(self.llm_service)
        self.doc_agent = DocAgent(self.llm_service)
        self.mindmap_agent = MindMapAgent(self.llm_service)
        self.exercise_agent = ExerciseAgent(self.llm_service)
        self.code_agent = CodeAgent(self.llm_service)
        self.video_agent = VideoAgent(self.llm_service)
        self.safety_agent = SafetyAgent(self.llm_service)

        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ResourceGraphState)

        graph.add_node("load_profile", self._node_load_profile)
        graph.add_node("retrieve_knowledge", self._node_retrieve_knowledge)
        graph.add_node("design_resources", self._node_design_resources)
        graph.add_node("generate_document", self._node_generate_document)
        graph.add_node("generate_mind_map", self._node_generate_mind_map)
        graph.add_node("generate_exercise", self._node_generate_exercise)
        graph.add_node("generate_code_case", self._node_generate_code_case)
        graph.add_node("generate_video_script", self._node_generate_video_script)
        graph.add_node("safety_review", self._node_safety_review)
        graph.add_node("save_resources", self._node_save_resources)

        graph.add_edge(START, "load_profile")
        graph.add_edge("load_profile", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "design_resources")
        graph.add_edge("design_resources", "generate_document")
        graph.add_edge("generate_document", "generate_mind_map")
        graph.add_edge("generate_mind_map", "generate_exercise")
        graph.add_edge("generate_exercise", "generate_code_case")
        graph.add_edge("generate_code_case", "generate_video_script")
        graph.add_edge("generate_video_script", "safety_review")
        graph.add_edge("safety_review", "save_resources")
        graph.add_edge("save_resources", END)

        return graph.compile()

    def run(self, resource_task_id: str) -> Dict[str, Any]:
        resource_task = (
            self.db.query(ResourceGenerationTask)
            .filter(ResourceGenerationTask.id == resource_task_id)
            .first()
        )
        if not resource_task:
            raise RuntimeError("资源生成任务不存在")

        agent_task_id = "agent_" + uuid.uuid4().hex[:12]
        agent_task = AgentTask(
            id=agent_task_id,
            task_type="resource_generate",
            related_task_id=resource_task_id,
            student_id=resource_task.student_id,
            course_id=resource_task.course_id,
            status="running",
            progress=1,
            input_json={
                "resource_task_id": resource_task_id,
                "student_id": resource_task.student_id,
                "course_id": resource_task.course_id,
                "knowledge_point": resource_task.knowledge_point,
                "goal": resource_task.goal,
                "resource_types": resource_task.resource_types_json,
                "difficulty": resource_task.difficulty,
            },
        )
        self.db.add(agent_task)
        self.db.commit()

        try:
            self._update_resource_task(resource_task_id, "running", 1, "多智能体任务开始")

            state: ResourceGraphState = {
                "db": self.db,
                "resource_task_id": resource_task_id,
                "agent_task_id": agent_task_id,
                "student_id": resource_task.student_id,
                "course_id": resource_task.course_id,
                "knowledge_point": resource_task.knowledge_point or "",
                "knowledge_point_id": None,
                "goal": resource_task.goal or "",
                "resource_types": resource_task.resource_types_json or [],
                "difficulty": resource_task.difficulty or "基础",
                "use_profile": True,
                "profile": {},
                "knowledge_chunks": [],
                "resource_plan": [],
                "generated_resources": [],
                "reviewed_resources": [],
                "resource_ids": [],
            }

            final_state = self.graph.invoke(state)

            output = {
                "resource_ids": final_state.get("resource_ids", []),
                "agent_task_id": agent_task_id,
            }

            self._update_resource_task(
                resource_task_id,
                "completed",
                100,
                "生成完成",
                result_resource_ids_json=final_state.get("resource_ids", []),
            )
            self._update_agent_task(agent_task_id, "completed", 100, output_json=output)

            return output

        except Exception as exc:
            self.db.rollback()
            error_message = str(exc)
            self._update_resource_task(
                resource_task_id,
                "failed",
                100,
                "生成失败",
                error_message=error_message,
            )
            self._update_agent_task(
                agent_task_id,
                "failed",
                100,
                error_message=error_message,
            )
            raise

    def _node_load_profile(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.profile_agent, 1, "读取学习画像", 10)

    def _node_retrieve_knowledge(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.knowledge_agent, 2, "检索课程知识库", 25)

    def _node_design_resources(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.designer_agent, 3, "设计资源生成方案", 35)

    def _node_generate_document(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.doc_agent, 4, "生成讲解文档", 50)

    def _node_generate_mind_map(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.mindmap_agent, 5, "生成思维导图", 60)

    def _node_generate_exercise(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.exercise_agent, 6, "生成练习题", 70)

    def _node_generate_code_case(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.code_agent, 7, "生成代码案例", 80)

    def _node_generate_video_script(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.video_agent, 8, "生成视频脚本", 88)

    def _node_safety_review(self, state: ResourceGraphState) -> Dict[str, Any]:
        return self._run_agent_step(state, self.safety_agent, 9, "安全审核与幻觉风险检查", 94)

    def _node_save_resources(self, state: ResourceGraphState) -> Dict[str, Any]:
        self._update_resource_task(
            state["resource_task_id"],
            "running",
            97,
            "保存生成资源",
        )

        resources = state.get("reviewed_resources") or state.get("generated_resources", [])
        resource_ids = []

        knowledge_point_id = state.get("knowledge_point_id")
        if not knowledge_point_id:
            knowledge_point_id = self._find_knowledge_point_id(
                course_id=state["course_id"],
                knowledge_point=state.get("knowledge_point") or "",
            )

        for item in resources:
            resource_id = "res_" + uuid.uuid4().hex[:12]
            resource = LearningResource(
                id=resource_id,
                student_id=state["student_id"],
                course_id=state["course_id"],
                knowledge_point_id=knowledge_point_id,
                title=item.get("title") or "未命名资源",
                type=item.get("type") or "document",
                difficulty=item.get("difficulty") or state.get("difficulty") or "基础",
                description=item.get("description"),
                reason=item.get("reason"),
                content_text=item.get("content_text"),
                content_json=item.get("content_json"),
                source=item.get("source"),
                review_status=item.get("review_status", "auto_passed"),
                safety_score=item.get("safety_score", 0.95),
                hallucination_risk=item.get("hallucination_risk", "low"),
                generated_by_task_id=state["resource_task_id"],
            )
            self.db.add(resource)
            resource_ids.append(resource_id)

        self.db.commit()

        return {
            "resource_ids": resource_ids,
            "summary": f"已保存 {len(resource_ids)} 份学习资源"
        }

    def _run_agent_step(
        self,
        state: ResourceGraphState,
        agent,
        step_order: int,
        step_name: str,
        progress: int,
    ) -> Dict[str, Any]:
        self._update_resource_task(
            state["resource_task_id"],
            "running",
            progress,
            step_name,
        )
        self._update_agent_task(
            state["agent_task_id"],
            "running",
            progress,
        )

        step_id = "step_" + uuid.uuid4().hex[:12]
        start_time = time.time()

        step = AgentTaskStep(
            id=step_id,
            task_id=state["agent_task_id"],
            agent_name=agent.name,
            step_order=step_order,
            status="running",
            input_summary=step_name,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(step)
        self.db.commit()

        try:
            result = asyncio.run(agent.run(dict(state)))

            step.status = "completed"
            step.output_summary = result.get("summary", "执行完成")
            step.duration_ms = int((time.time() - start_time) * 1000)
            step.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            return result

        except Exception as exc:
            step.status = "failed"
            step.error_message = str(exc)
            step.output_summary = str(exc)
            step.duration_ms = int((time.time() - start_time) * 1000)
            step.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            raise

    def _find_knowledge_point_id(self, course_id: str, knowledge_point: str) -> Optional[str]:
        if not knowledge_point:
            return None

        kp = (
            self.db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.name == knowledge_point,
            )
            .first()
        )
        return kp.id if kp else None

    def _update_resource_task(
        self,
        task_id: str,
        status: str,
        progress: int,
        current_step: str,
        result_resource_ids_json: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        task = (
            self.db.query(ResourceGenerationTask)
            .filter(ResourceGenerationTask.id == task_id)
            .first()
        )
        if not task:
            return

        task.status = status
        task.progress = progress
        task.current_step = current_step

        if result_resource_ids_json is not None:
            task.result_resource_ids_json = result_resource_ids_json

        if error_message is not None:
            task.error_message = error_message

        self.db.commit()

    def _update_agent_task(
        self,
        task_id: str,
        status: str,
        progress: int,
        output_json: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        task = (
            self.db.query(AgentTask)
            .filter(AgentTask.id == task_id)
            .first()
        )
        if not task:
            return

        task.status = status
        task.progress = progress

        if output_json is not None:
            task.output_json = output_json

        if error_message is not None:
            task.error_message = error_message

        self.db.commit()


def run_resource_generation_graph(resource_task_id: str) -> None:
    """
    BackgroundTasks 调用入口。

    注意：
    后台任务必须重新创建 db session，不能复用接口请求里的 db。
    """
    db = SessionLocal()
    try:
        service = ResourceGenerationGraphService(db)
        service.run(resource_task_id)
    except Exception:
        logger.exception("resource generation background task failed | task_id=%s", resource_task_id)
    finally:
        db.close()
