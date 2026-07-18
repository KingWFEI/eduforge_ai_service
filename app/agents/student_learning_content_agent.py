import json
from typing import Any, Dict

from app.agents.base import BaseAgent


from app.constants.resource_generation import DEFAULT_SECTION_RESOURCE_SHELL_TYPES


SECTION_RESOURCE_TYPES = tuple(item.value for item in DEFAULT_SECTION_RESOURCE_SHELL_TYPES)
EXERCISE_TYPES = ("choice", "multi_choice", "fill_blank", "true_false")
DIFFICULTIES = {"基础": "easy", "中等": "medium", "提高": "hard", "easy": "easy", "medium": "medium", "hard": "hard"}


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
      "id": "ex_001",
      "type": "choice",
      "question": "题目文本",
      "options": [{"key": "A", "text": "选项文本"}],
      "correct_answer": "A",
      "explanation": "答案解析",
      "difficulty": "easy"
    }
  ],
  "practice_prompts": []
}
要求：
1. 面向学生，不要写成教师教案或后台说明。
2. 优先依据 RAG 资料，不要编造资料中没有的专业细节。
3. 如果 RAG 资料不足，可以基于章节标题、知识点和结构生成基础版内容，并在表述中保持谨慎。
4. 内容要适合移动端阅读，分点清楚，避免长篇堆砌。
5. exercises 是随堂练习题，必须和本小节学习内容一并生成，数量 3 到 5 道。
6. exercises 只允许四种题型：choice、multi_choice、fill_blank、true_false。
7. choice / multi_choice 必须有 options，选项字段为 key 和 text；choice 的 correct_answer 是字符串，multi_choice 的 correct_answer 是字符串数组。
8. fill_blank 的 question 必须用 ___ 标记空位，blanks 数量必须和 ___ 数量一致。
9. true_false 的 correct_answer 必须是布尔值。
10. difficulty 只能是 easy、medium、hard。
11. practice_prompts 保留为空数组，正式练习题只放在 exercises。
12. 不要输出 resources、supplement_suggestion 或任何资源推荐字段；资源推荐由独立接口生成。
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
                max_tokens=5000,
                temperature=0.2,
            )
            section_id = str((input_data.get("section") or {}).get("section_id") or "")
            content_json = self.normalize_content_json(content_json, section_id=section_id)
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
        content_json = StudentLearningContentAgent.normalize_content_json(content_json)
        practice_prompts = content_json.get("practice_prompts") or []
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
        for index, prompt in enumerate(practice_prompts, start=1):
            if isinstance(prompt, dict):
                lines.append(f"{index}. {prompt.get('question') or ''}")
                if prompt.get("answer_hint"):
                    lines.append(f"   提示：{prompt['answer_hint']}")
            else:
                lines.append(f"{index}. {prompt}")
        if exercises:
            lines.extend(["", "## 随堂练习"])
            for index, exercise in enumerate(exercises, start=1):
                lines.append(f"{index}. {exercise.get('question') or ''}")
                for option in exercise.get("options") or []:
                    lines.append(f"   - {option.get('key')}. {option.get('text')}")
        return "\n".join(lines).strip()

    @staticmethod
    def normalize_content_json(content_json: Dict[str, Any], section_id: str | None = None) -> Dict[str, Any]:
        if not isinstance(content_json, dict):
            return {}
        normalized = dict(content_json)
        normalized["exercises"] = StudentLearningContentAgent.normalize_exercises(
            normalized.get("exercises") or [],
            section_id=section_id,
            default_difficulty=normalized.get("difficulty") or "easy",
        )
        raw_practice_prompts = normalized.get("practice_prompts")
        if raw_practice_prompts is None:
            raw_practice_prompts = []
        normalized["practice_prompts"] = StudentLearningContentAgent.normalize_practice_prompts(
            raw_practice_prompts or []
        )
        normalized.pop("resources", None)
        normalized.pop("supplement_suggestion", None)
        return normalized

    @staticmethod
    def normalize_resource_shells(
        resources: Any,
        section_id: str | None = None,
        title: str = "本节内容",
    ) -> list[dict[str, str]]:
        existing = {}
        if isinstance(resources, list):
            existing = {
                str(item.get("type")): item
                for item in resources
                if isinstance(item, dict) and item.get("type") in SECTION_RESOURCE_TYPES
            }

        shells = []
        for resource_type in SECTION_RESOURCE_TYPES:
            item = existing.get(resource_type) or {}
            shells.append(
                {
                    "id": StudentLearningContentAgent.build_resource_shell_id(section_id, resource_type),
                    "title": str(item.get("title") or StudentLearningContentAgent.default_resource_title(title, resource_type)),
                    "subtitle": str(item.get("subtitle") or StudentLearningContentAgent.default_resource_subtitle(resource_type)),
                    "type": resource_type,
                }
            )
        return shells

    @staticmethod
    def build_resource_shell_id(section_id: str | None, resource_type: str) -> str:
        stable_section = str(section_id or "section").replace(" ", "_")
        return f"res_{stable_section}_{resource_type}"

    @staticmethod
    def default_resource_title(section_title: str, resource_type: str) -> str:
        labels = {
            "illustration": "图解讲解",
            "code_case": "代码案例",
            "exercise": "巩固练习",
            "mind_map": "思维导图",
        }
        return f"{section_title}{labels[resource_type]}"

    @staticmethod
    def default_resource_subtitle(resource_type: str) -> str:
        subtitles = {
            "illustration": "用可视化方式理解本节核心概念",
            "code_case": "结合代码示例掌握关键步骤",
            "exercise": "通过选择题和填空题检查掌握情况",
            "mind_map": "用结构化导图梳理知识关系",
        }
        return subtitles[resource_type]

    @staticmethod
    def normalize_practice_prompts(practice_prompts: Any) -> list[dict[str, str | None]]:
        if not isinstance(practice_prompts, list):
            return []

        normalized: list[dict[str, str | None]] = []
        for item in practice_prompts:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if not question:
                continue
            normalized.append(
                {
                    "question": question,
                    "answer_hint": item.get("answer_hint") or item.get("hint") or "请回顾本节内容后作答。",
                }
            )

        return normalized

    @staticmethod
    def normalize_exercises(
        exercises: Any,
        section_id: str | None = None,
        default_difficulty: Any = "easy",
    ) -> list[dict[str, Any]]:
        if not isinstance(exercises, list):
            return []

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(exercises, start=1):
            if not isinstance(item, dict):
                continue
            exercise_type = StudentLearningContentAgent.normalize_exercise_type(item.get("type"))
            question = str(item.get("question") or "").strip()
            if not question:
                continue
            exercise = {
                "id": str(item.get("id") or StudentLearningContentAgent.build_exercise_id(section_id, index)),
                "type": exercise_type,
                "question": StudentLearningContentAgent.normalize_exercise_question(question, exercise_type),
                "explanation": str(item.get("explanation") or item.get("analysis") or "请回顾本节内容后复盘。"),
                "difficulty": StudentLearningContentAgent.normalize_difficulty(item.get("difficulty") or default_difficulty),
            }
            if exercise_type in {"choice", "multi_choice"}:
                options = StudentLearningContentAgent.normalize_exercise_options(item.get("options"))
                if len(options) < 2:
                    continue
                exercise["options"] = options
                exercise["correct_answer"] = StudentLearningContentAgent.normalize_choice_answer(
                    item.get("correct_answer") or item.get("answer"),
                    exercise_type,
                    options,
                )
            elif exercise_type == "fill_blank":
                exercise["blanks"] = StudentLearningContentAgent.normalize_blanks(
                    item.get("blanks"),
                    item.get("correct_answer") or item.get("answer"),
                    exercise["question"],
                )
                if not exercise["blanks"]:
                    continue
            else:
                exercise["correct_answer"] = StudentLearningContentAgent.normalize_boolean_answer(
                    item.get("correct_answer") if "correct_answer" in item else item.get("answer")
                )
            normalized.append(exercise)
        return normalized

    @staticmethod
    def normalize_exercise_type(value: Any) -> str:
        raw = str(value or "").strip()
        aliases = {
            "single_choice": "choice",
            "choice": "choice",
            "multi": "multi_choice",
            "multiple_choice": "multi_choice",
            "multi_choice": "multi_choice",
            "fill": "fill_blank",
            "blank": "fill_blank",
            "fill_blank": "fill_blank",
            "true_false": "true_false",
            "judgement": "true_false",
        }
        return aliases.get(raw, "fill_blank")

    @staticmethod
    def normalize_difficulty(value: Any) -> str:
        return DIFFICULTIES.get(str(value or "").strip(), "easy")

    @staticmethod
    def build_exercise_id(section_id: str | None, index: int) -> str:
        stable_section = str(section_id or "section").replace(" ", "_")
        return f"ex_{stable_section}_{index}"

    @staticmethod
    def normalize_exercise_question(question: str, exercise_type: str) -> str:
        if exercise_type == "fill_blank" and "___" not in question:
            return f"{question}___"
        return question

    @staticmethod
    def normalize_exercise_options(options: Any) -> list[dict[str, str]]:
        if not isinstance(options, list):
            return []
        normalized = []
        for index, option in enumerate(options):
            key = chr(ord("A") + index)
            if isinstance(option, dict):
                text = option.get("text") or option.get("value")
                normalized.append({"key": str(option.get("key") or key), "text": str(text or "")})
            else:
                normalized.append({"key": key, "text": str(option)})
        return [item for item in normalized if item["text"]]

    @staticmethod
    def normalize_choice_answer(answer: Any, exercise_type: str, options: list[dict[str, str]]) -> Any:
        valid_keys = {item["key"] for item in options}
        if exercise_type == "multi_choice":
            values = answer if isinstance(answer, list) else [answer]
            keys = [str(item) for item in values if str(item) in valid_keys]
            return keys or [options[0]["key"]]
        answer_key = str(answer or "")
        return answer_key if answer_key in valid_keys else options[0]["key"]

    @staticmethod
    def normalize_blanks(blanks: Any, answer: Any, question: str) -> list[dict[str, Any]]:
        blank_count = max(1, question.count("___"))
        if isinstance(blanks, list):
            normalized = []
            for index, blank in enumerate(blanks[:blank_count]):
                if not isinstance(blank, dict):
                    continue
                blank_answer = str(blank.get("answer") or "").strip()
                if not blank_answer:
                    continue
                item = {"index": int(blank.get("index") if blank.get("index") is not None else index), "answer": blank_answer}
                alternatives = blank.get("alternatives")
                if isinstance(alternatives, list):
                    item["alternatives"] = [str(value) for value in alternatives if str(value).strip()]
                normalized.append(item)
            if normalized:
                return normalized
        if answer is None:
            return []
        values = answer if isinstance(answer, list) else [answer]
        return [
            {"index": index, "answer": str(value)}
            for index, value in enumerate(values[:blank_count])
            if str(value).strip()
        ]

    @staticmethod
    def normalize_boolean_answer(answer: Any) -> bool:
        if isinstance(answer, bool):
            return answer
        if isinstance(answer, str):
            return answer.strip().lower() in {"true", "1", "yes", "对", "正确"}
        return bool(answer)
