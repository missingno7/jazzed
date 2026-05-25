from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with: python -m pip install pillow") from exc

from ..raw_data import *
from ..raw.event_semantics import _first_modifier_for_pickup
from ..raw.sprites import _signed_byte

class OverviewMixin:
    def _build_build_overview_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Build")
        ttk.Label(
            tab,
            text="BUILD is the normal WYSIWYG level-design workspace. Use object prefabs/types from this level, place them on the map, move them, delete them, and keep raw definitions out of the way.",
            wraplength=420,
        ).pack(anchor="w")
        flow = ttk.LabelFrame(tab, text="Recommended workflow", padding=6)
        flow.pack(fill=tk.X, pady=(8, 8))
        for line in [
            "1. Pick an object type from Objects palette.",
            "2. Paint or move it in Objects mode; right-click erases events/blocks.",
            "3. Use Tiles mode only for visual blocks/BG.",
            "4. Use Layers to show sprites, names, collision, paths and water.",
            "5. When behavior must change, jump to DEFINE or duplicate the type first.",
        ]:
            ttk.Label(flow, text=line).pack(anchor="w")
        actions = ttk.LabelFrame(tab, text="Build shortcuts", padding=6)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Open object prefab palette", command=lambda: self.build_tabs.select(self.objects_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Open tile palette", command=lambda: self.build_tabs.select(self.tiles_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Open layer controls", command=lambda: self.build_tabs.select(self.layers_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Switch to LEVEL LOCAL", command=lambda: self.workspace_tabs.select(self.define_workspace)).pack(fill=tk.X, pady=(8, 2))

    def _build_define_overview_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Define")
        ttk.Label(
            tab,
            text="LEVEL LOCAL edits definitions stored inside the currently opened level file. These are not game-global hardcoded objects: changing Event 12 changes every Event 12 placement only in this level file.",
            wraplength=420,
        ).pack(anchor="w")
        flow = ttk.LabelFrame(tab, text="Safe authoring workflow", padding=6)
        flow.pack(fill=tk.X, pady=(8, 8))
        for line in [
            "• To change one placed object: select it in BUILD, then duplicate its type.",
            "• To change all objects of a type: edit the shared Event Definition here.",
            "• Event definitions, animations, paths and masks here are level-local shared definitions.",
            "• Advanced tables are saved only when their save checkbox is enabled.",
        ]:
            ttk.Label(flow, text=line).pack(anchor="w")
        actions = ttk.LabelFrame(tab, text="Definition shortcuts", padding=6)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Object Types", command=lambda: self.define_tabs.select(self.object_types_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Event Definitions", command=lambda: self.define_tabs.select(self.global_event_defs_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Animations", command=lambda: self.define_tabs.select(self.global_animations_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Paths", command=lambda: self.define_tabs.select(self.global_paths_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Game Globals", command=lambda: self.workspace_tabs.select(self.game_globals_workspace)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Back to BUILD", command=lambda: self.workspace_tabs.select(self.build_workspace)).pack(fill=tk.X, pady=(8, 2))

    def jump_to_selected_object_type(self) -> None:
        if not self.level:
            return
        event_id = self.current_event.get()
        if self.selected_object is not None:
            event_id = self.selected_object[0] if isinstance(self.selected_object, int) else self.level.grid[self.selected_object[1]][self.selected_object[0]]["event"]
        self.workspace_tabs.select(self.define_workspace)
        if hasattr(self, "define_tabs") and hasattr(self, "event_defs_tab"):
            self.define_tabs.select(self.event_defs_tab)
        if hasattr(self, "event_defs_inner_tabs") and hasattr(self, "event_concept_tab"):
            self.event_defs_inner_tabs.select(self.event_concept_tab)
        self.highlight_event_id.set(event_id)
        self.current_event.set(event_id)
        self.refresh_event_def_selector()
        self.select_event_definition(event_id)
        self.status.set(f"Editing Event {event_id:03d}.")

    def _build_game_globals_overview_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Game Globals")
        ttk.Label(
            tab,
            text="GAME GLOBALS are files/assets from the Jazz installation that are shared by many levels or by the whole game. They are not stored inside the current LEVEL file.",
            wraplength=440,
        ).pack(anchor="w")
        table = ttk.LabelFrame(tab, text="Where things live", padding=6)
        table.pack(fill=tk.X, pady=(8, 8))
        rows = [
            ("LEVEL PLACEMENT", "current LEVEL file", "tile ID, BG flag, event ID placed at x/y"),
            ("LEVEL LOCAL DEFINITIONS", "current LEVEL file", "event definitions, level animations, paths, tile collision masks, start/next/water metadata"),
            ("GAME GLOBAL ASSETS", "separate game files", "BLOCKS.xxx tilesets/palettes, SPRITES.xxx, MAINCHAR.000, PSM music, sounds/cutscenes/resource files"),
            ("ENGINE GLOBAL BEHAVIOR", "Jazz 1 DOS engine / OpenJazz reference code", "meaning of movement values, physics, pickup/enemy behavior, rendering rules"),
        ]
        for r, (scope, where, examples) in enumerate(rows):
            ttk.Label(table, text=scope, font=("", 9, "bold")).grid(row=r, column=0, sticky="nw", padx=(0, 8), pady=3)
            ttk.Label(table, text=where).grid(row=r, column=1, sticky="nw", padx=(0, 8), pady=3)
            ttk.Label(table, text=examples, wraplength=250).grid(row=r, column=2, sticky="nw", pady=3)
        actions = ttk.LabelFrame(tab, text="Game-global browsers", padding=6)
        actions.pack(fill=tk.X, pady=(4, 8))
        ttk.Button(actions, text="Refresh all game-global tabs", command=self.refresh_game_global_tabs).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Game files / assets", command=lambda: self.game_tabs.select(self.game_assets_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Tilesets / BLOCKS.xxx", command=lambda: self.game_tabs.select(self.game_tilesets_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Sprites / MAINCHAR + SPRITES.xxx", command=lambda: self.game_tabs.select(self.game_sprites_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Back to BUILD", command=lambda: self.workspace_tabs.select(self.build_workspace)).pack(fill=tk.X, pady=(8, 2))
        note = tk.Text(tab, height=10, wrap="word")
        note.pack(fill=tk.BOTH, expand=True)
        note.insert("1.0", "\n".join([
            "Practical rule:",
            "",
            "• If changing it should affect only the opened level, it belongs in LEVEL LOCAL.",
            "• If changing it would affect many levels or the game installation, it belongs in GAME GLOBALS.",
            "• If it is hardcoded in Jazz 1 DOS engine behavior / OpenJazz reference behavior, it is ENGINE GLOBAL and should be documented/read-only unless the editor later supports code patches.",
        ]))
        note.configure(state="disabled")
