import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import illustration_render_service


class IllustrationRenderServiceTests(unittest.TestCase):
    def test_renders_png_and_returns_static_url(self):
        code = (
            "import numpy as np\n"
            "import matplotlib.pyplot as plt\n"
            "points = np.array([[0, 0], [1, 1], [4, 4]])\n"
            "fig, ax = plt.subplots()\n"
            "ax.scatter(points[:, 0], points[:, 1])\n"
            "ax.set_title('聚类结果示意图')\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                illustration_render_service,
                "ILLUSTRATION_OUTPUT_DIR",
                Path(temp_dir),
            ):
                result = illustration_render_service.render_python_illustration(code)

            filename = result["image_url"].rsplit("/", 1)[-1]
            output = Path(temp_dir) / filename
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 100)
            self.assertEqual(result["renderer"], "image")
            self.assertEqual(result["mime_type"], "image/png")


if __name__ == "__main__":
    unittest.main()
