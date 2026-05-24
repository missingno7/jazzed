import unittest

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from jazzed_editor.raw.constants import TILE_SIZE, TKEY


@unittest.skipIf(Image is None, "Pillow is not installed")
class TilesetImageTests(unittest.TestCase):
    def test_tile_colour_key_becomes_transparent(self) -> None:
        from jazzed_editor.raw.parser import _tile_from_indices

        palette = [(i, i, i) for i in range(256)]
        raw = bytes([TKEY, 1] + [2] * (TILE_SIZE * TILE_SIZE - 2))
        tile = _tile_from_indices(raw, palette)

        self.assertEqual(tile.getpixel((0, 0))[3], 0)
        self.assertEqual(tile.getpixel((1, 0))[3], 255)


if __name__ == "__main__":
    unittest.main()
