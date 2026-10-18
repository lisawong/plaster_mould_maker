"""Stage 3: `mouldflow intake` and `mouldflow prepare` print versioned JSON (PRD R9.1, R9.2)."""
import json
import os
import subprocess
import sys

import pytest

from test_intake import box_stl, degenerate_stl, two_body_stl


def run(*args):
    result = subprocess.run([sys.executable, '-m', 'mouldflow.cli', *map(str, args)],
                            capture_output=True, text=True, env={**os.environ})
    return result.returncode, json.loads(result.stdout)


def test_intake_then_prepare(tmp_path):
    job = tmp_path / 'job'
    assert run('job', 'init', job)[1]['next_action'] == 'intake'
    code, out = run('intake', job, box_stl(tmp_path / 'thing.stl'), '--units', 'cm',
                    '--target-mm', '60', '--target-axis', 'z', '--purpose', 'cup')
    assert code == 0, out
    assert out['command'] == 'intake' and out['next_action'] == 'generate_input'
    code, out = run('prepare', job, '--rotate', 'x=90', '--rotate', 'z=45')
    assert code == 0, out
    assert out['command'] == 'prepare' and out['stage'] == 'input'
    assert out['outcome'] == 'strict_pass' and out['next_action'] == 'review_input'
    extent = out['metrics']['extent_z_mm']
    assert extent['value'] == pytest.approx(60, abs=1e-4) and (extent['unit'], extent['kind']) == ('mm', 'measured')
    assert all(not os.path.isabs(p) for p in out['evidence'])
    code, out = run('job', 'status', job)
    assert out['details']['gates']['input']['status'] == 'pending'


def test_units_required(tmp_path):
    job = tmp_path / 'job'
    run('job', 'init', job)
    result = subprocess.run([sys.executable, '-m', 'mouldflow.cli', 'intake', str(job),
                             str(box_stl(tmp_path / 'thing.stl'))], capture_output=True, text=True)
    assert result.returncode == 2 and '--units' in result.stderr


def test_rejection_is_actionable_json(tmp_path):
    job = tmp_path / 'job'
    run('job', 'init', job)
    run('intake', job, degenerate_stl(tmp_path / 'bad.stl'), '--units', 'mm')
    code, out = run('prepare', job)
    assert code == 2 and out['status'] == 'error'
    assert out['details']['problems'][0]['code'] == 'degenerate_faces'
    assert '--repair drop-degenerate' in out['next_action']
    code, out = run('prepare', job, '--repair', 'drop-degenerate', '--repair', 'stitch=0.01')
    assert code == 0, out


def test_unsupported_input_says_so(tmp_path):
    job = tmp_path / 'job'
    run('job', 'init', job)
    run('intake', job, two_body_stl(tmp_path / 'two.stl'), '--units', 'mm')
    code, out = run('prepare', job)
    assert code == 2 and out['outcome'] == 'unsupported'
    assert 'new job' in out['next_action']


def test_prepare_before_intake(tmp_path):
    job = tmp_path / 'job'
    run('job', 'init', job)
    code, out = run('prepare', job)
    assert code == 2 and 'intake' in out['error']
