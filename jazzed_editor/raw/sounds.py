from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .codecs import read_u16


@dataclass
class RawSound:
    name: str
    offset: int
    length: int
    data: bytes


@dataclass
class SoundArchive:
    path: Path
    sounds: List[RawSound]

    @property
    def by_name(self) -> Dict[str, RawSound]:
        return {sound.name.upper(): sound for sound in self.sounds if sound.name}

    def get(self, name: str) -> Optional[RawSound]:
        return self.by_name.get(name.upper())


def parse_sound_archive(path: Path) -> SoundArchive:
    data = path.read_bytes()
    if len(data) < 8 or data[:3] != b"sfx" or data[3] != 0x1A:
        raise ValueError(f"{path.name} is not a JJ1 SOUNDS archive")

    header_offset = int.from_bytes(data[-4:], "little")
    if header_offset < 4 or header_offset > len(data) - 4:
        raise ValueError(f"{path.name} has an invalid sound table offset")
    table_end = len(data) - 4
    if (table_end - header_offset) % 18:
        raise ValueError(f"{path.name} has an invalid sound table length")

    sounds: List[RawSound] = []
    for pos in range(header_offset, table_end, 18):
        raw_name = data[pos:pos + 12]
        name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="replace").strip()
        offset = int.from_bytes(data[pos + 12:pos + 16], "little")
        length, _ = read_u16(data, pos + 16)
        if offset < 0 or length < 0 or offset + length > len(data):
            clip = b""
        else:
            clip = data[offset:offset + length]
        sounds.append(RawSound(name, offset, length, clip))
    return SoundArchive(path, sounds)


def sound_to_wav_bytes(sound: RawSound, rate: int = 11025) -> bytes:
    # OpenJazz treats JJ1 raw clips as signed 8-bit mono PCM. WAV 8-bit PCM is unsigned.
    unsigned = bytes((sample + 128) & 0xFF for sample in sound.data)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(1)
        wav.setframerate(max(1, int(rate)))
        wav.writeframes(unsigned)
    return out.getvalue()
