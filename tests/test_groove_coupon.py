import unittest

import numpy as np

from tools.groove_coupon import (
    CLEARANCES,
    FILL_LINE_DEPTH,
    WALL,
    build_groove_block,
    build_tongue,
    slot_layout,
)

MK3_BED = (250.0, 210.0, 210.0)


class SlotLayoutTest(unittest.TestCase):
    def test_slot_width_is_wall_plus_clearance_each_side(self):
        for (x0, x1), c in zip(slot_layout(), CLEARANCES):
            self.assertAlmostEqual(x1 - x0, WALL + 2 * c)

    def test_default_clearance_is_the_middle_slot(self):
        self.assertEqual(CLEARANCES[2], 0.25)


class GrooveBlockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mesh = build_groove_block()

    def test_is_single_watertight_solid(self):
        self.assertTrue(self.mesh.is_watertight)
        self.assertTrue(self.mesh.is_winding_consistent)
        self.assertEqual(len(self.mesh.split(only_watertight=False)), 1)
        self.assertGreater(self.mesh.volume, 0)

    def test_sits_on_bed_and_fits_mk3(self):
        lo, hi = self.mesh.bounds
        self.assertAlmostEqual(lo[2], 0.0)
        self.assertTrue(np.all(hi - lo < MK3_BED))

    def test_slots_are_open_and_rails_are_solid_at_measured_width(self):
        z = WALL + 2.5  # mid-height of the rails
        y = 10.0
        eps = 0.02
        for x0, x1 in slot_layout():
            probes = np.array(
                [
                    [(x0 + x1) / 2, y, z],  # slot centre: empty
                    [x0 + eps, y, z],  # just inside slot: empty
                    [x1 - eps, y, z],
                    [x0 - eps, y, z],  # just inside rails: solid
                    [x1 + eps, y, z],
                ]
            )
            inside = self.mesh.contains(probes)
            self.assertEqual(list(inside), [False, False, False, True, True])


class TongueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mesh = build_tongue()

    def test_is_single_watertight_solid(self):
        self.assertTrue(self.mesh.is_watertight)
        self.assertEqual(len(self.mesh.split(only_watertight=False)), 1)

    def test_prints_flat_at_wall_thickness(self):
        lo, hi = self.mesh.bounds
        self.assertAlmostEqual(lo[2], 0.0)
        self.assertAlmostEqual(hi[2], WALL)

    def test_fill_line_is_debossed_into_top_face(self):
        lo, hi = self.mesh.bounds
        cx = (lo[0] + hi[0]) / 2
        cy = (lo[1] + hi[1]) / 2
        in_line = [cx, cy, WALL - FILL_LINE_DEPTH / 2]
        below_line = [cx, cy, WALL - FILL_LINE_DEPTH - 0.05]
        self.assertEqual(list(self.mesh.contains([in_line, below_line])), [False, True])


if __name__ == "__main__":
    unittest.main()
