import json
from typing import Any, Dict, Optional


def sse_event(
    event: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None,
) -> str:
    """
    组装 SSE 消息。

    标准格式：
    event: delta
    data: {"content":"你好"}

    每条消息必须以两个换行结尾。
    """
    lines = []

    if event_id is not None:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event}")
    lines.append(
        "data: " + json.dumps(data, ensure_ascii=False)
    )

    return "\n".join(lines) + "\n\n"