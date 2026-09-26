"""Stage 1: job folder and hash-bound review gates (PRD R1.1, R1.3, G5; EVALUATION-PLAN state tests)."""
import json
import shutil

import pytest

from mouldflow.job import GATES, GateBlocked, GateStatus, Job, JobError, MissingAnswer
from mouldflow.settings import JobSettings


def artifact(job, rel, text):
    path = job.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return rel


def approve(job, gate, rel=None, outcome='strict_pass'):
    rel = artifact(job, rel or f'candidates/{gate}/part.stl', f'{gate} geometry')
    revision = job.submit(gate, [rel], outcome=outcome)
    job.decide(gate, revision, 'approve', f'User approves {gate}')
    return revision


@pytest.fixture
def job(tmp_path):
    return Job.init(tmp_path / 'job')


# --- folder -----------------------------------------------------------------

def test_init_creates_folder_layout_with_relative_paths_only(tmp_path):
    job = Job.init(tmp_path / 'job')
    for name in ['job.json', 'state.json', 'source', 'candidates', 'reviews', 'approved']:
        assert (job.root / name).exists(), name
    state = json.loads((job.root / 'state.json').read_text())
    text = json.dumps({k: v for k, v in state.items() if k != 'last_verified_root'})
    assert str(tmp_path) not in text
    assert str(tmp_path) not in (job.root / 'job.json').read_text()


def test_init_refuses_non_empty_folder_and_open_refuses_non_job(tmp_path):
    (tmp_path / 'busy').mkdir()
    (tmp_path / 'busy' / 'x').write_text('x')
    with pytest.raises(JobError):
        Job.init(tmp_path / 'busy')
    with pytest.raises(JobError):
        Job.open(tmp_path / 'busy')


def test_all_gates_start_not_submitted(job):
    assert GATES == ('input', 'plaster', 'forms', 'export')
    assert all(job.gate_status(g) is GateStatus.NOT_SUBMITTED for g in GATES)
    assert job.next_action() == 'generate_input'


def test_artifacts_must_live_inside_the_job(job, tmp_path):
    outside = tmp_path / 'outside.stl'
    outside.write_text('x')
    for bad in [str(outside), '../outside.stl', 'candidates/missing.stl']:
        with pytest.raises(JobError):
            job.submit('input', [bad], outcome='strict_pass')
    with pytest.raises(JobError):
        job.submit('input', [], outcome='strict_pass')


# --- pending gate blocks ----------------------------------------------------

def test_pending_gate_blocks_its_dependent_stage(job):
    rel = artifact(job, 'source/input.stl', 'mesh')
    job.submit('input', [rel], outcome='strict_pass')
    assert job.gate_status('input') is GateStatus.PENDING
    assert job.next_action() == 'review_input'
    with pytest.raises(GateBlocked):
        job.require_approved('input')
    with pytest.raises(GateBlocked):
        job.submit('plaster', [artifact(job, 'candidates/p.stl', 'p')], outcome='strict_pass')


def test_failed_or_uncertain_outcome_cannot_be_approved(job):
    for outcome in ['fail', 'inconclusive', 'unsupported']:
        rev = job.submit('input', [artifact(job, 'source/input.stl', outcome)], outcome=outcome)
        assert job.next_action() == 'resolve_input_checks'
        with pytest.raises(GateBlocked):
            job.decide('input', rev, 'approve', 'looks fine to me')
        assert job.gate_status('input') is GateStatus.PENDING


def test_conditional_finishing_is_approvable(job):
    approve(job, 'input', outcome='conditional_finishing')
    assert job.gate_status('input') is GateStatus.APPROVED


def test_approval_survives_resume(job):
    approve(job, 'input')
    resumed = Job.open(job.root)
    assert resumed.gate_status('input') is GateStatus.APPROVED
    resumed.require_approved('input')
    assert resumed.next_action() == 'generate_plaster'


# --- missing answer is not approval -----------------------------------------

@pytest.mark.parametrize('answer', [None, '', '   '])
def test_missing_answer_is_not_approval(job, answer):
    rev = job.submit('input', [artifact(job, 'source/input.stl', 'mesh')], outcome='strict_pass')
    with pytest.raises(MissingAnswer):
        job.decide('input', rev, answer, 'note')
    assert job.gate_status('input') is GateStatus.PENDING
    assert Job.open(job.root).gate_status('input') is GateStatus.PENDING


def test_answer_must_be_explicit_and_carry_a_human_note(job):
    rev = job.submit('input', [artifact(job, 'source/input.stl', 'mesh')], outcome='strict_pass')
    for answer in ['yes', 'ok', 'Approve']:
        with pytest.raises(JobError):
            job.decide('input', rev, answer, 'note')
    with pytest.raises(JobError):
        job.decide('input', rev, 'approve', '  ')
    assert job.gate_status('input') is GateStatus.PENDING


def test_stale_revision_cannot_be_approved(job):
    old = job.submit('input', [artifact(job, 'source/input.stl', 'v1')], outcome='strict_pass')
    job.submit('input', [artifact(job, 'source/input.stl', 'v2')], outcome='strict_pass')
    with pytest.raises(GateBlocked):
        job.decide('input', old, 'approve', 'approve v1')


def test_request_changes_requires_resubmission(job):
    rev = job.submit('input', [artifact(job, 'source/input.stl', 'mesh')], outcome='strict_pass')
    job.decide('input', rev, 'request_changes', 'Rotate the handle')
    assert job.gate_status('input') is GateStatus.CHANGES_REQUESTED
    assert job.next_action() == 'regenerate_input'
    with pytest.raises(GateBlocked):
        job.decide('input', rev, 'approve', 'changed my mind')
    assert any(e['event'] == 'changes_requested' and e['note'] == 'Rotate the handle' for e in job.history())


# --- upstream change invalidates downstream ---------------------------------

def test_changed_upstream_artifact_invalidates_it_and_everything_downstream(job):
    for gate in GATES:
        approve(job, gate)
    (job.root / 'candidates/input/part.stl').write_text('edited')
    reopened = Job.open(job.root)
    assert [reopened.gate_status(g) for g in GATES] == [GateStatus.STALE] * 4
    assert reopened.next_action() == 'regenerate_input'


def test_resubmitting_upstream_invalidates_downstream(job):
    approve(job, 'input')
    approve(job, 'plaster')
    job.submit('input', [artifact(job, 'source/input-v2.stl', 'v2')], outcome='strict_pass')
    assert job.gate_status('input') is GateStatus.PENDING
    assert job.gate_status('plaster') is GateStatus.STALE


def test_request_changes_upstream_invalidates_downstream(job):
    rev = approve(job, 'input')
    approve(job, 'plaster')
    job.submit('input', ['candidates/input/part.stl'], outcome='strict_pass')
    job.decide('input', rev, 'request_changes', 'shorter spout')
    assert job.gate_status('plaster') is GateStatus.STALE


def test_settings_change_invalidates_only_its_gate_and_downstream(job):
    for gate in GATES:
        approve(job, gate)
    job.update_settings(job.settings.with_overrides({'forms': {'lip_extension_mm': 25}}))
    assert [job.gate_status(g) for g in GATES] == [GateStatus.APPROVED, GateStatus.APPROVED, GateStatus.STALE, GateStatus.STALE]


def test_hand_edited_settings_file_is_detected(job):
    approve(job, 'input')
    approve(job, 'plaster')
    data = json.loads((job.root / 'job.json').read_text())
    data['settings']['plaster']['finishing_allowance_mm'] = 0.5
    (job.root / 'job.json').write_text(json.dumps(data))
    reopened = Job.open(job.root)
    assert reopened.gate_status('input') is GateStatus.APPROVED
    assert reopened.gate_status('plaster') is GateStatus.STALE


def test_stale_never_heals_when_bytes_are_restored(job):
    approve(job, 'input')
    path = job.root / 'candidates/input/part.stl'
    original = path.read_text()
    path.write_text('edited')
    assert job.gate_status('input') is GateStatus.STALE
    path.write_text(original)
    assert Job.open(job.root).gate_status('input') is GateStatus.STALE


def test_deleted_artifact_invalidates(job):
    approve(job, 'input')
    (job.root / 'candidates/input/part.stl').unlink()
    assert job.gate_status('input') is GateStatus.STALE


# --- relocation reverifies, never reapproves --------------------------------

def test_relocation_is_detected_and_intact_approvals_survive(job, tmp_path):
    approve(job, 'input')
    moved = tmp_path / 'moved'
    shutil.move(job.root, moved)
    reopened = Job.open(moved)
    assert reopened.relocated
    assert reopened.gate_status('input') is GateStatus.APPROVED
    assert any(e['event'] == 'relocated' for e in reopened.history())
    assert not Job.open(moved).relocated  # recorded once


def test_relocation_never_approves_pending_or_stale_gates(job, tmp_path):
    approve(job, 'input')
    job.submit('plaster', [artifact(job, 'candidates/plaster/p.stl', 'p')], outcome='strict_pass')
    (job.root / 'candidates/input/part.stl').write_text('edited')
    assert job.gate_status('input') is GateStatus.STALE
    (job.root / 'candidates/input/part.stl').write_text('input geometry')
    moved = tmp_path / 'moved'
    shutil.move(job.root, moved)
    reopened = Job.open(moved)
    assert reopened.gate_status('input') is GateStatus.STALE
    assert reopened.gate_status('plaster') is GateStatus.STALE


def test_relocation_with_changed_artifact_invalidates(job, tmp_path):
    approve(job, 'input')
    moved = tmp_path / 'moved'
    shutil.move(job.root, moved)
    (moved / 'candidates/input/part.stl').write_text('edited in transit')
    assert Job.open(moved).gate_status('input') is GateStatus.STALE


# --- per-job settings don't leak --------------------------------------------

def test_per_job_allowance_does_not_leak(tmp_path):
    a = Job.init(tmp_path / 'a', JobSettings().with_overrides({'plaster': {'finishing_allowance_mm': 0.5}}))
    b = Job.init(tmp_path / 'b')
    assert a.settings.plaster.finishing_allowance_mm == 0.5
    assert b.settings.plaster.finishing_allowance_mm == 0.1
    assert Job.open(tmp_path / 'a').settings.plaster.finishing_allowance_mm == 0.5
    assert Job.open(tmp_path / 'b').settings.plaster.finishing_allowance_mm == 0.1
    assert JobSettings().plaster.finishing_allowance_mm == 0.1


def test_status_reports_every_gate_and_next_action(job):
    approve(job, 'input')
    status = job.status()
    assert status['next_action'] == 'generate_plaster'
    assert status['gates']['input']['status'] == 'approved'
    assert status['gates']['input']['decision'] == 'User approves input'
    assert status['gates']['plaster']['status'] == 'not_submitted'
    assert status['settings']['plaster']['finishing_allowance_mm'] == 0.1
