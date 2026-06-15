import json
from typing import Any, Dict, List

from app.agents.base import BaseAgent


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

        normalized_questions = self._normalize_questions(questions, kp)

        resources = input_data.get("generated_resources", [])
        resources.append(
            {
                "type": "exercise",
                "title": result.get("title") or f"{kp} 个性化练习题",
                "difficulty": result.get("difficulty") or difficulty,
                "description": result.get("description") or f"围绕 {kp} 生成的个性化练习题",
                "reason": result.get("reason") or plan.get("reason") or "用于检测并巩固当前知识点掌握情况",
                "content_text": None,
                "content_json": {"questions": normalized_questions},
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
1. 生成 4 到 6 道题，题型包含 single_choice 和 short_answer。
2. 每道题必须有 question_id、type、question、answer、analysis、related_knowledge。
3. single_choice 必须有 options，格式为 [{{"key":"A","value":""}}]。
4. 难度和解析要匹配 difficulty 与学生画像。
5. 不要编造课程资料之外的专有事实。
6. 严格输出 JSON 对象，不要输出 Markdown。

JSON 格式：
{{
  "title": "",
  "difficulty": "",
  "description": "",
  "reason": "",
  "questions": [
    {{
      "question_id": "q1",
      "type": "single_choice",
      "question": "",
      "options": [{{"key": "A", "value": ""}}],
      "answer": "A",
      "analysis": "",
      "related_knowledge": ""
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
                "type": "single_choice",
                "question": f"关于{kp}，下列哪一项最符合当前学习目标：{goal}？",
                "options": [
                    {"key": "A", "value": f"理解{kp}的基本概念，并能说明它解决的问题"},
                    {"key": "B", "value": "只记住术语名称，不需要理解使用条件"},
                    {"key": "C", "value": "忽略数据与标签之间的关系"},
                    {"key": "D", "value": "只关注代码形式，不需要解释结果"},
                ],
                "answer": "A",
                "analysis": f"本题考查对{kp}学习目标的整体理解。",
                "related_knowledge": kp,
            },
            {
                "question_id": "q2",
                "type": "single_choice",
                "question": f"在使用{kp}解决特征选择问题时，最应该关注什么？",
                "options": [
                    {"key": "A", "value": "特征与标签之间是否存在统计相关性"},
                    {"key": "B", "value": "特征名称是否足够短"},
                    {"key": "C", "value": "样本顺序是否完全随机"},
                    {"key": "D", "value": "模型文件是否足够小"},
                ],
                "answer": "A",
                "analysis": f"{kp}通常用于判断变量之间的关联程度，特征选择时应关注特征与标签的关系。",
                "related_knowledge": kp,
            },
            {
                "question_id": "q3",
                "type": "short_answer",
                "question": f"请用自己的话说明{kp}在本课程任务中的作用。",
                "answer": f"{kp}用于帮助判断特征与目标标签之间的关系，从而选择更有价值的特征。",
                "analysis": f"回答应体现{kp}与任务目标、特征选择或结果解释之间的联系。",
                "related_knowledge": kp,
            },
            {
                "question_id": "q4",
                "type": "short_answer",
                "question": f"结合以下课程片段，说明学习{kp}时需要注意的一个前提或限制：{context}",
                "answer": "需要结合数据类型、任务目标和统计检验前提解释结果，不能只看数值大小。",
                "analysis": "本题考查学生能否把课程材料中的条件或限制转化为实际使用判断。",
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
            question_type = item.get("type") or "short_answer"
            answer = item.get("answer")
            if answer is None:
                answer = item.get("correct_answer")
            normalized.append(
                {
                    "question_id": item.get("question_id") or item.get("id") or f"q{index}",
                    "type": question_type,
                    "question": item.get("question") or f"请说明{knowledge_point}的核心概念。",
                    "options": item.get("options") if question_type == "single_choice" else item.get("options"),
                    "answer": answer,
                    "analysis": item.get("analysis") or item.get("explanation") or "请结合课程资料复习该知识点。",
                    "related_knowledge": item.get("related_knowledge") or item.get("knowledge_point") or knowledge_point,
                }
            )
        return normalized or self._fallback_questions({"knowledge_point": knowledge_point})

    def _find_plan(self, input_data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        for item in input_data.get("resource_plan", []):
            if item.get("resource_type") == resource_type:
                return item
        return {}
