from typing import Any, Dict

from app.agents.base import BaseAgent


COURSE_STRUCTURE_SYSTEM_PROMPT = """
你是课程设计专家。请根据课程资料识别课程结构，只输出合法 JSON 对象。
JSON 格式必须为：
{
  "chapters": [
    {
      "title": "章标题",
      "description": "章说明",
      "sections": [
        {
          "title": "小节标题",
          "description": "小节说明",
          "knowledge_points": [
            {
              "name": "知识点名称",
              "description": "知识点说明",
              "difficulty": "基础/中等/较难"
            }
          ]
        }
      ]
    }
  ]
}
要求：
1. 章节、小节、知识点必须来自资料内容，不要凭空扩展。
2. 如果资料没有明显小节，也要按主题归纳出小节。
3. 知识点名称要短，适合用于检索和学习路径规划。
4. difficulty 只能使用：基础、中等、较难。
"""


class CourseStructureAgent(BaseAgent):
    """Identify chapters, sections, and knowledge points from course text."""

    name = "Course Structure Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_sync(input_data)

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        text_parts = input_data["text_parts"]
        prompt = (
            "请根据以下课程资料生成课程结构草稿。\n\n"
            + "\n\n---\n\n".join(text_parts)[:50000]
        )
        return self.llm_service.generate_json_sync(
            system_prompt=COURSE_STRUCTURE_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=5000,
            temperature=0.1,
        )
