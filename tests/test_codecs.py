import unittest

from jazzed_editor.raw.codecs import decode_palette, decode_rle_block, encode_rle_block, signed_byte


class CodecTests(unittest.TestCase):
    def test_signed_byte(self) -> None:
        self.assertEqual(signed_byte(0), 0)
        self.assertEqual(signed_byte(127), 127)
        self.assertEqual(signed_byte(128), -128)
        self.assertEqual(signed_byte(255), -1)
        self.assertEqual(signed_byte(511), -1)

    def test_rle_round_trip(self) -> None:
        raw = bytes([0, 0, 0, 1, 2, 2, 2, 2, 3, 0, 4, 4, 5])
        encoded = encode_rle_block(raw)
        decoded, start, payload, end = decode_rle_block(encoded, 0, len(raw))
        self.assertEqual(decoded, raw)
        self.assertEqual(start, 0)
        self.assertEqual(payload, 2)
        self.assertEqual(end, len(encoded))

    def test_decode_palette_expands_6_bit_channels(self) -> None:
        raw = bytes([0, 1, 63] * 256)
        palette, start, payload, end = decode_palette(encode_rle_block(raw), 0)
        self.assertEqual(start, 0)
        self.assertEqual(payload, 2)
        self.assertEqual(end, len(encode_rle_block(raw)))
        self.assertEqual(palette[0], (0, 4, 255))


if __name__ == "__main__":
    unittest.main()
