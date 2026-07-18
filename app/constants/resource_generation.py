from __future__ import annotations

from enum import Enum


class GenerationScope(str, Enum):
    SECTION = "section"
    CHAPTER = "chapter"
    COURSE = "course"


class ResourceType(str, Enum):
    ILLUSTRATION = "illustration"
    DOCUMENT = "document"
    MIND_MAP = "mind_map"
    EXERCISE = "exercise"
    CODE_CASE = "code_case"
    VIDEO = "video"
    PPT = "ppt"


SUPPORTED_SECTION_RESOURCE_TYPES = frozenset(ResourceType)
DEFAULT_SECTION_RESOURCE_SHELL_TYPES = (
    ResourceType.ILLUSTRATION,
    ResourceType.CODE_CASE,
    ResourceType.EXERCISE,
    ResourceType.MIND_MAP,
)
SUPPORTED_CHAPTER_RESOURCE_TYPES = frozenset(ResourceType)
SUPPORTED_COURSE_RESOURCE_TYPES = frozenset(
    {
        ResourceType.DOCUMENT,
        ResourceType.MIND_MAP,
        ResourceType.EXERCISE,
        ResourceType.CODE_CASE,
        ResourceType.VIDEO,
        ResourceType.PPT,
    }
)

RESOURCE_TYPE_SCOPES: dict[ResourceType, frozenset[GenerationScope]] = {
    resource_type: frozenset(
        scope
        for scope, supported in (
            (GenerationScope.SECTION, SUPPORTED_SECTION_RESOURCE_TYPES),
            (GenerationScope.CHAPTER, SUPPORTED_CHAPTER_RESOURCE_TYPES),
            (GenerationScope.COURSE, SUPPORTED_COURSE_RESOURCE_TYPES),
        )
        if resource_type in supported
    )
    for resource_type in ResourceType
}


def validate_resource_scope(resource_type: str, generation_scope: str) -> tuple[ResourceType, GenerationScope]:
    parsed_type = ResourceType(resource_type)
    parsed_scope = GenerationScope(generation_scope)
    if parsed_scope not in RESOURCE_TYPE_SCOPES[parsed_type]:
        raise ValueError(f"resource_type={parsed_type.value} 不支持 scope={parsed_scope.value}")
    return parsed_type, parsed_scope
