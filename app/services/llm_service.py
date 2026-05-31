# app/services/llm_service.py

import asyncio
import json
import os
import re
from typing import Any, Dict, Optional, AsyncGenerator

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class LLMService:
    """
    统一大模型调用服务。

    当前实现：
    - 使用 DeepSeek OpenAI-Compatible API
    - 支持 async 调用，方便在 FastAPI / Agent 中使用 await
    - 支持 generate_text：返回普通文本
    - 支持 generate_json：要求模型返回 JSON，并解析为 dict

    .env 配置示例：
    DEEPSEEK_API_KEY=你的key
    DEEPSEEK_BASE_URL=https://api.deepseek.com
    DEEPSEEK_MODEL=deepseek-chat
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if not self.api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在 .env 文件中配置")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.4,
    ) -> str:
        """
        生成普通文本。

        适用场景：
        - AI 对话回复
        - 学习建议
        - 总结文案
        - 非严格 JSON 输出的内容
        """
        final_system_prompt = system_prompt or "你是 EduForge AI 的学习智能体助手，请根据任务要求给出准确、清晰的回答。"

        def _call() -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content or ""

        # OpenAI SDK 这里是同步调用，放到线程里避免阻塞 FastAPI 事件循环
        content = await asyncio.to_thread(_call)
        return self._parse_json_content(content)

    async def stream_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.4,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本。

        用于：
        - DialogueGuideAgent 流式输出下一轮追问
        - TutorAgent 流式答疑
        """
        final_system_prompt = system_prompt or (
            "你是 EduForge AI 的学习画像对话助手。"
            "请自然、温和、简洁地回复学生。"
        )

        def _create_stream():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

        stream = await asyncio.to_thread(_create_stream)

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """
        生成 JSON 并解析成 dict。

        适用场景：
        - RelevanceJudgeAgent
        - ProfileExtractorAgent
        - DialogueGuideAgent
        - ProfileTypeAgent
        - SafetyAgent

        注意：
        使用 response_format={"type": "json_object"} 时，prompt 中仍然建议明确要求：
        “请严格输出 JSON，不要输出多余文字”。
        """
        final_system_prompt = system_prompt or (
            "你是 EduForge AI 的结构化输出智能体。"
            "你必须严格输出合法 JSON 对象，不要输出 Markdown，不要输出代码块，不要输出解释文字。"
        )

        def _call_deepseek() -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content or ""

        content = await asyncio.to_thread(_call_deepseek)
        return self._parse_json_content(content)


    def _parse_json_content(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 返回的 JSON。

        DeepSeek 在 response_format=json_object 下通常会直接返回合法 JSON。
        这里额外做一层兜底，防止模型返回 ```json ... ``` 代码块。
        """
        if not content or not content.strip():
            raise RuntimeError("DeepSeek 返回内容为空，无法解析 JSON")

        raw = content.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 兜底：提取 ```json ... ``` 或 ``` ... ``` 中的内容
        code_block_match = re.search(
            r"```(?:json)?\s*(.*?)```",
            raw,
            flags=re.DOTALL | re.IGNORECASE,
        )

        if code_block_match:
            json_text = code_block_match.group(1).strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

        # 兜底：尝试提取第一个 JSON 对象
        object_match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if object_match:
            json_text = object_match.group(0).strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

        raise RuntimeError(f"LLM返回内容不是合法 JSON：{content}")
