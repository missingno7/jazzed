from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .codecs import encode_rle_block, signed_byte, write_u16
from .constants import *
from .event_semantics import semantic_event_category

@dataclass
class RleSpan:
    name: str
    start: int
    payload_start: int
    end: int
    expected_len: int


@dataclass
class LevelMetadata:
    start_x: int = 0
    start_y: int = 0
    next_level: int = 0
    next_world: int = 0
    jump_height_raw: int = 0
    water_level: int = 0
    anim_speed: int = 0
    background_effect: int = 0
    sky_orb: int = 0
    start_x_pos: int = -1
    start_y_pos: int = -1
    next_level_pos: int = -1
    next_world_pos: int = -1
    jump_height_pos: int = -1
    water_level_pos: int = -1
    anim_speed_pos: int = -1


@dataclass
class EventDefinition:
    event_id: int
    name: str
    raw: bytes

    @property
    def category(self) -> str:
        return semantic_event_category(self.event_id, self.raw, self.name)

    @property
    def is_reserved_engine_marker(self) -> bool:
        return is_reserved_engine_event(self.event_id)

    @property
    def movement(self) -> int:
        return self.raw[4]

    @property
    def strength(self) -> int:
        return self.raw[9]

    @property
    def modifier(self) -> int:
        return self.raw[10]

    @property
    def points(self) -> int:
        return self.raw[11]

    @property
    def left_anim(self) -> int:
        return self.raw[5]

    @property
    def right_anim(self) -> int:
        return self.raw[6]


@dataclass
class SpriteFrame:
    index: int
    image: Image.Image
    x_offset: int = 0
    y_offset: int = 0


@dataclass
class AnimationDefinition:
    anim_id: int
    name: str
    raw: bytes
    length: int
    frame_ids: List[int]
    frame_x: List[int]
    frame_y: List[int]

    @property
    def first_frame(self) -> Optional[int]:
        for frame in self.frame_ids:
            if frame >= 0:
                return frame
        return None


@dataclass
class PathDefinition:
    path_id: int
    raw: bytes
    length: int
    points: List[Tuple[int, int]]

    @property
    def nonempty(self) -> bool:
        return self.length > 0 and bool(self.points)


@dataclass
class SpriteSetData:
    path: Path
    main_path: Path
    sprites: List[SpriteFrame]

    def get(self, index: int) -> Optional[SpriteFrame]:
        if 0 <= index < len(self.sprites):
            frame = self.sprites[index]
            if frame.image.width > 0 and frame.image.height > 0:
                return frame
        return None


@dataclass
class ObjectPlacement:
    x: int
    y: int
    event: int
    tile: int
    bg: int
    name: str



@dataclass
class BulletDefinition:
    bullet_id: int
    name: str
    raw: bytes

    @property
    def sprites(self) -> List[int]:
        return [self.raw[i] if i < len(self.raw) else 0 for i in range(4)]

    @property
    def xspeeds(self) -> List[int]:
        return [signed_byte(self.raw[4 + i]) if 4 + i < len(self.raw) else 0 for i in range(4)]

    @property
    def yspeeds(self) -> List[int]:
        return [signed_byte(self.raw[8 + i]) if 8 + i < len(self.raw) else 0 for i in range(4)]

    @property
    def gravities(self) -> List[int]:
        return [signed_byte(self.raw[12 + i]) if 12 + i < len(self.raw) else 0 for i in range(4)]

    @property
    def finish_anim(self) -> int:
        return self.raw[16] if len(self.raw) > 16 else 0

    @property
    def finish_sound(self) -> int:
        return self.raw[17] if len(self.raw) > 17 else 0

    @property
    def behaviour(self) -> int:
        return self.raw[18] if len(self.raw) > 18 else 0

    @property
    def start_sound(self) -> int:
        return self.raw[19] if len(self.raw) > 19 else 0

    @property
    def is_empty(self) -> bool:
        return not any(self.raw) and not self.name


def bullet_direction_name(i: int) -> str:
    return ["left", "right", "lower-left", "lower-right"][i] if 0 <= i < 4 else f"dir{i}"


def bullet_display_name(bullet: BulletDefinition) -> str:
    if bullet.name:
        return bullet.name
    if bullet.is_empty:
        return "Unused"
    nonzero_sprites = [s for s in bullet.sprites if s]
    if nonzero_sprites:
        return f"Sprite {'/'.join(map(str, nonzero_sprites[:2]))}"
    return bullet_type_label(bullet.bullet_id)


@dataclass
class LevelData:
    path: Path
    raw_file: bytes
    spans: Dict[str, RleSpan]
    level_num: int
    world_num: int
    blocks_ext: str
    grid: List[List[Dict[str, int]]]
    event_types: List[bytes]
    event_names: List[str]
    animations: List[AnimationDefinition]
    animation_names: List[str]
    bullet_defs: List[BulletDefinition]
    bullet_names: List[str]
    sound_rates: List[int]
    sound_names: List[str]
    bullets_raw: bytes
    attack_names_raw: bytes
    paths_raw: bytes
    path_defs: List[PathDefinition]
    masks: bytes
    metadata: LevelMetadata

    def event_def(self, event_id: int) -> EventDefinition:
        event_id = max(0, min(126, int(event_id)))
        name = self.event_names[event_id] if event_id < len(self.event_names) else ""
        return EventDefinition(event_id, name, self.event_types[event_id])

    def event_catalog(self) -> List[EventDefinition]:
        return [self.event_def(i) for i in range(EVENTS)]

    def animation(self, anim_id: int) -> Optional[AnimationDefinition]:
        anim_id = int(anim_id) & 0x7F
        if 0 <= anim_id < len(self.animations):
            return self.animations[anim_id]
        return None

    def bullet_def(self, bullet_id: int) -> BulletDefinition:
        bullet_id = max(0, min(BULLETS - 1, int(bullet_id)))
        if 0 <= bullet_id < len(self.bullet_defs):
            return self.bullet_defs[bullet_id]
        return BulletDefinition(bullet_id, "", bytes(BLENGTH))

    def sound_slot(self, sound_id: int) -> Tuple[str, int]:
        sound_id = int(sound_id)
        if sound_id <= 0:
            return "", 0
        idx = sound_id - 1
        name = self.sound_names[idx] if 0 <= idx < len(self.sound_names) else ""
        rate = self.sound_rates[idx] if 0 <= idx < len(self.sound_rates) else 11025
        return name, rate or 11025

    def bullets_to_bytes(self) -> bytes:
        out = bytearray(BULLETS * BLENGTH)
        for i in range(BULLETS):
            raw = self.bullet_defs[i].raw if i < len(self.bullet_defs) else bytes(BLENGTH)
            out[i * BLENGTH:(i + 1) * BLENGTH] = bytes(raw[:BLENGTH]).ljust(BLENGTH, b"\0")
        return bytes(out)

    def attack_names_to_bytes(self) -> bytes:
        out = bytearray(BULLETS * 21)
        for i in range(BULLETS):
            name = self.bullet_names[i] if i < len(self.bullet_names) else ""
            data = name.encode("ascii", errors="replace")[:20]
            out[i * 21] = len(data)
            out[i * 21 + 1:i * 21 + 1 + len(data)] = data
        return bytes(out)

    def mask_solid_at(self, tile: int, pixel_x: int, pixel_y: int) -> bool:
        # Each tile has an 8x8 low-resolution collision mask. One mask bit covers roughly 4x4 pixels.
        if tile < 0:
            return False
        idx = tile * 8 + (pixel_y >> 2)
        if idx < 0 or idx >= len(self.masks):
            return False
        return bool(self.masks[idx] & (1 << (pixel_x >> 2)))

    def tile_has_collision(self, tile: int) -> bool:
        start = tile * 8
        return 0 <= start < len(self.masks) and any(self.masks[start:start + 8])

    def grid_to_bytes(self) -> bytes:
        out = bytearray(LW * LH * 2)
        for x in range(LW):
            for y in range(LH):
                cell = self.grid[y][x]
                idx = (y + x * LH) * 2
                out[idx] = cell["tile"] & 0xFF
                out[idx + 1] = ((cell["bg"] & 1) << 7) | (cell["event"] & 0x7F)
        return bytes(out)

    def event_types_to_bytes(self) -> bytes:
        out = bytearray(EVENTS * ELENGTH)
        for i in range(EVENTS):
            raw = self.event_types[i] if i < len(self.event_types) else bytes(ELENGTH)
            out[i * ELENGTH:(i + 1) * ELENGTH] = bytes(raw[:ELENGTH]).ljust(ELENGTH, b"\0")
        return bytes(out)

    def paths_to_bytes(self) -> bytes:
        return bytes(self.paths_raw[:PATH_BYTES]).ljust(PATH_BYTES, b"\0")

    def masks_to_bytes(self) -> bytes:
        return bytes(self.masks[:MASK_BYTES]).ljust(MASK_BYTES, b"\0")

    def animations_to_bytes(self) -> bytes:
        out = bytearray(ANIMS << 6)
        for i in range(ANIMS):
            raw = self.animations[i].raw if i < len(self.animations) else bytes(64)
            out[i * 64:(i + 1) * 64] = bytes(raw[:64]).ljust(64, b"\0")
        return bytes(out)

    def set_path_points(self, path_id: int, points: List[Tuple[int, int]]) -> None:
        path_id = max(0, min(15, int(path_id)))
        points = points[:240]
        chunk = bytearray(512)
        chunk[0] = len(points) & 0xFF
        chunk[1] = (len(points) >> 8) & 0xFF
        for i, (dx, dy) in enumerate(points):
            # OpenJazz stores signed y first and signed x/4 second. Clamp to the data format.
            sx = max(-128, min(127, int(round(dx / 4))))
            sy = max(-128, min(127, int(dy)))
            off = 2 + i * 2
            chunk[off] = sy & 0xFF
            chunk[off + 1] = sx & 0xFF
        raw = bytearray(self.paths_raw[:PATH_BYTES]).ljust(PATH_BYTES, b"\0")
        raw[path_id * 512:(path_id + 1) * 512] = chunk
        self.paths_raw = bytes(raw)
        decoded = []
        for dx, dy in points:
            decoded.append((max(-128, min(127, int(round(dx / 4)))) << 2, max(-128, min(127, int(dy)))))
        self.path_defs[path_id] = PathDefinition(path_id, bytes(chunk), len(decoded), decoded)

    def set_tile_mask_rows(self, tile: int, rows: List[str]) -> None:
        tile = max(0, min(255, int(tile)))
        rows = rows[:8]
        raw = bytearray(self.masks[:MASK_BYTES]).ljust(MASK_BYTES, b"\0")
        start = tile * 8
        if start + 8 > len(raw):
            return
        for y in range(8):
            line = rows[y] if y < len(rows) else ""
            byte = 0
            for x, ch in enumerate((line + "........")[:8]):
                if ch in "#1Xx@█":
                    byte |= 1 << x
            raw[start + y] = byte
        self.masks = bytes(raw)

    def set_animation_frames(self, anim_id: int, frames: List[Tuple[int, int, int]]) -> None:
        anim_id = max(0, min(ANIMS - 1, int(anim_id)))
        frames = frames[:19]
        old = bytearray(self.animations[anim_id].raw if anim_id < len(self.animations) else bytes(64))
        old = bytearray(bytes(old[:64]).ljust(64, b"\0"))
        old[6] = len(frames) & 0xFF
        for i in range(19):
            frame_id = frames[i][0] if i < len(frames) else 0
            xoff = frames[i][1] if i < len(frames) else 0
            yoff = frames[i][2] if i < len(frames) else 0
            old[7 + i] = max(0, min(255, int(frame_id)))
            old[26 + i] = max(-128, min(127, int(xoff))) & 0xFF
            old[45 + i] = max(-128, min(127, int(yoff))) & 0xFF
        name = self.animations[anim_id].name if anim_id < len(self.animations) else ""
        frame_ids = [f for f, _x, _y in frames]
        frame_x = [x for _f, x, _y in frames]
        frame_y = [y for _f, _x, y in frames]
        self.animations[anim_id] = AnimationDefinition(anim_id, name, bytes(old), len(frames), frame_ids, frame_x, frame_y)

    def objects(self) -> List[ObjectPlacement]:
        result: List[ObjectPlacement] = []
        for y in range(LH):
            for x in range(LW):
                cell = self.grid[y][x]
                event = cell["event"]
                if event:
                    name = self.event_names[event] if event < len(self.event_names) else ""
                    result.append(ObjectPlacement(x, y, event, cell["tile"], cell["bg"], name))
        return result

    def save_as(self, target: Path, save_event_defs: bool = False, save_paths: bool = False, save_masks: bool = False, save_animations: bool = False, save_bullets: bool = False) -> None:
        replacements: List[Tuple[str, bytes]] = [("grid", encode_rle_block(self.grid_to_bytes()))]
        if save_masks:
            replacements.append(("masks", encode_rle_block(self.masks_to_bytes())))
        if save_paths:
            replacements.append(("paths", encode_rle_block(self.paths_to_bytes())))
        if save_event_defs:
            replacements.append(("events", encode_rle_block(self.event_types_to_bytes())))
        if save_animations:
            replacements.append(("animations", encode_rle_block(self.animations_to_bytes())))
        if save_bullets and "bullets" in self.spans:
            replacements.append(("bullets", encode_rle_block(self.bullets_to_bytes())))
        if save_bullets and "attack_names" in self.spans:
            replacements.append(("attack_names", encode_rle_block(self.attack_names_to_bytes())))

        patched = bytearray(self.raw_file)
        deltas: List[Tuple[int, int, int]] = []  # original start, original end, delta
        for name, block in sorted(replacements, key=lambda item: self.spans[item[0]].start, reverse=True):
            span = self.spans[name]
            patched[span.start:span.end] = block
            deltas.append((span.start, span.end, len(block) - (span.end - span.start)))

        def shifted(pos: int) -> int:
            # Replacements are recorded against original file coordinates.
            # A metadata byte moves by every earlier block whose original end is before it.
            offset = 0
            for start, end, delta in deltas:
                if pos > end:
                    offset += delta
            return pos + offset

        md = self.metadata
        if md.start_x_pos >= 0:
            write_u16(patched, shifted(md.start_x_pos), md.start_x)
        if md.start_y_pos >= 0:
            # OpenJazz adds +1 after reading; store visual/editor y - 1 back to file.
            write_u16(patched, shifted(md.start_y_pos), max(0, md.start_y - 1))
        if md.next_level_pos >= 0:
            patched[shifted(md.next_level_pos)] = md.next_level & 0xFF
        if md.next_world_pos >= 0:
            patched[shifted(md.next_world_pos)] = md.next_world & 0xFF
        if md.jump_height_pos >= 0:
            write_u16(patched, shifted(md.jump_height_pos), md.jump_height_raw)
        if md.water_level_pos >= 0:
            write_u16(patched, shifted(md.water_level_pos), md.water_level)
        if md.anim_speed_pos >= 0:
            patched[shifted(md.anim_speed_pos)] = md.anim_speed & 0xFF
        target.write_bytes(bytes(patched))


@dataclass
class TilesetData:
    path: Path
    palette: List[Tuple[int, int, int]]
    sky_palette: List[Tuple[int, int, int]]
    tiles: List[Image.Image]
    atlas: Image.Image
