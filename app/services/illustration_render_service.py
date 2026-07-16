import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.agents.illustration_agent import validate_visualization_python


ILLUSTRATION_OUTPUT_DIR = Path(
    os.getenv("ILLUSTRATION_OUTPUT_DIR", "uploads/generated/illustrations")
)
ILLUSTRATION_RENDER_TIMEOUT_SECONDS = int(
    os.getenv("ILLUSTRATION_RENDER_TIMEOUT_SECONDS", "10")
)


def render_python_illustration(python_code: str) -> dict[str, Any]:
    """Run validated plotting code in a short-lived process and persist a PNG."""
    validate_visualization_python(python_code)
    output_dir = ILLUSTRATION_OUTPUT_DIR.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"illustration_{uuid.uuid4().hex}.png"
    output_path = output_dir / filename

    with tempfile.TemporaryDirectory(prefix="eduforge_illustration_") as temp_dir:
        temp_path = Path(temp_dir)
        script_path = temp_path / "render.py"
        script = (
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
            "matplotlib.rcParams['font.sans-serif'] = "
            "['Microsoft YaHei', 'SimHei', 'SimSun', 'Noto Sans CJK SC', 'DejaVu Sans']\n"
            "matplotlib.rcParams['axes.unicode_minus'] = False\n"
            f"{python_code.rstrip()}\n"
            "if fig is None:\n"
            "    raise RuntimeError('fig is None')\n"
            f"fig.savefig({str(output_path)!r}, format='png', dpi=160, "
            "bbox_inches='tight', facecolor='white')\n"
        )
        script_path.write_text(script, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "TEMP": str(temp_path),
            "TMP": str(temp_path),
            "MPLCONFIGDIR": str(temp_path / "matplotlib"),
            "PYTHONIOENCODING": "utf-8",
        }
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-B", str(script_path)],
                cwd=str(temp_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=ILLUSTRATION_RENDER_TIMEOUT_SECONDS,
                check=False,
                creationflags=creation_flags,
            )
        except subprocess.TimeoutExpired as exc:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("Python 图解渲染超时") from exc

    if completed.returncode != 0 or not output_path.exists():
        output_path.unlink(missing_ok=True)
        error = (completed.stderr or completed.stdout or "未知错误").strip()[-1000:]
        raise RuntimeError(f"Python 图解渲染失败：{error}")

    return {
        "renderer": "image",
        "image_url": f"/uploads/generated/illustrations/{filename}",
        "mime_type": "image/png",
        "generated_by": "python_matplotlib",
    }
