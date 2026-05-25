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

from .raw_data import *
from .raw.event_semantics import _first_modifier_for_pickup
from .raw.sprites import _signed_byte
from .gui_parts.assets import AssetsMixin
from .gui_parts.build_tabs import BuildTabsMixin
from .gui_parts.editing import EditingMixin
from .gui_parts.event_defs import EventDefsMixin
from .gui_parts.level_io import LevelIoMixin
from .gui_parts.level_local import LevelLocalMixin
from .gui_parts.objects import ObjectsMixin
from .gui_parts.overview import OverviewMixin
from .gui_parts.rendering import RenderingMixin
from .gui_parts.sounds import SoundsMixin

class LevelEditorApp(
    OverviewMixin,
    AssetsMixin,
    BuildTabsMixin,
    EventDefsMixin,
    LevelLocalMixin,
    LevelIoMixin,
    ObjectsMixin,
    RenderingMixin,
    SoundsMixin,
    EditingMixin,
    tk.Tk,
):
    def __init__(self, game_dir: Path):
        super().__init__()
        self.title("Jazz Jackrabbit 1 DOS Data Level Editor v24")
        self.geometry("1420x880")
        self.minsize(1100, 700)

        self.parser = JJ1Parser(game_dir)
        self.level: Optional[LevelData] = None
        self.tileset: Optional[TilesetData] = None
        self.spriteset: Optional[SpriteSetData] = None
        self.level_paths: List[Path] = []

        self.tool_mode = tk.StringVar(value="tiles")
        self.current_tile = tk.IntVar(value=0)
        self.current_event = tk.IntVar(value=0)
        self.current_bg = tk.IntVar(value=0)
        self.paint_bg = tk.BooleanVar(value=False)
        self.zoom = tk.IntVar(value=1)
        self.show_grid = tk.BooleanVar(value=True)
        self.show_events = tk.BooleanVar(value=True)
        self.show_bg_overlay = tk.BooleanVar(value=False)
        self.show_collision = tk.BooleanVar(value=False)
        self.show_player_start = tk.BooleanVar(value=True)
        self.show_object_sprites = tk.BooleanVar(value=True)
        self.show_event_labels = tk.BooleanVar(value=True)
        self.show_paths = tk.BooleanVar(value=False)
        self.show_object_names = tk.BooleanVar(value=False)
        self.show_water_level = tk.BooleanVar(value=True)
        self.fast_paint = tk.BooleanVar(value=True)
        self.show_brush_preview = tk.BooleanVar(value=True)
        self.lock_tiles = tk.BooleanVar(value=False)
        self.lock_events = tk.BooleanVar(value=False)
        self.lock_objects = tk.BooleanVar(value=False)
        self.lock_start = tk.BooleanVar(value=False)
        self.highlight_event_id = tk.IntVar(value=0)
        self.save_event_defs_var = tk.BooleanVar(value=False)
        self.save_paths_var = tk.BooleanVar(value=False)
        self.save_masks_var = tk.BooleanVar(value=False)
        self.object_category_filter = tk.StringVar(value="all")
        self.object_palette_view = tk.StringVar(value="atlas")
        self.selected_path = tk.IntVar(value=0)
        self._editing_event_id = 0
        self.status = tk.StringVar(value="Open a Jazz Jackrabbit DOS directory or choose a level.")

        self.selected_object: Optional[Tuple[int, int]] = None
        self.move_object_mode = tk.BooleanVar(value=False)
        self.undo_stack: List[Tuple[bytes, Tuple[int, int, int, int, int, int, int]]] = []
        self.redo_stack: List[Tuple[bytes, Tuple[int, int, int, int, int, int, int]]] = []
        self.max_undo = 80

        self._map_photo: Optional[ImageTk.PhotoImage] = None
        self._atlas_photo: Optional[ImageTk.PhotoImage] = None
        self._object_icon_photos: Dict[int, ImageTk.PhotoImage] = {}
        self._sprite_photo_refs: List[ImageTk.PhotoImage] = []
        self._event_preview_cache: Dict[Tuple[int, int], Optional[Image.Image]] = {}
        self._rendered_map: Optional[Image.Image] = None
        self._last_painted_cell: Optional[Tuple[int, int]] = None
        self._paint_stroke_active = False
        self._stroke_cells: set[Tuple[int, int]] = set()
        self._dirty_chunks: set[Tuple[int, int]] = set()
        self._chunk_photos: Dict[Tuple[int, int], ImageTk.PhotoImage] = {}
        self._chunk_items: Dict[Tuple[int, int], int] = {}
        self._collision_tile_cache: Dict[Tuple[int, bytes, int], Image.Image] = {}
        self._collision_chunk_cache: Dict[Tuple[int, int, int], Tuple[Tuple[Any, ...], ImageTk.PhotoImage]] = {}
        self._brush_preview_items: List[int] = []
        self._brush_preview_photos: List[ImageTk.PhotoImage] = []
        self._asset_photo_refs: List[ImageTk.PhotoImage] = []
        self._sound_archive = None
        self._sound_archive_loaded = False
        self._last_played_sound_path = None
        self.dirty = False
        self.current_save_path: Optional[Path] = None

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()
        self._load_level_list()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=6)
        root.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(root)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Open game dir", command=self.open_game_dir).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Reload", command=self.reload_current).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Save", command=self.save).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Save as...", command=self.save_as).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(toolbar, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Redo", command=self.redo).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(toolbar, text="Validate", command=self.refresh_validation).pack(side=tk.LEFT, padx=(6, 0))
        self.bind_all("<Control-s>", lambda _e: self.save())
        self.bind_all("<Control-z>", lambda _e: self.undo())
        self.bind_all("<Control-y>", lambda _e: self.redo())
        self.bind_all("<Control-Shift-Z>", lambda _e: self.redo())
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Label(toolbar, text="Level:").pack(side=tk.LEFT)
        self.level_combo = ttk.Combobox(toolbar, state="readonly", width=24)
        self.level_combo.pack(side=tk.LEFT, padx=(4, 8))
        self.level_combo.bind("<<ComboboxSelected>>", lambda _e: self.request_load_selected_level())
        ttk.Label(toolbar, text="Zoom:").pack(side=tk.LEFT)
        ttk.Spinbox(toolbar, from_=1, to=4, textvariable=self.zoom, width=4, command=self.render_map).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Checkbutton(toolbar, text="Grid", variable=self.show_grid, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Events", variable=self.show_events, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="BG overlay", variable=self.show_bg_overlay, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Collision", variable=self.show_collision, command=self.render_map_and_atlas).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Player start", variable=self.show_player_start, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Object sprites", variable=self.show_object_sprites, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Event labels", variable=self.show_event_labels, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Paths", variable=self.show_paths, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Names", variable=self.show_object_names, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Water", variable=self.show_water_level, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Fast paint", variable=self.fast_paint, command=self.render_map).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="Brush preview", variable=self.show_brush_preview).pack(side=tk.LEFT)

        modebar = ttk.LabelFrame(root, text="Editing mode", padding=6)
        modebar.pack(fill=tk.X, pady=(6, 0))
        for value, text in [
            ("tiles", "Tiles: edit visual tile/BG only"),
            ("events", "Events: edit numeric event ID only"),
            ("objects", "Objects: select/move/delete placed events"),
            ("start", "Start: place player start only"),
            ("inspect", "Inspect: no editing"),
        ]:
            ttk.Radiobutton(modebar, text=text, value=value, variable=self.tool_mode, command=self._mode_changed).pack(side=tk.LEFT, padx=(0, 12))

        self.main_tabs = ttk.Notebook(root)
        self.main_tabs.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.level_editor_page = ttk.Frame(self.main_tabs)
        self.assets_browser_page = ttk.Frame(self.main_tabs)
        self.main_tabs.add(self.level_editor_page, text="Level Editor")
        self.main_tabs.add(self.assets_browser_page, text="Assets Browser")

        panes = ttk.PanedWindow(self.level_editor_page, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes)
        panes.add(left, weight=5)
        right = ttk.Frame(panes)
        panes.add(right, weight=2)

        self.canvas = tk.Canvas(left, background="#202020", highlightthickness=0)
        hbar = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=self.canvas.xview)
        vbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.erase_from_map)
        self.canvas.bind("<Shift-Button-3>", self.pick_from_map)
        self.canvas.bind("<Button-2>", self.pick_from_map)
        self.canvas.bind("<Motion>", self.on_canvas_motion)

        self.workspace_tabs = ttk.Notebook(right)
        self.workspace_tabs.pack(fill=tk.BOTH, expand=True)

        self.build_workspace = ttk.Frame(self.workspace_tabs)
        self.define_workspace = ttk.Frame(self.workspace_tabs)
        self.workspace_tabs.add(self.build_workspace, text="BUILD")
        self.workspace_tabs.add(self.define_workspace, text="LEVEL LOCAL")

        self.build_tabs = ttk.Notebook(self.build_workspace)
        self.build_tabs.pack(fill=tk.BOTH, expand=True)
        self.define_tabs = ttk.Notebook(self.define_workspace)
        self.define_tabs.pack(fill=tk.BOTH, expand=True)
        self.event_defs_tabs = self.define_tabs

        self.tabs = self.build_tabs
        self._build_objects_tab()
        self._build_tiles_tab()
        self._build_metadata_tab()
        self._build_layers_tab()

        self.tabs = self.define_tabs
        self._build_event_defs_tab()
        self._build_animations_tab()
        self._build_bullets_tab()
        self._build_paths_tab()
        self._build_masks_tab()
        self._build_validation_tab()

        self.game_tabs = ttk.Notebook(self.assets_browser_page)
        self.game_tabs.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.tabs = self.game_tabs
        self._build_game_assets_tab()
        self._build_game_tilesets_tab()
        self._build_game_sprites_tab()
        self._build_game_audio_tab()

        self.tabs = self.define_tabs

        bottom_info = ttk.Frame(root)
        bottom_info.pack(fill=tk.X, pady=(6, 0))
        self.cell_label = ttk.Label(bottom_info, text="Cell: -", relief=tk.SUNKEN, anchor="w")
        self.cell_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.object_label = ttk.Label(bottom_info, text="Object: none", relief=tk.SUNKEN, anchor="w")
        self.object_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Button(bottom_info, text="Edit type", command=self.jump_to_selected_object_type).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(bottom_info, text="Duplicate type", command=self.duplicate_selected_object_definition).pack(side=tk.LEFT, padx=(4, 0))

        statusbar = ttk.Label(root, textvariable=self.status, relief=tk.SUNKEN, anchor="w")
        statusbar.pack(fill=tk.X, pady=(3, 0))











































        # Reserved markers are numeric IDs, not a cloneable raw template.



















































































































