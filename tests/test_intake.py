"""Stage 3: intake and prepare (PRD R1.2, R2.1-R2.3).

Scale is never guessed, invalid meshes are rejected with reasons, repairs only run when asked
and every prepare is a new revision that invalidates downstream gates.
"""
import json

import numpy as np
import pytest
import trimesh

from mouldflow.intake import InputRejected, IntakeError, UNIT_MM, intake, prepare
from mouldflow.job import GateStatus, Job
from mouldflow.known_answers import fixture


# --- fixtures ---------------------------------------------------------------------------------

def _write(mesh, path):
    mesh.export(path)
    return path


def box_stl(path, extents=(1, 2, 3)):
    box = trimesh.creation.box(extents)
    box.apply_translation((5, 5, 5))  # off-centre, so centring is observable
    return _write(box, path)


def open_stl(path):
    box = trimesh.creation.box((10, 10, 10))
    box.update_faces(np.arange(1, len(box.faces)))
    return _write(box, path)


def two_body_stl(path):
    a = trimesh.creation.box((10, 10, 10))
    b = trimesh.creation.box((10, 10, 10))
    b.apply_translation((30, 0, 0))
    return _write(trimesh.util.concatenate([a, b]), path)


def inverted_stl(path):
    box = trimesh.creation.box((10, 10, 10))
    box.invert()
    return _write(box, path)


def inconsistent_stl(path):
    box = trimesh.creation.box((10, 10, 10))
    faces = box.faces.copy()
    faces[0] = faces[0][::-1]
    return _write(trimesh.Trimesh(box.vertices, faces, process=False), path)


def degenerate_stl(path):
    """Closed box with a zero-area sliver at a T-junction (common in exported CAD/Boolean STLs).

    Dropping the sliver opens the T-junction, so it needs stitching afterwards as well.
    """
    box = trimesh.creation.box((10, 20, 30))
    vertices, faces = box.vertices.tolist(), box.faces.tolist()
    a, b, c = faces[0]
    m = len(vertices)
    vertices.append(((np.array(vertices[a]) + np.array(vertices[b])) / 2).tolist())
    faces[0] = [a, m, c]
    faces += [[m, b, c], [a, b, m]]
    return _write(trimesh.Trimesh(vertices, faces, process=False), path)


def self_intersecting_stl(path):
    return _write(fixture('self-intersecting-input').fixed, path)  # the overlapping shells


@pytest.fixture
def job(tmp_path):
    return Job.init(tmp_path / 'job')


def prepared_mesh(job, record):
    return trimesh.load_mesh(job.root / record.details['revision_dir'] / 'prepared.stl')


def codes(error):
    return {p['code'] for p in error.value.problems}


# --- intake -----------------------------------------------------------------------------------

def test_intake_copies_and_hashes_source(job, tmp_path):
    stl = box_stl(tmp_path / 'thing.stl')
    record = intake(job, stl, units='cm', purpose='test vase')
    copied = job.root / 'source' / 'thing.stl'
    assert copied.read_bytes() == stl.read_bytes()
    source = Job.open(job.root).settings.source
    assert (source.file, source.units, source.purpose) == ('source/thing.stl', 'cm', 'test vase')
    assert source.sha256 == record.hashes['source/thing.stl'] and len(source.sha256) == 64
    assert record.status == 'ok' and record.next_action == 'generate_input'
    assert record.details['raw_extents'] == pytest.approx([1, 2, 3])
    assert record.details['extents_mm'] == pytest.approx([10, 20, 30])


def test_units_are_never_guessed(job, tmp_path):
    stl = box_stl(tmp_path / 'thing.stl')
    for units in (None, '', 'furlongs'):
        with pytest.raises(IntakeError, match='units'):
            intake(job, stl, units=units)
    assert not any((job.root / 'source').iterdir())


def test_prepare_refuses_without_intake(job):
    with pytest.raises(IntakeError, match='intake'):
        prepare(job)
    assert job.next_action() == 'intake'


def test_target_axis_without_target_is_an_error(job, tmp_path):
    with pytest.raises(IntakeError, match='target'):
        intake(job, box_stl(tmp_path / 'thing.stl'), units='mm', target_mm=None, target_axis='Z')


def test_intake_rejects_non_stl_and_unloadable(job, tmp_path):
    other = tmp_path / 'thing.obj'
    other.write_text('v 0 0 0\n')
    with pytest.raises(IntakeError, match='STL'):
        intake(job, other, units='mm')
    broken = tmp_path / 'broken.stl'
    broken.write_bytes(b'not an stl')
    with pytest.raises(IntakeError):
        intake(job, broken, units='mm')
    with pytest.raises(IntakeError, match='not found'):
        intake(job, tmp_path / 'missing.stl', units='mm')


def test_one_source_per_job(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    intake(job, tmp_path / 'thing.stl', units='cm')  # same file, corrected declaration: fine
    with pytest.raises(IntakeError, match='new job'):
        intake(job, box_stl(tmp_path / 'other.stl', (4, 4, 4)), units='mm')


# --- prepare: scale, orientation, centring ----------------------------------------------------

@pytest.mark.parametrize('units', UNIT_MM)
def test_declared_units_convert_to_mm(job, tmp_path, units):
    intake(job, box_stl(tmp_path / 'thing.stl'), units=units)
    record = prepare(job)
    factor = UNIT_MM[units]
    mesh = prepared_mesh(job, record)
    assert mesh.extents == pytest.approx(np.array([1, 2, 3]) * factor)
    assert mesh.bounds.mean(axis=0) == pytest.approx([0, 0, 0], abs=1e-5)  # binary STL is float32
    assert record.details['unit_scale'] == factor
    assert record.metrics['extent_z_mm'].value == pytest.approx(3 * factor)


def test_target_rescales_after_rotation(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm', target_mm=50, target_axis='Y')
    record = prepare(job, rotations=['x=90'])  # Y and Z swap: Y extent is 3 before target scaling
    mesh = prepared_mesh(job, record)
    assert mesh.extents == pytest.approx(np.array([1, 3, 2]) * 50 / 3)
    assert record.details['target_scale'] == pytest.approx(50 / 3)


def test_rotations_apply_in_order_and_are_recorded(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    record = prepare(job, rotations=['z=90', 'x=90'])  # (1,2,3) -> (2,1,3) -> (2,3,1)
    assert prepared_mesh(job, record).extents == pytest.approx([2, 3, 1])
    assert Job.open(job.root).settings.source.rotations == (('Z', 90.0), ('X', 90.0))


def test_transform_maps_source_to_prepared(job, tmp_path):
    stl = box_stl(tmp_path / 'thing.stl')
    intake(job, stl, units='cm', target_mm=100, target_axis='Z')
    record = prepare(job, rotations=['y=30'])
    source = trimesh.load_mesh(stl)
    source.apply_transform(np.array(record.details['transform']))
    assert source.bounds == pytest.approx(prepared_mesh(job, record).bounds, abs=1e-4)


@pytest.mark.parametrize('bad', ['x', 'w=90', 'x=abc', 'x=nan', 'x=inf'])
def test_bad_rotation_is_an_error(job, tmp_path, bad):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    with pytest.raises(IntakeError, match='rotate'):
        prepare(job, rotations=[bad])


# --- prepare: validation and repairs ----------------------------------------------------------

@pytest.mark.parametrize('make, code, repair', [
    (open_stl, 'open', 'stitch=TOL'),
    (two_body_stl, 'multiple_components', None),
    (inverted_stl, 'inverted', 'fix-winding'),
    (inconsistent_stl, 'inconsistent_winding', 'fix-winding'),
    (degenerate_stl, 'degenerate_faces', 'drop-degenerate'),
    (self_intersecting_stl, 'self_intersecting', None),
])
def test_invalid_meshes_rejected_with_reasons(job, tmp_path, make, code, repair):
    intake(job, make(tmp_path / 'bad.stl'), units='mm')
    with pytest.raises(InputRejected) as error:
        prepare(job)
    problem = next(p for p in error.value.problems if p['code'] == code)
    assert problem['message'] and problem['repair'] == repair
    assert error.value.outcome == (None if repair else 'unsupported')
    assert not (job.root / 'candidates' / 'input').exists()  # a rejection writes no revision
    assert job.gate_status('input') is GateStatus.NOT_SUBMITTED


def test_requested_repairs_create_a_valid_revision(job, tmp_path):
    intake(job, degenerate_stl(tmp_path / 'bad.stl'), units='mm')
    with pytest.raises(InputRejected) as error:
        prepare(job, repairs=['drop-degenerate'])
    assert codes(error) == {'open'}  # dropping the sliver opens its T-junction
    record = prepare(job, repairs=['drop-degenerate', 'stitch=0.01'])
    mesh = prepared_mesh(job, record)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert mesh.volume == pytest.approx(6000)
    assert [r['repair'] for r in record.details['repairs']] == ['drop-degenerate', 'stitch']
    assert record.details['repairs'][1]['tolerance_mm'] == 0.01
    assert (job.root / record.details['revision_dir'] / 'before' / 'views.png').is_file()


@pytest.mark.parametrize('make', [inverted_stl, inconsistent_stl])
def test_fix_winding(job, tmp_path, make):
    intake(job, make(tmp_path / 'bad.stl'), units='mm')
    mesh = prepared_mesh(job, prepare(job, repairs=['fix-winding']))
    assert mesh.is_winding_consistent and mesh.volume == pytest.approx(1000)


def test_unneeded_or_unknown_repair_is_an_error(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    with pytest.raises(IntakeError, match='fix-winding'):
        prepare(job, repairs=['fix-winding'])
    for bad in ('melt', 'stitch', 'stitch=-1', 'stitch=abc'):
        with pytest.raises(IntakeError, match='repair'):
            prepare(job, repairs=[bad])


# --- revisions and gates ----------------------------------------------------------------------

def test_prepare_submits_input_gate_with_previews(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    record = prepare(job)
    folder = record.details['revision_dir']
    assert folder == 'candidates/input/r001'
    for name in ('prepared.stl', 'prepare-report.json', 'views.png', 'sections.png', 'viewer.html',
                 'before/views.png'):
        assert f'{folder}/{name}' in record.evidence
        assert (job.root / folder / name).is_file()
    assert record.outcome == 'strict_pass' and record.next_action == 'review_input'
    status = Job.open(job.root).status()['gates']['input']
    assert status['status'] == 'pending' and status['revision'] == record.details['revision']
    assert 'source/thing.stl' in status['artifacts']
    report = json.loads((job.root / folder / 'prepare-report.json').read_text())
    assert report['revision_dir'] == folder and report['limitations']


def test_each_prepare_is_a_new_revision(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    first = prepare(job)
    first_bytes = (job.root / first.details['revision_dir'] / 'prepared.stl').read_bytes()
    second = prepare(job, rotations=['z=90'])
    assert second.details['revision_dir'] == 'candidates/input/r002'
    assert second.details['revision'] != first.details['revision']
    assert (job.root / first.details['revision_dir'] / 'prepared.stl').read_bytes() == first_bytes


def _approve_input_and_plaster(job):
    job.decide('input', job.status()['gates']['input']['revision'], 'approve', 'looks right')
    (job.root / 'candidates' / 'plaster.stl').write_text('stand-in plaster artifact')
    revision = job.submit('plaster', ['candidates/plaster.stl'], 'strict_pass')
    job.decide('plaster', revision, 'approve', 'ok')
    assert job.gate_status('plaster') is GateStatus.APPROVED


def test_repair_revision_invalidates_downstream(job, tmp_path):
    intake(job, degenerate_stl(tmp_path / 'bad.stl'), units='mm')
    prepare(job, repairs=['drop-degenerate', 'stitch=0.01'])
    _approve_input_and_plaster(job)
    prepare(job, repairs=['drop-degenerate', 'stitch=0.02'])
    reopened = Job.open(job.root)
    assert reopened.gate_status('input') is GateStatus.PENDING
    assert reopened.gate_status('plaster') is GateStatus.STALE


def test_changed_declaration_invalidates_downstream(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    prepare(job)
    _approve_input_and_plaster(job)
    intake(job, tmp_path / 'thing.stl', units='cm')
    reopened = Job.open(job.root)
    assert reopened.gate_status('input') is GateStatus.STALE
    assert reopened.gate_status('plaster') is GateStatus.STALE
    assert reopened.next_action() == 'regenerate_input'


def test_changed_source_bytes_block_prepare(job, tmp_path):
    intake(job, box_stl(tmp_path / 'thing.stl'), units='mm')
    prepare(job)
    box_stl(job.root / 'source' / 'thing.stl', (7, 7, 7))
    with pytest.raises(IntakeError, match='changed'):
        prepare(job)
    assert Job.open(job.root).gate_status('input') is GateStatus.STALE
