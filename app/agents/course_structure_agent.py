from typing import Any, Dict

from app.agents.base import BaseAgent


COURSE_STRUCTURE_SYSTEM_PROMPT = """
你是课程结构设计专家。请根据课程资料识别课程章节结构，只输出合法 JSON 对象。

输出格式必须为：
{
  "chapters": [
    {
      "title": "章节标题",
      "description": "章节说明，不超过60字",
      "sections": [
        {
          "title": "小节标题",
          "description": "小节说明，不超过60字",
          "knowledge_points": [
            {
              "name": "知识点名称",
              "description": "知识点说明，不超过50字",
              "difficulty": "基础"
            }
          ]
        }
      ]
    }
  ]
}

严格要求：
1. 只输出 JSON，不要输出 Markdown，不要输出解释文字。
2. 章节、小节、知识点必须来自给定候选片段，不要凭空扩展。
3. 最多输出 6 个章节。
4. 每个章节最多输出 4 个小节。
5. 每个小节最多输出 4 个知识点。
6. difficulty 只能使用：基础、中等、较难。
7. title、name 要短，description 要短，不要复述原文段落。
8. 输入通常是 RAG 检索出的目录/标题候选片段，请将它们整理成完整、去重、层级清晰的课程目录。
"""


class CourseStructureAgent(BaseAgent):
    """Identify chapters, sections, and knowledge points from course text."""

    name = "Course Structure Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_sync(input_data)

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        text_parts = input_data["text_parts"]
        prompt = (
            "请根据以下由 RAG 检索出的目录、章节、标题或大纲候选片段，生成精简课程结构草稿。"
            "请合并重复标题，修正层级关系，只保留最适合管理员审核的目录结构。\n\n"
            + "\n\n---\n\n".join(text_parts)[:24000]
        )
        return self.llm_service.generate_json_sync(
            system_prompt=COURSE_STRUCTURE_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=4000,
            temperature=0.1,
        )
