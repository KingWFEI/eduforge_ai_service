from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    name: str = "Base Agent"

    @abstractmethod
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass