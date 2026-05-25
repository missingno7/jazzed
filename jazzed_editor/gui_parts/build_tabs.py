from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..raw_data import *

class BuildTabsMixin:
    def _build_tiles_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tiles_tab = tab
        self.tabs.add(tab, text="Tiles")

        form = ttk.Frame(tab)
        form.pack(fill=tk.X)
        ttk.Label(form, text="Selected tile").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(form, from_=0, to=239, textvariable=self.current_tile, width=7).grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="BG flag").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(form, from_=0, to=1, textvariable=self.current_bg, width=7).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(form, text="also paint BG flag in Tiles mode", variable=self.paint_bg).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(form, text="Fast paint updates only the affected 16x16-tile chunk while dragging.").grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        atlas_frame = ttk.LabelFrame(tab, text="Tile Atlas", padding=4)
        atlas_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.atlas_canvas = tk.Canvas(atlas_frame, background="#181818", height=420, highlightthickness=0)
        atlas_scroll = ttk.Scrollbar(atlas_frame, orient=tk.VERTICAL, command=self.atlas_canvas.yview)
        self.atlas_canvas.configure(yscrollcommand=atlas_scroll.set)
        self.atlas_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        atlas_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.atlas_canvas.bind("<Button-1>", self.on_atlas_click)
        self.atlas_canvas.bind("<Configure>", lambda _e: self.render_atlas())

    def _build_objects_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.objects_tab = tab
        self.tabs.add(tab, text="Object Prefabs")
        controls = ttk.Frame(tab)
        controls.pack(fill=tk.X, pady=(6, 4))
        ttk.Checkbutton(controls, text="move selected object on next map click", variable=self.move_object_mode).pack(anchor="w")
        filter_row = ttk.Frame(tab)
        filter_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(filter_row, text="Category").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(filter_row, state="readonly", width=26, textvariable=self.object_category_filter, values=[
            "all", "pickup/powerup", "enemy/hazard", "trampoline/spring", "mechanism/destructible", "trigger/other", "engine marker/collision", "engine marker/foreground", "engine marker/hazard"
        ])
        self.category_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: (self.refresh_object_palette(), self.refresh_objects()))
        self.object_preview_label = ttk.Label(filter_row, text="preview: -")
        self.object_preview_label.pack(side=tk.LEFT, padx=(10, 0))
        self.object_help_text = tk.Text(tab, height=4, wrap="word")
        self.object_help_text.pack(fill=tk.X, pady=(2, 6))
        self.object_help_text.insert("1.0", "")
        self.object_help_text.configure(state="disabled")
        palette_frame = ttk.LabelFrame(tab, text="Palette", padding=4)
        palette_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        palette_toolbar = ttk.Frame(palette_frame)
        palette_toolbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Radiobutton(palette_toolbar, text="Atlas", value="atlas", variable=self.object_palette_view, command=self.refresh_object_palette).pack(side=tk.LEFT)
        ttk.Radiobutton(palette_toolbar, text="List", value="list", variable=self.object_palette_view, command=self.refresh_object_palette).pack(side=tk.LEFT, padx=(8, 0))
        self.palette_tree_frame = ttk.Frame(palette_frame)
        self.palette_tree = ttk.Treeview(self.palette_tree_frame, columns=("cat", "uses", "name"), show="headings", height=8, selectmode="browse")
        for col, width, text in [("cat", 145, "Category"), ("uses", 45, "Uses"), ("name", 190, "Event / Name")]:
            self.palette_tree.heading(col, text=text)
            self.palette_tree.column(col, width=width, stretch=(col == "name"))
        self.palette_tree_frame.pack(fill=tk.BOTH, expand=True)
        self.palette_tree.pack(fill=tk.BOTH, expand=True)
        self.palette_tree.bind("<<TreeviewSelect>>", self.on_palette_tree_select)
        self.palette_atlas_frame = ttk.Frame(palette_frame)
        self.palette_atlas_canvas = tk.Canvas(self.palette_atlas_frame, background="#181818", highlightthickness=0, height=220)
        self.palette_atlas_scroll = ttk.Scrollbar(self.palette_atlas_frame, orient=tk.VERTICAL, command=self.palette_atlas_canvas.yview)
        self.palette_atlas_canvas.configure(yscrollcommand=self.palette_atlas_scroll.set)
        self.palette_atlas_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.palette_atlas_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.palette_atlas_canvas.bind("<Configure>", lambda _e: self.render_object_palette_atlas())
        buttons = ttk.Frame(tab)
        buttons.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(buttons, text="Refresh list", command=self.refresh_objects).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Delete", command=self.delete_selected_object).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(buttons, text="Use selected as brush", command=self.duplicate_selected_object_to_brush).pack(side=tk.LEFT, padx=(6, 0))

        columns = ("event", "name", "x", "y", "tile", "bg")
        self.object_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16, selectmode="browse")
        headings = {"event": "Event", "name": "Name", "x": "X", "y": "Y", "tile": "Tile", "bg": "BG"}
        widths = {"event": 54, "name": 130, "x": 46, "y": 46, "tile": 54, "bg": 40}
        for col in columns:
            self.object_tree.heading(col, text=headings[col])
            self.object_tree.column(col, width=widths[col], stretch=(col == "name"))
        yscroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.object_tree.yview)
        self.object_tree.configure(yscrollcommand=yscroll.set)
        self.object_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.object_tree.bind("<<TreeviewSelect>>", self.on_object_tree_select)

    def _build_object_types_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.object_types_tab = tab
        self.tabs.add(tab, text="Object Types")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_object_types).pack(side=tk.LEFT)
        ttk.Button(row, text="Use as brush", command=self.use_object_type_as_brush).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Highlight type", command=self.highlight_selected_object_type).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Clear highlight", command=lambda: (self.highlight_event_id.set(0), self.render_map())).pack(side=tk.LEFT, padx=(6, 0))
        actions = ttk.LabelFrame(tab, text="Actions", padding=6)
        actions.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Duplicate selected placement into new type", command=self.duplicate_selected_object_definition).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Replace selected placement with current brush", command=self.replace_selected_object_with_brush).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Replace all highlighted/selected type with current brush", command=self.replace_all_selected_type_with_brush).pack(fill=tk.X, pady=2)
        columns = ("event", "uses", "category", "name")
        self.object_types_tree = ttk.Treeview(tab, columns=columns, show="headings", height=12, selectmode="browse")
        for col, width, text in [("event", 54, "Event"), ("uses", 48, "Uses"), ("category", 135, "Category"), ("name", 260, "Readable object type")]:
            self.object_types_tree.heading(col, text=text)
            self.object_types_tree.column(col, width=width, stretch=(col == "name"))
        self.object_types_tree.pack(fill=tk.BOTH, expand=True)
        self.object_types_tree.bind("<<TreeviewSelect>>", self.on_object_type_select)
        self.object_type_detail = tk.Text(tab, height=8, wrap="word")
        self.object_type_detail.pack(fill=tk.BOTH, expand=False, pady=(6, 0))

    def _build_layers_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.layers_tab = tab
        self.tabs.add(tab, text="Layers")
        grid = ttk.Frame(tab)
        grid.pack(fill=tk.X, pady=(8, 0))
        rows = [
            ("Tiles / visual map", self.show_grid, self.lock_tiles, "Grid visible", "Lock tile paint"),
            ("Event labels", self.show_event_labels, self.lock_events, "Labels visible", "Lock raw event paint"),
            ("Object sprites", self.show_object_sprites, self.lock_objects, "Sprites visible", "Lock object move/delete"),
            ("Collision masks", self.show_collision, None, "Collision visible", ""),
            ("Paths", self.show_paths, None, "Paths visible", ""),
            ("Player start", self.show_player_start, self.lock_start, "Start visible", "Lock start"),
            ("Water level", self.show_water_level, None, "Water visible", ""),
            ("Object names", self.show_object_names, None, "Names visible", ""),
            ("Brush preview", self.show_brush_preview, None, "Preview visible", ""),
            ("Fast paint / chunk cache", self.fast_paint, None, "Fast paint enabled", ""),
        ]
        for r, (label, visible, locked, visible_text, locked_text) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Checkbutton(grid, text=visible_text, variable=visible, command=self.render_map).grid(row=r, column=1, sticky="w", padx=(8, 0))
            if locked is not None:
                ttk.Checkbutton(grid, text=locked_text, variable=locked).grid(row=r, column=2, sticky="w", padx=(8, 0))

    def _build_metadata_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.metadata_tab = tab
        self.tabs.add(tab, text="Level / Start")
        grid = ttk.Frame(tab)
        grid.pack(anchor="w", pady=(8, 0))
        self.start_x_var = tk.IntVar(value=0)
        self.start_y_var = tk.IntVar(value=0)
        self.next_level_var = tk.IntVar(value=0)
        self.next_world_var = tk.IntVar(value=0)
        self.water_level_var = tk.IntVar(value=0)
        self.jump_height_raw_var = tk.IntVar(value=0)
        self.anim_speed_var = tk.IntVar(value=0)
        fields = [
            ("Start X tile", self.start_x_var, 0, LW - 1),
            ("Start Y tile", self.start_y_var, 0, LH - 1),
            ("Next level", self.next_level_var, 0, 255),
            ("Next world", self.next_world_var, 0, 255),
            ("Water level raw", self.water_level_var, 0, 65535),
            ("Jump height raw", self.jump_height_raw_var, 0, 65535),
            ("Jazz anim speed", self.anim_speed_var, 0, 255),
        ]
        for r, (label, var, lo, hi) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Spinbox(grid, from_=lo, to=hi, textvariable=var, width=10, command=self.apply_metadata_from_ui).grid(row=r, column=1, sticky="w", padx=(8, 0), pady=2)
        ttk.Button(tab, text="Apply metadata fields", command=self.apply_metadata_from_ui).pack(anchor="w", pady=(8, 0))
        ttk.Button(tab, text="Switch to Start placement mode", command=lambda: (self.tool_mode.set("start"), self.workspace_tabs.select(self.build_workspace), self.build_tabs.select(tab), self.status.set("Start mode: click map to move player spawn."))).pack(anchor="w", pady=(4, 0))

    def _build_globals_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Summary")
        ttk.Label(tab, text="These are LEVEL-LOCAL shared definitions stored inside the currently opened LEVEL file. They are shared by placements in this level, but they are not game-global assets.", wraplength=360).pack(anchor="w")
        ttk.Label(tab, text="A placement in the map only says 'use event ID N'. The behavior, animation references, paths and tile collision masks below are shared tables inside this one level file.", wraplength=360).pack(anchor="w", pady=(4, 8))
        nav = ttk.LabelFrame(tab, text="Jump to level-local editor", padding=6)
        nav.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(nav, text="Event definitions", command=lambda: self.define_tabs.select(self.level_local_event_defs_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(nav, text="Paths", command=lambda: self.define_tabs.select(self.level_local_paths_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(nav, text="Collision masks", command=lambda: self.define_tabs.select(self.level_local_masks_tab)).pack(fill=tk.X, pady=2)
        ttk.Button(nav, text="Animations", command=lambda: self.define_tabs.select(self.level_local_animations_tab)).pack(fill=tk.X, pady=2)
        self.level_local_summary_text = tk.Text(tab, height=14, wrap="word")
        self.level_local_summary_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def refresh_level_local_summary(self) -> None:
        if not hasattr(self, "level_local_summary_text"):
            return
        counts = self.event_usage_counts() if self.level else {}
        used_events = len([k for k, v in counts.items() if k and v])
        nonempty_paths = len([p for p in self.level.path_defs if p.nonempty]) if self.level else 0
        used_anims = set()
        if self.level:
            for ev in self.level.event_catalog()[1:]:
                for idx in [5, 6, 28, 29, 30, 31]:
                    if idx < len(ev.raw) and ev.raw[idx]:
                        used_anims.add(ev.raw[idx] & 0x7F)
        lines = [
            "What is LEVEL-LOCAL in a JJ1 level:",
            "",
            "- Event definitions: shared behavior table for event IDs 0..126.",
            "- Paths: 16 shared movement paths used by some object behaviors.",
            "- Collision masks: 8x8 collision data per tile; every placement of that tile uses the same mask.",
            "- Animations: 128 shared animation definitions; events reference them by ID.",
            "",
            f"Used event IDs in this map: {used_events}",
            f"Non-empty paths: {nonempty_paths}/16",
            f"Animations referenced by event defs: {len(used_anims)}",
            "",
            "Safe workflow: edit placements in BUILD, then edit LEVEL-LOCAL shared definitions here only when you really want every placement/reference in this level to change.",
        ]
        self.level_local_summary_text.configure(state="normal")
        self.level_local_summary_text.delete("1.0", tk.END)
        self.level_local_summary_text.insert("1.0", "\n".join(lines))
        self.level_local_summary_text.configure(state="disabled")

    def _build_masks_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Masks")
        self.level_local_masks_tab = tab
        ttk.Checkbutton(tab, text="Show collision overlay on map", variable=self.show_collision, command=self.render_map).pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 2))
        self.mask_tile_var = tk.IntVar(value=0)
        ttk.Label(row, text="Tile mask").pack(side=tk.LEFT)
        ttk.Spinbox(row, from_=0, to=255, width=6, textvariable=self.mask_tile_var, command=lambda: self.render_mask_info(self.mask_tile_var.get())).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Load selected tile", command=lambda: (self.mask_tile_var.set(self.current_tile.get()), self.render_mask_info(self.current_tile.get()))).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Apply mask", command=self.apply_mask_from_ui).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Clear mask", command=self.clear_current_mask).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Fill mask", command=self.fill_current_mask).pack(side=tk.LEFT, padx=(6, 0))

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        left = ttk.LabelFrame(body, text="Tile atlas", padding=4)
        right = ttk.Frame(body)
        body.add(left, weight=2)
        body.add(right, weight=3)

        self.mask_atlas_canvas = tk.Canvas(left, background="#181818", highlightthickness=0)
        self.mask_atlas_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.mask_atlas_canvas.yview)
        self.mask_atlas_canvas.configure(yscrollcommand=self.mask_atlas_scroll.set)
        self.mask_atlas_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.mask_atlas_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.mask_atlas_canvas.bind("<Configure>", lambda _e: self.render_mask_atlas())

        editor = ttk.LabelFrame(right, text="Tile collision mask", padding=6)
        editor.pack(fill=tk.BOTH, expand=True)
        self.mask_editor_canvas = tk.Canvas(editor, width=384, height=384, background="#111111", highlightthickness=0)
        self.mask_editor_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.mask_editor_canvas.bind("<Button-1>", lambda e: self.paint_mask_cell(e, True))
        self.mask_editor_canvas.bind("<B1-Motion>", lambda e: self.paint_mask_cell(e, True))
        self.mask_editor_canvas.bind("<Button-3>", lambda e: self.paint_mask_cell(e, False))
        self.mask_editor_canvas.bind("<B3-Motion>", lambda e: self.paint_mask_cell(e, False))
        self.mask_editor_canvas.bind("<Configure>", lambda _e: self.render_mask_editor(self.mask_tile_var.get()))




