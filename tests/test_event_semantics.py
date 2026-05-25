import unittest

from jazzed_editor.raw.constants import ELENGTH
from jazzed_editor.raw.event_semantics import (
    difficulty_badge,
    difficulty_label,
    event_field_label_for,
    event_force_overlay,
    infer_event_concept,
    touch_mechanism_summary,
)


def _raw(values):
    data = bytearray(ELENGTH)
    for idx, value in values.items():
        data[int(idx)] = int(value) & 0xFF
    return bytes(data)


class EventSemanticsTests(unittest.TestCase):
    def test_belt_semantics_use_signed_magnitude(self):
        raw = _raw({8: 0xFE, 10: 28})

        self.assertEqual(infer_event_concept(23, raw), "Conveyor belt")
        self.assertIn("belt push", event_field_label_for(raw, 8))
        self.assertEqual(event_force_overlay(raw)["dx"], -1)
        self.assertIn("magnitude*64 (-128)", touch_mechanism_summary(raw)[0])

    def test_float_semantics_use_multib_as_vertical_flag(self):
        raw = _raw({10: 32, 22: 6, 23: 1})

        self.assertEqual(infer_event_concept(24, raw), "Float / blower")
        self.assertEqual(event_force_overlay(raw)["dy"], -1)
        self.assertIn("vertical lift mode", touch_mechanism_summary(raw)[0])

    def test_repel_semantics_use_movement_and_direction_sign(self):
        raw = _raw({4: 37, 8: 0xFF, 22: 8, 23: 1})

        self.assertEqual(infer_event_concept(27, raw), "Repel / sucker tube")
        force = event_force_overlay(raw)
        self.assertEqual(force["dx"], -1)
        self.assertEqual(force["dy"], -1)
        self.assertIn("Repel/sucker movement", touch_mechanism_summary(raw)[0])

    def test_difficulty_labels_match_openjazz_order(self):
        self.assertEqual(difficulty_label(0), "Easy+")
        self.assertEqual(difficulty_badge(1), "M")
        self.assertEqual(difficulty_badge(2), "H")
        self.assertEqual(difficulty_badge(3), "T")
