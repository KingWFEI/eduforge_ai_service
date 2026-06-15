from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.services.llm_service import DeepSeekService


class BaseAgent(ABC):
    """Base class for agents.

    BaseAgent is the single owner of the LLM service dependency. Subclasses
    should focus on building prompts and handling model responses.
    """

    name: str = "Base Agent"

    def __init__(self, llm_service: Optional[DeepSeekService] = None):
        self.llm_service = llm_service or DeepSeekService()

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
