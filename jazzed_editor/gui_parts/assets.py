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

class AssetsMixin:
    def _build_game_assets_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_assets_tab = tab
        self.tabs.add(tab, text="Assets")
        ttk.Label(tab, text="Read-only browser of game-global files in the selected Jazz installation. These are outside the current level file.", wraplength=430).pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 4))
        ttk.Button(row, text="Refresh asset list", command=self.refresh_game_assets).pack(side=tk.LEFT)
        self.asset_filter_var = tk.StringVar(value="all")
        ttk.Label(row, text="Filter").pack(side=tk.LEFT, padx=(8, 2))
        combo = ttk.Combobox(row, state="readonly", width=16, textvariable=self.asset_filter_var, values=["all", "levels", "tilesets", "sprites", "music", "sounds", "other"])
        combo.pack(side=tk.LEFT)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_game_assets())
        columns = ("scope", "kind", "file", "note")
        self.game_assets_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("scope", 105, "Scope"), ("kind", 85, "Kind"), ("file", 145, "File"), ("note", 260, "Meaning")]:
            self.game_assets_tree.heading(col, text=title)
            self.game_assets_tree.column(col, width=width, stretch=(col == "note"))
        self.game_assets_tree.pack(fill=tk.BOTH, expand=True)

    def _build_game_tilesets_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_tilesets_tab = tab
        self.tabs.add(tab, text="Tilesets")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_game_tilesets).pack(side=tk.LEFT)
        ttk.Label(row, text="Click a BLOCKS file to preview its tile atlas.").pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        right = ttk.Frame(body)
        body.add(right, weight=3)

        columns = ("file", "used_by", "tiles")
        self.game_tilesets_tree = ttk.Treeview(left, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("file", 110, "Tileset"), ("used_by", 75, "Levels"), ("tiles", 60, "Tiles")]:
            self.game_tilesets_tree.heading(col, text=title)
            self.game_tilesets_tree.column(col, width=width, stretch=(col == "file"))
        self.game_tilesets_tree.pack(fill=tk.BOTH, expand=True)
        self.game_tilesets_tree.bind("<<TreeviewSelect>>", self.on_game_tileset_select)

        self.asset_tileset_canvas = tk.Canvas(right, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.asset_tileset_canvas.yview)
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.asset_tileset_canvas.xview)
        self.asset_tileset_canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.asset_tileset_canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

    def _build_game_sprites_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_sprites_tab = tab
        self.tabs.add(tab, text="Sprites")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_game_sprites).pack(side=tk.LEFT)
        ttk.Label(row, text="Click a SPRITES file to preview a sprite atlas.").pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        right = ttk.Frame(body)
        body.add(right, weight=3)

        columns = ("file", "scope")
        self.game_sprites_tree = ttk.Treeview(left, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("file", 140, "File"), ("scope", 120, "Scope")]:
            self.game_sprites_tree.heading(col, text=title)
            self.game_sprites_tree.column(col, width=width, stretch=(col == "file"))
        self.game_sprites_tree.pack(fill=tk.BOTH, expand=True)
        self.game_sprites_tree.bind("<<TreeviewSelect>>", self.on_game_sprite_select)

        self.asset_sprite_canvas = tk.Canvas(right, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.asset_sprite_canvas.yview)
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.asset_sprite_canvas.xview)
        self.asset_sprite_canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.asset_sprite_canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

    def _build_game_audio_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.game_audio_tab = tab
        self.tabs.add(tab, text="Audio")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="Refresh", command=self.refresh_game_audio).pack(side=tk.LEFT)
        ttk.Button(row, text="Open selected externally", command=self.open_selected_audio_external).pack(side=tk.LEFT, padx=(6, 0))

        panes = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        columns = ("kind", "file", "size")
        self.game_audio_tree = ttk.Treeview(left, columns=columns, show="headings", height=22, selectmode="browse")
        for col, width, title in [("kind", 100, "Kind"), ("file", 220, "File"), ("size", 80, "Bytes")]:
            self.game_audio_tree.heading(col, text=title)
            self.game_audio_tree.column(col, width=width, stretch=(col == "file"))
        self.game_audio_tree.pack(fill=tk.BOTH, expand=True)
        self.game_audio_tree.bind("<<TreeviewSelect>>", self.on_game_audio_select)

        self.game_audio_detail = ttk.Frame(right, padding=(8, 0, 0, 0))
        self.game_audio_detail.pack(fill=tk.BOTH, expand=True)

    def _make_image_atlas(self, images: List[Image.Image], cell: int = 40, columns: int = 12, label_prefix: str = "") -> Image.Image:
        rows = max(1, (len(images) + columns - 1) // columns)
        atlas = Image.new("RGBA", (columns * cell, rows * (cell + 12)), (24, 24, 24, 255))
        draw = ImageDraw.Draw(atlas)
        for i, img in enumerate(images):
            x = (i % columns) * cell
            y = (i // columns) * (cell + 12)
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(70, 70, 70, 255))
            if img is not None:
                thumb = img.copy().convert("RGBA")
                thumb.thumbnail((cell - 4, cell - 4), Image.Resampling.NEAREST)
                atlas.alpha_composite(thumb, (x + (cell - thumb.width)//2, y + (cell - thumb.height)//2))
            draw.text((x + 2, y + cell), f"{label_prefix}{i}", fill=(230, 230, 230, 255))
        return atlas

    def on_game_tileset_select(self, _event: tk.Event) -> None:
        if not hasattr(self, "game_tilesets_tree"):
            return
        sel = self.game_tilesets_tree.selection()
        if not sel:
            return
        name = sel[0]
        try:
            ts = self.parser.parse_tileset(self.parser.find_file(name))
            self.render_asset_tileset_atlas(ts)
        except Exception as exc:
            messagebox.showerror("Tileset preview failed", str(exc))

    def render_asset_tileset_atlas(self, tileset: TilesetData) -> None:
        if not hasattr(self, "asset_tileset_canvas"):
            return
        scale = 2
        columns = max(1, (self.asset_tileset_canvas.winfo_width() or 800) // (TILE_SIZE * scale))
        rows = max(1, (len(tileset.tiles) + columns - 1) // columns)
        img = Image.new("RGBA", (columns * TILE_SIZE * scale, rows * (TILE_SIZE * scale + 14)), (24, 24, 24, 255))
        draw = ImageDraw.Draw(img)
        for i, tile in enumerate(tileset.tiles):
            x = (i % columns) * TILE_SIZE * scale
            y = (i // columns) * (TILE_SIZE * scale + 14)
            tile_img = tile.resize((TILE_SIZE * scale, TILE_SIZE * scale), Image.Resampling.NEAREST)
            img.alpha_composite(tile_img, (x, y))
            draw.rectangle((x, y, x + TILE_SIZE * scale - 1, y + TILE_SIZE * scale - 1), outline=(70, 70, 70, 255))
            draw.text((x + 2, y + TILE_SIZE * scale), str(i), fill=(230, 230, 230, 255))
        self._asset_photo_refs = [ImageTk.PhotoImage(img)]
        self.asset_tileset_canvas.delete("all")
        self.asset_tileset_canvas.create_image(0, 0, image=self._asset_photo_refs[0], anchor="nw")
        self.asset_tileset_canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def on_game_sprite_select(self, _event: tk.Event) -> None:
        if not hasattr(self, "game_sprites_tree"):
            return
        sel = self.game_sprites_tree.selection()
        if not sel:
            return
        name = sel[0]
        try:
            path = self.parser.find_file(name)
            main = self.parser.find_file("MAINCHAR.000")
            palette = self.tileset.palette if self.tileset else self.parser.parse_tileset(next(iter(sorted(self.parser.game_dir.glob("BLOCKS.*"))))).palette
            if name.upper().startswith("MAINCHAR"):
                # MAINCHAR alone does not have the SPRITES offset table. Show via current level/world if available.
                if self.level:
                    sprites = self.parser.load_sprites_for_level(self.level, palette)
                else:
                    messagebox.showinfo("MAINCHAR", "MAINCHAR.000 needs a SPRITES.xxx offset table. Select a SPRITES file or open a level first.")
                    return
            else:
                sprites = self.parser.parse_sprites(path, main, palette)
            if sprites:
                self.render_asset_sprite_atlas(sprites)
        except Exception as exc:
            messagebox.showerror("Sprite preview failed", str(exc))

    def render_asset_sprite_atlas(self, sprites: SpriteSetData) -> None:
        if not hasattr(self, "asset_sprite_canvas"):
            return
        images = [s.image for s in sprites.sprites if s.image.width > 1 or s.image.height > 1]
        # Keep indices aligned by using the original list; empty frames remain boxes.
        images = [s.image for s in sprites.sprites[:256]]
        img = self._make_image_atlas(images, cell=48, columns=max(1, (self.asset_sprite_canvas.winfo_width() or 900)//48), label_prefix="")
        self._asset_photo_refs = [ImageTk.PhotoImage(img)]
        self.asset_sprite_canvas.delete("all")
        self.asset_sprite_canvas.create_image(0, 0, image=self._asset_photo_refs[0], anchor="nw")
        self.asset_sprite_canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def refresh_game_audio(self) -> None:
        if not hasattr(self, "game_audio_tree"):
            return
        self.game_audio_tree.delete(*self.game_audio_tree.get_children(""))
        exts = {".PSM": "music", ".S3M": "music", ".MOD": "music", ".WAV": "sound", ".VOC": "sound", ".SND": "sound"}
        for p in sorted([p for p in self.parser.game_dir.iterdir() if p.is_file()], key=lambda p: p.name.upper()):
            kind = exts.get(p.suffix.upper())
            if kind or "SOUND" in p.name.upper() or "MUSIC" in p.name.upper():
                self.game_audio_tree.insert("", "end", iid=p.name, values=(kind or "resource", p.name, p.stat().st_size))
        self.render_audio_detail(None)

    def on_game_audio_select(self, _event: tk.Event = None) -> None:
        if not hasattr(self, "game_audio_tree"):
            return
        sel = self.game_audio_tree.selection()
        self.render_audio_detail(sel[0] if sel else None)

    def render_audio_detail(self, name: Optional[str]) -> None:
        if not hasattr(self, "game_audio_detail"):
            return
        for child in self.game_audio_detail.winfo_children():
            child.destroy()
        if not name:
            ttk.Label(self.game_audio_detail, text="Select an audio asset.").pack(anchor="w")
            return
        path = self.parser.game_dir / name
        ttk.Label(self.game_audio_detail, text=name, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(self.game_audio_detail, text=f"{path.stat().st_size} bytes").pack(anchor="w", pady=(0, 8))
        upper = name.upper()
        if upper == "SOUNDS.000":
            self.render_sound_archive_detail(path)
        elif path.suffix.upper() == ".PSM":
            self.render_music_asset_detail(path)
        else:
            ttk.Label(self.game_audio_detail, text="No native decoder for this file type yet.").pack(anchor="w", pady=(0, 8))
            ttk.Button(self.game_audio_detail, text="Open externally", command=self.open_selected_audio_external).pack(anchor="w")

    def render_sound_archive_detail(self, path: Path) -> None:
        try:
            archive = parse_sound_archive(path)
        except Exception as exc:
            ttk.Label(self.game_audio_detail, text=f"Could not parse sound archive: {exc}").pack(anchor="w")
            return
        controls = ttk.Frame(self.game_audio_detail)
        controls.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(controls, text="Play selected", command=lambda: play_selected()).pack(side=tk.LEFT)
        ttk.Label(controls, text="Signed 8-bit mono PCM clips").pack(side=tk.LEFT, padx=(8, 0))
        columns = ("index", "name", "length", "offset")
        tree = ttk.Treeview(self.game_audio_detail, columns=columns, show="headings", height=18, selectmode="browse")
        for col, width, title in [("index", 56, "Index"), ("name", 150, "Name"), ("length", 80, "Bytes"), ("offset", 80, "Offset")]:
            tree.heading(col, text=title)
            tree.column(col, width=width, stretch=(col == "name"))
        tree.pack(fill=tk.BOTH, expand=True)
        for i, sound in enumerate(archive.sounds):
            tree.insert("", "end", iid=str(i), values=(i, sound.name, sound.length, sound.offset))

        def play_selected() -> None:
            selection = tree.selection()
            if not selection:
                return
            idx = int(selection[0])
            if 0 <= idx < len(archive.sounds):
                self.play_raw_sound(archive.sounds[idx], 11025)

        tree.bind("<Double-1>", lambda _e: play_selected())
        if archive.sounds:
            tree.selection_set("0")

    def render_music_asset_detail(self, path: Path) -> None:
        ttk.Label(self.game_audio_detail, text="PSM music is a tracker/module format.").pack(anchor="w")
        ttk.Label(
            self.game_audio_detail,
            text="OpenJazz plays it through libxmp. Direct MIDI export is lossy/non-trivial because modules contain samples, patterns, and tracker effects.",
            wraplength=420,
        ).pack(anchor="w", pady=(4, 8))
        row = ttk.Frame(self.game_audio_detail)
        row.pack(fill=tk.X)
        ttk.Button(row, text="Open externally", command=self.open_selected_audio_external).pack(side=tk.LEFT)
        ttk.Button(row, text="Play externally", command=self.open_selected_audio_external).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(
            self.game_audio_detail,
            text="Native playback can be added with a libxmp/OpenMPT backend when that dependency is available.",
            wraplength=420,
        ).pack(anchor="w", pady=(8, 0))

    def play_selected_audio_asset(self) -> None:
        if not hasattr(self, "game_audio_tree"):
            return
        sel = self.game_audio_tree.selection()
        if not sel:
            return
        name = sel[0]
        path = self.parser.game_dir / name
        if name.upper() == "SOUNDS.000":
            try:
                archive = parse_sound_archive(path)
            except Exception as exc:
                messagebox.showerror("Sound archive failed", str(exc))
                return
            self.open_sound_archive_browser(archive)
            return
        self.status.set(f"{name} is not a decoded SFX archive yet; opening externally.")
        self.open_selected_audio_external()

    def open_sound_archive_browser(self, archive: SoundArchive) -> None:
        win = tk.Toplevel(self)
        win.title(f"Sound clips - {archive.path.name}")
        win.geometry("620x520")
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(frame)
        top.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(top, text="Play selected", command=lambda: play_selected()).pack(side=tk.LEFT)
        ttk.Label(top, text="Raw JJ1 clips are signed 8-bit mono PCM, played as WAV.").pack(side=tk.LEFT, padx=(8, 0))
        columns = ("index", "name", "length", "offset")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20, selectmode="browse")
        for col, width, title in [("index", 60, "Index"), ("name", 180, "Name"), ("length", 90, "Bytes"), ("offset", 90, "Offset")]:
            tree.heading(col, text=title)
            tree.column(col, width=width, stretch=(col == "name"))
        tree.pack(fill=tk.BOTH, expand=True)
        for i, sound in enumerate(archive.sounds):
            tree.insert("", "end", iid=str(i), values=(i, sound.name, sound.length, sound.offset))

        def play_selected() -> None:
            selection = tree.selection()
            if not selection:
                return
            idx = int(selection[0])
            if 0 <= idx < len(archive.sounds):
                self.play_raw_sound(archive.sounds[idx], 11025)

        tree.bind("<Double-1>", lambda _e: play_selected())
        if archive.sounds:
            tree.selection_set("0")

    def open_selected_audio_external(self) -> None:
        if not hasattr(self, "game_audio_tree"):
            return
        sel = self.game_audio_tree.selection()
        if not sel:
            return
        path = self.parser.game_dir / sel[0]
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    def _classify_game_asset(self, path: Path) -> Tuple[str, str, str]:
        name = path.name.upper()
        if name.startswith("LEVEL"):
            return "Level file", "levels", "Contains level placement + level-local definitions"
        if name.startswith("BLOCKS."):
            return "Tileset", "tilesets", "External tiles/palette asset referenced by levels"
        if name.startswith("SPRITES."):
            return "Sprites", "sprites", "External world sprite asset referenced by level-local animations"
        if name == "MAINCHAR.000":
            return "Sprites", "sprites", "Main character/shared sprite asset"
        if name.endswith(".PSM"):
            return "Music", "music", "External music module referenced by levels"
        if name.startswith("SOUNDS") or name.endswith(".SND"):
            return "Sounds", "sounds", "External/global audio resource"
        return "Other", "other", "Game installation file"

    def refresh_game_global_tabs(self) -> None:
        self.refresh_game_assets()
        self.refresh_game_tilesets()
        self.refresh_game_sprites()
        self.refresh_game_audio()

    def refresh_game_assets(self) -> None:
        if not hasattr(self, "game_assets_tree"):
            return
        self.game_assets_tree.delete(*self.game_assets_tree.get_children(""))
        filt = self.asset_filter_var.get() if hasattr(self, "asset_filter_var") else "all"
        try:
            files = sorted([p for p in self.parser.game_dir.iterdir() if p.is_file()], key=lambda p: p.name.upper())
        except Exception:
            files = []
        for p in files:
            kind, group, note = self._classify_game_asset(p)
            if filt != "all" and filt != group:
                continue
            scope = "LEVEL LOCAL" if group == "levels" else "GAME GLOBAL"
            self.game_assets_tree.insert("", "end", values=(scope, kind, p.name, note))

    def refresh_game_tilesets(self) -> None:
        if not hasattr(self, "game_tilesets_tree"):
            return
        self.game_tilesets_tree.delete(*self.game_tilesets_tree.get_children(""))
        usage = {}
        for lp in self.level_paths:
            try:
                level = self.parser.parse_level(lp)
                ext = f"{level.world_num:03d}" if level.blocks_ext == "999" else level.blocks_ext.zfill(3)
                usage[ext] = usage.get(ext, 0) + 1
            except Exception:
                continue
        for p in sorted(self.parser.game_dir.glob("BLOCKS.*"), key=lambda p: p.name.upper()):
            ext = p.suffix[1:].upper()
            tile_count = "?"
            try:
                ts = self.parser.parse_tileset(p)
                tile_count = str(len(ts.tiles))
            except Exception:
                pass
            note = "Referenced externally by levels. Editing it is game-global for all levels using this BLOCKS file."
            self.game_tilesets_tree.insert("", "end", iid=p.name, values=(p.name, usage.get(ext, 0), tile_count))

    def refresh_game_sprites(self) -> None:
        if not hasattr(self, "game_sprites_tree"):
            return
        self.game_sprites_tree.delete(*self.game_sprites_tree.get_children(""))
        rows = []
        for p in sorted(self.parser.game_dir.glob("MAINCHAR.*"), key=lambda p: p.name.upper()):
            rows.append((p.name, "shared/main"))
        for p in sorted(self.parser.game_dir.glob("SPRITES.*"), key=lambda p: p.name.upper()):
            rows.append((p.name, "world/episode"))
        for row in rows:
            self.game_sprites_tree.insert("", "end", iid=row[0], values=row)
