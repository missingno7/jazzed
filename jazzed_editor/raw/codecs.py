from __future__ import annotations

import struct
from typing import List, Tuple


def signed_byte(value: int) -> int:
    return struct.unpack("b", bytes([value & 0xFF]))[0]


_signed_byte = signed_byte


def read_u16(data: bytes, pos: int) -> Tuple[int, int]:
    return data[pos] | (data[pos + 1] << 8), pos + 2


def write_u16(buf: bytearray, pos: int, value: int) -> None:
    value = max(0, min(0xFFFF, int(value)))
    buf[pos] = value & 0xFF
    buf[pos + 1] = (value >> 8) & 0xFF


def skip_c_string(data: bytes, pos: int, max_len: int) -> int:
    # OpenJazz loadTerminatedString(max_len) is length-prefixed and then padded
    # to a fixed max_len-byte field: total bytes consumed = 1 + max_len.
    return min(len(data), pos + max_len + 1)


def decode_rle_block(data: bytes, pos: int, expected_len: int) -> Tuple[bytes, int, int, int]:
    """Decode an OpenJazz RLE block with a two-byte compressed-size prefix."""
    if pos + 2 > len(data):
        raise ValueError(f"RLE block at 0x{pos:X} has no size prefix")
    compressed_size, payload_pos = read_u16(data, pos)
    end_pos = payload_pos + compressed_size
    if end_pos > len(data):
        raise ValueError(f"RLE block at 0x{pos:X} extends past EOF")

    out = bytearray()
    p = payload_pos
    while len(out) < expected_len and p < end_pos:
        code = data[p]
        p += 1
        amount = code & 0x7F
        if code & 0x80:
            if p >= end_pos:
                break
            value = data[p]
            p += 1
            if len(out) + amount >= expected_len:
                break
            out.extend([value] * amount)
        elif amount:
            if len(out) + amount >= expected_len:
                break
            out.extend(data[p:p + amount])
            p += amount
        else:
            if p >= end_pos:
                break
            out.append(data[p])
            p += 1
            break

    if len(out) < expected_len:
        out.extend(b"\x00" * (expected_len - len(out)))
    return bytes(out[:expected_len]), pos, payload_pos, end_pos


def encode_rle_block(raw: bytes) -> bytes:
    """Encode data into Jazz 1 DOS-compatible RLE.

    The original decoder treats copy/repeat chunks that exactly reach the target
    length as a terminator condition before copying, so this encoder emits the
    final byte using the special zero-length literal marker.
    """
    if not raw:
        payload = b"\x00\x00"
        return struct.pack("<H", len(payload)) + payload

    payload = bytearray()
    limit = len(raw) - 1
    i = 0
    while i < limit:
        run = 1
        max_run = min(126, limit - i)
        while run < max_run and raw[i + run] == raw[i]:
            run += 1
        if run >= 3:
            payload.append(0x80 | run)
            payload.append(raw[i])
            i += run
            continue

        start = i
        i += 1
        while i < limit and (i - start) < 126:
            next_run = 1
            max_next = min(126, limit - i)
            while next_run < max_next and raw[i + next_run] == raw[i]:
                next_run += 1
            if next_run >= 3:
                break
            i += 1
        payload.append(i - start)
        payload.extend(raw[start:i])

    payload.append(0)
    payload.append(raw[-1])
    if len(payload) > 0xFFFF:
        raise ValueError("Encoded RLE block is too large for a two-byte size field")
    return struct.pack("<H", len(payload)) + payload


def decode_palette(data: bytes, pos: int) -> Tuple[List[Tuple[int, int, int]], int, int, int]:
    raw, start, payload, end = decode_rle_block(data, pos, 256 * 3)
    palette = []
    for i in range(256):
        r, g, b = raw[i * 3:i * 3 + 3]
        palette.append(((r << 2) + (r >> 4), (g << 2) + (g >> 4), (b << 2) + (b >> 4)))
    return palette, start, payload, end

