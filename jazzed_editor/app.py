from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from .gui import LevelEditorApp


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone Jazz Jackrabbit 1 DOS GUI level editor")
    parser.add_argument("game_dir", nargs="?", default="game_data", help="Directory containing Jazz Jackrabbit DOS files")
    args = parser.parse_args(argv)
    app = LevelEditorApp(Path(args.game_dir).expanduser().resolve())
    app.mainloop()
    return 0

