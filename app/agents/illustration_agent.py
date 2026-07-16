import ast
import json
from typing import Any, Dict

from app.agents.base import BaseAgent


ALLOWED_VISUALIZATION_PACKAGES = {"matplotlib", "numpy"}
DISALLOWED_CALLS = {"eval", "exec", "open", "compile", "__import__", "input"}
DISALLOWED_ATTRIBUTES = {
    "savefig", "imsave", "load", "loadtxt", "genfromtxt", "fromfile", "tofile",
    "system", "popen", "remove", "unlink", "read", "write",
}


class IllustrationAgent(BaseAgent):
    """Decide whether an illustration helps, then generate safe renderable Python."""

    name = "Illustration Agent"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        decision = await self.llm_service.generate_json(
            prompt=self._build_decision_prompt(input_data),
            max_tokens=1000,
            temperature=0.1,
        )
        normalized_decision = self._normalize_decision(decision)
        if not normalized_decision["should_generate"]:
            return {
                "should_generate": False,
                "decision": normalized_decision,
                "resource": None,
            }

        result = await self.llm_service.generate_json(
            prompt=self._build_generation_prompt(input_data, normalized_decision),
            max_tokens=4000,
            temperature=0.2,
        )
        python_code = str(result.get("python_code") or "").strip()
        validate_visualization_python(python_code)
        content_json = {
            "decision": normalized_decision,
            "overview": result.get("overview") or "",
            "scenes": result.get("scenes") if isinstance(result.get("scenes"), list) else [],
            "key_takeaways": (
                result.get("key_takeaways")
                if isinstance(result.get("key_takeaways"), list)
                else []
            ),
        }
        return {
            "should_generate": True,
            "decision": normalized_decision,
            "resource": {
                "type": "illustration",
                "title": result.get("title"),
                "description": result.get("description"),
                "content_text": result.get("overview"),
                "content_json": content_json,
                "_python_code": python_code,
                "source": "DeepSeek + 课程知识库 + 学生画像 + Python 可视化",
            },
        }

    @staticmethod
    def _normalize_decision(value: Dict[str, Any]) -> Dict[str, Any]:
        suitability_score = _score(value.get("suitability_score"))
        profile_fit_score = _score(value.get("profile_fit_score"))
        requested = value.get("should_generate") in (True, 1, "true", "True", "yes")
        should_generate = requested and suitability_score >= 0.55 and profile_fit_score >= 0.4
        return {
            "should_generate": should_generate,
            "reason": str(value.get("reason") or "未提供判断原因"),
            "suitability_score": suitability_score,
            "profile_fit_score": profile_fit_score,
            "visualization_kind": str(value.get("visualization_kind") or "concept_diagram"),
        }

    def _build_decision_prompt(self, input_data: Dict[str, Any]) -> str:
        payload = self._payload(input_data)
        return f"""
你是 EduForge AI 的图解适用性判断智能体。请先判断当前小节是否适合生成图解，并结合学生画像判断图解是否对该用户有实际帮助。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

判断规则：
1. 算法过程、空间关系、数据分布、结构关系、状态变化、流程和对比实验通常适合图解。
2. 纯定义、简单事实、缺乏可视化数据或图解会造成误导时，不建议生成。
3. 学生偏好图像、案例、动手实验，或基础较弱时，提高 profile_fit_score。
4. 课程内容是否适合与用户是否需要必须分别评分。
5. suitability_score 和 profile_fit_score 均为 0 到 1；只有两者综合足够高时 should_generate 才为 true。
6. 严格返回 JSON，不输出 Markdown。
7. reason 和 visualization_kind 之外的说明必须使用简体中文，不要输出整段英文说明。

JSON 格式：
{{
  "should_generate": true,
  "reason": "",
  "suitability_score": 0.0,
  "profile_fit_score": 0.0,
  "visualization_kind": "scatter_plot | process_diagram | comparison_chart | concept_diagram"
}}
"""

    def _build_generation_prompt(
        self,
        input_data: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> str:
        payload = self._payload(input_data)
        payload["decision"] = decision
        return f"""
你是 EduForge AI 的 Python 教学图解生成智能体。判断阶段已确认适合生成图解，请生成可由后端隔离渲染进程执行的 Python 可视化代码。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

要求：
1. 只允许导入 numpy、matplotlib 及其子模块，不允许网络、文件、进程、系统、动态执行相关操作。
2. 代码必须完整、确定性可复现；随机数据必须设置固定随机种子。
3. 代码最后必须保留名为 fig 的 matplotlib Figure 对象，不调用 plt.show()，不保存文件。
4. title、description、overview、scenes、key_takeaways 以及图表标题、坐标轴、图例、标注必须使用简体中文；Python 变量名可以使用英文。
5. 对聚类算法等主题，优先用散点图、不同簇颜色和聚类中心直观演示。
6. 仅基于提供的课程资料生成，不要编造课程外的结论。
7. python_code 返回纯代码字符串，不包含 Markdown 代码围栏。
8. 严格返回 JSON。
9. 不要因为算法名称或代码是英文，就把教学说明和图表标签改成英文。

JSON 格式：
{{
  "title": "",
  "description": "",
  "overview": "",
  "scenes": [{{"title": "", "visual": "", "explanation": ""}}],
  "key_takeaways": [],
  "python_code": "import numpy as np\\nimport matplotlib.pyplot as plt\\n...\\nfig = plt.gcf()"
}}
"""

    @staticmethod
    def _payload(input_data: Dict[str, Any]) -> Dict[str, Any]:
        chunks = []
        for item in input_data.get("knowledge_chunks", [])[:6]:
            chunks.append(
                {
                    "section": item.get("section"),
                    "content": str(item.get("content") or "")[:1200],
                }
            )
        return {
            "chapter_title": input_data.get("chapter_title"),
            "section_title": input_data.get("section_title"),
            "knowledge_point": input_data.get("knowledge_point"),
            "goal": input_data.get("goal"),
            "difficulty": input_data.get("difficulty"),
            "profile": input_data.get("profile") or {},
            "knowledge_chunks": chunks,
            "resource_plan": input_data.get("resource_plan") or [],
        }


def validate_visualization_python(code: str) -> None:
    if not code:
        raise RuntimeError("图解智能体未返回 Python 可视化代码")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise RuntimeError("图解智能体返回的 Python 代码语法无效") from exc

    has_matplotlib = False
    assigns_figure = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_VISUALIZATION_PACKAGES:
                    raise RuntimeError(f"图解代码包含不允许的依赖：{root}")
                has_matplotlib = has_matplotlib or root == "matplotlib"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_VISUALIZATION_PACKAGES:
                raise RuntimeError(f"图解代码包含不允许的依赖：{root}")
            has_matplotlib = has_matplotlib or root == "matplotlib"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in DISALLOWED_CALLS:
                raise RuntimeError(f"图解代码包含不允许的调用：{node.func.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in DISALLOWED_ATTRIBUTES:
                raise RuntimeError(f"图解代码包含不允许的属性调用：{node.attr}")
        elif isinstance(node, ast.While):
            raise RuntimeError("图解代码不允许使用 while 循环")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assigns_figure = assigns_figure or any(
                any(
                    isinstance(child, ast.Name) and child.id == "fig"
                    for child in ast.walk(target)
                )
                for target in targets
            )

    if not has_matplotlib:
        raise RuntimeError("图解代码必须使用 matplotlib")
    if not assigns_figure:
        raise RuntimeError("图解代码必须生成名为 fig 的 Figure 对象")


def _score(value: Any) -> float:
    try:
        return round(min(max(float(value), 0.0), 1.0), 4)
    except (TypeError, ValueError):
        return 0.0
