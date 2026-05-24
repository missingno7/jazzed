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

class ObjectsMixin:
    def populate_events(self) -> None:
        self.event_list.delete(0, tk.END)
        if not self.level:
            return
        for i, name in enumerate(self.level.event_names):
            label = name or f"event_{i:03d}"
            self.event_list.insert(tk.END, f"{i:03d}: {label}")

    def event_usage_counts(self) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        if not self.level:
            return counts
        for y in range(LH):
            for x in range(LW):
                ev = self.level.grid[y][x]["event"]
                if ev:
                    counts[ev] = counts.get(ev, 0) + 1
        return counts

    def event_display_name(self, event_id: int) -> str:
        if not self.level:
            return f"event_{event_id:03d}"
        ev = self.level.event_def(event_id)
        return friendly_event_name(ev)

    def event_preview_image(self, event_id: int, max_size: int = 48) -> Optional[Image.Image]:
        if not self.level or not self.spriteset or not event_id:
            return None
        cache_key = (int(event_id), int(max_size))
        if cache_key in self._event_preview_cache:
            cached = self._event_preview_cache[cache_key]
            return cached.copy() if cached is not None else None
        raw = self.level.event_types[event_id]
        candidates = []
        for idx in [5, 6, 28, 29, 30, 31]:
            if idx < len(raw) and raw[idx]:
                anim_id = raw[idx] & 0x7F
                # Do not invent an icon from animation 0. Several event types have no explicit
                # animation and otherwise fall back to a misleading Jazz/rabbit sprite.
                if anim_id != 0:
                    candidates.append(anim_id)
        if not candidates:
            self._event_preview_cache[cache_key] = None
            return None
        for anim_id in candidates:
            anim = self.level.animation(anim_id)
            if not anim or anim.length <= 0:
                continue
            for frame_id in anim.frame_ids:
                frame = self.spriteset.get(frame_id)
                if frame:
                    img = frame.image.copy()
                    img.thumbnail((max_size, max_size), Image.Resampling.NEAREST)
                    self._event_preview_cache[cache_key] = img.copy()
                    return img
        self._event_preview_cache[cache_key] = None
        return None

    def render_event_icon(self, event_id: int, size: int = 40) -> Optional[ImageTk.PhotoImage]:
        img = self.event_preview_image(event_id, size)
        if img is None:
            return None
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
        photo = ImageTk.PhotoImage(canvas)
        self._object_icon_photos[event_id] = photo
        return photo

    def show_reserved_markers_help(self) -> None:
        lines = ["Reserved engine marker events:", ""]
        for event_id in sorted(RESERVED_ENGINE_EVENTS):
            info = RESERVED_ENGINE_EVENTS[event_id]
            lines.append(f"{event_id}: {info['name']}")
            lines.append(f"    {info['summary']}")
            lines.append("")
        lines.append(f"Normal event definitions are safest in range 1..{NORMAL_EDITABLE_EVENT_MAX}.")
        lines.append("Events 122..126 are reserved engine/render/collision markers and should be edited as marker placements, not duplicated as normal object types.")
        messagebox.showinfo("Reserved engine marker events", "\n".join(lines))

    def refresh_object_palette(self) -> None:
        if not hasattr(self, "palette_tree"):
            return
        self.palette_tree.delete(*self.palette_tree.get_children())
        if not self.level:
            return
        counts = self.event_usage_counts()
        category_filter = self.object_category_filter.get()
        for evdef in self.level.event_catalog()[1:]:
            # Show used events plus named/meaningful definitions. This keeps placeholder empty definitions out of the way.
            if not evdef.name and counts.get(evdef.event_id, 0) == 0 and evdef.raw[5] == 0 and evdef.raw[6] == 0 and evdef.raw[9] == 0 and evdef.raw[10] == 0 and evdef.raw[11] == 0:
                continue
            if category_filter != "all" and evdef.category != category_filter:
                continue
            label = f"{evdef.event_id:03d}: {friendly_event_name(evdef)}"
            self.palette_tree.insert("", tk.END, iid=str(evdef.event_id), values=(evdef.category, counts.get(evdef.event_id, 0), label))

    def on_palette_tree_select(self, _event: tk.Event) -> None:
        selection = self.palette_tree.selection()
        if not selection:
            return
        event_id = int(selection[0])
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.render_event_definition(event_id)
        photo = self.render_event_icon(event_id, 32)
        if hasattr(self, "object_preview_label"):
            self.object_preview_label.configure(text=f"preview: event {event_id}", image=photo or "", compound=tk.LEFT)
        if hasattr(self, "object_help_text") and self.level:
            self.object_help_text.configure(state="normal")
            self.object_help_text.delete("1.0", tk.END)
            self.object_help_text.insert("1.0", object_tooltip(self.level.event_def(event_id)))
            self.object_help_text.configure(state="disabled")
        self.status.set(f"Selected object palette event {event_id}: {self.event_display_name(event_id)}. Click the map in Events mode to place it.")

    def use_palette_event(self) -> None:
        selection = self.palette_tree.selection()
        if not selection:
            self.status.set("No palette event selected.")
            return
        event_id = int(selection[0])
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.workspace_tabs.select(self.build_workspace)
        self.build_tabs.select(self.objects_tab)
        self._sync_event_selection()
        self.status.set(f"Using event {event_id} as object brush. Left-click map to place; right-click erases.")

    def refresh_objects(self) -> None:
        if not hasattr(self, "object_tree"):
            return
        self.object_tree.delete(*self.object_tree.get_children())
        if not self.level:
            return
        category_filter = self.object_category_filter.get() if hasattr(self, "object_category_filter") else "all"
        for obj in self.level.objects():
            evdef = self.level.event_def(obj.event)
            if category_filter != "all" and evdef.category != category_filter:
                continue
            iid = f"{obj.x},{obj.y}"
            self.object_tree.insert("", tk.END, iid=iid, values=(obj.event, self.event_display_name(obj.event), obj.x, obj.y, obj.tile, obj.bg))

    def refresh_object_types(self) -> None:
        if not hasattr(self, "object_types_tree"):
            return
        self.object_types_tree.delete(*self.object_types_tree.get_children())
        if not self.level:
            return
        counts = self.event_usage_counts()
        for evdef in self.level.event_catalog()[1:]:
            meaningful = bool(evdef.name or counts.get(evdef.event_id, 0) or any(evdef.raw))
            if not meaningful:
                continue
            self.object_types_tree.insert(
                "", tk.END, iid=str(evdef.event_id),
                values=(evdef.event_id, counts.get(evdef.event_id, 0), evdef.category, friendly_event_name(evdef)),
            )

    def _selected_object_type_id(self) -> Optional[int]:
        if hasattr(self, "object_types_tree"):
            sel = self.object_types_tree.selection()
            if sel:
                return int(sel[0])
        if self.selected_object and self.level:
            x, y = self.selected_object
            ev = self.level.grid[y][x]["event"]
            return ev or None
        cur = int(self.current_event.get()) if hasattr(self, "current_event") else 0
        return cur or None

    def on_object_type_select(self, _event: tk.Event) -> None:
        event_id = self._selected_object_type_id()
        if not event_id or not self.level:
            return
        self.current_event.set(event_id)
        self.render_event_definition(event_id)
        self.highlight_event_id.set(event_id)
        if hasattr(self, "object_type_detail"):
            ev = self.level.event_def(event_id)
            count = self.event_usage_counts().get(event_id, 0)
            self.object_type_detail.configure(state="normal")
            self.object_type_detail.delete("1.0", tk.END)
            self.object_type_detail.insert("1.0", object_tooltip(ev) + f"\n\nUsed {count} time(s) in this level. Changing this event definition changes all of those placements in this level only.")
            self.object_type_detail.configure(state="disabled")
        self.render_map()

    def use_object_type_as_brush(self) -> None:
        event_id = self._selected_object_type_id()
        if not event_id:
            self.status.set("No object type selected.")
            return
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.status.set(f"Using object type event {event_id} as brush: {self.event_display_name(event_id)}")

    def highlight_selected_object_type(self) -> None:
        event_id = self._selected_object_type_id()
        if not event_id:
            self.status.set("No object type selected to highlight.")
            return
        self.highlight_event_id.set(event_id)
        self.render_map()
        self.status.set(f"Highlighted all placements of event {event_id}: {self.event_display_name(event_id)}")

    def find_free_event_id(self) -> Optional[int]:
        if not self.level:
            return None
        used = set(self.event_usage_counts())
        for i in range(1, NORMAL_EDITABLE_EVENT_MAX + 1):
            raw = self.level.event_types[i]
            if i not in used and not self.level.event_names[i] and not any(raw):
                return i
        for i in range(1, NORMAL_EDITABLE_EVENT_MAX + 1):
            if i not in used:
                return i
        return None

    def duplicate_selected_object_definition(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("Select a placed object first. Then this can duplicate its level-local event definition.")
            return
        x, y = self.selected_object
        old_id = self.level.grid[y][x]["event"]
        if not old_id:
            self.status.set("Selected cell has no event/object.")
            return
        if is_reserved_engine_event(old_id):
            self.status.set(f"Event {old_id} is a reserved engine marker ({friendly_event_name(self.level.event_def(old_id))}); duplicate its placement, not its definition.")
            return
        new_id = self.find_free_event_id()
        if new_id is None:
            self.status.set("No free event definition slot found in this level.")
            return
        self._push_undo()
        self.level.event_types[new_id] = bytes(self.level.event_types[old_id])
        old_name = self.level.event_names[old_id] if old_id < len(self.level.event_names) else ""
        self.level.event_names[new_id] = ("Copy " + old_name)[:15] if old_name else f"Copy{old_id:03d}"
        self.level.grid[y][x]["event"] = new_id
        self.current_event.set(new_id)
        self.highlight_event_id.set(new_id)
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.render_event_definition(new_id)
        self.render_map()
        self.status.set(f"Duplicated event type {old_id} into free slot {new_id} and changed only selected placement ({x},{y}). Enable/save event definitions to persist the new type.")

    def replace_selected_object_with_brush(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("Select a placed object first.")
            return
        new_id = max(0, min(126, int(self.current_event.get())))
        x, y = self.selected_object
        old_id = self.level.grid[y][x]["event"]
        if old_id == new_id:
            self.status.set("Selected object already uses the current brush event.")
            return
        self._push_undo()
        self.level.grid[y][x]["event"] = new_id
        self.highlight_event_id.set(new_id)
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.render_map()
        self.status.set(f"Replaced selected placement ({x},{y}) event {old_id} -> {new_id}.")

    def replace_all_selected_type_with_brush(self) -> None:
        if not self.level:
            return
        old_id = self.highlight_event_id.get() or self._selected_object_type_id()
        new_id = max(0, min(126, int(self.current_event.get())))
        if not old_id:
            self.status.set("Select or highlight an object type first.")
            return
        if old_id == new_id:
            self.status.set("Old type and current brush are the same.")
            return
        self._push_undo()
        changed = 0
        for y in range(LH):
            for x in range(LW):
                if self.level.grid[y][x]["event"] == old_id:
                    self.level.grid[y][x]["event"] = new_id
                    changed += 1
        self.highlight_event_id.set(new_id)
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.render_map()
        self.status.set(f"Replaced {changed} placement(s): event {old_id} -> {new_id}. Definitions were not changed.")

    def on_event_select(self, _event: tk.Event) -> None:
        selection = self.event_list.curselection()
        if selection:
            event_id = int(selection[0])
            self.current_event.set(event_id)
            self.tool_mode.set("events")
            self.render_event_definition(event_id)
            self.status.set(f"Selected event {event_id}; mode set to Events")

    def _sync_event_selection(self) -> None:
        event_id = max(0, min(126, int(self.current_event.get())))
        self.current_event.set(event_id)
        self.event_list.selection_clear(0, tk.END)
        self.event_list.selection_set(event_id)
        self.event_list.see(event_id)
        self.render_event_definition(event_id)

    def on_object_tree_select(self, _event: tk.Event) -> None:
        selection = self.object_tree.selection()
        if not selection or not self.level:
            return
        x_s, y_s = selection[0].split(",")
        x, y = int(x_s), int(y_s)
        self.selected_object = (x, y)
        event_id = self.level.grid[y][x]["event"]
        self.current_event.set(event_id)
        self.tool_mode.set("objects")
        self.render_event_definition(event_id)
        self.render_map()
        self.status.set(f"Selected object at ({x},{y}), event={event_id}")

    def delete_selected_object(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("No selected object to delete.")
            return
        x, y = self.selected_object
        self._push_undo()
        event_id = self.level.grid[y][x]["event"]
        self.level.grid[y][x]["event"] = 0
        self.selected_object = None
        self.render_map()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.refresh_validation()
        self.status.set(f"Deleted object/event {event_id} at ({x},{y}). Tile was preserved.")

    def duplicate_selected_object_to_brush(self) -> None:
        if not self.level or not self.selected_object:
            self.status.set("No selected object to duplicate.")
            return
        x, y = self.selected_object
        event_id = self.level.grid[y][x]["event"]
        self.current_event.set(event_id)
        self.tool_mode.set("events")
        self.workspace_tabs.select(self.build_workspace)
        self.build_tabs.select(self.objects_tab)
        self._sync_event_selection()
        self.status.set(f"Copied object event={event_id} to event brush. Click map in Events mode to place another instance.")

