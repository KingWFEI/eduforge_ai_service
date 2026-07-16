import json
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.agents.student_learning_content_agent import StudentLearningContentAgent


ALLOWED_EXERCISE_TYPES = {"choice", "multi_choice", "fill_blank", "true_false"}


class ExerciseAgent(BaseAgent):
    name = "Exercise Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if "exercise" not in input_data.get("resource_types", []):
            return {
                "generated_resources": input_data.get("generated_resources", []),
                "summary": "跳过练习题生成",
            }

        kp = input_data.get("knowledge_point") or "知识点"
        difficulty = input_data.get("difficulty") or "基础"
        plan = self._find_plan(input_data, "exercise")

        result: Dict[str, Any] = {}
        fallback_reason = None
        try:
            result = await self.llm_service.generate_json(
                prompt=self._build_prompt(input_data),
                max_tokens=3500,
                temperature=0.25,
            )
        except Exception as exc:
            fallback_reason = str(exc)

        questions = result.get("questions") if isinstance(result, dict) else None
        if not isinstance(questions, list) or not questions:
            questions = self._fallback_questions(input_data)
            fallback_reason = fallback_reason or "LLM 未返回可用题目"

        title = result.get("title") or f"{kp} 个性化练习题"
        resource_difficulty = result.get("difficulty") or difficulty
        description = result.get("description") or f"围绕 {kp} 生成的个性化练习题"
        reason = result.get("reason") or plan.get("reason") or "用于检测并巩固当前知识点掌握情况"
        normalized_questions = self._normalize_questions(questions, kp)
        content_json = {
            "title": title,
            "difficulty": resource_difficulty,
            "description": description,
            "reason": reason,
            "exercises": normalized_questions,
        }

        resources = input_data.get("generated_resources", [])
        resources.append(
            {
                "type": "exercise",
                "title": title,
                "difficulty": resource_difficulty,
                "description": description,
                "reason": reason,
                "content_text": None,
                "content_json": content_json,
                "source": "DeepSeek + 课程知识库 + 学生画像" if not fallback_reason else "本地兜底生成 + 课程知识库",
            }
        )

        if fallback_reason:
            return {
                "generated_resources": resources,
                "summary": f"练习题使用本地兜底生成，原因：{fallback_reason}",
            }
        return {"generated_resources": resources, "summary": "DeepSeek 生成练习题 1 份"}

    def _build_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = self._payload(input_data, "exercise")
        return f"""
你是 EduForge AI 的练习题生成智能体。
请基于输入生成一组个性化练习题。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
0. 练习标题、描述、题干、选项、答案解析和提示必须使用简体中文，代码片段及必要的专业缩写除外。
1. 生成 4 到 6 道题，题型只能包含 choice、multi_choice、fill_blank、true_false。
2. 每道题必须有 id、type、question、explanation、difficulty。
3. choice / multi_choice 必须有 options，格式为 [{{"key":"A","text":""}}]。
4. choice 的 correct_answer 是字符串；multi_choice 的 correct_answer 是字符串数组。
5. fill_blank 的 question 必须使用 ___ 标出空位，并提供 blanks 数组。
6. true_false 的 correct_answer 必须是布尔值。
7. difficulty 只能是 easy、medium、hard。
8. 不要生成编程题、代码题、代码补全题、问答题或简答题。
9. 不要编造课程资料之外的专有事实。
10. 严格输出 JSON 对象，不要输出 Markdown。

JSON 格式：
{{
  "title": "",
  "difficulty": "",
  "description": "",
  "reason": "",
  "questions": [
    {{
      "id": "ex_001",
      "type": "choice",
      "question": "",
      "options": [{{"key": "A", "text": ""}}],
      "correct_answer": "A",
      "explanation": "",
      "difficulty": "easy"
    }}
  ]
}}
"""

    def _payload(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        return {
            "knowledge_point": input_data.get("knowledge_point", ""),
            "difficulty": input_data.get("difficulty", "基础"),
            "goal": input_data.get("goal", ""),
            "profile": input_data.get("profile", {}),
            "knowledge_chunks": input_data.get("knowledge_chunks", []),
            "resource_plan": self._find_plan(input_data, resource_type),
        }

    def _fallback_questions(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        kp = input_data.get("knowledge_point") or "知识点"
        goal = input_data.get("goal") or f"理解并应用 {kp}"
        context = self._fallback_context(input_data)
        return [
            {
                "question_id": "q1",
                "id": "ex_001",
                "type": "choice",
                "question": f"关于{kp}，下列哪一项最符合当前学习目标：{goal}？",
                "options": [
                    {"key": "A", "text": f"理解{kp}的基本概念，并能说明它解决的问题"},
                    {"key": "B", "text": "只记住术语名称，不需要理解使用条件"},
                    {"key": "C", "text": "忽略数据与标签之间的关系"},
                    {"key": "D", "text": "只关注代码形式，不需要解释结果"},
                ],
                "correct_answer": "A",
                "explanation": f"本题考查对{kp}学习目标的整体理解。",
                "difficulty": "easy",
                "related_knowledge": kp,
            },
            {
                "question_id": "q2",
                "id": "ex_002",
                "type": "choice",
                "question": f"在使用{kp}解决特征选择问题时，最应该关注什么？",
                "options": [
                    {"key": "A", "text": "特征与标签之间是否存在统计相关性"},
                    {"key": "B", "text": "特征名称是否足够短"},
                    {"key": "C", "text": "样本顺序是否完全随机"},
                    {"key": "D", "text": "模型文件是否足够小"},
                ],
                "correct_answer": "A",
                "explanation": f"{kp}通常用于判断变量之间的关联程度，特征选择时应关注特征与标签的关系。",
                "difficulty": "easy",
                "related_knowledge": kp,
            },
            {
                "question_id": "q3",
                "id": "ex_003",
                "type": "fill_blank",
                "question": f"{kp}在本课程任务中的作用是帮助判断___与目标标签之间的关系。",
                "blanks": [{"index": 0, "answer": "特征"}],
                "explanation": f"回答应体现{kp}与任务目标、特征选择或结果解释之间的联系。",
                "difficulty": "medium",
                "related_knowledge": kp,
            },
            {
                "question_id": "q4",
                "id": "ex_004",
                "type": "true_false",
                "question": f"学习{kp}时可以脱离课程材料中的适用条件直接使用结论。",
                "correct_answer": False,
                "explanation": f"需要结合课程片段“{context}”中的条件或限制解释结果。",
                "difficulty": "medium",
                "related_knowledge": kp,
            },
        ]

    def _fallback_context(self, input_data: Dict[str, Any]) -> str:
        chunks = input_data.get("knowledge_chunks") or []
        for item in chunks:
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or item.get("chunk_text")
                if content:
                    return str(content).strip()[:120]
        return "暂无可用片段，请结合课堂材料和练习解析复习。"

    def _normalize_questions(self, questions: List[Any], knowledge_point: str) -> List[Dict[str, Any]]:
        normalized = []
        for index, item in enumerate(questions, start=1):
            if not isinstance(item, dict):
                continue
            normalized.extend(
                StudentLearningContentAgent.normalize_exercises(
                    [{**item, "id": item.get("id") or item.get("question_id") or f"ex_{index}"}],
                    default_difficulty=item.get("difficulty") or "easy",
                )
            )
        return normalized or self._fallback_questions({"knowledge_point": knowledge_point})

    def _find_plan(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
