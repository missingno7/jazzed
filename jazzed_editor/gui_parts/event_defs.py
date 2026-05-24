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

class EventDefsMixin:
    def event_def_selector_values(self) -> List[str]:
        if not self.level:
            return []
        counts = self.event_usage_counts()
        values = []
        for event_id in range(EVENTS):
            ev = self.level.event_def(event_id)
            used = counts.get(event_id, 0)
            if event_id == 0:
                label = "Empty / erase"
            elif not any(ev.raw) and not ev.name and used == 0:
                label = "Unused"
            else:
                label = friendly_event_name(ev)
            values.append(f"{event_id:03d}  {label}  ({used}×)")
        return values

    def refresh_event_def_selector(self) -> None:
        if hasattr(self, "event_def_combo"):
            values = self.event_def_selector_values()
            self.event_def_combo["values"] = values
            eid = max(0, min(126, int(getattr(self, "_editing_event_id", 0))))
            if values:
                self.event_def_combo.current(eid)

    def on_event_def_combo_select(self, _event: tk.Event = None) -> None:
        if not hasattr(self, "event_def_combo"):
            return
        idx = self.event_def_combo.current()
        if idx >= 0:
            self.select_event_definition(idx)

    def select_event_definition(self, event_id: int) -> None:
        event_id = max(0, min(126, int(event_id)))
        self._editing_event_id = event_id
        self.current_event.set(event_id)
        if hasattr(self, "event_def_combo"):
            vals = self.event_def_combo["values"]
            if vals:
                self.event_def_combo.current(event_id)
        self.render_event_definition(event_id)

    def create_new_object_type(self) -> None:
        if not self.level:
            return
        used = self.event_usage_counts()
        event_id = self.find_free_event_id()
        raw = bytearray(ELENGTH)
        self.level.event_types[event_id] = bytes(raw)
        self.set_dirty(True)
        self.refresh_event_def_selector()
        self.select_event_definition(event_id)
        self.status.set(f"Created new object type in free Event {event_id:03d}.")

    def duplicate_event_definition_as_new(self) -> None:
        if not self.level:
            return
        src_id = max(0, min(126, int(getattr(self, "_editing_event_id", self.current_event.get()))))
        if src_id == 0:
            self.status.set("Cannot duplicate empty event 0.")
            return
        if is_reserved_engine_event(src_id):
            self.status.set(f"Event {src_id} is a reserved engine marker; duplicate its placement, not its definition.")
            return
        dst_id = self.find_free_event_id()
        self.level.event_types[dst_id] = bytes(self.level.event_types[src_id])
        if dst_id < len(self.level.event_names):
            base_name = self.level.event_names[src_id] if src_id < len(self.level.event_names) else ""
            self.level.event_names[dst_id] = (base_name + " copy").strip()[:32] if base_name else ""
        self.set_dirty(True)
        self.refresh_event_def_selector()
        self.select_event_definition(dst_id)
        self.status.set(f"Duplicated Event {src_id:03d} as new Event {dst_id:03d}.")

    def apply_concept_template_to_raw(self, raw: bytearray, concept: str) -> None:
        # Keep animations/sound/score unless the concept needs a known behavior field.
        if concept == "Unused / empty":
            raw[:] = bytes(ELENGTH)
            return
        if concept == "Enemy / hazard":
            raw[10] = 0
            raw[9] = max(1, raw[9])
            raw[11] = max(1, raw[11])
            if raw[4] == 0:
                raw[4] = 4
        elif concept == "Touch pickup / item":
            raw[9] = 0
            if raw[10] not in PICKUP_MODIFIER_MEANINGS:
                raw[10] = _first_modifier_for_pickup()
            raw[11] = max(1, raw[11])
        elif concept == "Shootable pickup / container":
            raw[9] = max(1, raw[9])
            if raw[10] not in PICKUP_MODIFIER_MEANINGS:
                raw[10] = 15
            raw[11] = max(1, raw[11])
        elif concept == "Destructible block":
            raw[4] = 21
            raw[10] = 7
            raw[9] = max(1, raw[9])
        elif concept == "Spring / bounce":
            raw[10] = 29
            raw[9] = 0
            raw[8] = raw[8] or 250
        elif concept == "Warp trigger":
            raw[10] = 13
            raw[9] = 0
        elif concept == "Conveyor belt":
            raw[10] = 28
            raw[9] = 0
            raw[8] = raw[8] or 2
        elif concept == "Path-moving object":
            raw[4] = 6
            raw[22] = min(15, raw[22])

    def rebuild_event_concept_editor(self, event_id: int, raw: bytes) -> None:
        if not hasattr(self, "event_concept_frame"):
            return
        for child in self.event_concept_frame.winfo_children():
            child.destroy()
        self.event_concept_vars = {}
        name = self.level.event_names[event_id] if self.level and event_id < len(self.level.event_names) else ""
        inferred = infer_event_concept(event_id, raw, name)
        concept = inferred
        if hasattr(self, "event_concept_var"):
            current = self.event_concept_var.get()
            if current in EVENT_CONCEPTS and current not in {"Auto / keep current"}:
                concept = current
            else:
                self.event_concept_var.set(inferred)
        if concept == "Auto / keep current":
            concept = inferred

        def add_spin(row: int, key: str, label: str, value: int, frm: int = 0, to: int = 255, hint: str = "") -> int:
            ttk.Label(self.event_concept_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.IntVar(value=int(value))
            self.event_concept_vars[key] = var
            field = ttk.Frame(self.event_concept_frame)
            field.grid(row=row, column=1, sticky="w", pady=2)
            ttk.Spinbox(field, from_=frm, to=to, width=8, textvariable=var).pack(side=tk.LEFT)
            if key in {"left_anim", "right_anim", "finish_left", "finish_right", "shoot_left", "shoot_right"}:
                ttk.Button(field, text="Atlas…", command=lambda k=key: self.open_animation_picker_for(k)).pack(side=tk.LEFT, padx=(4, 0))
            if key == "bullet":
                ttk.Button(field, text="Pick…", command=lambda k=key: self.open_bullet_picker_for(k)).pack(side=tk.LEFT, padx=(4, 0))
            if hint:
                ttk.Label(self.event_concept_frame, text=hint).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=2)
            return row + 1

        def add_combo(row: int, key: str, label: str, values: List[str], current: str) -> int:
            ttk.Label(self.event_concept_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.StringVar(value=current)
            self.event_concept_vars[key] = var
            cb = ttk.Combobox(self.event_concept_frame, state="readonly", values=values, textvariable=var, width=34)
            cb.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
            return row + 1

        def add_check(row: int, key: str, label: str, value: bool) -> int:
            var = tk.BooleanVar(value=bool(value))
            self.event_concept_vars[key] = var
            ttk.Checkbutton(self.event_concept_frame, text=label, variable=var).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
            return row + 1

        row = 0
        if concept == "Unused / empty":
            ttk.Label(self.event_concept_frame, text="This event definition is currently unused/empty.", wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            row += 1
            ttk.Label(self.event_concept_frame, text="Choose a concept above to turn it into a normal object type, then click Apply.", wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            return
        if is_reserved_engine_event(event_id):
            info = RESERVED_ENGINE_EVENTS[event_id]
            ttk.Label(self.event_concept_frame, text=info["summary"], wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            row += 1
            ttk.Label(self.event_concept_frame, text="This is edited by placing this exact event ID in the map. Its core behavior is not made by these fields.", wraplength=420).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            return

        common_anims = [(5, "left_anim"), (6, "right_anim"), (28, "finish_left"), (29, "finish_right"), (30, "shoot_left"), (31, "shoot_right")]
        if concept == "Unused / empty":
            raw[:] = bytes(ELENGTH)
            return
        if concept in {"Touch pickup / item", "Shootable pickup / container"}:
            cur = f"{raw[10]}: {PICKUP_MODIFIER_MEANINGS.get(raw[10], (f'modifier_{raw[10]}', ''))[0]}"
            if raw[10] not in PICKUP_MODIFIER_MEANINGS:
                cur = PICKUP_COMBO_LABELS[0]
            row = add_combo(row, "pickup_modifier", "Pickup / reward effect", PICKUP_COMBO_LABELS, cur)
            row = add_check(row, "shootable", "Requires shooting / destroying before pickup", raw[9] > 0)
            row = add_spin(row, "strength", "Hits / strength", max(1, raw[9]) if raw[9] else 1, 0, 255)
            row = add_spin(row, "points", "Score points ×10", raw[11], 0, 255)
            row = add_spin(row, "sound", "Pickup sound", raw[21], 0, 255)
        elif concept == "Enemy / hazard":
            row = add_combo(row, "movement", "Movement behavior", [f"{k}: {v[0]}" for k, v in sorted(MOVEMENT_FIELD_MEANINGS.items())], f"{raw[4]}: {movement_meaning_detail(raw[4])[0]}")
            row = add_spin(row, "strength", "Health / hits to kill", raw[9] or 1, 1, 255)
            row = add_spin(row, "points", "Kill score points ×10", raw[11], 0, 255)
            row = add_spin(row, "bullet", "Bullet type", raw[12], 0, 31)
            row = add_spin(row, "bullet_period", "Bullet period", raw[13], 0, 255)
            row = add_spin(row, "speed", "Movement speed divisor", raw[15] + 1, 1, 256)
        elif concept == "Destructible block":
            row = add_spin(row, "strength", "Hits required", raw[9] or 1, 1, 255)
            row = add_spin(row, "destroy_tile", "Tile after destroyed (multiA)", raw[22], 0, 255)
            row = add_spin(row, "piece_size", "Debris piece size", raw[24], 0, 255)
            row = add_spin(row, "pieces", "Debris pieces", raw[25], 0, 255)
            row = add_spin(row, "sound", "Destroy sound", raw[21], 0, 255)
        elif concept == "Spring / bounce":
            row = add_spin(row, "magnitude_signed", "Bounce magnitude (signed)", _signed_byte(raw[8]), -128, 127)
            row = add_spin(row, "sound", "Spring sound", raw[21], 0, 255)
        elif concept == "Warp trigger":
            row = add_spin(row, "warp_x", "Target X tile", raw[22], 0, 255)
            row = add_spin(row, "warp_y", "Target Y tile", raw[23], 0, 255)
            row = add_spin(row, "sound", "Sound", raw[21], 0, 255)
        elif concept == "Conveyor belt":
            row = add_spin(row, "magnitude_signed", "Push magnitude (signed)", _signed_byte(raw[8]), -128, 127)
            row = add_spin(row, "sound", "Sound", raw[21], 0, 255)
        elif concept == "Path-moving object":
            row = add_spin(row, "path_index", "Path index (multiA)", raw[22], 0, 15)
            row = add_combo(row, "movement", "Path movement mode", ["6: Use level path", "7: Flying snake / path"], f"{raw[4]}: {movement_meaning_detail(raw[4])[0]}")
            row = add_spin(row, "strength", "Health / strength", raw[9], 0, 255)
        else:
            row = add_combo(row, "movement", "Movement behavior", [f"{k}: {v[0]}" for k, v in sorted(MOVEMENT_FIELD_MEANINGS.items())], f"{raw[4]}: {movement_meaning_detail(raw[4])[0]}")
            row = add_combo(row, "modifier", "Modifier / touch behavior", [f"{k}: {v[0]}" for k, v in sorted(MODIFIER_TOUCH_MEANINGS.items())], f"{raw[10]}: {modifier_meaning(raw[10])[0]}")
            row = add_spin(row, "strength", "Strength / health / hits", raw[9], 0, 255)
            row = add_spin(row, "points", "Score points ×10", raw[11], 0, 255)
            row = add_spin(row, "magnitude", "Magnitude", raw[8], 0, 255)
            row = add_spin(row, "multi_a", "multiA", raw[22], 0, 255)
            row = add_spin(row, "multi_b", "multiB", raw[23], 0, 255)

        # Visuals are useful for all normal object types.
        row += 1
        ttk.Label(self.event_concept_frame, text="Visuals").grid(row=row, column=0, sticky="w", pady=(8, 2))
        row += 1
        for idx, key in common_anims:
            row = add_spin(row, key, event_field_label_for(raw, idx), raw[idx], 0, 127)
        row = add_spin(row, "anim_speed", "Animation speed", raw[17] + 1, 1, 256)

    def open_bullet_picker_for(self, key: str) -> None:
        win = tk.Toplevel(self)
        win.title("Choose bullet type")
        win.geometry("620x420")
        columns = ("id", "name", "sprites", "finish", "behaviour")
        tree = ttk.Treeview(win, columns=columns, show="headings", selectmode="browse")
        for col, width, title in [
            ("id", 45, "ID"), ("name", 190, "Name"), ("sprites", 120, "Sprites"),
            ("finish", 70, "Finish"), ("behaviour", 80, "Behaviour"),
        ]:
            tree.heading(col, text=title)
            tree.column(col, width=width, stretch=(col == "name"))
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        if self.level and getattr(self.level, "bullet_defs", None):
            for b in self.level.bullet_defs:
                tree.insert("", "end", iid=str(b.bullet_id), values=(b.bullet_id, bullet_display_name(b), "/".join(map(str, b.sprites)), b.finish_anim, b.behaviour))
        else:
            for i in range(BULLETS):
                tree.insert("", "end", iid=str(i), values=(i, bullet_type_label(i), "", "", ""))
        def choose(_event=None):
            sel = tree.selection()
            if not sel:
                return
            var = self.event_concept_vars.get(key)
            if var is not None:
                var.set(int(sel[0]))
            win.destroy()
        ttk.Button(win, text="Use selected", command=choose).pack(pady=(0, 8))
        tree.bind("<Double-1>", choose)

    def open_animation_picker_for(self, key: str) -> None:
        if not self.level:
            return
        win = tk.Toplevel(self)
        win.title(f"Choose animation for {key}")
        win.geometry("900x640")

        top = ttk.Frame(win, padding=(8, 8, 8, 4))
        top.pack(fill=tk.X)
        ttk.Label(top, text="Click any animation tile to select it. Hover highlights the whole tile.").pack(side=tk.LEFT)

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        canvas = tk.Canvas(frame, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        refs: List[ImageTk.PhotoImage] = []
        cell_w = 110
        cell_h = 96
        cols = 8
        used = set()
        for ev in self.level.event_catalog()[1:]:
            for idx in [5, 6, 28, 29, 30, 31]:
                if idx < len(ev.raw) and ev.raw[idx]:
                    used.add(ev.raw[idx] & 0x7F)

        visible_anims = [
            anim for anim in self.level.animations
            if anim.length > 0 or anim.anim_id in used or anim.name
        ]

        hovered = {"tag": None}

        def set_hover(tag: str, on: bool) -> None:
            if on:
                hovered["tag"] = tag
                canvas.itemconfigure(f"{tag}_bg", fill="#303030", outline="#ffff00", width=3)
                canvas.config(cursor="hand2")
            else:
                if hovered.get("tag") == tag:
                    hovered["tag"] = None
                canvas.itemconfigure(f"{tag}_bg", fill="#202020", outline="#555555", width=1)
                canvas.config(cursor="")

        def choose_anim(anim_id: int) -> None:
            var = self.event_concept_vars.get(key)
            if var is not None:
                var.set(anim_id)
            win.destroy()

        for pos, anim in enumerate(visible_anims):
            i = anim.anim_id
            col = pos % cols
            row = pos // cols
            x = col * cell_w
            y = row * cell_h
            tag = f"anim_pick_{i}"

            # Filled background is intentionally visible and receives mouse events across the whole tile.
            canvas.create_rectangle(
                x + 3, y + 3, x + cell_w - 3, y + cell_h - 3,
                fill="#202020", outline="#555555", width=1,
                tags=(tag, f"{tag}_bg"),
            )
            canvas.create_text(x + 8, y + 8, text=f"A{i}", fill="#ffff80", anchor="nw", tags=(tag,))
            title = anim.name[:16] if anim.name else ("used" if i in used else "")
            if title:
                canvas.create_text(x + 40, y + 8, text=title, fill="#dddddd", anchor="nw", tags=(tag,))

            if self.spriteset and anim.frame_ids:
                for n, frame_id in enumerate(anim.frame_ids[:4]):
                    frame_img = self.spriteset.get(frame_id)
                    if frame_img:
                        img = frame_img.image.copy()
                        img.thumbnail((30, 30), Image.Resampling.NEAREST)
                        photo = ImageTk.PhotoImage(img)
                        refs.append(photo)
                        canvas.create_image(x + 20 + n * 22, y + 48, image=photo, anchor="center", tags=(tag,))
                canvas.create_text(x + 8, y + 72, text=",".join(map(str, anim.frame_ids[:6])), fill="#a8a8a8", anchor="nw", tags=(tag,))
            else:
                canvas.create_text(x + 8, y + 45, text="no frames", fill="#777777", anchor="nw", tags=(tag,))

            canvas.tag_bind(tag, "<Enter>", lambda _e, t=tag: set_hover(t, True))
            canvas.tag_bind(tag, "<Leave>", lambda _e, t=tag: set_hover(t, False))
            canvas.tag_bind(tag, "<Button-1>", lambda _e, anim_id=i: choose_anim(anim_id))
            canvas.tag_bind(tag, "<Double-1>", lambda _e, anim_id=i: choose_anim(anim_id))

        rows = max(1, (len(visible_anims) + cols - 1) // cols)
        canvas.configure(scrollregion=(0, 0, cols * cell_w, rows * cell_h))
        win._photo_refs = refs  # keep image references alive

    def apply_event_concept_to_raw(self, raw: bytearray, concept: str) -> None:
        self.apply_concept_template_to_raw(raw, concept)
        vars = getattr(self, "event_concept_vars", {})
        def get_int(key, default=0):
            var = vars.get(key)
            if var is None:
                return default
            try:
                return int(var.get())
            except Exception:
                return default
        def get_bool(key, default=False):
            var = vars.get(key)
            if var is None:
                return default
            return bool(var.get())
        def combo_num(key, default=0):
            var = vars.get(key)
            if var is None:
                return default
            try:
                return int(str(var.get()).split(":", 1)[0])
            except Exception:
                return default

        if concept == "Unused / empty":
            raw[:] = bytes(ELENGTH)
            return
        if concept in {"Touch pickup / item", "Shootable pickup / container"}:
            raw[10] = combo_num("pickup_modifier", raw[10])
            shootable = get_bool("shootable", concept == "Shootable pickup / container")
            raw[9] = max(1, get_int("strength", raw[9] or 1)) if shootable else 0
            raw[11] = get_int("points", raw[11])
            raw[21] = get_int("sound", raw[21])
        elif concept == "Enemy / hazard":
            raw[10] = 0
            raw[4] = combo_num("movement", raw[4])
            raw[9] = max(1, get_int("strength", raw[9] or 1))
            raw[11] = get_int("points", raw[11])
            raw[12] = max(0, min(31, get_int("bullet", raw[12])))
            raw[13] = get_int("bullet_period", raw[13])
            raw[15] = max(0, min(255, get_int("speed", raw[15] + 1) - 1))
        elif concept == "Destructible block":
            raw[4] = 21
            raw[10] = 7
            raw[9] = max(1, get_int("strength", raw[9] or 1))
            raw[22] = get_int("destroy_tile", raw[22])
            raw[24] = get_int("piece_size", raw[24])
            raw[25] = get_int("pieces", raw[25])
            raw[21] = get_int("sound", raw[21])
        elif concept == "Spring / bounce":
            raw[10] = 29
            raw[9] = 0
            raw[8] = get_int("magnitude_signed", _signed_byte(raw[8])) & 0xFF
            raw[21] = get_int("sound", raw[21])
        elif concept == "Warp trigger":
            raw[10] = 13
            raw[9] = 0
            raw[22] = get_int("warp_x", raw[22])
            raw[23] = get_int("warp_y", raw[23])
            raw[21] = get_int("sound", raw[21])
        elif concept == "Conveyor belt":
            raw[10] = 28
            raw[9] = 0
            raw[8] = get_int("magnitude_signed", _signed_byte(raw[8])) & 0xFF
            raw[21] = get_int("sound", raw[21])
        elif concept == "Path-moving object":
            raw[4] = combo_num("movement", raw[4])
            raw[22] = max(0, min(15, get_int("path_index", raw[22])))
            raw[9] = get_int("strength", raw[9])
        elif concept == "Raw / advanced":
            raw[4] = combo_num("movement", raw[4])
            raw[10] = combo_num("modifier", raw[10])
            raw[9] = get_int("strength", raw[9])
            raw[11] = get_int("points", raw[11])
            raw[8] = get_int("magnitude", raw[8])
            raw[22] = get_int("multi_a", raw[22])
            raw[23] = get_int("multi_b", raw[23])

        # Visual fields.
        for key, idx in [("left_anim", 5), ("right_anim", 6), ("finish_left", 28), ("finish_right", 29), ("shoot_left", 30), ("shoot_right", 31)]:
            if key in vars:
                raw[idx] = max(0, min(127, get_int(key, raw[idx])))
        if "anim_speed" in vars:
            raw[17] = max(0, min(255, get_int("anim_speed", raw[17] + 1) - 1))

    def _build_event_defs_tab(self) -> None:
        # This method builds the EVENT DEFS workspace. It has two internal tabs:
        # a concept editor for normal work and a raw/interpretation view for diagnostics.
        concept_tab = ttk.Frame(self.tabs, padding=8)
        raw_tab = ttk.Frame(self.tabs, padding=8)
        self.event_concept_tab = concept_tab
        self.event_raw_tab = raw_tab
        self.global_event_defs_tab = concept_tab
        self.tabs.add(concept_tab, text="Concept editor")
        self.tabs.add(raw_tab, text="Raw / interpretation")

        selector = ttk.Frame(concept_tab)
        selector.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(selector, text="Event").pack(side=tk.LEFT)
        self.event_def_combo = ttk.Combobox(selector, state="readonly", width=46)
        self.event_def_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        self.event_def_combo.bind("<<ComboboxSelected>>", self.on_event_def_combo_select)
        ttk.Button(selector, text="New type", command=self.create_new_object_type).pack(side=tk.LEFT)
        ttk.Button(selector, text="Duplicate as new", command=self.duplicate_event_definition_as_new).pack(side=tk.LEFT, padx=(6, 0))

        concept_row = ttk.Frame(concept_tab)
        concept_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(concept_row, text="Concept").pack(side=tk.LEFT)
        self.event_concept_var = tk.StringVar(value="Unused / empty")
        self.event_concept_combo = ttk.Combobox(concept_row, state="readonly", values=EVENT_CONCEPTS, textvariable=self.event_concept_var, width=32)
        self.event_concept_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.event_concept_combo.bind("<<ComboboxSelected>>", self.on_event_concept_changed)
        ttk.Button(concept_row, text="Apply", command=self.apply_event_definition_from_ui).pack(side=tk.LEFT)
        ttk.Button(concept_row, text="Refresh", command=lambda: self.render_event_definition(self._editing_event_id)).pack(side=tk.LEFT, padx=(6, 0))

        self.event_concept_frame = ttk.LabelFrame(concept_tab, text="Object concept", padding=6)
        self.event_concept_frame.pack(fill=tk.BOTH, expand=True)
        self.event_concept_vars: Dict[str, Any] = {}

        raw_selector = ttk.Frame(raw_tab)
        raw_selector.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(raw_selector, text="Same selected event as Concept editor").pack(side=tk.LEFT)
        ttk.Button(raw_selector, text="Refresh", command=lambda: self.render_event_definition(self._editing_event_id)).pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.PanedWindow(raw_tab, orient=tk.VERTICAL)
        body.pack(fill=tk.BOTH, expand=True)

        interp_frame = ttk.LabelFrame(body, text="Interpretation")
        body.add(interp_frame, weight=1)
        self.event_semantic_text = tk.Text(interp_frame, height=8, wrap="word")
        self.event_semantic_text.pack(fill=tk.BOTH, expand=True)

        raw_frame = ttk.LabelFrame(body, text="Raw editor")
        body.add(raw_frame, weight=1)
        self.event_raw_fields_frame = ttk.Frame(raw_frame)
        self.event_raw_fields_frame.pack(fill=tk.X, pady=(4, 4))
        self.event_def_edit_vars: Dict[int, tk.IntVar] = {}
        self.event_def_field_labels: Dict[int, ttk.Label] = {}
        for n, idx in enumerate(EDITABLE_EVENT_FIELD_INDICES):
            var = tk.IntVar(value=0)
            self.event_def_edit_vars[idx] = var
            label = ttk.Label(self.event_raw_fields_frame, text=EVENT_FIELD_NAMES[idx])
            self.event_def_field_labels[idx] = label
            label.grid(row=n // 3, column=(n % 3) * 2, sticky="w", padx=(0, 4), pady=1)
            ttk.Spinbox(self.event_raw_fields_frame, from_=0, to=255, width=6, textvariable=var).grid(row=n // 3, column=(n % 3) * 2 + 1, sticky="w", padx=(0, 10), pady=1)
        ttk.Button(raw_frame, text="Apply raw fields", command=self.apply_event_definition_from_ui).pack(anchor="w", pady=(4, 4))
        self.event_def_text = tk.Text(raw_frame, height=8, wrap="none")
        self.event_def_text.pack(fill=tk.BOTH, expand=True)

    def on_event_concept_changed(self, _event: tk.Event = None) -> None:
        if not self.level:
            return
        event_id = max(0, min(126, int(self._editing_event_id)))
        self.rebuild_event_concept_editor(event_id, self.level.event_types[event_id])

    def render_event_definition(self, event_id: int) -> None:
        if not self.level or not hasattr(self, "event_def_text"):
            return
        event_id = max(0, min(126, int(event_id)))
        self._editing_event_id = event_id
        raw = self.level.event_types[event_id]
        name = self.level.event_names[event_id] if event_id < len(self.level.event_names) else ""
        evdef = EventDefinition(event_id, name, raw)

        if hasattr(self, "event_def_combo"):
            vals = self.event_def_combo["values"]
            if vals:
                self.event_def_combo.current(event_id)

        if hasattr(self, "event_def_edit_vars"):
            for idx, var in self.event_def_edit_vars.items():
                if idx < len(raw):
                    var.set(raw[idx])
            if hasattr(self, "event_def_field_labels"):
                for idx, label in self.event_def_field_labels.items():
                    label.configure(text=event_field_label_for(raw, idx))

        if hasattr(self, "event_concept_var"):
            self.event_concept_var.set(infer_event_concept(event_id, raw, name))
        if hasattr(self, "event_concept_frame"):
            self.rebuild_event_concept_editor(event_id, raw)

        if hasattr(self, "event_def_title"):
            self.event_def_title.configure(text=f"Event {event_id:03d}: {friendly_event_name(evdef)}")

        semantic_lines = semantic_event_lines(event_id, raw, name)
        semantic_lines.append("")
        semantic_lines.append(f"Used by placements in this level: {self.event_usage_counts().get(event_id, 0)}")
        if hasattr(self, "event_semantic_text"):
            self.event_semantic_text.configure(state="normal")
            self.event_semantic_text.delete("1.0", tk.END)
            self.event_semantic_text.insert("1.0", "\n".join(semantic_lines))
            self.event_semantic_text.configure(state="disabled")

        lines = [f"event_id: {event_id}", f"name: {name or '(unnamed)'}", f"friendly: {friendly_event_name(evdef)}"]
        if is_reserved_engine_event(event_id):
            info = RESERVED_ENGINE_EVENTS[event_id]
            lines.extend([
                "",
                "RESERVED ENGINE MARKER:",
                f"  {info['summary']}",
                f"  {info['editor_hint']}",
                "  The numeric event ID is what matters for the special behavior.",
                "  The 32-byte definition is still shown below for completeness.",
            ])
        lines.extend(["", "bytes:"])
        for i, value in enumerate(raw):
            label = EVENT_FIELD_NAMES[i] if i < len(EVENT_FIELD_NAMES) else f"byte_{i:02d}"
            editable = "" if i in EDITABLE_EVENT_FIELD_INDICES else "  (unused/not editable)"
            lines.append(f"  {i:02d} {label:<16} = {value:3d}  0x{value:02X}{editable}")

        if len(raw) >= 32:
            lines.extend([
                "",
                "decoded fields:",
                f"  category    = {semantic_event_category(event_id, raw, name)}",
                f"  concept     = {infer_event_concept(event_id, raw, name)}",
                f"  movement    = {raw[4]} ({movement_meaning_detail(raw[4])[0]})",
                f"  modifier    = {raw[10]} ({modifier_meaning(raw[10])[0]})",
                f"  left_anim   = {raw[5]}",
                f"  right_anim  = {raw[6]}",
                f"  magnitude   = {raw[8]} / signed {_signed_byte(raw[8])}",
                f"  strength    = {raw[9]}",
                f"  points      = {raw[11]}",
                f"  bullet      = {raw[12]} ({bullet_type_label(raw[12])})",
                f"  bullet_per. = {raw[13]}",
                f"  speed       = {raw[15] + 1}",
                f"  anim_speed  = {raw[17] + 1}",
                f"  sound       = {raw[21]}",
                f"  multi_a/b   = {raw[22]} / {raw[23]}",
                f"  pieces      = size {raw[24]}, count {raw[25]}",
                f"  angle       = {raw[26]}",
                f"  finish      = {raw[28]} / {raw[29]}",
                f"  shoot       = {raw[30]} / {raw[31]}",
            ])
            for label, anim_id in [("left", raw[5]), ("right", raw[6]), ("left_finish", raw[28]), ("right_finish", raw[29]), ("left_shoot", raw[30]), ("right_shoot", raw[31])]:
                anim = self.level.animation(anim_id) if self.level else None
                if anim:
                    lines.append(f"  {label:<12} anim {anim_id:03d}: len={anim.length}, frames={anim.frame_ids}")
        self.event_def_text.configure(state="normal")
        self.event_def_text.delete("1.0", tk.END)
        self.event_def_text.insert("1.0", "\n".join(lines))
        self.event_def_text.configure(state="disabled")

    def apply_event_definition_from_ui(self) -> None:
        if not self.level:
            return
        event_id = max(0, min(126, int(self._editing_event_id)))
        raw = bytearray(self.level.event_types[event_id])

        concept = self.event_concept_var.get() if hasattr(self, "event_concept_var") else infer_event_concept(event_id, raw)
        if concept == "Auto / keep current":
            concept = infer_event_concept(event_id, raw, self.level.event_names[event_id] if event_id < len(self.level.event_names) else "")

        if not is_reserved_engine_event(event_id):
            self.apply_event_concept_to_raw(raw, concept)

        # Advanced raw fields can override the concept editor when visible.
        if hasattr(self, "event_raw_fields_frame") and self.event_raw_fields_frame.winfo_ismapped():
            for idx, var in getattr(self, "event_def_edit_vars", {}).items():
                try:
                    raw[idx] = max(0, min(255, int(var.get())))
                except Exception:
                    pass

        self.level.event_types[event_id] = bytes(raw)
        self.set_dirty(True)
        self._event_preview_cache.clear()
        self.populate_events()
        self.refresh_event_def_selector()
        self.refresh_object_palette()
        self.refresh_objects()
        self.refresh_object_types()
        self.populate_animations()
        self.render_event_definition(event_id)
        self.render_map()
        self.refresh_validation()
        uses = self.event_usage_counts().get(event_id, 0)
        self.status.set(f"Applied Event {event_id:03d} as '{concept}'. It affects {uses} placed object(s) in this level.")

