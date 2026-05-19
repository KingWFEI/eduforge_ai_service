# app/services/deepseek_service.py

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class DeepSeekService:
    """
    DeepSeek 大模型调用服务。
    """

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if not self.api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在 .env 文件中配置")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500
    ) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            response_format={
                "type": "json_object"
            },
            temperature=0.2,
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise RuntimeError(f"DeepSeek 返回内容不是合法 JSON：{content}")