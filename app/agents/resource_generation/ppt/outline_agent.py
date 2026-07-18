from __future__ import annotations

from app.agents.resource_generation.ppt.schemas import PptDeck, PptRequirement, PptSlide, VisualSpec


class PptOutlineAgent:
    def build(self, requirement: PptRequirement, state: dict) -> PptDeck:
        chunks = state.get("retrieved_chunks") or state.get("knowledge_chunks") or []
        chapter = state.get("current_chapter_context") or {}
        section = state.get("current_section_context") or {}
        subject = section.get("title") or chapter.get("title") or state.get("knowledge_point") or "课程主题"
        source_ids = [str(item.get("chunk_id")) for item in chunks if item.get("chunk_id")]
        topics = list(requirement.focus_knowledge_points)
        if not topics:
            topics = [str(item.get("name")) for item in (state.get("target_knowledge_points") or []) if item.get("name")]
        if not topics:
            topics = [subject]

        slides: list[PptSlide] = []
        for number in range(1, requirement.slide_count + 1):
            if number == 1:
                title, layout, goal = subject, "title_slide", "了解本课件的学习目标"
                subtitle = requirement.purpose
            elif number == requirement.slide_count:
                title, layout, goal = "总结与下一步", "summary", "巩固关键结论并规划下一步学习"
                subtitle = "回顾核心概念"
            else:
                topic = topics[(number - 2) % len(topics)]
                title = topic if number == 2 else f"{topic}：理解与应用"
                layout, goal, subtitle = "content", f"掌握{topic}的核心含义", "从概念到示例"
            slides.append(
                PptSlide(
                    slide_no=number,
                    title=title,
                    subtitle=subtitle,
                    layout=layout,
                    learning_goal=goal,
                    content_blocks=[],
                    visual_spec=VisualSpec(
                        type="concept_illustration" if requirement.needs_visuals else "none",
                        description=f"用清晰图示辅助理解{title}" if requirement.needs_visuals else "",
                    ),
                    notes="每页只讲一个主要教学目标",
                    source_chunk_ids=source_ids[:3],
                )
            )
        return PptDeck(overview=f"通过互动课件系统学习{subject}", key_takeaways=topics[:5], slides=slides)
