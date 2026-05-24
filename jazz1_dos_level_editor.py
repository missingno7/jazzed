#!/usr/bin/env python3
"""Compatibility launcher for the Jazz Jackrabbit 1 DOS level editor."""
from __future__ import annotations

from jazzed_editor.app import main
from jazzed_editor.gui import LevelEditorApp
from jazzed_editor.raw_data import *


if __name__ == "__main__":
    raise SystemExit(main())
