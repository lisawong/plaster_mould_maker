"""Printable test coupon for casting-form tongue-and-groove clearance (PRD R6.3, R6.5).

Groove block: a 3 mm base with rails forming open-ended slots, one per clearance,
ordered smallest to largest and marked with 1..N dots. Tongue: a flat 3 mm plate
(printed the same way as real walls) with the 0.6 mm fill line debossed on top.

Run: python -m tools.groove_coupon [out_dir]
"""

import sys
from pathlib import Path

import numpy as np
import trimesh

WALL = 3.0  # wall = lip = tongue thickness (mm)
CLEARANCES = (0.15, 0.20, 0.25, 0.30, 0.35)  # per side (mm); 0.25 is the default
FILL_LINE_DEPTH = 0.6
FILL_LINE_WIDTH = 1.0

RAIL = 2.0  # rail thickness between slots
RAIL_HEIGHT = 5.0  # groove depth above the base
SLOT_LENGTH = 20.0  # along Y; slots are open at both ends
MARK_STRIP = 12.0  # base extension in front of the slots for index dots
DOT = 1.2
DOT_GAP = 0.8
DOT_HEIGHT = 0.6

TONGUE_LENGTH = 30.0
TONGUE_WIDTH = SLOT_LENGTH


def _box(x0, x1, y0, y1, z0, z1):
    box = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
    box.apply_translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    return box


def slot_layout():
    """X ranges of each slot, in CLEARANCES order."""
    slots, x = [], RAIL
    for c in CLEARANCES:
        width = WALL + 2 * c
        slots.append((x, x + width))
        x += width + RAIL
    return slots


def build_groove_block():
    slots = slot_layout()
    length = slots[-1][1] + RAIL
    parts = [_box(0, length, 0, SLOT_LENGTH + MARK_STRIP, 0, WALL)]
    top = WALL + RAIL_HEIGHT

    rail_x = [0.0] + [x1 for _, x1 in slots]
    for x in rail_x:
        parts.append(_box(x, x + RAIL, 0, SLOT_LENGTH, WALL, top))

    for i, (x0, x1) in enumerate(slots, start=1):
        cx = (x0 + x1) / 2
        for d in range(i):
            y = SLOT_LENGTH + 1.5 + d * (DOT + DOT_GAP)
            parts.append(_box(cx - DOT / 2, cx + DOT / 2, y, y + DOT, WALL, WALL + DOT_HEIGHT))

    return _union(parts)


def build_tongue():
    plate = _box(0, TONGUE_LENGTH, 0, TONGUE_WIDTH, 0, WALL)
    cy = TONGUE_WIDTH / 2
    line = _box(
        -1, TONGUE_LENGTH + 1,
        cy - FILL_LINE_WIDTH / 2, cy + FILL_LINE_WIDTH / 2,
        WALL - FILL_LINE_DEPTH, WALL + 1,
    )
    return _clean(trimesh.boolean.difference([plate, line], engine="manifold"))


def _union(parts):
    return _clean(trimesh.boolean.union(parts, engine="manifold"))


def _clean(mesh):
    mesh.merge_vertices()
    mesh.apply_translation((0, 0, -mesh.bounds[0][2]))
    return mesh


def main(out_dir="prints/groove-coupon"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    build_groove_block().export(out / "groove-block.stl")
    build_tongue().export(out / "tongue.stl")
    for i, ((x0, x1), c) in enumerate(zip(slot_layout(), CLEARANCES), start=1):
        print(f"slot {i} ({i} dot{'s' * (i > 1)}): clearance {c:.2f} mm/side, width {x1 - x0:.2f} mm")
    print(f"wrote {out}/groove-block.stl, {out}/tongue.stl")


if __name__ == "__main__":
    main(*sys.argv[1:])
