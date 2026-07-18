from __future__ import annotations

import html
import re


FORBIDDEN_HTML_PATTERNS = (
    r"<\s*(iframe|object|embed|form|base)\b",
    r"\bon\w+\s*=",
    r"\b(fetch|XMLHttpRequest|window\.open|top\.location|localStorage)\s*\(",
    r"javascript\s*:",
)


class HtmlSanitizer:
    @staticmethod
    def escape(value: object) -> str:
        return html.escape(str(value or ""), quote=True)

    @staticmethod
    def assert_safe_document(document: str) -> None:
        for pattern in FORBIDDEN_HTML_PATTERNS:
            if re.search(pattern, document, flags=re.IGNORECASE):
                raise ValueError(f"HTML 包含危险内容：{pattern}")
        for script_src in re.findall(r"<script\b[^>]*\bsrc\s*=", document, flags=re.IGNORECASE):
            if script_src:
                raise ValueError("HTML 不允许外部脚本")
