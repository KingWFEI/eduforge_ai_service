from abc import ABC, abstractmethod
from typing import Any, Dict


from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    name: str

    def __init__(self, llm_service):
        self.llm_service = llm_service

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass