from pathlib import Path
import tempfile
import unittest

from jazzed_editor.raw.sounds import parse_sound_archive, sound_to_wav_bytes


class SoundArchiveTests(unittest.TestCase):
    def test_parse_sound_archive_and_wav_export(self) -> None:
        clip = bytes([128, 0, 127])
        header_offset = 4 + len(clip)
        entry = b"TEST\0\0\0\0\0\0\0\0" + (4).to_bytes(4, "little") + len(clip).to_bytes(2, "little")
        data = b"sfx\x1A" + clip + entry + header_offset.to_bytes(4, "little")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SOUNDS.000"
            path.write_bytes(data)
            archive = parse_sound_archive(path)

        self.assertEqual(len(archive.sounds), 1)
        self.assertEqual(archive.sounds[0].name, "TEST")
        self.assertEqual(archive.get("test").data, clip)
        wav = sound_to_wav_bytes(archive.sounds[0], 11025)
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertIn(b"WAVE", wav[:16])


if __name__ == "__main__":
    unittest.main()
