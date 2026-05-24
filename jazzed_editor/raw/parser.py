from __future__ import annotations

import struct
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from .codecs import decode_palette, decode_rle_block, read_u16, skip_c_string
from .constants import *
from .models import *
from .sprites import _read_one_jj1_sprite

class JJ1Parser:
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir

    def find_file(self, name: str) -> Path:
        for candidate in (self.game_dir / name, self.game_dir / name.upper(), self.game_dir / name.lower()):
            if candidate.exists():
                return candidate
        for child in self.game_dir.iterdir():
            if child.name.upper() == name.upper():
                return child
        raise FileNotFoundError(name)

    def level_files(self) -> List[Path]:
        files = [p for p in self.game_dir.iterdir() if p.is_file() and p.name.upper().startswith("LEVEL")]
        return sorted(files, key=lambda p: p.name.upper())

    def parse_level(self, path: Path) -> LevelData:
        data = path.read_bytes()
        if len(data) < 3 or data[:2] != b"DD" or data[2] != 0x1A:
            raise ValueError(f"{path.name} is not a JJ1 level file")

        spans: Dict[str, RleSpan] = {}
        pos = 39
        for name in [
            "prescan_0", "prescan_1", "prescan_2", "prescan_3",
            "prescan_4", "prescan_5", "prescan_6", "prescan_7",
        ]:
            _, start, payload, end = decode_rle_block(data, pos, 1)
            spans[name] = RleSpan(name, start, payload, end, -1)
            pos = end
        pos += 598
        _, start, payload, end = decode_rle_block(data, pos, 1)
        spans["prescan_8"] = RleSpan("prescan_8", start, payload, end, -1)
        pos = end + 4
        for name in ["prescan_9", "prescan_10"]:
            _, start, payload, end = decode_rle_block(data, pos, 1)
            spans[name] = RleSpan(name, start, payload, end, -1)
            pos = end
        pos += 25
        _, start, payload, end = decode_rle_block(data, pos, 1)
        spans["prescan_11"] = RleSpan("prescan_11", start, payload, end, -1)
        pos = end + 3

        level_num = data[pos] ^ 210
        world_num = data[pos + 1] ^ 4
        pos += 2 + 8
        ext_len = min(data[pos], 3)
        blocks_ext = data[pos + 1:pos + 1 + ext_len].decode("ascii", errors="replace")

        pos = 39
        raw_grid, start, payload, end = decode_rle_block(data, pos, LW * LH * 2)
        spans["grid"] = RleSpan("grid", start, payload, end, LW * LH * 2)
        pos = end

        _, start, payload, end = decode_rle_block(data, pos, LW * LH)
        spans["transparency"] = RleSpan("transparency", start, payload, end, LW * LH)
        pos = end

        masks_raw, start, payload, end = decode_rle_block(data, pos, MASK_BYTES)
        spans["masks"] = RleSpan("masks", start, payload, end, MASK_BYTES)
        pos = end

        paths_raw, start, payload, end = decode_rle_block(data, pos, PATH_BYTES)
        spans["paths"] = RleSpan("paths", start, payload, end, PATH_BYTES)
        pos = end

        event_raw, start, payload, end = decode_rle_block(data, pos, EVENTS * ELENGTH)
        spans["events"] = RleSpan("events", start, payload, end, EVENTS * ELENGTH)
        event_types = [event_raw[i * ELENGTH:(i + 1) * ELENGTH] for i in range(EVENTS)]
        pos = end

        names_raw, start, payload, end = decode_rle_block(data, pos, EVENTS * LONGNAME)
        spans["event_names"] = RleSpan("event_names", start, payload, end, EVENTS * LONGNAME)
        event_names = []
        for i in range(EVENTS):
            chunk = names_raw[i * LONGNAME:(i + 1) * LONGNAME]
            n = min(chunk[0], LONGNAME - 1)
            event_names.append(chunk[1:1 + n].decode("ascii", errors="replace").strip("\x00"))
        pos = end

        # Skip through the OpenJazz layout to find metadata offsets that are not part of the map grid.
        metadata = LevelMetadata()
        try:
            anim_raw, start, payload, end = decode_rle_block(data, pos, ANIMS << 6)
            spans["animations"] = RleSpan("animations", start, payload, end, ANIMS << 6)
            pos = end
            anim_names_raw, start, payload, end = decode_rle_block(data, pos, ANIMS * LONGNAME)
            spans["animation_names"] = RleSpan("animation_names", start, payload, end, ANIMS * LONGNAME)
            pos = end
            pos += 16 * (SHORTNAME + 1) + 9
            pos += 2 * 32  # sound rates, 32 little-endian shorts
            for _ in range(32):
                pos = skip_c_string(data, pos, SHORTNAME)
            pos = skip_c_string(data, pos, 12)  # music file
            pos += 13  # start cutscene
            pos = skip_c_string(data, pos, 12)  # end scene
            pos += 39  # editor tileset files
            metadata.start_x_pos = pos
            metadata.start_x, pos = read_u16(data, pos)
            metadata.start_y_pos = pos
            stored_y, pos = read_u16(data, pos)
            metadata.start_y = min(LH - 1, stored_y + 1)
            metadata.next_level_pos = pos
            metadata.next_level = data[pos]
            pos += 1
            metadata.next_world_pos = pos
            metadata.next_world = data[pos]
            pos += 1
            metadata.jump_height_pos = pos
            metadata.jump_height_raw, pos = read_u16(data, pos)
            pos += 2
            metadata.water_level_pos = pos
            metadata.water_level, pos = read_u16(data, pos)
            metadata.anim_speed_pos = pos
            metadata.anim_speed = data[pos]
            pos += 1
            pos += 2  # unknown/end marker after animation speed

            try:
                _, start, payload, end = decode_rle_block(data, pos, JJ1PANIMS * 2)
                spans["player_anims"] = RleSpan("player_anims", start, payload, end, JJ1PANIMS * 2)
                pos = end
                pos += JJ1MANIMS
                bullets_raw, start, payload, end = decode_rle_block(data, pos, BULLETS * BLENGTH)
                spans["bullets"] = RleSpan("bullets", start, payload, end, BULLETS * BLENGTH)
                pos = end
                attack_names_raw, start, payload, end = decode_rle_block(data, pos, BULLETS * 21)
                spans["attack_names"] = RleSpan("attack_names", start, payload, end, BULLETS * 21)
                pos = end
                if pos + 3 <= len(data):
                    metadata.background_effect = data[pos]
                    sky_orb_flag = data[pos + 1]
                    metadata.sky_orb = data[pos + 2] if sky_orb_flag else 0
            except Exception:
                bullets_raw = bytes(BULLETS * BLENGTH)
                attack_names_raw = bytes(BULLETS * 21)
        except Exception:
            metadata = LevelMetadata()
            bullets_raw = bytes(BULLETS * BLENGTH)
            attack_names_raw = bytes(BULLETS * 21)

        grid: List[List[Dict[str, int]]] = [[{"tile": 0, "bg": 0, "event": 0} for _ in range(LW)] for _ in range(LH)]
        for x in range(LW):
            for y in range(LH):
                idx = (y + x * LH) * 2
                grid[y][x] = {
                    "tile": raw_grid[idx],
                    "bg": raw_grid[idx + 1] >> 7,
                    "event": raw_grid[idx + 1] & 0x7F,
                }

        animations: List[AnimationDefinition] = []
        animation_names: List[str] = []
        # These variables are only present if metadata parsing got far enough. If not, keep safe blanks.
        if 'anim_raw' not in locals():
            anim_raw = bytes(ANIMS << 6)
        if 'anim_names_raw' not in locals():
            anim_names_raw = bytes(ANIMS * LONGNAME)
        for i in range(ANIMS):
            raw = anim_raw[i * 64:(i + 1) * 64]
            length = raw[6] if len(raw) > 6 else 0
            length = max(0, min(19, length))
            frame_ids = [raw[7 + j] for j in range(length) if 7 + j < len(raw)]
            frame_x = [struct.unpack('b', raw[26 + j:27 + j])[0] for j in range(length) if 26 + j < len(raw)]
            frame_y = [struct.unpack('b', raw[45 + j:46 + j])[0] for j in range(length) if 45 + j < len(raw)]
            chunk = anim_names_raw[i * LONGNAME:(i + 1) * LONGNAME]
            n = min(chunk[0], LONGNAME - 1) if chunk else 0
            aname = chunk[1:1 + n].decode("ascii", errors="replace").strip("\x00") if chunk else ""
            animation_names.append(aname)
            animations.append(AnimationDefinition(i, aname, raw, length, frame_ids, frame_x, frame_y))

        bullet_names: List[str] = []
        bullet_defs: List[BulletDefinition] = []
        for i in range(BULLETS):
            raw = bullets_raw[i * BLENGTH:(i + 1) * BLENGTH]
            chunk = attack_names_raw[i * 21:(i + 1) * 21]
            n = min(chunk[0], 20) if chunk else 0
            bname = chunk[1:1 + n].decode("ascii", errors="replace").strip("\x00") if chunk else ""
            bullet_names.append(bname)
            bullet_defs.append(BulletDefinition(i, bname, bytes(raw[:BLENGTH]).ljust(BLENGTH, b"\0")))

        path_defs: List[PathDefinition] = []
        for path_id in range(16):
            chunk = paths_raw[path_id * 512:(path_id + 1) * 512]
            if len(chunk) < 2:
                path_defs.append(PathDefinition(path_id, chunk, 0, []))
                continue
            raw_len = chunk[0] | (chunk[1] << 8)
            length = max(0, min(raw_len, 240))
            points: List[Tuple[int, int]] = []
            for j in range(length):
                off = 2 + j * 2
                if off + 1 >= len(chunk):
                    break
                # Jazz 1/OpenJazz-reference reads y from the first signed byte and x from the second signed byte << 2.
                y_delta = struct.unpack('b', chunk[off:off + 1])[0]
                x_delta = struct.unpack('b', chunk[off + 1:off + 2])[0] << 2
                points.append((x_delta, y_delta))
            path_defs.append(PathDefinition(path_id, chunk, length, points))

        return LevelData(path, data, spans, level_num, world_num, blocks_ext, grid, event_types, event_names, animations, animation_names, bullet_defs, bullet_names, bullets_raw, attack_names_raw, paths_raw, path_defs, masks_raw, metadata)

    def load_tileset_for_level(self, level: LevelData) -> TilesetData:
        ext = f"{level.world_num:03d}" if level.blocks_ext == "999" else level.blocks_ext.zfill(3)
        path = self.find_file(f"BLOCKS.{ext}")
        return self.parse_tileset(path)

    def parse_tileset(self, path: Path) -> TilesetData:
        data = path.read_bytes()
        pos = 0
        palette, _, _, pos = decode_palette(data, pos)
        sky_palette, _, _, pos = decode_palette(data, pos)
        _, _, _, pos = decode_rle_block(data, pos, 256 * 3)

        tiles: List[Image.Image] = []
        flat_palette: List[int] = []
        for r, g, b in palette:
            flat_palette.extend([r, g, b])
        for set_index in range(TSETS):
            marker = data[pos:pos + 2]
            pos += 2
            if marker == b"ok":
                for _ in range(TNUM):
                    raw, _, _, pos = decode_rle_block(data, pos, TILE_SIZE * TILE_SIZE)
                    img = Image.frombytes("P", (TILE_SIZE, TILE_SIZE), raw)
                    img.putpalette(flat_palette)
                    tiles.append(img.convert("RGBA"))
            elif marker == b"  ":
                continue
            else:
                raise ValueError(f"Unexpected tileset marker {marker!r} in {path.name} at 0x{pos - 2:X}")

        columns = 20
        rows = max(1, (len(tiles) + columns - 1) // columns)
        atlas = Image.new("RGBA", (columns * TILE_SIZE, rows * TILE_SIZE), (0, 0, 0, 0))
        for i, tile in enumerate(tiles):
            atlas.paste(tile, ((i % columns) * TILE_SIZE, (i // columns) * TILE_SIZE))
        return TilesetData(path, palette, sky_palette, tiles, atlas)

    def load_sprites_for_level(self, level: LevelData, palette: List[Tuple[int, int, int]]) -> Optional[SpriteSetData]:
        try:
            spec_path = self.find_file(f"SPRITES.{level.world_num:03d}")
            main_path = self.find_file("MAINCHAR.000")
            return self.parse_sprites(spec_path, main_path, palette)
        except Exception:
            return None

    def parse_sprites(self, spec_path: Path, main_path: Path, palette: List[Tuple[int, int, int]]) -> SpriteSetData:
        spec = spec_path.read_bytes()
        main = main_path.read_bytes()
        if len(spec) < 2:
            raise ValueError(f"{spec_path.name} is too small")
        sprite_count = min(256, spec[0] | (spec[1] << 8))
        offsets_start = 2
        offsets_end = offsets_start + sprite_count * 2
        if offsets_end > len(spec):
            raise ValueError(f"{spec_path.name} has truncated sprite offsets")
        xoffs = [spec[offsets_start + i] << 2 for i in range(sprite_count)]
        yoffs = [spec[offsets_start + sprite_count + i] for i in range(sprite_count)]
        sprites: List[SpriteFrame] = []
        main_pos = 2
        spec_pos = offsets_end
        for i in range(sprite_count):
            frame = None
            if main_pos < len(main):
                frame, main_pos = _read_one_jj1_sprite(main, main_pos, i, palette, xoffs[i], yoffs[i])
            if spec_pos < len(spec):
                spec_frame, spec_pos = _read_one_jj1_sprite(spec, spec_pos, i, palette, xoffs[i], yoffs[i])
                if spec_frame is not None:
                    frame = spec_frame
            if frame is None:
                frame = SpriteFrame(i, Image.new("RGBA", (1, 1), (0, 0, 0, 0)), xoffs[i], yoffs[i])
            sprites.append(frame)
        sprites.append(SpriteFrame(sprite_count, Image.new("RGBA", (1, 1), (0, 0, 0, 0)), 0, 0))
        return SpriteSetData(spec_path, main_path, sprites)

