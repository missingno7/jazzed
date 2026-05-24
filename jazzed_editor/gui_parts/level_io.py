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

class LevelIoMixin:
    def _build_validation_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Validation")
        ttk.Label(tab, text="Checks common mistakes before testing in OpenJazz: missing sprites, suspicious event definitions, bad start position, missing next level, invalid tiles.").pack(anchor="w")
        ttk.Button(tab, text="Run validation", command=self.refresh_validation).pack(anchor="w", pady=(6, 4))
        columns = ("severity", "where", "message")
        self.validation_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16)
        for col, width, text in [("severity", 75, "Severity"), ("where", 105, "Where"), ("message", 350, "Message")]:
            self.validation_tree.heading(col, text=text)
            self.validation_tree.column(col, width=width, stretch=(col == "message"))
        self.validation_tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.validation_text = tk.Text(tab, height=7, wrap="word")
        self.validation_text.pack(fill=tk.BOTH, expand=False, pady=(6, 0))

    def _load_level_list(self) -> None:
        try:
            files = self.parser.level_files()
        except Exception as exc:
            messagebox.showerror("OpenJazz Level Editor", str(exc))
            return
        self.level_paths = files
        self.level_combo["values"] = [p.name for p in files]
        if files:
            self.level_combo.current(0)
            self.load_selected_level()

    def set_dirty(self, dirty: bool = True) -> None:
        self.dirty = bool(dirty)
        if self.level:
            mark = "*" if self.dirty else ""
            save_path = self.current_save_path.name if self.current_save_path else self.level.path.name
            self.title(f"Jazz Jackrabbit 1 DOS Data Level Editor v24{mark} - {save_path}")
        else:
            self.title("Jazz Jackrabbit 1 DOS Data Level Editor v24")

    def maybe_save_changes(self, action: str = "continue") -> bool:
        if not self.dirty or not self.level:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            f"{self.level.path.name} has unsaved changes.\n\nSave before {action}?"
        )
        if answer is None:
            return False
        if answer:
            return self.save()
        return True

    def on_close(self) -> None:
        if self.maybe_save_changes("closing"):
            self.destroy()

    def open_game_dir(self) -> None:
        if not self.maybe_save_changes("opening another game directory"):
            return
        selected = filedialog.askdirectory(title="Select Jazz Jackrabbit DOS game directory")
        if not selected:
            return
        self.parser = JJ1Parser(Path(selected))
        self._load_level_list()

    def request_load_selected_level(self) -> None:
        if self.maybe_save_changes("loading another level"):
            self.load_selected_level()
        else:
            if self.level and self.level.path in self.level_paths:
                self.level_combo.current(self.level_paths.index(self.level.path))

    def load_selected_level(self) -> None:
        idx = self.level_combo.current()
        if idx < 0:
            return
        try:
            self.level = self.parser.parse_level(self.level_paths[idx])
            self.tileset = self.parser.load_tileset_for_level(self.level)
            self.spriteset = self.parser.load_sprites_for_level(self.level, self.tileset.palette)
        except Exception as exc:
            messagebox.showerror("Could not load level", str(exc))
            return
        self.current_tile.set(0)
        self.current_event.set(0)
        self.current_bg.set(0)
        self.selected_object = None
        self.move_object_mode.set(False)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_save_path = self.level.path
        self.set_dirty(False)
        self._event_preview_cache.clear()
        self._object_icon_photos.clear()
        self._collision_tile_cache.clear()
        self._collision_chunk_cache.clear()
        self._sound_archive = None
        self._sound_archive_loaded = False
        self.status.set(
            f"Loaded {self.level.path.name}: level={self.level.level_num}, world={self.level.world_num}, "
            f"blocks={self.tileset.path.name}, tiles={len(self.tileset.tiles)}, "
            f"sprites={len(self.spriteset.sprites) if self.spriteset else 0}"
        )
        self.populate_events()
        self.refresh_event_def_selector()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.sync_metadata_ui()
        self.render_atlas()
        self.render_event_definition(0)
        self.populate_animations()
        self.populate_bullets()
        self.populate_paths()
        self.render_mask_info(0)
        self.refresh_validation()
        self.refresh_global_summary()
        self.render_map()

    def reload_current(self) -> None:
        if self.maybe_save_changes("reloading"):
            self.load_selected_level()

    def _mode_changed(self) -> None:
        mode = self.tool_mode.get()
        if mode == "tiles":
            self.tabs.select(0)
        elif mode == "events":
            self.tabs.select(1)
        elif mode == "objects":
            self.tabs.select(2)
        elif mode == "start":
            self.tabs.select(3)
        self.status.set(f"Mode: {mode}")
        self.render_map()

    def _metadata_tuple(self) -> Tuple[int, int, int, int, int, int, int]:
        if not self.level:
            return (0, 0, 0, 0, 0, 0, 0)
        md = self.level.metadata
        return (md.start_x, md.start_y, md.next_level, md.next_world, md.jump_height_raw, md.water_level, md.anim_speed)

    def _restore_metadata_tuple(self, values: Tuple[int, int, int, int, int, int, int]) -> None:
        if not self.level:
            return
        md = self.level.metadata
        md.start_x, md.start_y, md.next_level, md.next_world, md.jump_height_raw, md.water_level, md.anim_speed = values
        self.sync_metadata_ui()

    def _snapshot_state(self) -> Tuple[bytes, Tuple[int, int, int, int, int, int, int]]:
        assert self.level is not None
        return (self.level.grid_to_bytes(), self._metadata_tuple())

    def _restore_state(self, snapshot: Tuple[bytes, Tuple[int, int, int, int, int, int, int]]) -> None:
        if not self.level:
            return
        raw_grid, md_tuple = snapshot
        for x in range(LW):
            for y in range(LH):
                idx = (y + x * LH) * 2
                self.level.grid[y][x] = {"tile": raw_grid[idx], "bg": raw_grid[idx + 1] >> 7, "event": raw_grid[idx + 1] & 0x7F}
        self._restore_metadata_tuple(md_tuple)
        self.selected_object = None
        self.render_map()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.refresh_validation()

    def _push_undo(self) -> None:
        if not self.level:
            return
        snap = self._snapshot_state()
        if self.undo_stack and self.undo_stack[-1] == snap:
            return
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.set_dirty(True)

    def undo(self) -> None:
        if not self.level or not self.undo_stack:
            self.status.set("Nothing to undo.")
            return
        self.redo_stack.append(self._snapshot_state())
        snap = self.undo_stack.pop()
        self._restore_state(snap)
        self.set_dirty(True)
        self.status.set("Undo applied.")

    def redo(self) -> None:
        if not self.level or not self.redo_stack:
            self.status.set("Nothing to redo.")
            return
        self.undo_stack.append(self._snapshot_state())
        snap = self.redo_stack.pop()
        self._restore_state(snap)
        self.set_dirty(True)
        self.status.set("Redo applied.")

    def validate_level(self) -> List[Tuple[str, str, str]]:
        issues: List[Tuple[str, str, str]] = []
        if not self.level:
            return issues
        level = self.level
        if self.tileset:
            for y in range(LH):
                for x in range(LW):
                    tile = level.grid[y][x]["tile"]
                    if tile >= len(self.tileset.tiles):
                        issues.append(("error", f"cell {x},{y}", f"Tile {tile} is outside loaded tileset range 0..{len(self.tileset.tiles)-1}."))
                        if len(issues) > 200:
                            break
                if len(issues) > 200:
                    break
        counts = self.event_usage_counts()
        for event_id, count in sorted(counts.items()):
            ev = level.event_def(event_id)
            raw = ev.raw
            if not ev.name and not any(raw):
                issues.append(("error", f"event {event_id:03d}", f"Used {count} time(s) but the event definition is empty."))
            for label, idx in [("left",5),("right",6),("finishL",28),("finishR",29),("shootL",30),("shootR",31)]:
                anim_id = raw[idx] & 0x7F
                if raw[idx] and (anim_id >= len(level.animations) or level.animations[anim_id].length == 0):
                    issues.append(("warning", f"event {event_id:03d}", f"{label} animation {anim_id} has no frames; object may be invisible."))
            if self.spriteset:
                preview = self.event_preview_image(event_id, 30)
                if preview is None and ev.category in {"pickup/powerup", "enemy/hazard", "trampoline/spring"}:
                    issues.append(("info", f"event {event_id:03d}", f"No sprite preview resolved for {friendly_event_name(ev)}; editor will show label only."))
        md = level.metadata
        if md.start_x_pos >= 0:
            if not (0 <= md.start_x < LW and 0 <= md.start_y < LH):
                issues.append(("error", "player start", f"Start position ({md.start_x},{md.start_y}) is outside the 256x64 map."))
            else:
                tile = level.grid[md.start_y][md.start_x]["tile"]
                if level.tile_has_collision(tile):
                    issues.append(("warning", "player start", f"Start position is on tile {tile}, which has collision mask bits."))
        try:
            next_file = self.parser.find_file(f"LEVEL{md.next_level}.{md.next_world:03d}")
            if not next_file.exists():
                issues.append(("warning", "next level", f"Next level LEVEL{md.next_level}.{md.next_world:03d} was not found."))
        except Exception:
            if md.next_world or md.next_level:
                issues.append(("warning", "next level", f"Next level LEVEL{md.next_level}.{md.next_world:03d} was not found."))
        for anim in level.animations:
            if anim.length:
                for frame_id in anim.frame_ids:
                    if self.spriteset and self.spriteset.get(frame_id) is None:
                        issues.append(("warning", f"anim {anim.anim_id:03d}", f"References missing sprite frame {frame_id}."))
                        break
        return issues

    def refresh_validation(self) -> None:
        if not hasattr(self, "validation_tree"):
            return
        self.validation_tree.delete(*self.validation_tree.get_children())
        issues = self.validate_level()
        for i, issue in enumerate(issues):
            self.validation_tree.insert("", tk.END, iid=str(i), values=issue)
        errors = sum(1 for sev, _, _ in issues if sev == "error")
        warnings = sum(1 for sev, _, _ in issues if sev == "warning")
        infos = sum(1 for sev, _, _ in issues if sev == "info")
        text = f"Validation complete: {errors} error(s), {warnings} warning(s), {infos} info note(s).\n"
        if not issues:
            text += "No obvious issues found by the current checks. This does not guarantee the level is valid in every engine edge case."
        else:
            text += "Errors are likely to break the level. Warnings deserve checking. Info notes are mostly editor limitations or unknown object semantics."
        self.validation_text.configure(state="normal")
        self.validation_text.delete("1.0", tk.END)
        self.validation_text.insert("1.0", text)
        self.validation_text.configure(state="disabled")

    def place_player_start(self, x: int, y: int) -> None:
        if not self.level:
            return
        if self.lock_start.get():
            self.status.set("Player start layer is locked. Unlock it in Layers tab to move the spawn.")
            return
        self._push_undo()
        self.level.metadata.start_x = x
        self.level.metadata.start_y = y
        self.sync_metadata_ui()
        self.render_map()
        self.refresh_validation()
        self.status.set(f"Moved player start to ({x},{y}). This changes level metadata, not events.")

    def sync_metadata_ui(self) -> None:
        if not self.level or not hasattr(self, "start_x_var"):
            return
        md = self.level.metadata
        self.start_x_var.set(md.start_x)
        self.start_y_var.set(md.start_y)
        self.next_level_var.set(md.next_level)
        self.next_world_var.set(md.next_world)
        self.water_level_var.set(md.water_level)
        self.jump_height_raw_var.set(md.jump_height_raw)
        self.anim_speed_var.set(md.anim_speed)

    def apply_metadata_from_ui(self) -> None:
        if not self.level or not hasattr(self, "start_x_var"):
            return
        self._push_undo()
        md = self.level.metadata
        md.start_x = max(0, min(LW - 1, int(self.start_x_var.get())))
        md.start_y = max(0, min(LH - 1, int(self.start_y_var.get())))
        md.next_level = max(0, min(255, int(self.next_level_var.get())))
        md.next_world = max(0, min(255, int(self.next_world_var.get())))
        md.water_level = max(0, min(65535, int(self.water_level_var.get())))
        md.jump_height_raw = max(0, min(65535, int(self.jump_height_raw_var.get())))
        md.anim_speed = max(0, min(255, int(self.anim_speed_var.get())))
        self.render_map()
        self.refresh_validation()
        self.status.set("Applied level metadata fields. Use Save to write them.")

    def render_mask_info(self, tile: int) -> None:
        if not self.level or not hasattr(self, "mask_text"):
            return
        tile = max(0, min(255, int(tile)))
        start = tile * 8
        self.mask_tile_var.set(tile) if hasattr(self, "mask_tile_var") else None
        lines = [f"Tile {tile} collision mask:", "", "Edit only the 8 rows below (# solid, . empty), then click Apply 8x8 mask:", "Leftmost character is mask bit 0 / left side of tile.", ""]
        if start + 8 <= len(self.level.masks):
            for row in self.level.masks[start:start + 8]:
                lines.append("".join("#" if row & (1 << bit) else "." for bit in range(8)))
            lines.extend(["", "# = solid low-res mask bit, . = empty"] )
        else:
            lines.append("No mask data for this tile index.")
        self.mask_text.configure(state="normal")
        self.mask_text.delete("1.0", tk.END)
        self.mask_text.insert("1.0", "\n".join(lines))
        # Keep editable so the user can patch the global tile mask.
        self.mask_text.configure(state="normal")

    def _save_to_path(self, path: Path) -> bool:
        if not self.level:
            return False
        try:
            self.level.save_as(
                path,
                save_event_defs=True,
                save_paths=True,
                save_masks=True,
                save_animations=True,
                save_bullets=True,
            )
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
        self.current_save_path = path
        self.set_dirty(False)
        self.status.set(f"Saved {path}")
        return True

    def save(self) -> bool:
        if not self.level:
            return False
        target = self.current_save_path or self.level.path
        return self._save_to_path(Path(target))

    def save_as(self) -> bool:
        if not self.level:
            return False
        default = self.current_save_path or self.level.path
        target = filedialog.asksaveasfilename(
            title="Save level as",
            initialdir=str(default.parent),
            initialfile=default.name,
            filetypes=[("JJ1 level", "LEVEL*.*"), ("All files", "*")],
        )
        if not target:
            return False
        return self._save_to_path(Path(target))
