from __future__ import annotations

from app.agents.resource_generation.ppt.schemas import ContentBlock, PptDeck, PptRequirement


class PptContentAgent:
    """Builds validated slide content; it never emits HTML or JavaScript."""

    def build(self, outline: PptDeck, requirement: PptRequirement, state: dict) -> PptDeck:
        chunks = state.get("retrieved_chunks") or state.get("knowledge_chunks") or []
        grounded = [item for item in chunks if item.get("content")]
        takeaways: list[str] = []
        for slide in outline.slides:
            if slide.layout == "title_slide":
                slide.content_blocks = [
                    ContentBlock(type="bullets", items=[slide.learning_goal, f"难度：{requirement.difficulty}"])
                ]
            elif slide.layout == "summary":
                items = takeaways[-4:] or outline.key_takeaways
                slide.content_blocks = [ContentBlock(type="bullets", items=items[:6])]
            else:
                chunk = grounded[(slide.slide_no - 2) % len(grounded)] if grounded else None
                text = str(chunk.get("content") if chunk else "当前课程资料未提供足够正文，请结合课堂材料复习。")
                text = " ".join(text.split())[:520]
                slide.content_blocks = [ContentBlock(type="paragraph", text=text)]
                if requirement.needs_examples:
                    slide.content_blocks.append(
                        ContentBlock(type="callout", title="学习提示", text="先用直觉解释，再核对定义、公式与例题。")
                    )
                takeaways.append(slide.title)
                if chunk and chunk.get("chunk_id"):
                    slide.source_chunk_ids = [str(chunk["chunk_id"])]
        outline.key_takeaways = (takeaways or outline.key_takeaways)[:6]
        return PptDeck.model_validate(outline.model_dump())
