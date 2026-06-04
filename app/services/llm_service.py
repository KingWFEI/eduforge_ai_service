# app/services/llm_service.py

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

logger = logging.getLogger("app.services.llm_service")


class LLMService:
    """
    统一大模型调用服务。

    当前通过 OpenAI-Compatible API 调用模型，业务代码只依赖本服务。
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

    def _chat_completion_content(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format is not None:
            request_kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**request_kwargs)
        choice = response.choices[0]
        content = choice.message.content

        if not content:
            raise RuntimeError("LLM 返回内容为空")

        if choice.finish_reason != "stop":
            logger.error(
                "LLM output incomplete | model=%s | finish_reason=%s | content_length=%d",
                self.model,
                choice.finish_reason,
                len(content),
            )
            if choice.finish_reason == "length":
                raise RuntimeError(
                    f"LLM 输出因 max_tokens={max_tokens} 限制被截断，未生成完整内容"
                )
            raise RuntimeError(f"LLM 输出未正常完成：finish_reason={choice.finish_reason}")

        return content.strip()

    def generate_text_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.4,
    ) -> str:
        """同步生成普通文本，供同步 service/skill 调用。"""
        final_system_prompt = system_prompt or (
            "你是 EduForge AI 的学习智能体助手，请根据任务要求给出准确、清晰的回答。"
        )
        return self._chat_completion_content(
            system_prompt=final_system_prompt,
            user_prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.4,
    ) -> str:
        """异步生成普通文本，供 FastAPI/Agent 中 await 调用。"""
        return await asyncio.to_thread(
            self.generate_text_sync,
            prompt,
            system_prompt,
            max_tokens,
            temperature,
        )

    def rag_generate_text_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> str:
        """同步 RAG 文本生成。"""
        return self._chat_completion_content(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def rag_generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> str:
        """异步 RAG 文本生成。"""
        return await asyncio.to_thread(
            self.rag_generate_text_sync,
            system_prompt,
            user_prompt,
            max_tokens,
            temperature,
        )

    def generate_json_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """
        同步生成 JSON 并解析成 dict。

        这个方法供同步 skill/service 生成结构化结果。
        """
        content = self._chat_completion_content(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return self._parse_json_content(content)

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """异步生成 JSON 并解析成 dict。"""
        final_system_prompt = system_prompt or (
            "你是 EduForge AI 的结构化输出智能体。"
            "你必须严格输出合法 JSON 对象，不要输出 Markdown，不要输出代码块，不要输出解释文字。"
        )
        return await asyncio.to_thread(
            self.generate_json_sync,
            final_system_prompt,
            prompt,
            max_tokens,
            temperature,
        )

    async def stream_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.4,
    ) -> AsyncGenerator[str, None]:
        """流式生成文本。"""
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

    def _parse_json_content(self, content: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON，兼容少量代码块包裹。"""
        if not content or not content.strip():
            raise RuntimeError("LLM 返回内容为空，无法解析 JSON")

        raw = content.strip()
        parse_error: Optional[json.JSONDecodeError] = None

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            parse_error = exc

        code_block_match = re.search(
            r"```(?:json)?\s*(.*?)```",
            raw,
            flags=re.DOTALL | re.IGNORECASE,
        )

        if code_block_match:
            json_text = code_block_match.group(1).strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as exc:
                parse_error = exc

        object_match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if object_match:
            json_text = object_match.group(0).strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as exc:
                parse_error = exc

        logger.error(
            "LLM returned invalid JSON | model=%s | content_length=%d | "
            "json_error=%s | line=%s | column=%s | preview=%r",
            self.model,
            len(content),
            parse_error.msg if parse_error else "unknown",
            parse_error.lineno if parse_error else "unknown",
            parse_error.colno if parse_error else "unknown",
            content[:500],
        )
        if parse_error:
            raise RuntimeError(
                "LLM 返回内容不是合法 JSON："
                f"{parse_error.msg}（第 {parse_error.lineno} 行，第 {parse_error.colno} 列）"
            )
        raise RuntimeError("LLM 返回内容不是合法 JSON")
