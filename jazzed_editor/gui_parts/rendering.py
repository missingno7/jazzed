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

class RenderingMixin:
    def _atlas_columns(self, scale: int = 2) -> int:
        if not hasattr(self, "atlas_canvas"):
            return 10
        width = max(1, self.atlas_canvas.winfo_width())
        if width <= 1:
            width = 640
        return max(1, width // (TILE_SIZE * scale))

    def render_atlas(self) -> None:
        if not self.tileset:
            return
        scale = 2
        columns = self._atlas_columns(scale)
        rows = max(1, (len(self.tileset.tiles) + columns - 1) // columns)
        bg = self._background_color_rgba()
        img = Image.new("RGBA", (columns * TILE_SIZE * scale, rows * TILE_SIZE * scale), bg)
        for i, tile in enumerate(self.tileset.tiles):
            x = (i % columns) * TILE_SIZE * scale
            y = (i // columns) * TILE_SIZE * scale
            tile_img = tile.resize((TILE_SIZE * scale, TILE_SIZE * scale), Image.Resampling.NEAREST)
            img.alpha_composite(tile_img, (x, y))
            if self.show_collision.get() and self.level:
                overlay = self._collision_tile_overlay_image(i, scale)
                if overlay:
                    img.alpha_composite(overlay, (x, y))
        draw = ImageDraw.Draw(img)
        for i in range(len(self.tileset.tiles)):
            x = (i % columns) * TILE_SIZE * scale
            y = (i // columns) * TILE_SIZE * scale
            outline = (80, 80, 80, 255)
            width = 1
            if i == int(self.current_tile.get()):
                outline = (255, 255, 0, 255)
                width = 3
            draw.rectangle((x, y, x + TILE_SIZE * scale - 1, y + TILE_SIZE * scale - 1), outline=outline, width=width)
            draw.text((x + 2, y + 2), str(i), fill=(255, 255, 255, 255))
        self._atlas_photo = ImageTk.PhotoImage(img)
        self.atlas_canvas.delete("all")
        self.atlas_canvas.create_image(0, 0, image=self._atlas_photo, anchor="nw")
        self.atlas_canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def render_map_and_atlas(self) -> None:
        self.render_map()
        self.render_atlas()

    def render_map(self) -> None:
        """Render base tile chunks and draw overlays as independent canvas items.

        v14 keeps pixel art in chunk images, but collision, labels, grid, paths,
        event numbers, water line and start marker are vector canvas overlays.
        That keeps overlays crisp and independent from pixel-art scaling.
        """
        if not self.level or not self.tileset:
            return
        self._clear_brush_preview()
        self._chunk_photos.clear()
        self._chunk_items.clear()
        self.canvas.delete("all")
        z = max(1, int(self.zoom.get()))
        bg = self._background_color_rgba()
        self.canvas.configure(background=f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}")
        chunks_x = (LW + CHUNK_TILES - 1) // CHUNK_TILES
        chunks_y = (LH + CHUNK_TILES - 1) // CHUNK_TILES
        for cy in range(chunks_y):
            for cx in range(chunks_x):
                self._render_chunk(cx, cy)
        self.canvas.configure(scrollregion=(0, 0, LW * TILE_SIZE * z, LH * TILE_SIZE * z))
        self._draw_canvas_overlays()
        self._dirty_chunks.clear()

    def _render_chunk(self, cx: int, cy: int) -> None:
        if not self.level or not self.tileset:
            return
        z = max(1, int(self.zoom.get()))
        x0 = cx * CHUNK_TILES
        y0 = cy * CHUNK_TILES
        x1 = min(LW, x0 + CHUNK_TILES)
        y1 = min(LH, y0 + CHUNK_TILES)
        w = (x1 - x0) * TILE_SIZE
        h = (y1 - y0) * TILE_SIZE

        img = self._background_chunk_image(x0, y0, w, h)
        draw = ImageDraw.Draw(img, "RGBA")

        for y in range(y0, y1):
            for x in range(x0, x1):
                cell = self.level.grid[y][x]
                tile_id = cell["tile"]
                tile_img = self.tileset.tiles[tile_id] if 0 <= tile_id < len(self.tileset.tiles) else None
                px = (x - x0) * TILE_SIZE
                py = (y - y0) * TILE_SIZE
                if cell["bg"]:
                    draw.rectangle((px, py, px + TILE_SIZE - 1, py + TILE_SIZE - 1), fill=(0, 0, 0, 255))
                if tile_img is not None:
                    img.alpha_composite(tile_img, (px, py))
                else:
                    draw.rectangle((px, py, px + TILE_SIZE - 1, py + TILE_SIZE - 1), fill=(80, 0, 80, 255))
                    draw.text((px + 4, py + 10), str(tile_id), fill=(255, 255, 255, 255))

                # Object sprites are still raster images, but no text/lines are burned into the tile layer.
                event = cell["event"]
                if event and self.show_events.get() and self.show_object_sprites.get():
                    sprite_img = self.event_preview_image(event, 30)
                    if sprite_img is not None:
                        img.alpha_composite(sprite_img, (px + (TILE_SIZE - sprite_img.width) // 2, py + (TILE_SIZE - sprite_img.height) // 2))

        if z != 1:
            img = img.resize((img.width * z, img.height * z), Image.Resampling.NEAREST)
        photo = ImageTk.PhotoImage(img)
        self._chunk_photos[(cx, cy)] = photo
        canvas_x = x0 * TILE_SIZE * z
        canvas_y = y0 * TILE_SIZE * z
        old_item = self._chunk_items.get((cx, cy))
        if old_item:
            self.canvas.itemconfigure(old_item, image=photo)
        else:
            item = self.canvas.create_image(canvas_x, canvas_y, image=photo, anchor="nw", tags=("map_chunk",))
            self._chunk_items[(cx, cy)] = item

    def _background_chunk_image(self, tile_x0: int, tile_y0: int, width: int, height: int) -> Image.Image:
        """Approximate the JJ1 in-game background for the editor's full-map view."""
        bg = self._background_color_rgba()
        if not self.tileset or not self.level or self.level.metadata.background_effect != 2:
            return Image.new("RGBA", (width, height), bg)

        palette = self.tileset.sky_palette or self.tileset.palette
        if len(palette) < 256:
            return Image.new("RGBA", (width, height), bg)

        img = Image.new("RGBA", (width, height), bg)
        draw = ImageDraw.Draw(img, "RGBA")
        global_y0 = tile_y0 * TILE_SIZE
        for y in range(height):
            r, g, b = palette[156 + ((global_y0 + y) % 100)]
            draw.line((0, y, width, y), fill=(r, g, b, 255))

        sky_orb = self.level.metadata.sky_orb
        if sky_orb and 0 <= sky_orb < len(self.tileset.tiles):
            chunk_x0 = tile_x0 * TILE_SIZE
            chunk_y0 = tile_y0 * TILE_SIZE
            orb_global_x = (LW * TILE_SIZE * 4) // 5
            orb_global_y = (LH * TILE_SIZE * 3) // 25
            if chunk_x0 <= orb_global_x < chunk_x0 + width and chunk_y0 <= orb_global_y < chunk_y0 + height:
                img.alpha_composite(self.tileset.tiles[sky_orb], (orb_global_x - chunk_x0, orb_global_y - chunk_y0))
        return img

    def _background_color_rgba(self) -> Tuple[int, int, int, int]:
        """Approximate game background as a stretched canvas base color.

        OpenJazz clears non-sky levels to palette index 127 and renders sky
        levels from BLOCKS' background palette at indices 156..255.
        """
        if self.tileset:
            if self.level and self.level.metadata.background_effect == 2 and len(self.tileset.sky_palette) > 156:
                r, g, b = self.tileset.sky_palette[156]
                return (r, g, b, 255)
            if len(self.tileset.palette) > 127:
                r, g, b = self.tileset.palette[127]
                return (r, g, b, 255)
        return (0, 0, 0, 255)

    def _draw_canvas_overlays(self) -> None:
        if not self.level:
            return
        z = max(1, int(self.zoom.get()))
        self.canvas.delete("overlay")
        self.canvas.delete("path_overlay")
        tile_px = TILE_SIZE * z
        map_w = LW * tile_px
        map_h = LH * tile_px

        # Background tint/sky layer is already in chunks; water is a vector overlay.
        if self.show_bg_overlay.get():
            for y in range(LH):
                for x in range(LW):
                    if self.level.grid[y][x]["bg"]:
                        px = x * tile_px
                        py = y * tile_px
                        self.canvas.create_rectangle(px, py, px + tile_px, py + tile_px, fill="#50a0ff", stipple="gray50", outline="", tags=("overlay", "bg_overlay"))

        if self.show_collision.get():
            self._draw_collision_overlay_canvas(tile_px)

        if self.show_grid.get():
            for x in range(0, LW + 1):
                px = x * tile_px
                self.canvas.create_line(px, 0, px, map_h, fill="#ffffff", stipple="gray75", tags=("overlay", "grid_overlay"))
            for y in range(0, LH + 1):
                py = y * tile_px
                self.canvas.create_line(0, py, map_w, py, fill="#ffffff", stipple="gray75", tags=("overlay", "grid_overlay"))

        if self.show_water_level.get() and self.level.metadata.water_level not in (0, 65535):
            wy = max(0, min(map_h - 1, int(self.level.metadata.water_level) * z))
            self.canvas.create_rectangle(0, wy, map_w, map_h, fill="#2882ff", stipple="gray75", outline="", tags=("overlay", "water_overlay"))
            self.canvas.create_line(0, wy, map_w, wy, fill="#40c8ff", width=2, tags=("overlay", "water_overlay"))
            self.canvas.create_text(8, max(12, wy - 10), text=f"water {self.level.metadata.water_level}", anchor="w", fill="#80dcff", tags=("overlay", "water_overlay"))

        if self.show_events.get():
            color_by_cat = {
                "pickup/powerup": "#50ff78",
                "enemy/hazard": "#ff4646",
                "trampoline/spring": "#50beff",
                "mechanism/destructible": "#ffaa32",
                "trigger/other": "#d278ff",
            }
            for y in range(LH):
                for x in range(LW):
                    event = self.level.grid[y][x]["event"]
                    if not event:
                        continue
                    px = x * tile_px
                    py = y * tile_px
                    selected = self.selected_object == (x, y)
                    highlighted = self.highlight_event_id.get() == event
                    category = self.level.event_def(event).category
                    outline = "#ffff00" if selected else ("#ff00ff" if highlighted else color_by_cat.get(category, "#ff5050"))
                    self.canvas.create_rectangle(px + 1, py + 1, px + tile_px - 2, py + tile_px - 2, outline=outline, width=3 if selected else 2, tags=("overlay", "event_overlay"))
                    if self.show_event_labels.get():
                        self.canvas.create_rectangle(px + 2, py + 2, px + 23, py + 16, fill="#000000", outline="", stipple="gray50", tags=("overlay", "event_overlay"))
                        self.canvas.create_text(px + 4, py + 3, text=str(event), fill="#ffff00", anchor="nw", tags=("overlay", "event_overlay"))
                    if self.show_object_names.get():
                        label = friendly_event_name(self.level.event_def(event))[:26]
                        self.canvas.create_text(px + 3, py + tile_px - 13, text=label, fill="#ffffff", anchor="nw", tags=("overlay", "event_overlay"))

        if self.show_paths.get():
            self._draw_path_overlay_canvas()

        if self.show_player_start.get() and self.level.metadata.start_x_pos >= 0:
            sx = self.level.metadata.start_x * tile_px
            sy = self.level.metadata.start_y * tile_px
            self.canvas.create_rectangle(sx + 3, sy + 3, sx + tile_px - 4, sy + tile_px - 4, outline="#50ffff", width=3, tags=("overlay", "start_overlay"))
            self.canvas.create_text(sx + 4, sy + max(12, tile_px - 14), text="START", fill="#50ffff", anchor="nw", tags=("overlay", "start_overlay"))

        self.canvas.tag_raise("overlay")
        self.canvas.tag_raise("path_overlay")
        self.canvas.tag_raise("brush_preview")

    def _draw_collision_overlay_canvas(self, tile_px: int) -> None:
        if not self.level or not self.tileset:
            return
        z = max(1, int(self.zoom.get()))
        chunks_x = (LW + CHUNK_TILES - 1) // CHUNK_TILES
        chunks_y = (LH + CHUNK_TILES - 1) // CHUNK_TILES
        for cy in range(chunks_y):
            for cx in range(chunks_x):
                photo = self._collision_chunk_photo(cx, cy, z)
                if not photo:
                    continue
                self.canvas.create_image(
                    cx * CHUNK_SIZE * z,
                    cy * CHUNK_SIZE * z,
                    image=photo,
                    anchor="nw",
                    tags=("overlay", "collision_overlay"),
                )

    def _collision_mask_rows(self, tile: int) -> bytes:
        if not self.level:
            return b""
        start = tile * 8
        if start < 0 or start + 8 > len(self.level.masks):
            return b""
        rows = self.level.masks[start:start + 8]
        return rows if any(rows) else b""

    def _collision_tile_overlay_image(self, tile: int, z: int) -> Optional[Image.Image]:
        rows = self._collision_mask_rows(tile)
        if not rows:
            return None
        z = max(1, int(z))
        key = (int(tile), bytes(rows), z)
        cached = self._collision_tile_cache.get(key)
        if cached is not None:
            return cached

        size = TILE_SIZE * z
        cell = max(1, size // 8)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle((1, 1, size - 2, size - 2), outline=(255, 255, 255, 150), width=max(1, z))
        for my, row in enumerate(rows):
            for mx in range(8):
                if row & (1 << mx):
                    x0 = mx * cell
                    y0 = my * cell
                    x1 = (mx + 1) * cell - 1
                    y1 = (my + 1) * cell - 1
                    fill = (255, 154, 52, 72)
                    draw.rectangle((x0, y0, x1, y1), fill=fill)
                    draw.line((x0, y1, x1, y0), fill=(255, 255, 255, 190), width=max(1, z))
                    if cell >= 8:
                        draw.line((x0, y0, x1, y1), fill=(255, 255, 255, 115), width=max(1, z))
        self._collision_tile_cache[key] = img
        return img

    def _collision_chunk_photo(self, cx: int, cy: int, z: int) -> Optional[ImageTk.PhotoImage]:
        if not self.level:
            return None
        x0 = cx * CHUNK_TILES
        y0 = cy * CHUNK_TILES
        x1 = min(LW, x0 + CHUNK_TILES)
        y1 = min(LH, y0 + CHUNK_TILES)
        rows_signature: List[Tuple[int, int, int, bytes]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                tile = self.level.grid[y][x]["tile"]
                rows = self._collision_mask_rows(tile)
                if rows:
                    rows_signature.append((x, y, tile, rows))
        if not rows_signature:
            self._collision_chunk_cache.pop((cx, cy, z), None)
            return None

        signature: Tuple[Any, ...] = (self.level.path, x0, y0, x1, y1, tuple(rows_signature))
        cached = self._collision_chunk_cache.get((cx, cy, z))
        if cached and cached[0] == signature:
            return cached[1]

        img = Image.new("RGBA", ((x1 - x0) * TILE_SIZE * z, (y1 - y0) * TILE_SIZE * z), (0, 0, 0, 0))
        for y in range(y0, y1):
            for x in range(x0, x1):
                tile = self.level.grid[y][x]["tile"]
                overlay = self._collision_tile_overlay_image(tile, z)
                if overlay:
                    img.alpha_composite(overlay, ((x - x0) * TILE_SIZE * z, (y - y0) * TILE_SIZE * z))
        photo = ImageTk.PhotoImage(img)
        self._collision_chunk_cache[(cx, cy, z)] = (signature, photo)
        return photo

    def _cell_chunk(self, x: int, y: int) -> Tuple[int, int]:
        return x // CHUNK_TILES, y // CHUNK_TILES

    def _refresh_cell_chunk(self, x: int, y: int) -> None:
        if not self.fast_paint.get():
            self.render_map()
            return
        cx, cy = self._cell_chunk(x, y)
        self._render_chunk(cx, cy)
        self.canvas.tag_lower("map_chunk")
        self._draw_canvas_overlays()

    def _draw_path_overlay_canvas(self) -> None:
        if not self.level:
            return
        self.canvas.delete("path_overlay")
        z = max(1, int(self.zoom.get()))
        origin_x = self.level.metadata.start_x * TILE_SIZE
        origin_y = self.level.metadata.start_y * TILE_SIZE
        if self.selected_object:
            origin_x = self.selected_object[0] * TILE_SIZE + TILE_SIZE // 2
            origin_y = self.selected_object[1] * TILE_SIZE + TILE_SIZE // 2
        for path in self.level.path_defs:
            if not path.nonempty:
                continue
            x = origin_x
            y = origin_y
            pts = [(x * z, y * z)]
            for dx, dy in path.points[:path.length]:
                x += dx
                y += dy
                pts.append((x * z, y * z))
            if len(pts) >= 2:
                flat = [coord for pt in pts for coord in pt]
                self.canvas.create_line(*flat, fill="#ffff00", width=2, tags=("path_overlay", "overlay"))
                self.canvas.create_text(pts[0][0] + 5, pts[0][1] + 5, text=f"P{path.path_id}", fill="#ffff00", anchor="nw", tags=("path_overlay", "overlay"))

    def _clear_brush_preview(self) -> None:
        if not hasattr(self, "canvas"):
            return
        for item in getattr(self, "_brush_preview_items", []):
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._brush_preview_items = []
        self._brush_preview_photos = []

    def _tile_brush_preview_photo(self, tile_id: int, size: int) -> Optional[ImageTk.PhotoImage]:
        if not self.tileset or not (0 <= tile_id < len(self.tileset.tiles)):
            return None
        img = self.tileset.tiles[tile_id].resize((size, size), Image.Resampling.NEAREST)
        if self.paint_bg.get() and int(self.current_bg.get()):
            overlay = Image.new("RGBA", (size, size), (80, 160, 255, 65))
            img = Image.alpha_composite(img.convert("RGBA"), overlay)
        return ImageTk.PhotoImage(img)

    def _event_brush_preview_photo(self, event_id: int, size: int) -> Optional[ImageTk.PhotoImage]:
        if event_id <= 0:
            return None
        sprite = self.event_preview_image(event_id, max(16, min(48, size - 4)))
        if sprite is None:
            return None
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sprite = sprite.copy()
        sprite.thumbnail((size - 4, size - 4), Image.Resampling.NEAREST)
        canvas.alpha_composite(sprite, ((size - sprite.width) // 2, (size - sprite.height) // 2))
        return ImageTk.PhotoImage(canvas)

    def _update_brush_preview(self, x: int, y: int) -> None:
        self._clear_brush_preview()
        if not self.show_brush_preview.get():
            return
        z = max(1, int(self.zoom.get()))
        px = x * TILE_SIZE * z
        py = y * TILE_SIZE * z
        size = TILE_SIZE * z
        mode = self.tool_mode.get()
        label = ""
        outline = "#ffffff"
        photo: Optional[ImageTk.PhotoImage] = None

        if mode == "tiles":
            tile_id = int(self.current_tile.get())
            label = f"tile {tile_id}"
            outline = "#00ffff"
            photo = self._tile_brush_preview_photo(tile_id, size)
        elif mode in {"events", "objects"}:
            ev = int(self.current_event.get())
            label = "erase event" if ev == 0 else f"event {ev}: {self.event_display_name(ev)[:22]}"
            outline = "#ffff00"
            photo = self._event_brush_preview_photo(ev, size)
        elif mode == "start":
            label = "START"
            outline = "#00ffff"
        else:
            label = "inspect"
            outline = "#aaaaaa"

        items = []
        if photo is not None:
            self._brush_preview_photos.append(photo)
            items.append(self.canvas.create_image(px, py, image=photo, anchor="nw", tags=("brush_preview", "overlay")))
            # translucent-ish checker/outline effect is approximated by the dashed outline; Tk images don't support per-item alpha.
        r = self.canvas.create_rectangle(px, py, px + size, py + size, outline=outline, width=2, dash=(4, 3), tags=("brush_preview", "overlay"))
        t = self.canvas.create_text(px + 4, py + 4, text=label, fill=outline, anchor="nw", tags=("brush_preview", "overlay"))
        items.extend([r, t])
        self._brush_preview_items = items
        self.canvas.tag_raise("brush_preview")

