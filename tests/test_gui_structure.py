from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GuiStructureTests(unittest.TestCase):
    def test_gui_shell_stays_small_enough_to_scan(self) -> None:
        gui = PROJECT_ROOT / "jazzed_editor" / "gui.py"
        line_count = len(gui.read_text(encoding="utf-8").splitlines())
        self.assertLess(line_count, 700)

    def test_expected_gui_part_modules_exist(self) -> None:
        gui_parts = PROJECT_ROOT / "jazzed_editor" / "gui_parts"
        expected = {
            "assets.py",
            "build_tabs.py",
            "editing.py",
            "event_defs.py",
            "level_io.py",
            "level_local.py",
            "objects.py",
            "overview.py",
            "rendering.py",
        }
        self.assertTrue(gui_parts.is_dir())
        self.assertTrue(expected.issubset({p.name for p in gui_parts.glob("*.py")}))


if __name__ == "__main__":
    unittest.main()
