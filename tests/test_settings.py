"""Stage 1: per-job settings schema and defaults (PRD R1, R5.3, R6)."""
import pytest
from pydantic import ValidationError

from mouldflow.settings import GATE_SECTIONS, JobSettings


def test_defaults_match_prd():
    s = JobSettings()
    assert s.source.units is None  # STL has no units; never guessed
    assert s.plaster.finishing_allowance_mm == 0.1
    assert s.forms.wall_thickness_mm == 3
    assert s.forms.lip_thickness_mm == s.forms.wall_thickness_mm
    assert s.forms.lip_extension_mm == 20
    assert s.forms.groove_clearance_mm == 0.25
    assert s.forms.wall_clearance_mm == 30
    assert s.forms.fill_line_depth_mm == 0.6
    assert s.printer.bed_mm == (250, 210, 210)


def test_teapot_allowance_is_not_the_default():
    assert JobSettings().plaster.finishing_allowance_mm != 0.5


def test_settings_are_immutable_so_one_job_cannot_change_the_defaults():
    s = JobSettings()
    with pytest.raises(ValidationError):
        s.plaster.finishing_allowance_mm = 0.5
    changed = s.with_overrides({'plaster': {'finishing_allowance_mm': 0.5}})
    assert changed.plaster.finishing_allowance_mm == 0.5
    assert s.plaster.finishing_allowance_mm == 0.1
    assert JobSettings().plaster.finishing_allowance_mm == 0.1


def test_overrides_merge_per_field():
    s = JobSettings().with_overrides({'forms': {'lip_extension_mm': 25}})
    assert s.forms.lip_extension_mm == 25
    assert s.forms.wall_thickness_mm == 3


@pytest.mark.parametrize('overrides', [
    {'plaster': {'finishing_allowance_mm': -0.1}},
    {'forms': {'wall_thickness_mm': 0}},
    {'forms': {'groove_clearance_mm': -1}},
    {'forms': {'fill_line_depth_mm': 3}},  # would cut through a 3 mm wall
    {'source': {'units': 'furlongs'}},
    {'source': {'target_axis': 'W'}},
    {'printer': {'bed_mm': [250, 210]}},
    {'forms': {'unknown_field': 1}},
    {'unknown_section': {}},
])
def test_invalid_settings_are_rejected(overrides):
    with pytest.raises(ValidationError):
        JobSettings().with_overrides(overrides)


def test_json_round_trip():
    s = JobSettings().with_overrides({'source': {'units': 'mm', 'target_mm': 50, 'target_axis': 'Y'}})
    assert JobSettings.model_validate_json(s.model_dump_json()) == s


def test_each_gate_binds_one_section_and_hash_tracks_only_that_section():
    assert GATE_SECTIONS == {'input': 'source', 'plaster': 'plaster', 'forms': 'forms', 'export': 'printer'}
    a = JobSettings()
    b = a.with_overrides({'forms': {'lip_extension_mm': 25}})
    assert a.section_hash('source') == b.section_hash('source')
    assert a.section_hash('plaster') == b.section_hash('plaster')
    assert a.section_hash('forms') != b.section_hash('forms')
