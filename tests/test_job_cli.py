"""Stage 1: `mouldflow job init|status|decide` returns versioned JSON (PRD R9)."""
import json
import os
import subprocess
import sys

from mouldflow.job import Job


def run(*args):
    result = subprocess.run([sys.executable, '-m', 'mouldflow.cli', *map(str, args)],
                            capture_output=True, text=True, env={**os.environ})
    return result.returncode, json.loads(result.stdout)


def test_init_then_status(tmp_path):
    code, out = run('job', 'init', tmp_path / 'job', '--finishing-allowance-mm', '0.2')
    assert code == 0, out
    assert out['schema_version'] == 'mouldflow.result/1'
    assert out['status'] == 'ok' and out['next_action'] == 'generate_input'
    code, out = run('job', 'status', tmp_path / 'job')
    assert code == 0
    assert out['details']['settings']['plaster']['finishing_allowance_mm'] == 0.2
    assert out['details']['gates']['input']['status'] == 'not_submitted'


def test_init_with_settings_file(tmp_path):
    overrides = tmp_path / 'o.json'
    overrides.write_text(json.dumps({'forms': {'lip_extension_mm': 25}}))
    code, out = run('job', 'init', tmp_path / 'job', '--settings', overrides)
    assert code == 0, out
    assert out['details']['settings']['forms']['lip_extension_mm'] == 25


def test_errors_are_json_with_nonzero_exit(tmp_path):
    code, out = run('job', 'status', tmp_path / 'nope')
    assert code != 0
    assert out['status'] == 'error' and out['error'] and out['next_action']
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'plaster': {'finishing_allowance_mm': -1}}))
    code, out = run('job', 'init', tmp_path / 'job', '--settings', bad)
    assert code != 0 and out['status'] == 'error'
    assert not (tmp_path / 'job').exists()


def test_decide_without_answer_is_not_approval(tmp_path):
    job = Job.init(tmp_path / 'job')
    (job.root / 'source/input.stl').write_text('mesh')
    revision = job.submit('input', ['source/input.stl'], outcome='strict_pass')
    code, out = run('job', 'decide', job.root, 'input', '--revision', revision, '--note', 'fine')
    assert code != 0 and out['status'] == 'error'
    code, out = run('job', 'status', job.root)
    assert out['details']['gates']['input']['status'] == 'pending'
    code, out = run('job', 'decide', job.root, 'input', '--revision', revision, '--answer', 'approve', '--note', 'User approves scale')
    assert code == 0, out
    assert out['details']['gates']['input']['status'] == 'approved'
    assert out['next_action'] == 'generate_plaster'


def test_top_level_help_lists_job_commands(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'mouldflow.cli', '--help'], capture_output=True, text=True)
    assert result.returncode == 0 and 'job' in result.stdout
