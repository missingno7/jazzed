import unittest

from jazzed_editor.raw.models import BulletDefinition, LevelMetadata


class ModelTests(unittest.TestCase):
    def test_bullet_signed_motion_fields(self) -> None:
        raw = bytes([
            1, 2, 3, 4,
            255, 1, 128, 127,
            0, 254, 2, 3,
            128, 255, 0, 1,
            7, 8, 9, 10,
        ])
        bullet = BulletDefinition(0, "test", raw)
        self.assertEqual(bullet.sprites, [1, 2, 3, 4])
        self.assertEqual(bullet.xspeeds, [-1, 1, -128, 127])
        self.assertEqual(bullet.yspeeds, [0, -2, 2, 3])
        self.assertEqual(bullet.gravities, [-128, -1, 0, 1])
        self.assertEqual(bullet.finish_anim, 7)
        self.assertEqual(bullet.finish_sound, 8)
        self.assertEqual(bullet.behaviour, 9)
        self.assertEqual(bullet.start_sound, 10)

    def test_level_metadata_defaults_are_safe(self) -> None:
        md = LevelMetadata()
        self.assertEqual(md.start_x_pos, -1)
        self.assertEqual(md.background_effect, 0)
        self.assertEqual(md.sky_orb, 0)


if __name__ == "__main__":
    unittest.main()
