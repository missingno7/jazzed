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

class EditingMixin:
    def canvas_to_cell(self, event: tk.Event) -> Optional[Tuple[int, int]]:
        z = max(1, int(self.zoom.get()))
        x = int(self.canvas.canvasx(event.x) // (TILE_SIZE * z))
        y = int(self.canvas.canvasy(event.y) // (TILE_SIZE * z))
        if 0 <= x < LW and 0 <= y < LH:
            return x, y
        return None

    def on_canvas_motion(self, event: tk.Event) -> None:
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        x, y = cell_pos
        cell = self.level.grid[y][x]
        name = self.level.event_names[cell["event"]] if cell["event"] < len(self.level.event_names) else ""
        category = self.level.event_def(cell["event"]).category if cell["event"] else "none"
        self.cell_label.configure(text=f"Cell: x={x}, y={y}, tile={cell['tile']}, event={cell['event']} {name}, bg={cell['bg']}")
        if cell["event"]:
            self.object_label.configure(text=f"Object under cursor: event={cell['event']} {self.event_display_name(cell['event'])} [{category}] at ({x},{y})")
        else:
            self.object_label.configure(text="Object under cursor: none")
        self._update_brush_preview(x, y)

    def on_canvas_click(self, event: tk.Event) -> None:
        self._last_painted_cell = None
        self.handle_map_action(event)

    def on_canvas_drag(self, event: tk.Event) -> None:
        if self.tool_mode.get() in {"tiles", "events"}:
            self.handle_map_action(event)

    def on_canvas_release(self, _event: tk.Event) -> None:
        self._last_painted_cell = None
        if self._paint_stroke_active:
            count = len(self._stroke_cells)
            self._paint_stroke_active = False
            self._stroke_cells.clear()
            self._dirty_chunks.clear()
            if count:
                self.refresh_validation()
                if self.tool_mode.get() == "events":
                    self.refresh_object_palette()
                    self.refresh_objects()
                    self.refresh_object_types()
                self.status.set(f"Paint stroke finished: {count} cell(s) changed.")

    def _begin_paint_stroke_if_needed(self) -> None:
        if not self._paint_stroke_active:
            self._push_undo()
            self._paint_stroke_active = True
            self._stroke_cells.clear()
            self._dirty_chunks.clear()

    def handle_map_action(self, event: tk.Event) -> None:
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        if self._last_painted_cell == cell_pos and self.tool_mode.get() in {"tiles", "events"}:
            return
        self._last_painted_cell = cell_pos
        x, y = cell_pos
        mode = self.tool_mode.get()
        if mode == "tiles":
            self.paint_tile(x, y)
        elif mode == "events":
            self.paint_event(x, y)
        elif mode == "objects":
            self.object_click(x, y)
        elif mode == "start":
            self.place_player_start(x, y)
        else:
            self.inspect_cell(x, y)

    def paint_tile(self, x: int, y: int) -> None:
        assert self.level is not None
        if self.lock_tiles.get():
            self.status.set("Tiles layer is locked. Unlock it in Layers tab to paint tiles.")
            return
        self._begin_paint_stroke_if_needed()
        cell = self.level.grid[y][x]
        old = (cell["tile"], cell["bg"])
        cell["tile"] = max(0, min(255, int(self.current_tile.get())))
        if self.paint_bg.get():
            cell["bg"] = max(0, min(1, int(self.current_bg.get())))
        if old != (cell["tile"], cell["bg"]):
            self._stroke_cells.add((x, y))
            self._dirty_chunks.add(self._cell_chunk(x, y))
            self._refresh_cell_chunk(x, y)
        self.status.set(f"Painting tile {cell['tile']} at ({x},{y}) into chunk {self._cell_chunk(x,y)}. Stroke cells: {len(self._stroke_cells)}.")

    def paint_event(self, x: int, y: int) -> None:
        assert self.level is not None
        if self.lock_events.get():
            self.status.set("Events layer is locked. Unlock it in Layers tab to paint event IDs.")
            return
        self._begin_paint_stroke_if_needed()
        cell = self.level.grid[y][x]
        new_event = max(0, min(126, int(self.current_event.get())))
        old_event = cell["event"]
        cell["event"] = new_event
        self.selected_object = (x, y) if cell["event"] else None
        if old_event != new_event:
            self._stroke_cells.add((x, y))
            self._dirty_chunks.add(self._cell_chunk(x, y))
            self._refresh_cell_chunk(x, y)
        self.status.set(f"Painting event {cell['event']} at ({x},{y}) into chunk {self._cell_chunk(x,y)}. Tile unchanged: {cell['tile']}. Stroke cells: {len(self._stroke_cells)}.")

    def object_click(self, x: int, y: int) -> None:
        assert self.level is not None
        if self.lock_objects.get():
            self.status.set("Objects layer is locked. Unlock it in Layers tab to move/select-edit objects.")
            return
        if self.move_object_mode.get() and self.selected_object:
            sx, sy = self.selected_object
            if (sx, sy) != (x, y):
                source = self.level.grid[sy][sx]
                target = self.level.grid[y][x]
                if target["event"]:
                    self.status.set("Target cell already has an object/event. Delete it first or choose an empty cell.")
                    return
                self._push_undo()
                target["event"] = source["event"]
                source["event"] = 0
                self.selected_object = (x, y)
                self.move_object_mode.set(False)
                self.render_map()
                self.refresh_objects()
                self.select_object_in_tree(x, y)
                self.refresh_validation()
                self.status.set(f"Moved object event={target['event']} from ({sx},{sy}) to ({x},{y}).")
            return
        self.select_object_at(x, y)

    def inspect_cell(self, x: int, y: int) -> None:
        assert self.level is not None
        cell = self.level.grid[y][x]
        self.status.set(f"Inspect x={x}, y={y}: tile={cell['tile']}, event={cell['event']}, bg={cell['bg']}")

    def select_object_at(self, x: int, y: int) -> None:
        assert self.level is not None
        cell = self.level.grid[y][x]
        if cell["event"]:
            self.selected_object = (x, y)
            self.current_event.set(cell["event"])
            self.render_event_definition(cell["event"])
            self.render_map()
            self.refresh_objects()
            self.select_object_in_tree(x, y)
            name = self.level.event_names[cell["event"]] if cell["event"] < len(self.level.event_names) else ""
            self.status.set(f"Selected object at ({x},{y}): event={cell['event']} {self.event_display_name(cell['event'])}")
        else:
            self.selected_object = None
            self.render_map()
            self.status.set(f"No object/event at ({x},{y}).")

    def select_object_in_tree(self, x: int, y: int) -> None:
        iid = f"{x},{y}"
        if iid in self.object_tree.get_children(""):
            self.object_tree.selection_set(iid)
            self.object_tree.see(iid)

    def erase_from_map(self, event: tk.Event) -> None:
        """Right-click erase.

        Tiles mode clears the visual block/BG flag.
        Events/Objects mode clears only the event placement and preserves the tile.
        Inspect mode erases event if present, otherwise clears the tile.
        Shift+right-click or middle-click still picks values from the map.
        """
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        x, y = cell_pos
        cell = self.level.grid[y][x]
        mode = self.tool_mode.get()

        if mode == "tiles":
            if self.lock_tiles.get():
                self.status.set("Tiles layer is locked; cannot erase tile.")
                return
            if cell["tile"] == 0 and cell["bg"] == 0:
                return
            self._push_undo()
            old_tile, old_bg = cell["tile"], cell["bg"]
            cell["tile"] = 0
            cell["bg"] = 0
            self._refresh_cell_chunk(x, y)
            self.refresh_validation()
            self.status.set(f"Right-click erased tile/BG at ({x},{y}): tile {old_tile}->0, bg {old_bg}->0. Event preserved: {cell['event']}.")
            return

        if mode in {"events", "objects"} or cell["event"]:
            if self.lock_events.get() or self.lock_objects.get():
                self.status.set("Event/object layer is locked; cannot erase event.")
                return
            if not cell["event"]:
                self.status.set(f"No event to erase at ({x},{y}).")
                return
            self._push_undo()
            old_event = cell["event"]
            cell["event"] = 0
            if self.selected_object == (x, y):
                self.selected_object = None
            self._refresh_cell_chunk(x, y)
            self.refresh_object_palette()
            self.refresh_objects()
            self.refresh_object_types()
            self.refresh_validation()
            self.status.set(f"Right-click erased event {old_event} at ({x},{y}). Tile preserved: {cell['tile']}.")
            return

        if cell["tile"] or cell["bg"]:
            self._push_undo()
            old_tile, old_bg = cell["tile"], cell["bg"]
            cell["tile"] = 0
            cell["bg"] = 0
            self._refresh_cell_chunk(x, y)
            self.refresh_validation()
            self.status.set(f"Right-click erased tile/BG at ({x},{y}): tile {old_tile}->0, bg {old_bg}->0.")
        else:
            self.status.set(f"Cell ({x},{y}) is already empty.")

    def pick_from_map(self, event: tk.Event) -> None:
        cell_pos = self.canvas_to_cell(event)
        if not cell_pos or not self.level:
            return
        x, y = cell_pos
        cell = self.level.grid[y][x]
        mode = self.tool_mode.get()
        if mode == "tiles":
            self.current_tile.set(cell["tile"])
            self.current_bg.set(cell["bg"])
            self.render_atlas()
            self.render_mask_info(cell["tile"])
            self.status.set(f"Picked tile/BG from ({x},{y}): tile={cell['tile']}, bg={cell['bg']}")
        elif mode in {"events", "objects"}:
            self.current_event.set(cell["event"])
            self._sync_event_selection()
            self.status.set(f"Picked event from ({x},{y}): event={cell['event']}")
        else:
            self.current_tile.set(cell["tile"])
            self.current_event.set(cell["event"])
            self.current_bg.set(cell["bg"])
            self.status.set(f"Picked all from ({x},{y}): tile={cell['tile']}, event={cell['event']}, bg={cell['bg']}")

    def on_atlas_click(self, event: tk.Event) -> None:
        if not self.tileset:
            return
        scale = 2
        columns = self._atlas_columns(scale)
        x = int(self.atlas_canvas.canvasx(event.x) // (TILE_SIZE * scale))
        y = int(self.atlas_canvas.canvasy(event.y) // (TILE_SIZE * scale))
        tile = y * columns + x
        if 0 <= tile < len(self.tileset.tiles):
            self.current_tile.set(tile)
            self.tool_mode.set("tiles")
            self.tabs.select(0)
            self.render_atlas()
            self.render_mask_info(tile)
            self.status.set(f"Selected tile {tile}; mode set to Tiles")

