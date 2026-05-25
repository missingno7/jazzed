from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with: python -m pip install pillow") from exc

from ..raw_data import *

class LevelLocalMixin:
    def _build_animations_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Animations")
        self.level_local_animations_tab = tab

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=3)

        columns = ("anim", "name", "len", "frames")
        self.anim_tree = ttk.Treeview(left, columns=columns, show="headings", height=24, selectmode="browse")
        for col, width, text in [("anim", 55, "Anim"), ("name", 140, "Name"), ("len", 42, "Len"), ("frames", 170, "Sprite frames")]:
            self.anim_tree.heading(col, text=text)
            self.anim_tree.column(col, width=width, stretch=(col == "frames"))
        self.anim_tree.pack(fill=tk.BOTH, expand=True)
        self.anim_tree.bind("<<TreeviewSelect>>", self.on_anim_tree_select)

        toolbar = ttk.Frame(right)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(toolbar, text="Apply", command=self.apply_animation_from_ui).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Refresh", command=self.populate_animations).pack(side=tk.LEFT, padx=(6, 0))

        meta = ttk.LabelFrame(right, text="Animation", padding=6)
        meta.pack(fill=tk.X, pady=(0, 6))
        self.anim_name_var = tk.StringVar(value="")
        ttk.Label(meta, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(meta, textvariable=self.anim_name_var, width=28).grid(row=0, column=1, sticky="ew")
        self.anim_length_label = ttk.Label(meta, text="Frames: 0 / 19")
        self.anim_length_label.grid(row=0, column=2, sticky="w", padx=(12, 0))
        meta.columnconfigure(1, weight=1)

        preview = ttk.LabelFrame(right, text="Preview", padding=6)
        preview.pack(fill=tk.X, pady=(0, 6))
        self.anim_preview_canvas = tk.Canvas(preview, height=116, background="#181818", highlightthickness=0)
        self.anim_preview_canvas.pack(fill=tk.X)
        self.anim_preview_canvas.bind("<Configure>", lambda _e: self.render_animation_preview())

        frame_box = ttk.LabelFrame(right, text="Frames", padding=6)
        frame_box.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        frame_tools = ttk.Frame(frame_box)
        frame_tools.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(frame_tools, text="Add from sprite atlas", command=self.add_animation_frame_from_atlas).pack(side=tk.LEFT)
        ttk.Button(frame_tools, text="Remove", command=self.remove_selected_animation_frame).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(frame_tools, text="Move up", command=lambda: self.move_selected_animation_frame(-1)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(frame_tools, text="Move down", command=lambda: self.move_selected_animation_frame(1)).pack(side=tk.LEFT, padx=(6, 0))

        frame_columns = ("index", "sprite", "x", "y")
        self.anim_frame_tree = ttk.Treeview(frame_box, columns=frame_columns, show="headings", height=8, selectmode="browse")
        for col, width, text in [("index", 52, "#"), ("sprite", 74, "Sprite"), ("x", 70, "X offset"), ("y", 70, "Y offset")]:
            self.anim_frame_tree.heading(col, text=text)
            self.anim_frame_tree.column(col, width=width, stretch=False)
        self.anim_frame_tree.pack(fill=tk.BOTH, expand=True)
        self.anim_frame_tree.bind("<<TreeviewSelect>>", self.on_anim_frame_select)

        frame_edit = ttk.Frame(frame_box)
        frame_edit.pack(fill=tk.X, pady=(6, 0))
        self.anim_frame_sprite_var = tk.IntVar(value=0)
        self.anim_frame_x_var = tk.IntVar(value=0)
        self.anim_frame_y_var = tk.IntVar(value=0)
        ttk.Label(frame_edit, text="Sprite").pack(side=tk.LEFT)
        ttk.Spinbox(frame_edit, from_=0, to=255, width=7, textvariable=self.anim_frame_sprite_var).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(frame_edit, text="Atlas...", command=self.pick_sprite_for_selected_animation_frame).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(frame_edit, text="X offset").pack(side=tk.LEFT)
        ttk.Spinbox(frame_edit, from_=-128, to=127, width=7, textvariable=self.anim_frame_x_var).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(frame_edit, text="Y offset").pack(side=tk.LEFT)
        ttk.Spinbox(frame_edit, from_=-128, to=127, width=7, textvariable=self.anim_frame_y_var).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Button(frame_edit, text="Update frame", command=self.update_selected_animation_frame).pack(side=tk.LEFT)

        self.anim_detail_text = tk.Text(right, height=6, wrap="word")
        self.anim_detail_text.pack(fill=tk.BOTH, expand=False)

    def _build_bullets_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.bullets_tab = tab
        self.tabs.add(tab, text="Bullets")

        body = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        right = ttk.Frame(body)
        body.add(right, weight=3)

        columns = ("id", "name", "sprites", "finish", "behaviour")
        self.bullet_tree = ttk.Treeview(left, columns=columns, show="headings", height=22, selectmode="browse")
        for col, width, title in [
            ("id", 42, "ID"), ("name", 150, "Name"), ("sprites", 120, "Sprites"),
            ("finish", 70, "Finish"), ("behaviour", 70, "Behaviour"),
        ]:
            self.bullet_tree.heading(col, text=title)
            self.bullet_tree.column(col, width=width, stretch=(col == "name"))
        self.bullet_tree.pack(fill=tk.BOTH, expand=True)
        self.bullet_tree.bind("<<TreeviewSelect>>", self.on_bullet_tree_select)

        top = ttk.Frame(right)
        top.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(top, text="Apply", command=self.apply_bullet_definition_from_ui).pack(side=tk.LEFT)
        ttk.Button(top, text="Refresh", command=self.populate_bullets).pack(side=tk.LEFT, padx=(6, 0))

        self.bullet_edit_frame = ttk.LabelFrame(right, text="Bullet definition", padding=6)
        self.bullet_edit_frame.pack(fill=tk.X, pady=(0, 6))
        self.bullet_edit_vars: Dict[str, Any] = {}
        self.bullet_sound_combos: Dict[str, ttk.Combobox] = {}
        self._build_bullet_fields(self.bullet_edit_frame)

        preview_frame = ttk.LabelFrame(right, text="Sprite preview", padding=6)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        self.bullet_preview_frame = preview_frame

    def _build_bullet_fields(self, parent: ttk.Frame) -> None:
        self.bullet_edit_vars.clear()
        self.bullet_sound_combos.clear()
        row = 0
        self.bullet_name_var = tk.StringVar(value="")
        self.bullet_edit_vars["name"] = self.bullet_name_var
        ttk.Label(parent, text="Name").grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(parent, textvariable=self.bullet_name_var, width=28).grid(row=row, column=1, columnspan=5, sticky="ew", pady=2)
        row += 1
        for i, dname in enumerate(["left", "right", "lower-left", "lower-right"]):
            ttk.Label(parent, text=f"{dname} sprite/event").grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.IntVar(value=0)
            self.bullet_edit_vars[f"sprite_{i}"] = var
            field = ttk.Frame(parent)
            field.grid(row=row, column=1, sticky="w", pady=2)
            ttk.Spinbox(field, from_=0, to=255, width=7, textvariable=var).pack(side=tk.LEFT)
            ttk.Button(field, text="Sprite atlas...", command=lambda k=f"sprite_{i}": self.open_sprite_picker_for_bullet(k)).pack(side=tk.LEFT, padx=(4, 0))
            ttk.Label(parent, text="x").grid(row=row, column=2, sticky="e")
            xv = tk.IntVar(value=0)
            self.bullet_edit_vars[f"xspeed_{i}"] = xv
            ttk.Spinbox(parent, from_=-128, to=127, width=6, textvariable=xv).grid(row=row, column=3, sticky="w")
            ttk.Label(parent, text="y").grid(row=row, column=4, sticky="e")
            yv = tk.IntVar(value=0)
            self.bullet_edit_vars[f"yspeed_{i}"] = yv
            ttk.Spinbox(parent, from_=-128, to=127, width=6, textvariable=yv).grid(row=row, column=5, sticky="w")
            ttk.Label(parent, text="gravity").grid(row=row, column=6, sticky="e")
            gv = tk.IntVar(value=0)
            self.bullet_edit_vars[f"gravity_{i}"] = gv
            ttk.Spinbox(parent, from_=-128, to=127, width=6, textvariable=gv).grid(row=row, column=7, sticky="w")
            row += 1
        for key, label, frm, to in [
            ("finish_anim", "Finish animation", 0, 127), ("finish_sound", "Finish sound", 0, 255),
            ("behaviour", "Behaviour", 0, 255), ("start_sound", "Start sound", 0, 255),
        ]:
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.StringVar(value=self.sound_choice_value(0)) if key in {"finish_sound", "start_sound"} else tk.IntVar(value=0)
            self.bullet_edit_vars[key] = var
            field = ttk.Frame(parent)
            field.grid(row=row, column=1, sticky="w", pady=2)
            if key in {"finish_sound", "start_sound"}:
                combo = ttk.Combobox(field, state="readonly", values=self.sound_choice_values(), textvariable=var, width=24)
                combo.pack(side=tk.LEFT)
                self.bullet_sound_combos[key] = combo
            else:
                ttk.Spinbox(field, from_=frm, to=to, width=7, textvariable=var).pack(side=tk.LEFT)
            if key == "finish_anim":
                ttk.Button(field, text="Atlas...", command=lambda k=key: self.open_animation_picker_for_bullet(k)).pack(side=tk.LEFT, padx=(4, 0))
            if key in {"finish_sound", "start_sound"}:
                ttk.Button(field, text="Play", command=lambda v=var: self.play_sound_id(self.sound_id_from_choice(v.get()))).pack(side=tk.LEFT, padx=(4, 0))
            row += 1

    def populate_bullets(self) -> None:
        if not hasattr(self, "bullet_tree"):
            return
        self.bullet_tree.delete(*self.bullet_tree.get_children())
        if not self.level:
            return
        used = {ev.raw[12] for ev in self.level.event_catalog()[1:] if ev.raw[12]}
        for b in self.level.bullet_defs:
            suffix = " *used" if b.bullet_id in used else ""
            self.bullet_tree.insert("", tk.END, iid=str(b.bullet_id), values=(b.bullet_id, bullet_display_name(b) + suffix, "/".join(map(str, b.sprites)), b.finish_anim, b.behaviour))
        if not self.bullet_tree.selection() and self.level.bullet_defs:
            self.bullet_tree.selection_set("0")
            self.on_bullet_tree_select(None)

    def on_bullet_tree_select(self, _event: tk.Event = None) -> None:
        if not self.level or not hasattr(self, "bullet_tree"):
            return
        sel = self.bullet_tree.selection()
        if not sel:
            return
        bullet_id = int(sel[0])
        b = self.level.bullet_def(bullet_id)
        self._editing_bullet_id = bullet_id
        self.bullet_name_var.set(b.name)
        for i in range(4):
            self.bullet_edit_vars[f"sprite_{i}"].set(b.sprites[i])
            self.bullet_edit_vars[f"xspeed_{i}"].set(b.xspeeds[i])
            self.bullet_edit_vars[f"yspeed_{i}"].set(b.yspeeds[i])
            self.bullet_edit_vars[f"gravity_{i}"].set(b.gravities[i])
        self.bullet_edit_vars["finish_anim"].set(b.finish_anim)
        self.bullet_edit_vars["finish_sound"].set(self.sound_choice_value(b.finish_sound))
        self.bullet_edit_vars["behaviour"].set(b.behaviour)
        self.bullet_edit_vars["start_sound"].set(self.sound_choice_value(b.start_sound))
        self.refresh_bullet_sound_choices()
        self.render_bullet_preview(b)

    def refresh_bullet_sound_choices(self) -> None:
        values = self.sound_choice_values()
        for combo in getattr(self, "bullet_sound_combos", {}).values():
            combo.configure(values=values)

    def render_bullet_preview(self, b: BulletDefinition) -> None:
        if not hasattr(self, "bullet_preview_frame"):
            return
        for child in self.bullet_preview_frame.winfo_children():
            child.destroy()
        self._bullet_photo_refs = []
        ttk.Label(self.bullet_preview_frame, text=f"Bullet {b.bullet_id}: {bullet_display_name(b)}").pack(anchor="w")
        strip = ttk.Frame(self.bullet_preview_frame)
        strip.pack(fill=tk.X, pady=(6, 0))
        for i, sprite_id in enumerate(b.sprites):
            cell = ttk.LabelFrame(strip, text=bullet_direction_name(i), padding=4)
            cell.pack(side=tk.LEFT, padx=(0, 6), anchor="n")
            frame = self.spriteset.get(sprite_id) if self.spriteset and sprite_id else None
            if frame:
                img = frame.image.copy()
                img.thumbnail((48, 48), Image.Resampling.NEAREST)
                canvas = Image.new("RGBA", (54, 54), (0, 0, 0, 0))
                canvas.alpha_composite(img, ((54 - img.width) // 2, (54 - img.height) // 2))
                photo = ImageTk.PhotoImage(canvas)
                self._bullet_photo_refs.append(photo)
                ttk.Label(cell, image=photo).pack()
            else:
                ttk.Label(cell, text="no sprite").pack()
            ttk.Label(cell, text=f"S{sprite_id}\nx={b.xspeeds[i]} y={b.yspeeds[i]}\ng={b.gravities[i]}").pack()

    def apply_bullet_definition_from_ui(self) -> None:
        if not self.level:
            return
        bullet_id = max(0, min(BULLETS - 1, int(getattr(self, "_editing_bullet_id", 0))))
        raw = bytearray(BLENGTH)
        for i in range(4):
            raw[i] = max(0, min(255, int(self.bullet_edit_vars[f"sprite_{i}"].get())))
            raw[4 + i] = int(self.bullet_edit_vars[f"xspeed_{i}"].get()) & 0xFF
            raw[8 + i] = int(self.bullet_edit_vars[f"yspeed_{i}"].get()) & 0xFF
            raw[12 + i] = int(self.bullet_edit_vars[f"gravity_{i}"].get()) & 0xFF
        raw[16] = max(0, min(127, int(self.bullet_edit_vars["finish_anim"].get())))
        raw[17] = self.sound_id_from_choice(self.bullet_edit_vars["finish_sound"].get())
        raw[18] = max(0, min(255, int(self.bullet_edit_vars["behaviour"].get())))
        raw[19] = self.sound_id_from_choice(self.bullet_edit_vars["start_sound"].get())
        name = self.bullet_name_var.get().strip()[:20]
        self.level.bullet_names[bullet_id] = name
        self.level.bullet_defs[bullet_id] = BulletDefinition(bullet_id, name, bytes(raw))
        self.set_dirty(True)
        self.populate_bullets()
        self.bullet_tree.selection_set(str(bullet_id))
        self.on_bullet_tree_select(None)
        self.status.set(f"Applied bullet definition {bullet_id}.")

    def open_sprite_picker_for_bullet(self, key: str) -> None:
        if not self.spriteset:
            return
        win = tk.Toplevel(self)
        win.title(f"Choose sprite for {key}")
        win.geometry("900x640")
        canvas = tk.Canvas(win, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=yscroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        refs: List[ImageTk.PhotoImage] = []
        cell = 72
        cols = 12
        for sid, frame in enumerate(self.spriteset.sprites[:256]):
            x = (sid % cols) * cell
            y = (sid // cols) * cell
            tag = f"sprite_pick_{sid}"
            canvas.create_rectangle(x + 2, y + 2, x + cell - 2, y + cell - 2, fill="#202020", outline="#555555", tags=(tag, f"{tag}_bg"))
            canvas.create_text(x + 4, y + 4, text=f"S{sid}", fill="#ffff80", anchor="nw", tags=(tag,))
            if frame:
                img = frame.image.copy()
                img.thumbnail((40, 40), Image.Resampling.NEAREST)
                photo = ImageTk.PhotoImage(img)
                refs.append(photo)
                canvas.create_image(x + cell // 2, y + 42, image=photo, anchor="center", tags=(tag,))
            def hover_on(_e, t=tag):
                canvas.itemconfigure(f"{t}_bg", fill="#303030", outline="#ffff00", width=3)
                canvas.config(cursor="hand2")
            def hover_off(_e, t=tag):
                canvas.itemconfigure(f"{t}_bg", fill="#202020", outline="#555555", width=1)
                canvas.config(cursor="")
            def choose(_e, sprite_id=sid):
                self.bullet_edit_vars[key].set(sprite_id)
                win.destroy()
            canvas.tag_bind(tag, "<Enter>", hover_on)
            canvas.tag_bind(tag, "<Leave>", hover_off)
            canvas.tag_bind(tag, "<Button-1>", choose)
        canvas.configure(scrollregion=(0, 0, cols * cell, ((256 + cols - 1) // cols) * cell))
        win._photo_refs = refs

    def open_animation_picker_for_bullet(self, key: str) -> None:
        if not self.level:
            return
        original_vars = getattr(self, "event_concept_vars", None)
        self.event_concept_vars = self.bullet_edit_vars
        try:
            self.open_animation_picker_for(key)
        finally:
            self.event_concept_vars = original_vars if original_vars is not None else {}

    def _build_paths_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Paths")
        self.level_local_paths_tab = tab
        ttk.Label(tab, text="Special event paths: 16 level-local movement paths. Display is read-only/diagnostic for now; use it to understand platforms, flying enemies and scripted objects.").pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 4))
        ttk.Label(row, text="Selected path").pack(side=tk.LEFT)
        self.path_combo = ttk.Combobox(row, state="readonly", width=24, textvariable=self.selected_path)
        self.path_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_select)
        ttk.Checkbutton(row, text="Show path overlay", variable=self.show_paths, command=self.render_map).pack(side=tk.LEFT, padx=(10, 0))
        self.path_canvas = tk.Canvas(tab, background="#181818", height=220, highlightthickness=0)
        self.path_canvas.pack(fill=tk.X, expand=False, pady=(4, 6))
        edit = ttk.LabelFrame(tab, text="Editable path deltas", padding=4)
        edit.pack(fill=tk.BOTH, expand=False, pady=(4, 4))
        ttk.Label(edit, text="One point/delta per line: dx dy. X will be stored in 4-pixel units because that is how JJ1/Jazz 1/OpenJazz-reference reads paths.").pack(anchor="w")
        self.path_edit_text = tk.Text(edit, height=7, wrap="none")
        self.path_edit_text.pack(fill=tk.BOTH, expand=True, pady=(3, 3))
        ttk.Button(edit, text="Apply path in memory", command=self.apply_path_from_ui).pack(anchor="w")
        self.path_text = tk.Text(tab, height=8, wrap="none")
        self.path_text.pack(fill=tk.BOTH, expand=True)

    def populate_animations(self) -> None:
        if not hasattr(self, "anim_tree"):
            return
        self.anim_tree.delete(*self.anim_tree.get_children())
        if not self.level:
            return
        used = set()
        for ev in self.level.event_catalog()[1:]:
            for idx in [5, 6, 28, 29, 30, 31]:
                if idx < len(ev.raw) and ev.raw[idx]:
                    used.add(ev.raw[idx] & 0x7F)
        for anim in self.level.animations:
            if anim.length <= 0 and anim.anim_id not in used and not anim.name:
                continue
            suffix = " *used" if anim.anim_id in used else ""
            self.anim_tree.insert("", tk.END, iid=str(anim.anim_id), values=(anim.anim_id, (anim.name or "") + suffix, anim.length, ",".join(map(str, anim.frame_ids))))

    def on_anim_tree_select(self, _event: tk.Event) -> None:
        if not self.level:
            return
        selection = self.anim_tree.selection()
        if not selection:
            return
        anim_id = int(selection[0])
        anim = self.level.animation(anim_id)
        if not anim:
            return
        self._editing_anim_id = anim_id
        if hasattr(self, "anim_name_var"):
            self.anim_name_var.set(anim.name or "")
        self.populate_animation_frame_tree(anim)
        self.render_animation_preview()
        details = [
            f"Animation {anim_id}",
            f"name: {anim.name or '(unnamed)'}",
            f"length: {anim.length}",
            f"sprite frames: {anim.frame_ids}",
            f"frame x offsets: {anim.frame_x}",
            f"frame y offsets: {anim.frame_y}",
        ]
        users = []
        for ev in self.level.event_catalog()[1:]:
            raw = ev.raw
            labels = []
            for label, idx in [("left",5),("right",6),("finishL",28),("finishR",29),("shootL",30),("shootR",31)]:
                if idx < len(raw) and (raw[idx] & 0x7F) == anim_id:
                    labels.append(label)
            if labels:
                users.append(f"event {ev.event_id:03d} {ev.name or '(unnamed)'} uses as {','.join(labels)}")
        details.append("")
        details.append("Used by:")
        details.extend(users[:25] or ["no obvious event reference"])
        self.anim_detail_text.configure(state="normal")
        self.anim_detail_text.delete("1.0", tk.END)
        self.anim_detail_text.insert("1.0", "\n".join(details))
        self.anim_detail_text.configure(state="disabled")

    def populate_animation_frame_tree(self, anim: AnimationDefinition) -> None:
        if not hasattr(self, "anim_frame_tree"):
            return
        self.anim_frame_tree.delete(*self.anim_frame_tree.get_children())
        for i, (sprite_id, xoff, yoff) in enumerate(zip(anim.frame_ids, anim.frame_x, anim.frame_y)):
            self.anim_frame_tree.insert("", tk.END, iid=str(i), values=(i, sprite_id, xoff, yoff))
        if hasattr(self, "anim_length_label"):
            self.anim_length_label.configure(text=f"Frames: {anim.length} / 19")
        if anim.length:
            self.anim_frame_tree.selection_set("0")
            self.on_anim_frame_select(None)

    def _animation_frame_rows_from_tree(self) -> List[Tuple[int, int, int]]:
        rows: List[Tuple[int, int, int]] = []
        if not hasattr(self, "anim_frame_tree"):
            return rows
        for item in self.anim_frame_tree.get_children():
            values = self.anim_frame_tree.item(item, "values")
            if len(values) >= 4:
                rows.append((int(values[1]), int(values[2]), int(values[3])))
        return rows

    def _rebuild_animation_frame_tree(self, rows: List[Tuple[int, int, int]], select_index: Optional[int] = None) -> None:
        self.anim_frame_tree.delete(*self.anim_frame_tree.get_children())
        for i, (sprite_id, xoff, yoff) in enumerate(rows[:19]):
            self.anim_frame_tree.insert("", tk.END, iid=str(i), values=(i, sprite_id, xoff, yoff))
        if hasattr(self, "anim_length_label"):
            self.anim_length_label.configure(text=f"Frames: {len(rows[:19])} / 19")
        if rows:
            idx = 0 if select_index is None else max(0, min(len(rows[:19]) - 1, select_index))
            self.anim_frame_tree.selection_set(str(idx))
            self.on_anim_frame_select(None)
        self.render_animation_preview()

    def on_anim_frame_select(self, _event: tk.Event = None) -> None:
        if not hasattr(self, "anim_frame_tree"):
            return
        sel = self.anim_frame_tree.selection()
        if not sel:
            return
        values = self.anim_frame_tree.item(sel[0], "values")
        if len(values) >= 4:
            self.anim_frame_sprite_var.set(int(values[1]))
            self.anim_frame_x_var.set(int(values[2]))
            self.anim_frame_y_var.set(int(values[3]))

    def update_selected_animation_frame(self) -> None:
        sel = self.anim_frame_tree.selection() if hasattr(self, "anim_frame_tree") else ()
        if not sel:
            return
        idx = int(sel[0])
        rows = self._animation_frame_rows_from_tree()
        if 0 <= idx < len(rows):
            rows[idx] = (
                max(0, min(255, int(self.anim_frame_sprite_var.get()))),
                max(-128, min(127, int(self.anim_frame_x_var.get()))),
                max(-128, min(127, int(self.anim_frame_y_var.get()))),
            )
            self._rebuild_animation_frame_tree(rows, idx)

    def add_animation_frame_from_atlas(self) -> None:
        self.open_sprite_picker_for_animation(lambda sprite_id: self._append_animation_frame(sprite_id))

    def _append_animation_frame(self, sprite_id: int) -> None:
        rows = self._animation_frame_rows_from_tree()
        if len(rows) >= 19:
            messagebox.showinfo("Animation", "JJ1 animation definitions can store at most 19 frames.")
            return
        rows.append((max(0, min(255, int(sprite_id))), 0, 0))
        self._rebuild_animation_frame_tree(rows, len(rows) - 1)

    def pick_sprite_for_selected_animation_frame(self) -> None:
        sel = self.anim_frame_tree.selection() if hasattr(self, "anim_frame_tree") else ()
        if not sel:
            return
        idx = int(sel[0])
        self.open_sprite_picker_for_animation(lambda sprite_id: self._set_animation_frame_sprite(idx, sprite_id))

    def _set_animation_frame_sprite(self, idx: int, sprite_id: int) -> None:
        rows = self._animation_frame_rows_from_tree()
        if 0 <= idx < len(rows):
            _old, xoff, yoff = rows[idx]
            rows[idx] = (max(0, min(255, int(sprite_id))), xoff, yoff)
            self._rebuild_animation_frame_tree(rows, idx)

    def remove_selected_animation_frame(self) -> None:
        sel = self.anim_frame_tree.selection() if hasattr(self, "anim_frame_tree") else ()
        if not sel:
            return
        idx = int(sel[0])
        rows = self._animation_frame_rows_from_tree()
        if 0 <= idx < len(rows):
            rows.pop(idx)
            self._rebuild_animation_frame_tree(rows, min(idx, len(rows) - 1) if rows else None)

    def move_selected_animation_frame(self, delta: int) -> None:
        sel = self.anim_frame_tree.selection() if hasattr(self, "anim_frame_tree") else ()
        if not sel:
            return
        idx = int(sel[0])
        rows = self._animation_frame_rows_from_tree()
        new_idx = idx + int(delta)
        if 0 <= idx < len(rows) and 0 <= new_idx < len(rows):
            rows[idx], rows[new_idx] = rows[new_idx], rows[idx]
            self._rebuild_animation_frame_tree(rows, new_idx)

    def render_animation_preview(self) -> None:
        if not hasattr(self, "anim_preview_canvas"):
            return
        canvas = self.anim_preview_canvas
        canvas.delete("all")
        self._anim_preview_photo_refs = []
        rows = self._animation_frame_rows_from_tree()
        canvas.create_line(0, 78, max(500, canvas.winfo_width()), 78, fill="#383838")
        if not rows:
            canvas.create_text(12, 18, text="Empty animation", fill="#dddddd", anchor="w")
            return
        cell = 72
        for i, (sprite_id, xoff, yoff) in enumerate(rows[:12]):
            x = 8 + i * cell
            origin_x = x + 34
            origin_y = 78
            canvas.create_line(origin_x - 8, origin_y, origin_x + 8, origin_y, fill="#606060")
            canvas.create_line(origin_x, origin_y - 8, origin_x, origin_y + 8, fill="#606060")
            frame = self.spriteset.get(sprite_id) if self.spriteset and sprite_id else None
            if frame:
                img = frame.image.copy()
                img.thumbnail((48, 48), Image.Resampling.NEAREST)
                photo = ImageTk.PhotoImage(img)
                self._anim_preview_photo_refs.append(photo)
                canvas.create_image(origin_x + xoff, origin_y + yoff, image=photo, anchor="s")
            else:
                canvas.create_rectangle(origin_x - 16 + xoff, origin_y - 32 + yoff, origin_x + 16 + xoff, origin_y + yoff, outline="#777777")
                canvas.create_text(origin_x + xoff, origin_y - 16 + yoff, text=f"S{sprite_id}", fill="#888888")
            canvas.create_text(x + 4, 8, text=f"#{i}", fill="#ffff80", anchor="nw")
            canvas.create_text(x + 4, 96, text=f"x{xoff} y{yoff}", fill="#b8b8b8", anchor="nw")

    def open_sprite_picker_for_animation(self, callback) -> None:
        if not self.spriteset:
            return
        win = tk.Toplevel(self)
        win.title("Choose animation sprite frame")
        win.geometry("900x640")
        canvas = tk.Canvas(win, background="#181818", highlightthickness=0)
        yscroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=yscroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        refs: List[ImageTk.PhotoImage] = []
        cell = 72
        cols = 12
        for sid, frame in enumerate(self.spriteset.sprites[:256]):
            x = (sid % cols) * cell
            y = (sid // cols) * cell
            tag = f"anim_sprite_pick_{sid}"
            canvas.create_rectangle(x + 2, y + 2, x + cell - 2, y + cell - 2, fill="#202020", outline="#555555", tags=(tag, f"{tag}_bg"))
            canvas.create_text(x + 4, y + 4, text=f"S{sid}", fill="#ffff80", anchor="nw", tags=(tag,))
            if frame:
                img = frame.image.copy()
                img.thumbnail((42, 42), Image.Resampling.NEAREST)
                photo = ImageTk.PhotoImage(img)
                refs.append(photo)
                canvas.create_image(x + cell // 2, y + 42, image=photo, anchor="center", tags=(tag,))
            else:
                canvas.create_text(x + cell // 2, y + 42, text="empty", fill="#666666", anchor="center", tags=(tag,))
            def hover_on(_e, t=tag):
                canvas.itemconfigure(f"{t}_bg", fill="#303030", outline="#ffff00", width=3)
                canvas.config(cursor="hand2")
            def hover_off(_e, t=tag):
                canvas.itemconfigure(f"{t}_bg", fill="#202020", outline="#555555", width=1)
                canvas.config(cursor="")
            def choose(_e, sprite_id=sid):
                callback(sprite_id)
                win.destroy()
            canvas.tag_bind(tag, "<Enter>", hover_on)
            canvas.tag_bind(tag, "<Leave>", hover_off)
            canvas.tag_bind(tag, "<Button-1>", choose)
            canvas.tag_bind(tag, "<Double-1>", choose)
        canvas.configure(scrollregion=(0, 0, cols * cell, ((256 + cols - 1) // cols) * cell))
        win._photo_refs = refs

    def populate_paths(self) -> None:
        if not hasattr(self, "path_combo"):
            return
        if not self.level:
            self.path_combo["values"] = []
            return
        values = []
        for pdef in self.level.path_defs:
            marker = "used" if pdef.nonempty else "empty"
            values.append(f"{pdef.path_id}: {marker}, len={pdef.length}")
        self.path_combo["values"] = values
        if values:
            self.path_combo.current(0)
            self.selected_path.set(0)
            self.render_path_info(0)

    def on_path_select(self, _event: tk.Event) -> None:
        if not self.level or not hasattr(self, "path_combo"):
            return
        idx = self.path_combo.current()
        if idx < 0:
            return
        self.selected_path.set(idx)
        self.render_path_info(idx)
        self.render_map()

    def render_path_info(self, path_id: int) -> None:
        if not self.level or not hasattr(self, "path_text"):
            return
        path_id = max(0, min(15, int(path_id)))
        pdef = self.level.path_defs[path_id]
        self.path_canvas.delete("all")
        lines = [f"Path {path_id}", f"length: {pdef.length}", ""]
        lines.append("OpenJazz interpretation: each entry is read as signed y, signed x<<2. The exact semantic is event-dependent, so this tab treats it as diagnostic movement data.")
        lines.append("")
        lines.append("points / deltas:")
        for i, (dx, dy) in enumerate(pdef.points[:80]):
            lines.append(f"  {i:03d}: x={dx:4d}, y={dy:4d}")
        if len(pdef.points) > 80:
            lines.append(f"  ... {len(pdef.points) - 80} more")
        if hasattr(self, "path_edit_text"):
            self.path_edit_text.delete("1.0", tk.END)
            self.path_edit_text.insert("1.0", "\n".join(f"{dx} {dy}" for dx, dy in pdef.points))
        self.path_text.configure(state="normal")
        self.path_text.delete("1.0", tk.END)
        self.path_text.insert("1.0", "\n".join(lines))
        self.path_text.configure(state="disabled")
        if not pdef.points:
            self.path_canvas.create_text(12, 20, anchor="w", fill="white", text="Empty path")
            return
        pts = []
        x = y = 0
        for dx, dy in pdef.points:
            x += dx
            y += dy
            pts.append((x, y))
        min_x = min(x for x, _ in pts)
        max_x = max(x for x, _ in pts)
        min_y = min(y for _, y in pts)
        max_y = max(y for _, y in pts)
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)
        canvas_w = max(300, self.path_canvas.winfo_width() or 300)
        canvas_h = 210
        scale = min((canvas_w - 30) / w, (canvas_h - 30) / h, 4.0)
        def cv(pt):
            px, py = pt
            return (15 + (px - min_x) * scale, 15 + (py - min_y) * scale)
        prev = cv(pts[0])
        self.path_canvas.create_oval(prev[0]-4, prev[1]-4, prev[0]+4, prev[1]+4, outline="cyan")
        for pt in pts[1:]:
            cur = cv(pt)
            self.path_canvas.create_line(prev[0], prev[1], cur[0], cur[1], fill="cyan", width=2)
            prev = cur
        self.path_canvas.create_oval(prev[0]-4, prev[1]-4, prev[0]+4, prev[1]+4, outline="yellow")

    def apply_path_from_ui(self) -> None:
        if not self.level or not hasattr(self, "path_edit_text"):
            return
        path_id = max(0, min(15, int(self.selected_path.get())))
        points: List[Tuple[int, int]] = []
        for line_no, line in enumerate(self.path_edit_text.get("1.0", tk.END).splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                messagebox.showerror("Invalid path", f"Line {line_no}: expected dx dy")
                return
            try:
                dx, dy = int(float(parts[0])), int(float(parts[1]))
            except ValueError:
                messagebox.showerror("Invalid path", f"Line {line_no}: expected numeric dx dy")
                return
            points.append((dx, dy))
        self.level.set_path_points(path_id, points)
        self.set_dirty(True)
        self.populate_paths()
        self.selected_path.set(path_id)
        if hasattr(self, "path_combo"):
            self.path_combo.current(path_id)
        self.render_path_info(path_id)
        self.render_map()
        self.refresh_level_local_summary()
        self.status.set(f"Edited level-local path {path_id}. Save writes it.")

    def _mask_rows_for_tile(self, tile: int) -> List[int]:
        if not self.level:
            return [0] * 8
        tile = max(0, min(255, int(tile)))
        start = tile * 8
        if start < 0 or start + 8 > len(self.level.masks):
            return [0] * 8
        return list(self.level.masks[start:start + 8])

    def _mask_rows_to_text(self, rows: List[int]) -> List[str]:
        return ["".join("#" if row & (1 << bit) else "." for bit in range(8)) for row in rows[:8]]

    def render_mask_atlas(self) -> None:
        if not hasattr(self, "mask_atlas_canvas"):
            return
        canvas = self.mask_atlas_canvas
        canvas.delete("all")
        self._mask_atlas_photo_refs = []
        if not self.tileset:
            canvas.configure(scrollregion=(0, 0, 1, 1))
            return
        selected = max(0, min(255, int(self.mask_tile_var.get()))) if hasattr(self, "mask_tile_var") else 0
        width = max(220, canvas.winfo_width() or 360)
        cell = 52
        cols = max(1, width // cell)
        count = min(256, len(self.tileset.tiles))
        for tile in range(count):
            x = (tile % cols) * cell
            y = (tile // cols) * cell
            tag = f"mask_tile_{tile}"
            outline = "#ffff00" if tile == selected else "#555555"
            canvas.create_rectangle(x + 2, y + 2, x + cell - 2, y + cell - 2, fill="#202020", outline=outline, width=3 if tile == selected else 1, tags=(tag,))
            img = self.tileset.tiles[tile].resize((32, 32), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(img)
            self._mask_atlas_photo_refs.append(photo)
            canvas.create_image(x + 10, y + 14, image=photo, anchor="nw", tags=(tag,))
            if any(self._mask_rows_for_tile(tile)):
                canvas.create_rectangle(x + 31, y + 4, x + cell - 5, y + 16, fill="#ff9a34", outline="", stipple="gray50", tags=(tag,))
            canvas.create_text(x + 4, y + 4, text=str(tile), fill="#ffff80", anchor="nw", tags=(tag,))
            canvas.tag_bind(tag, "<Button-1>", lambda _e, t=tile: self.select_mask_tile(t))
        rows = max(1, (count + cols - 1) // cols)
        canvas.configure(scrollregion=(0, 0, cols * cell, rows * cell))

    def select_mask_tile(self, tile: int) -> None:
        if hasattr(self, "mask_tile_var"):
            self.mask_tile_var.set(max(0, min(255, int(tile))))
        self.render_mask_info(tile)

    def render_mask_editor(self, tile: int) -> None:
        if not hasattr(self, "mask_editor_canvas"):
            return
        tile = max(0, min(255, int(tile)))
        rows = getattr(self, "_editing_mask_rows", self._mask_rows_for_tile(tile))
        canvas = self.mask_editor_canvas
        canvas.delete("all")
        self._mask_editor_photo = None
        canvas_w = max(1, canvas.winfo_width())
        canvas_h = max(1, canvas.winfo_height())
        size = max(128, min(canvas_w, canvas_h) - 16)
        origin_x = (canvas_w - size) // 2
        origin_y = (canvas_h - size) // 2
        cell = size // 8
        size = cell * 8
        if self.tileset and 0 <= tile < len(self.tileset.tiles):
            img = self.tileset.tiles[tile].resize((size, size), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(img)
            self._mask_editor_photo = photo
            canvas.create_image(origin_x, origin_y, image=photo, anchor="nw")
        else:
            canvas.create_rectangle(origin_x, origin_y, origin_x + size, origin_y + size, fill="#181818", outline="#555555")
        for y in range(8):
            for x in range(8):
                solid = bool(rows[y] & (1 << x))
                x0 = origin_x + x * cell
                y0 = origin_y + y * cell
                fill = "#ff9a34" if solid else ""
                stipple = "gray50" if solid else ""
                canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=fill, stipple=stipple, outline="#ffffff", width=1)
                if solid:
                    canvas.create_line(x0 + 4, y0 + cell - 4, x0 + cell - 4, y0 + 4, fill="#ffffff", width=2)
                    canvas.create_line(x0 + 4, y0 + 4, x0 + cell - 4, y0 + cell - 4, fill="#ffffff", width=1)
        canvas.create_text(origin_x, origin_y + size + 6, text=f"Tile {tile} - left/drag solid, right/drag empty", fill="#dddddd", anchor="nw")

    def render_mask_preview(self, tile: int) -> None:
        if not hasattr(self, "mask_preview_canvas"):
            return
        canvas = self.mask_preview_canvas
        canvas.delete("all")
        self._mask_preview_photo = None
        tile = max(0, min(255, int(tile)))
        rows = getattr(self, "_editing_mask_rows", self._mask_rows_for_tile(tile))
        if self.tileset and 0 <= tile < len(self.tileset.tiles):
            img = self.tileset.tiles[tile].resize((128, 128), Image.Resampling.NEAREST).convert("RGBA")
            overlay = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay, "RGBA")
            cell = 16
            for y, row in enumerate(rows):
                for x in range(8):
                    if row & (1 << x):
                        x0 = x * cell
                        y0 = y * cell
                        draw.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill=(255, 154, 52, 90))
                        draw.line((x0, y0 + cell - 1, x0 + cell - 1, y0), fill=(255, 255, 255, 190), width=2)
            img.alpha_composite(overlay)
            photo = ImageTk.PhotoImage(img)
            self._mask_preview_photo = photo
            canvas.create_image(8, 8, image=photo, anchor="nw")
        canvas.create_text(8, 146, text=f"Tile {tile}", fill="#dddddd", anchor="nw")
        if hasattr(self, "mask_detail_text"):
            lines = [
                f"Tile {tile} collision mask",
                "",
                "Left-click/drag: solid",
                "Right-click/drag: empty",
                "",
                *self._mask_rows_to_text(rows),
            ]
            self.mask_detail_text.configure(state="normal")
            self.mask_detail_text.delete("1.0", tk.END)
            self.mask_detail_text.insert("1.0", "\n".join(lines))
            self.mask_detail_text.configure(state="disabled")

    def paint_mask_cell(self, event: tk.Event, solid: bool) -> None:
        if not hasattr(self, "mask_editor_canvas"):
            return
        tile = max(0, min(255, int(self.mask_tile_var.get()))) if hasattr(self, "mask_tile_var") else 0
        rows = list(getattr(self, "_editing_mask_rows", self._mask_rows_for_tile(tile)))
        canvas = self.mask_editor_canvas
        canvas_w = max(1, canvas.winfo_width())
        canvas_h = max(1, canvas.winfo_height())
        size = max(128, min(canvas_w, canvas_h) - 16)
        cell = (size // 8)
        size = cell * 8
        origin_x = (canvas_w - size) // 2
        origin_y = (canvas_h - size) // 2
        x = int((event.x - origin_x) // cell)
        y = int((event.y - origin_y) // cell)
        if not (0 <= x < 8 and 0 <= y < 8):
            return
        if solid:
            rows[y] |= 1 << x
        else:
            rows[y] &= ~(1 << x)
        self._editing_mask_rows = rows
        self.render_mask_editor(tile)

    def clear_current_mask(self) -> None:
        self._editing_mask_rows = [0] * 8
        self.render_mask_editor(int(self.mask_tile_var.get()))

    def fill_current_mask(self) -> None:
        self._editing_mask_rows = [0xFF] * 8
        self.render_mask_editor(int(self.mask_tile_var.get()))

    def apply_mask_from_ui(self) -> None:
        if not self.level or not hasattr(self, "mask_tile_var"):
            return
        tile = max(0, min(255, int(self.mask_tile_var.get())))
        rows = self._mask_rows_to_text(list(getattr(self, "_editing_mask_rows", self._mask_rows_for_tile(tile))))
        self.level.set_tile_mask_rows(tile, rows)
        self._collision_tile_cache.clear()
        self._collision_chunk_cache.clear()
        self.set_dirty(True)
        self.render_mask_info(tile)
        self.render_mask_atlas()
        self.render_map()
        self.render_atlas()
        self.refresh_validation()
        self.refresh_level_local_summary()
        self.status.set(f"Edited level-local collision mask for tile {tile}.")

    def apply_animation_from_ui(self) -> None:
        if not self.level or not hasattr(self, "anim_tree"):
            return
        selection = self.anim_tree.selection()
        if not selection:
            messagebox.showinfo("Animation", "Select an animation first.")
            return
        anim_id = int(selection[0])
        frames = self._animation_frame_rows_from_tree()
        name = self.anim_name_var.get().strip()[:LONGNAME - 1] if hasattr(self, "anim_name_var") else None
        self.level.set_animation_frames(anim_id, frames, name=name)
        self.set_dirty(True)
        self._event_preview_cache.clear()
        self.populate_animations()
        self.anim_tree.selection_set(str(anim_id))
        self.anim_tree.see(str(anim_id))
        self.on_anim_tree_select(tk.Event())
        self.render_map()
        self.refresh_validation()
        self.refresh_level_local_summary()
        self.status.set(f"Edited level-local animation {anim_id}.")

    def draw_path_overlay(self, draw: ImageDraw.ImageDraw) -> None:
        if not self.level or not self.level.path_defs:
            return
        path_id = max(0, min(15, int(self.selected_path.get())))
        pdef = self.level.path_defs[path_id]
        if not pdef.points:
            return
        if self.selected_object:
            anchor_x, anchor_y = self.selected_object
        else:
            anchor_x, anchor_y = self.level.metadata.start_x, self.level.metadata.start_y
        x = anchor_x * TILE_SIZE + TILE_SIZE // 2
        y = anchor_y * TILE_SIZE + TILE_SIZE // 2
        prev = (x, y)
        draw.ellipse((x-4, y-4, x+4, y+4), outline=(80, 255, 255, 255), width=2)
        for dx, dy in pdef.points[:240]:
            x += dx
            y += dy
            cur = (x, y)
            draw.line((prev[0], prev[1], cur[0], cur[1]), fill=(80, 255, 255, 220), width=2)
            prev = cur
        draw.ellipse((x-4, y-4, x+4, y+4), outline=(255, 255, 80, 255), width=2)
        draw.text((anchor_x * TILE_SIZE + 2, anchor_y * TILE_SIZE + 2), f"P{path_id}", fill=(80, 255, 255, 255))



