from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAgent(ABC):
    """
    所有智能体的基类。

    注意：
    llm_service 改成可选，是为了让一些规则型 Agent 不必强制传入大模型服务。
    """
    name: str = "Base Agent"

    def __init__(self, llm_service: Optional[Any] = None):
        self.llm_service = llm_service

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
