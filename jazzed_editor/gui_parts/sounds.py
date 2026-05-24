from __future__ import annotations

import tempfile
try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None

from ..raw_data import *


class SoundsMixin:
    def _ensure_sound_archive(self):
        if getattr(self, "_sound_archive_loaded", False):
            return self._sound_archive
        self._sound_archive_loaded = True
        try:
            self._sound_archive = self.parser.load_sound_archive()
        except Exception as exc:
            self._sound_archive = None
            self.status.set(f"Could not load SOUNDS.000: {exc}")
        return self._sound_archive

    def _play_wav_bytes(self, wav: bytes, label: str) -> None:
        if winsound is None:
            self.status.set("Sound playback is only implemented through winsound on Windows.")
            return
        try:
            tmp = tempfile.NamedTemporaryFile(prefix="jazzed_sound_", suffix=".wav", delete=False)
            tmp.write(wav)
            tmp.close()
            self._last_played_sound_path = tmp.name
            winsound.PlaySound(tmp.name, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.status.set(f"Playing {label}.")
        except Exception as exc:
            self.status.set(f"Could not play {label}: {exc}")

    def sound_label(self, sound_id: int) -> str:
        if not self.level:
            return f"sound {sound_id}"
        name, _rate = self.level.sound_slot(sound_id)
        if not name:
            return f"{sound_id}: empty"
        return f"{sound_id}: {name}"

    def sound_choice_values(self) -> list[str]:
        if not self.level:
            return ["0: empty"]
        values = ["0: empty"]
        for sound_id in range(1, SOUNDS + 1):
            values.append(self.sound_label(sound_id))
        return values

    def sound_choice_value(self, sound_id: int) -> str:
        sound_id = max(0, min(SOUNDS, int(sound_id)))
        return self.sound_label(sound_id) if sound_id else "0: empty"

    def sound_id_from_choice(self, value: str) -> int:
        try:
            return max(0, min(255, int(str(value).split(":", 1)[0].strip())))
        except (TypeError, ValueError):
            return 0

    def play_sound_id(self, sound_id: int) -> None:
        if not self.level:
            return
        sound_id = max(0, min(255, int(sound_id)))
        name, rate = self.level.sound_slot(sound_id)
        if sound_id == 0 or not name:
            self.status.set(f"Sound {sound_id} is empty in this level's sound map.")
            return
        archive = self._ensure_sound_archive()
        if not archive:
            return
        sound = archive.get(name)
        if not sound or not sound.data:
            self.status.set(f"Sound {sound_id} maps to {name!r}, but it was not found in SOUNDS.000.")
            return
        wav = sound_to_wav_bytes(sound, rate)
        self._play_wav_bytes(wav, f"sound {self.sound_label(sound_id)}")

    def play_raw_sound(self, sound: RawSound, rate: int = 11025) -> None:
        if not sound or not sound.data:
            self.status.set("Selected sound clip is empty.")
            return
        self._play_wav_bytes(sound_to_wav_bytes(sound, rate), f"{sound.name or 'unnamed sound'} @ {rate} Hz")
