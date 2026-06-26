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
3. 必须优先保留“文档完整目录”中的全部一级章节和二级小节，不得只保留部分章节。
4. 最多输出 12 个章节，每个章节最多输出 20 个小节。
5. 每个小节输出 1 至 3 个核心知识点。
6. difficulty 只能使用：基础、中等、较难。
7. title、name 要短，description 要短，不要复述原文段落。
8. 输入包含完整目录树和正文摘要。目录树决定章节层级，正文摘要仅用于补充描述和知识点。
"""


class CourseStructureAgent(BaseAgent):
    """Identify chapters, sections, and knowledge points from course text."""

    name = "Course Structure Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_sync(input_data)

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        text_parts = input_data["text_parts"]
        prompt = (
            "请根据以下文档完整目录和小节正文摘要生成课程结构草稿。"
            "必须保留完整目录中的一级章节和二级小节，合并重复目录，但不要因篇幅省略后半部分章节。\n\n"
            + "\n\n---\n\n".join(text_parts)[:24000]
        )
        return self.llm_service.generate_json_sync(
            system_prompt=COURSE_STRUCTURE_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=8000,
            temperature=0.1,
        )
