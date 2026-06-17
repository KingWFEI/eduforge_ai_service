import json
from typing import Any, Dict

from app.agents.base import BaseAgent


STUDENT_LEARNING_CONTENT_SYSTEM_PROMPT = """
你是 EduForge-AI 的学生学习内容生成智能体。
你必须基于课程结构和给定的 RAG 资料，为学生生成清晰、可学习、可复习的小节内容。
请严格输出 JSON 对象，不要输出 Markdown 代码块，不要输出额外解释。
JSON 格式必须为：
{
  "title": "小节标题",
  "learning_objectives": ["目标1", "目标2"],
  "prerequisites": ["前置知识1", "前置知识2"],
  "concept_explanation": "核心概念讲解",
  "plain_language_explanation": "通俗化解释",
  "key_steps_or_formulas": ["步骤或公式", "步骤或公式"],
  "example": "示例内容",
  "common_mistakes": ["易错点", "易错点"],
  "summary": "本节小结",
  "exercises": [
    {
      "question": "问题",
      "answer_hint": "提示"
    }
  ]
}
要求：
1. 面向学生，不要写成教师教案或后台说明。
2. 优先依据 RAG 资料，不要编造资料中没有的专业细节。
3. 如果 RAG 资料不足，可以基于章节标题、知识点和结构生成基础版内容，并在表述中保持谨慎。
4. 内容要适合移动端阅读，分点清楚，避免长篇堆砌。
"""


class StudentLearningContentAgent(BaseAgent):
    """Generate student-facing learning content for one course section."""

    name = "Student Learning Content Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_sync(input_data)

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.build_prompt(input_data)
        try:
            content_json = self.llm_service.generate_json_sync(
                system_prompt=STUDENT_LEARNING_CONTENT_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=3500,
                temperature=0.2,
            )
            return {
                "content_json": content_json,
                "content_markdown": self.to_markdown(content_json),
                "status": "generated",
                "generation_prompt": prompt,
                "generation_model": self.llm_service.model,
            }
        except Exception as json_error:
            raw_text = self.llm_service.generate_text_sync(
                prompt=prompt,
                system_prompt=(
                    "你是 EduForge-AI 的学生学习内容生成智能体。"
                    "请根据课程结构和资料生成面向学生的学习内容，结构清晰、便于阅读。"
                ),
                max_tokens=2500,
                temperature=0.2,
            )
            return {
                "content_json": None,
                "content_markdown": raw_text,
                "status": "generated_with_raw_text",
                "generation_prompt": prompt,
                "generation_model": self.llm_service.model,
                "json_error": str(json_error),
            }

    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        rag_chunks = input_data.get("rag_chunks") or []
        if rag_chunks:
            rag_context = "\n\n".join(
                f"[chunk_id={item.get('chunk_id')}]\n{item.get('content', '')}"
                for item in rag_chunks
            )
        else:
            rag_context = "当前知识库资料不足，请基于课程结构生成基础版学习内容，并避免扩展未经证实的细节。"

        return (
            "请为下面的小节生成面向学生的学习内容。\n\n"
            f"课程信息：{json.dumps(input_data.get('course') or {}, ensure_ascii=False)}\n"
            f"所属章节：{json.dumps(input_data.get('chapter') or {}, ensure_ascii=False)}\n"
            f"当前小节：{json.dumps(input_data.get('section') or {}, ensure_ascii=False)}\n"
            f"知识点：{json.dumps(input_data.get('knowledge_points') or [], ensure_ascii=False)}\n"
            f"课程结构摘要：{json.dumps(input_data.get('course_structure') or {}, ensure_ascii=False)}\n\n"
            "RAG 资料片段：\n"
            f"{rag_context}\n\n"
            "请严格输出指定 JSON 格式。"
        )

    @staticmethod
    def to_markdown(content_json: Dict[str, Any]) -> str:
        exercises = content_json.get("exercises") or []
        lines = [
            f"# {content_json.get('title') or '学习内容'}",
            "",
            "## 学习目标",
            *[f"- {item}" for item in content_json.get("learning_objectives") or []],
            "",
            "## 前置知识",
            *[f"- {item}" for item in content_json.get("prerequisites") or []],
            "",
            "## 核心概念讲解",
            str(content_json.get("concept_explanation") or ""),
            "",
            "## 通俗化解释",
            str(content_json.get("plain_language_explanation") or ""),
            "",
            "## 关键步骤或公式",
            *[f"- {item}" for item in content_json.get("key_steps_or_formulas") or []],
            "",
            "## 示例",
            str(content_json.get("example") or ""),
            "",
            "## 易错点",
            *[f"- {item}" for item in content_json.get("common_mistakes") or []],
            "",
            "## 小结",
            str(content_json.get("summary") or ""),
            "",
            "## 课后思考",
        ]
        for index, exercise in enumerate(exercises, start=1):
            if isinstance(exercise, dict):
                lines.append(f"{index}. {exercise.get('question') or ''}")
                if exercise.get("answer_hint"):
                    lines.append(f"   提示：{exercise['answer_hint']}")
            else:
                lines.append(f"{index}. {exercise}")
        return "\n".join(lines).strip()
