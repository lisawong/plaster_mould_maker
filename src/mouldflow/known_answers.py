"""Known-answer release fixtures (EVALUATION-PLAN geometry rows).

Each fixture is built from boxes whose maximum penetration depth and expected outcome
are known independently of the code under test. Depth is the two-sided definition
used by `release_check`: the largest distance of overlapping material below either
solid's surface, in mm. Volumes are mm3 and are never compared with depths.
"""
from dataclasses import dataclass, field

import numpy as np
import trimesh

from .pipeline import box_between, boolean


@dataclass(frozen=True)
class KnownAnswer:
    name: str
    evaluation_row: str
    moving: trimesh.Trimesh
    fixed: trimesh.Trimesh
    direction: tuple
    allowance_mm: float
    expected_outcome: str
    expected_max_depth_mm: float | None
    note: str
    distances: tuple | None = None
    options: dict = field(default_factory=dict)


def _fixed_block():
    return trimesh.creation.box([10, 10, 10])        # x, y, z in [-5, 5]


def _wedge(thickness):
    """Block on the fixed x=5 face whose z=+1 edge dips `thickness` mm into it."""
    mesh = box_between([5, -1, -1], [7, 1, 1])
    vertices = mesh.vertices.copy()
    vertices[(np.isclose(vertices[:, 0], 5)) & (np.isclose(vertices[:, 2], 1)), 0] -= thickness
    return trimesh.Trimesh(vertices, mesh.faces, process=False)


def clean_withdrawal():
    fixed = boolean('difference', [box_between([-5, -5, -5], [5, 5, 0]), box_between([-1, -1, -3], [1, 1, 0])])
    return KnownAnswer(
        'clean-withdrawal', 'Clean convex solid', box_between([-1, -1, -3], [1, 1, 2]), fixed, (0, 0, 1), .1,
        'strict_pass', 0., 'Square pin withdrawn from its exact-fit hole: sliding contact only.')


def thin_wide_overlap():
    return KnownAnswer(
        'thin-wide-overlap', 'Thin, wide overlap', box_between([4.95, -4, -4], [6.95, 4, 4]), _fixed_block(),
        (1, 0, 0), .1, 'conditional_finishing', .05,
        '0.05 mm deep but 3.2 mm3: a large volume does not imply a large depth.')


def deep_catch():
    return KnownAnswer(
        'deep-catch', 'Deep local catch', box_between([4, -1, -1], [6, 1, 1]), _fixed_block(), (1, 0, 0), .5,
        'fail', 1., '1 mm overlap at the start of withdrawal; measured depth exceeds the allowance.')


def bound_wider_than_depth():
    return KnownAnswer(
        'bound-wider-than-depth', 'Bound wider than known depth', box_between([4.6, -1, -1], [6.6, 1, 1]),
        _fixed_block(), (1, 0, 0), .5, 'conditional_finishing', .4,
        'True depth 0.4 mm; the boundary + half-slab bound is ~0.6 mm and straddles the 0.5 mm allowance '
        'until refined.')


def zero_thickness_contact():
    return KnownAnswer(
        'zero-thickness-contact', 'Zero-thickness contact', box_between([5, -1, -1], [7, 1, 1]), _fixed_block(),
        (0, 1, 0), .5, 'strict_pass', 0., 'Block slides along a shared face: contact, never penetration.')


def near_coplanar_sliver():
    return KnownAnswer(
        'near-coplanar-sliver', 'Near-coplanar 3D sliver', _wedge(1e-5), _fixed_block(), (0, 1, 0), .5,
        'strict_pass', 1e-5,
        'Near-coplanar face dips 1e-5 mm: a real but sub-contact-tolerance 3D overlap, retained as evidence.')


def shallow_sliver():
    return KnownAnswer(
        'shallow-sliver', 'Near-coplanar 3D sliver', _wedge(.02), _fixed_block(), (0, 1, 0), .5,
        'conditional_finishing', .02, 'Same wedge dipping 0.02 mm: above contact tolerance, below allowance.')


def between_sample_catch():
    return KnownAnswer(
        'between-sample-catch', 'Catch between coarse samples', box_between([0, -2, -2], [.3, 2, 2]),
        box_between([5.35, -.15, -.15], [5.65, .15, .15]), (1, 0, 0), .1, 'fail', .15,
        '0.3 mm plate sweeps through a 0.3 mm cube only between the 1 mm samples 5 and 6.',
        distances=(0, 1, 2, 3, 4, 5, 6))


def thin_fixed_wall():
    return KnownAnswer(
        'thin-fixed-wall', 'Deep local catch', box_between([-1, -1, -1], [1, 1, 1]),
        box_between([3, -5, -5], [3.2, 5, 5]), (1, 0, 0), .5, 'fail', 1.,
        'Block must pass through a 0.2 mm wall. Depth below the wall surface never exceeds 0.1 mm; depth below '
        'the block surface reaches 1 mm. One-sided depth misses this trap.')


def self_intersecting_input():
    a = box_between([-2, -2, -2], [2, 2, 2])
    b = a.copy(); b.apply_translation([1, .5, .5])
    return KnownAnswer(
        'self-intersecting-input', 'Invalid/self-intersecting mesh', box_between([10, -1, -1], [12, 1, 1]),
        trimesh.util.concatenate([a, b]), (1, 0, 0), .1, 'unsupported', None,
        'Two overlapping closed shells: watertight and consistently wound, but self-intersecting.')


_BUILDERS = {f.__name__.replace('_', '-'): f for f in (
    clean_withdrawal, thin_wide_overlap, deep_catch, bound_wider_than_depth, zero_thickness_contact,
    near_coplanar_sliver, shallow_sliver, between_sample_catch, thin_fixed_wall, self_intersecting_input)}
FIXTURES = tuple(_BUILDERS)


def fixture(name):
    """Build a fresh copy of the named fixture (meshes are mutable)."""
    return _BUILDERS[name]()
