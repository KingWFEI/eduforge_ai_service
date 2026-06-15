import json
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent


class ChunkClassifierAgent(BaseAgent):
    """Classify chunks into confirmed chapters and knowledge points."""

    name = "Chunk Classifier Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_sync(input_data)

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        chunks: list[str] = input_data["chunks"]
        structure_items: list[dict[str, Any]] = input_data["structure_items"]
        batch_size: int = input_data.get("batch_size", 12)

        if not chunks or not structure_items:
            return {"assignments": {}}

        structure_payload, valid_chapter_ids, valid_knowledge_point_ids = (
            self._build_structure_payload(structure_items)
        )
        assignments: dict[int, tuple[Optional[str], Optional[str], list[str]]] = {}

        for start in range(0, len(chunks), batch_size):
            batch = [
                {
                    "chunk_index": index,
                    "content": chunks[index][:900],
                }
                for index in range(start, min(start + batch_size, len(chunks)))
            ]
            result = self.llm_service.generate_json_sync(
                system_prompt="你是课程结构识别智能体，只输出合法 JSON。",
                user_prompt=self._build_prompt(structure_payload, batch),
                max_tokens=3000,
                temperature=0.1,
            )
            self._merge_assignments(
                assignments=assignments,
                result=result,
                chunk_count=len(chunks),
                valid_chapter_ids=valid_chapter_ids,
                valid_knowledge_point_ids=valid_knowledge_point_ids,
            )

        return {"assignments": assignments}

    def _build_structure_payload(
        self,
        structure_items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], set[str], set[str]]:
        structure_payload = []
        valid_chapter_ids = set()
        valid_knowledge_point_ids = set()

        for item in structure_items:
            chapter_id = item.get("section_id") or item.get("chapter_id")
            knowledge_point_id = item.get("knowledge_point_id")
            if chapter_id:
                valid_chapter_ids.add(chapter_id)
            if knowledge_point_id:
                valid_knowledge_point_ids.add(knowledge_point_id)
            structure_payload.append(
                {
                    "chapter_id": chapter_id,
                    "chapter_title": item.get("chapter_title"),
                    "section_title": item.get("section_title"),
                    "knowledge_point_id": knowledge_point_id,
                    "knowledge_point_name": item.get("knowledge_point_name"),
                    "knowledge_point_description": item.get("knowledge_point_description"),
                }
            )

        return structure_payload, valid_chapter_ids, valid_knowledge_point_ids

    def _build_prompt(
        self,
        structure_payload: list[dict[str, Any]],
        batch: list[dict[str, Any]],
    ) -> str:
        return f"""
你是 EduForge AI 的课程知识块归属识别智能体。

请根据课程结构，为每个 chunk 选择最匹配的 chapter_id 和 knowledge_point_id。

课程结构：
{json.dumps(structure_payload, ensure_ascii=False, indent=2)}

待识别 chunks：
{json.dumps(batch, ensure_ascii=False, indent=2)}

要求：
1. chapter_id 必须来自课程结构中的 chapter_id。
2. knowledge_point_id 必须来自课程结构中的 knowledge_point_id。
3. 如果无法判断，chapter_id 和 knowledge_point_id 返回 null。
4. confidence 为 0 到 1。
5. keywords 返回用于解释匹配的短关键词。
6. 严格输出 JSON 对象。

JSON 格式：
{{
  "assignments": [
    {{
      "chunk_index": 0,
      "chapter_id": null,
      "knowledge_point_id": null,
      "confidence": 0.0,
      "keywords": []
    }}
  ]
}}
"""

    def _merge_assignments(
        self,
        assignments: dict[int, tuple[Optional[str], Optional[str], list[str]]],
        result: Dict[str, Any],
        chunk_count: int,
        valid_chapter_ids: set[str],
        valid_knowledge_point_ids: set[str],
    ) -> None:
        rows = result.get("assignments", [])
        if not isinstance(rows, list):
            return

        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                chunk_index = int(row.get("chunk_index"))
            except (TypeError, ValueError):
                continue
            if chunk_index < 0 or chunk_index >= chunk_count:
                continue

            chapter_id = row.get("chapter_id")
            knowledge_point_id = row.get("knowledge_point_id")
            if chapter_id not in valid_chapter_ids:
                chapter_id = None
            if knowledge_point_id not in valid_knowledge_point_ids:
                knowledge_point_id = None

            keywords = row.get("keywords") or []
            if not isinstance(keywords, list):
                keywords = []
            assignments[chunk_index] = (
                chapter_id,
                knowledge_point_id,
                [str(keyword)[:50] for keyword in keywords[:8]],
            )
