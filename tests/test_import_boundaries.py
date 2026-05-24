import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "jazzed_editor" / "raw"


class ImportBoundaryTests(unittest.TestCase):
    def test_raw_layer_does_not_import_tkinter(self) -> None:
        for path in RAW_DIR.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                self.assertNotIn("tkinter", names, f"{path} should not import tkinter")


if __name__ == "__main__":
    unittest.main()
