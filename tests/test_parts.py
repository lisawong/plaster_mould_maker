"""Stage 1: generic part / release-direction / removal-order model (PRD G2, SCRATCHPAD A013)."""
import math

import pytest
from pydantic import ValidationError

from mouldflow.parts import MouldLayout, Part, two_part_planar


def test_release_direction_is_normalised_and_zero_rejected():
    assert Part(name='a', role='plaster', release_direction=(0, 3, 4)).release_direction == pytest.approx((0, .6, .8))
    with pytest.raises(ValidationError):
        Part(name='a', role='plaster', release_direction=(0, 0, 0))
    with pytest.raises(ValidationError):
        Part(name='a', role='plaster', release_direction=(math.nan, 0, 1))


def test_two_part_planar_layout_matches_prototype_order():
    layout = two_part_planar((0, 1, 0))
    steps = layout.steps()
    assert [s.part for s in steps] == ['plaster_1', 'plaster_2']
    assert steps[0].direction == (0, 1, 0) and steps[0].against == ('object', 'plaster_2')
    assert steps[1].direction == (0, -1, 0) and steps[1].against == ('object',)


def test_layout_supports_more_than_two_parts_structurally():
    parts = [Part(name='object', role='object'),
             *(Part(name=f'p{i}', role='plaster', release_direction=d)
               for i, d in enumerate([(1, 0, 0), (-1, 0, 0), (0, 0, 1)]))]
    layout = MouldLayout(parts=parts, fixed='object', removal_order=['p2', 'p0', 'p1'])
    assert [s.against for s in layout.steps()] == [('object', 'p0', 'p1'), ('object', 'p1'), ('object',)]


@pytest.mark.parametrize('kwargs', [
    dict(removal_order=['plaster_1']),                          # plaster_2 never removed
    dict(removal_order=['plaster_1', 'plaster_2', 'plaster_1']),  # removed twice
    dict(removal_order=['plaster_1', 'ghost']),                  # unknown part
    dict(removal_order=['object', 'plaster_1', 'plaster_2']),    # fixed part cannot move
    dict(fixed='ghost'),
])
def test_invalid_layouts_rejected(kwargs):
    base = dict(parts=[Part(name='object', role='object'),
                       Part(name='plaster_1', role='plaster', release_direction=(0, 1, 0)),
                       Part(name='plaster_2', role='plaster', release_direction=(0, -1, 0))],
                fixed='object', removal_order=['plaster_1', 'plaster_2'])
    with pytest.raises(ValidationError):
        MouldLayout(**{**base, **kwargs})


def test_duplicate_names_and_moving_part_without_direction_rejected():
    with pytest.raises(ValidationError):
        MouldLayout(parts=[Part(name='object', role='object'), Part(name='object', role='plaster', release_direction=(0, 1, 0))],
                    fixed='object', removal_order=[])
    with pytest.raises(ValidationError):
        MouldLayout(parts=[Part(name='object', role='object'), Part(name='p', role='plaster')],
                    fixed='object', removal_order=['p'])
