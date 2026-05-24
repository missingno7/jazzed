from __future__ import annotations

from typing import List, Optional, Tuple

from PIL import Image

from .constants import TKEY
from .codecs import signed_byte, _signed_byte
from .models import SpriteFrame


def _unscramble_pixels(raw: bytes, length: int) -> bytes:
    if len(raw) < length:
        raw = raw + bytes(length - len(raw))
    return bytes(raw[(i >> 2) + ((i & 3) * (length >> 2))] for i in range(length))


def _sprite_from_pixels(index: int, pixels: bytes, width: int, height: int, palette: List[Tuple[int, int, int]], xoff: int, yoff: int) -> SpriteFrame:
    if width <= 0 or height <= 0:
        return SpriteFrame(index, Image.new("RGBA", (1, 1), (0, 0, 0, 0)), xoff, yoff)
    rgba = bytearray()
    for v in pixels[:width * height]:
        if v == 254:
            rgba.extend((0, 0, 0, 0))
        else:
            r, g, b = palette[v] if 0 <= v < len(palette) else (255, 0, 255)
            rgba.extend((r, g, b, 255))
    return SpriteFrame(index, Image.frombytes("RGBA", (width, height), bytes(rgba)), xoff, yoff)


def _read_one_jj1_sprite(data: bytes, p: int, index: int, palette: List[Tuple[int, int, int]], xoff: int, yoff: int) -> Tuple[Optional[SpriteFrame], int]:
    if p >= len(data):
        return None, p
    if data[p] == 0xFF:
        return None, min(len(data), p + 2)
    if p + 10 > len(data):
        return None, len(data)
    width = (data[p] | (data[p + 1] << 8)) << 2
    height = data[p + 2] | (data[p + 3] << 8)
    mask_offset = data[p + 6] | (data[p + 7] << 8)
    pos_words = data[p + 8] | (data[p + 9] << 8)
    pos_bytes = pos_words << 2
    cur = p + 10
    if width <= 0 or height <= 0:
        return _sprite_from_pixels(index, b"", 1, 1, palette, xoff, yoff), cur
    length = width * height
    if mask_offset:
        h2 = height + 1
        length2 = width * h2
        mask_start = cur + mask_offset
        mask_bytes = (width >> 2) * h2
        if mask_start + mask_bytes > len(data):
            return None, len(data)
        mask_data = data[mask_start:mask_start + mask_bytes]
        scrambled_mask = bytearray(length2)
        for count in range(length2):
            m = mask_data[count >> 2] if (count >> 2) < len(mask_data) else 0
            scrambled_mask[count] = (m >> (count & 3)) & 1
        sorted_mask = bytearray(length2)
        for count in range(length2):
            sorted_mask[(count >> 2) + ((count & 3) * (length2 >> 2))] = scrambled_mask[count]
        pix_scrambled = bytearray([254] * length2)
        pp = mask_start + mask_bytes
        for count in range(length2):
            if sorted_mask[count]:
                if pp >= len(data):
                    break
                # Original loader avoids transparent key in masked solid pixels.
                val = data[pp]
                pp += 1
                while val == 254 and pp < len(data):
                    val = data[pp]
                    pp += 1
                pix_scrambled[count] = val
        pixels = _unscramble_pixels(bytes(pix_scrambled), length2)
        end = p + 10 + mask_offset + mask_bytes + pos_bytes
        return _sprite_from_pixels(index, pixels, width, h2, palette, xoff, yoff), min(len(data), max(pp, end))
    else:
        if cur + length > len(data):
            return None, len(data)
        pixels = _unscramble_pixels(data[cur:cur + length], length)
        return _sprite_from_pixels(index, pixels, width, height, palette, xoff, yoff), cur + length
