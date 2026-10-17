"""Stage 2.5: `mouldflow view` renders PNG contact sheets, sections and a rotatable HTML viewer."""
import base64
import json
import os
import re
import subprocess
import sys

import numpy as np
import pytest
import trimesh
from PIL import Image

from mouldflow import view


def box(centre, size=(10, 10, 10)):
    return trimesh.creation.box(extents=size).apply_translation(centre)


def ring():
    """Annulus around Z: one Z section has two loops (outer wall and hole)."""
    return trimesh.creation.annulus(r_min=3, r_max=6, height=4)


def red_pixels(path):
    pixels = np.asarray(Image.open(path).convert('RGB')).astype(int)
    r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    return int(((r > 200) & (g < 80) & (b < 80)).sum())


@pytest.fixture
def scene():
    return [view.Item('lower', box((0, 0, -6))), view.Item('upper', box((0, 0, 6)))]


# --- marks --------------------------------------------------------------------------------

def test_marks_from_assessment_and_result_record(tmp_path):
    bounds = [[1, 2, 3], [4, 5, 6]]
    raw = tmp_path / 'raw.json'
    raw.write_text(json.dumps({'outcome': 'fail', 'worst_location': {'travel_mm': [0, 0], 'bounds_mm': bounds}}))
    record = tmp_path / 'record.json'
    record.write_text(json.dumps({'schema_version': 'mouldflow.result/1', 'outcome': 'fail',
                                  'details': {'worst_location': {'travel_mm': [0, 1], 'bounds_mm': bounds}}}))
    for path in (raw, record):
        [mark] = view.marks_from_record(path)
        assert mark.bounds.tolist() == bounds and mark.label == 'fail'


def test_record_without_location_gives_no_marks(tmp_path):
    path = tmp_path / 'r.json'
    path.write_text(json.dumps({'outcome': 'strict_pass', 'worst_location': None}))
    assert view.marks_from_record(path) == []


def test_parse_mark_rejects_inverted_or_short_boxes():
    assert view.parse_mark('0,0,0,1,2,3').bounds.tolist() == [[0, 0, 0], [1, 2, 3]]
    for bad in ('0,0,0,1,2', '2,0,0,1,2,3', 'a,b,c,d,e,f'):
        with pytest.raises(ValueError):
            view.parse_mark(bad)


# --- explode ------------------------------------------------------------------------------

def test_explode_pushes_parts_away_from_scene_centre():
    items = [view.Item('a', box((0, -5, 0))), view.Item('b', box((0, 5, 0))), view.Item('mid', box((0, 0, 0)))]
    moved = view.explode(items, axis='y', distance_mm=10)
    centres = [m.mesh.bounds.mean(axis=0)[1] for m in moved]
    assert centres == pytest.approx([-15, 15, 0])
    assert [m.offset[1] for m in moved] == pytest.approx([-10, 10, 0])
    assert items[0].mesh.bounds.mean(axis=0)[1] == pytest.approx(-5), 'input meshes are not modified'


# --- sections -----------------------------------------------------------------------------

def test_section_finds_outer_loop_and_hole():
    [found] = view.section_loops([view.Item('ring', ring())], axis='z', offset_mm=0)
    assert found['label'] == 'ring' and found['loops'] == 2
    assert np.array(found['bounds_mm']) == pytest.approx(np.array([[-6, -6], [6, 6]]), abs=0.05)


def test_section_that_misses_is_reported_empty():
    [found] = view.section_loops([view.Item('ring', ring())], axis='z', offset_mm=50)
    assert found['loops'] == 0 and found['bounds_mm'] is None


def test_sections_png_written(tmp_path, scene):
    out = tmp_path / 'sections.png'
    summary = view.render_sections(scene, [('x', 0.0), ('z', 6.0)], out)
    assert out.exists() and Image.open(out).size[0] > 400
    assert [s['axis'] for s in summary] == ['x', 'z']
    at_z6 = {s['label']: s['loops'] for s in summary[1]['meshes']}
    assert at_z6 == {'lower': 0, 'upper': 1}


# --- PNG views ----------------------------------------------------------------------------

def test_views_png_has_content_and_red_marks(tmp_path, scene):
    plain, marked = tmp_path / 'plain.png', tmp_path / 'marked.png'
    view.render_views(scene, plain)
    view.render_views(scene, marked, marks=[view.Mark(np.array([[-2, -2, -2], [2, 2, 2]]), 'catch')])
    pixels = np.asarray(Image.open(plain).convert('L'))
    assert pixels.std() > 5, 'image is not blank'
    assert red_pixels(marked) > red_pixels(plain) + 50


def test_up_axis_changes_the_picture(tmp_path):
    item = [view.Item('slab', box((0, 0, 0), size=(40, 4, 10)))]
    view.render_views(item, tmp_path / 'z.png', up='z')
    view.render_views(item, tmp_path / 'y.png', up='y')
    a = np.asarray(Image.open(tmp_path / 'z.png').convert('L')).astype(int)
    b = np.asarray(Image.open(tmp_path / 'y.png').convert('L')).astype(int)
    assert np.abs(a - b).mean() > 1


def test_large_meshes_are_decimated_for_png_only(tmp_path):
    big = trimesh.creation.icosphere(subdivisions=5, radius=10)  # 20480 faces
    item = view.Item('ball', big)
    preview = view.preview_mesh(item.mesh, max_faces=2000)
    assert len(preview.faces) <= 2000 and len(item.mesh.faces) == 20480
    assert view.preview_mesh(item.mesh, max_faces=50000) is item.mesh


# --- HTML viewer --------------------------------------------------------------------------

def test_html_embeds_every_mesh_and_mark(tmp_path, scene):
    out = tmp_path / 'viewer.html'
    view.write_html(scene, out, marks=[view.Mark(np.array([[0, 0, 0], [1, 1, 1]]), 'catch')], title='Two boxes')
    html = out.read_text()
    data = json.loads(re.search(r'<script type="application/json" id="scene">(.*?)</script>', html, re.S).group(1))
    assert [m['label'] for m in data['meshes']] == ['lower', 'upper']
    for embedded, item in zip(data['meshes'], scene):
        stl = trimesh.load(trimesh.util.wrap_as_stream(base64.b64decode(embedded['stl_base64'])), file_type='stl')
        assert len(stl.faces) == len(item.mesh.faces)
    assert data['marks'] == [{'label': 'catch', 'bounds_mm': [[0, 0, 0], [1, 1, 1]]}]
    assert '<title>Two boxes</title>' in html
    urls = set(re.findall(r'https?://[^\s"\')]+', html))
    assert urls and all(u.startswith(f'https://cdn.jsdelivr.net/npm/three@{view.THREE_VERSION}/') for u in urls)


def test_html_escapes_labels(tmp_path):
    out = tmp_path / 'v.html'
    view.write_html([view.Item('</script><b>', box((0, 0, 0)))], out, title='<x>')
    html = out.read_text()
    assert '</script><b>' not in html and '<title>&lt;x&gt;</title>' in html


# --- CLI ----------------------------------------------------------------------------------

def run(*args, cwd=None):
    result = subprocess.run([sys.executable, '-m', 'mouldflow.cli', *map(str, args)],
                            capture_output=True, text=True, env={**os.environ}, cwd=cwd)
    return result.returncode, json.loads(result.stdout)


def test_cli_view_writes_outputs_and_record(tmp_path):
    a, b = tmp_path / 'a.stl', tmp_path / 'b.stl'
    box((0, 0, -6)).export(a)
    box((0, 0, 6)).export(b)
    code, out = run('view', f'{a}=lower', b, '--out', tmp_path / 'look', '--section', 'z=6', '--explode', 'z=5')
    assert code == 0, out
    assert out['schema_version'] == 'mouldflow.result/1' and out['command'] == 'view' and out['status'] == 'ok'
    assert out['evidence'] == ['views.png', 'sections.png', 'viewer.html']
    for name in out['evidence']:
        assert (tmp_path / 'look' / name).exists()
    meshes = out['details']['meshes']
    assert [m['label'] for m in meshes] == ['lower', 'b']
    assert meshes[0]['faces'] == 12 and meshes[0]['watertight'] is True
    assert meshes[0]['extents_mm'] == pytest.approx([10, 10, 10])
    assert meshes[1]['explode_offset_mm'] == pytest.approx([0, 0, 5])
    assert [s['axis'] for s in out['details']['sections']] == ['z']
    assert set(out['hashes']) == {'lower', 'b'}
    assert out['next_action']


def test_cli_default_sections_cut_through_scene_centre(tmp_path):
    a = tmp_path / 'a.stl'
    box((10, 20, 30)).export(a)
    code, out = run('view', a, '--out', tmp_path / 'look', '--no-html')
    assert code == 0, out
    assert [(s['axis'], s['offset_mm']) for s in out['details']['sections']] == [('x', 10), ('y', 20), ('z', 30)]
    assert 'viewer.html' not in out['evidence']


def test_cli_view_marks_from_release_record(tmp_path):
    a = tmp_path / 'a.stl'
    box((0, 0, 0)).export(a)
    record = tmp_path / 'release.json'
    record.write_text(json.dumps({'outcome': 'fail', 'worst_location': {'travel_mm': [0, 0],
                                                                       'bounds_mm': [[-1, -1, -1], [1, 1, 1]]}}))
    code, out = run('view', a, '--out', tmp_path / 'look', '--marks-from', record)
    assert code == 0, out
    assert out['details']['marks'] == [{'label': 'fail', 'bounds_mm': [[-1, -1, -1], [1, 1, 1]]}]


def test_cli_view_errors_are_json(tmp_path):
    code, out = run('view', tmp_path / 'missing.stl', '--out', tmp_path / 'look')
    assert code == 2 and out['status'] == 'error' and 'missing.stl' in out['error'] and out['next_action']
    a = tmp_path / 'a.stl'
    box((0, 0, 0)).export(a)
    code, out = run('view', a, '--out', tmp_path / 'look', '--section', 'w=1')
    assert code == 2 and out['status'] == 'error'


# --- skill and agent docs stay in step with the CLI ----------------------------------------

@pytest.mark.parametrize('doc', ['.claude/skills/look/SKILL.md', '.claude/agents/mould-inspector.md'])
def test_documented_view_options_exist(doc):
    from pathlib import Path
    from mouldflow.cli import _parser
    root = Path(__file__).resolve().parents[1]
    text = (root / doc).read_text()
    assert text.startswith('---\nname: ')
    view_parser = _parser()._subparsers._group_actions[0].choices['view']
    known = {o for action in view_parser._actions for o in action.option_strings}
    documented = set(re.findall(r'(--[a-z][a-z-]+)', text))
    assert documented and documented <= known, documented - known


# --- inspector feedback (first mould-inspector run, 2026-10-17) ----------------------------

def test_cli_reports_piece_count_per_mesh(tmp_path):
    two = trimesh.util.concatenate([box((0, 0, 0)), box((30, 0, 0), size=(1, 1, 1))])
    path = tmp_path / 'two.stl'
    two.export(path)
    code, out = run('view', path, '--out', tmp_path / 'look', '--no-html')
    assert code == 0, out
    assert out['details']['meshes'][0]['pieces'] == 2


def test_sections_cut_the_assembled_pose_even_when_exploded(tmp_path):
    a, b = tmp_path / 'a.stl', tmp_path / 'b.stl'
    box((0, -5, 0)).export(a)
    box((0, 5, 0)).export(b)
    code, out = run('view', a, b, '--out', tmp_path / 'look', '--explode', 'y=40', '--section', 'y=-1',
                    '--section', 'y=1', '--no-html')
    assert code == 0, out
    loops = [{m['label']: m['loops'] for m in s['meshes']} for s in out['details']['sections']]
    assert loops == [{'a': 1, 'b': 0}, {'a': 0, 'b': 1}]
    assert out['details']['meshes'][1]['explode_offset_mm'] == pytest.approx([0, 40, 0])


def test_colours_follow_labels_not_argument_order():
    first = view.colours(['object', 'half_1', 'half_2'])
    assert view.colours(['half_2', 'half_1']) == {k: first[k] for k in ('half_2', 'half_1')}
    assert first == {'object': '#c99762', 'half_1': '#5b8bd0', 'half_2': '#6aa874'}


def test_named_views_are_selectable(tmp_path, scene):
    assert {'iso', 'iso-back', 'front', 'back', 'left', 'right', 'top', 'bottom'} <= set(view.VIEWS)
    out = tmp_path / 'v.png'
    view.render_views(scene, out, views=['back', 'bottom'])
    assert out.exists()
    with pytest.raises(view.ViewError):
        view.render_views(scene, out, views=['sideways'])


def test_cli_views_option_and_help_explains_directions(tmp_path):
    a = tmp_path / 'a.stl'
    box((0, 0, 0)).export(a)
    code, out = run('view', a, '--out', tmp_path / 'look', '--views', 'front,back', '--no-html')
    assert code == 0, out
    assert out['details']['views'] == ['front', 'back']
    help_text = subprocess.run([sys.executable, '-m', 'mouldflow.cli', 'view', '--help'],
                               capture_output=True, text=True).stdout
    assert 'front' in help_text and 'looks along' in help_text


# --- review fixes (REVIEW-HANDOFF.md, 2026-10-17) ------------------------------------------

@pytest.mark.parametrize('content', [
    [],
    {'outcome': 'fail', 'worst_location': 'here'},
    {'outcome': 'fail', 'worst_location': {'bounds_mm': [[0, 0], [1, 1]]}},
    {'outcome': 'fail', 'worst_location': {'bounds_mm': [[0, 0, 0], [1, 1, float('nan')]]}},
    {'outcome': 'fail', 'worst_location': {'bounds_mm': [[2, 0, 0], [1, 1, 1]]}},
    {'outcome': 'fail', 'worst_location': {'bounds_mm': [['a', 0, 0], [1, 1, 1]]}},
    {'details': [], 'outcome': 'fail'},
])
def test_malformed_release_records_give_json_errors(tmp_path, content):
    a = tmp_path / 'a.stl'
    box((0, 0, 0)).export(a)
    record = tmp_path / 'bad.json'
    record.write_text(json.dumps(content))
    code, out = run('view', a, '--out', tmp_path / 'look', '--marks-from', record, '--no-html')
    assert code == 2 and out['status'] == 'error' and out['next_action']
    assert 'bad.json' in out['error']


def test_record_with_null_bounds_gives_no_marks(tmp_path):
    path = tmp_path / 'r.json'
    path.write_text(json.dumps({'outcome': 'inconclusive', 'worst_location': {'travel_mm': [0, 1], 'bounds_mm': None}}))
    assert view.marks_from_record(path) == []


def open_box():
    mesh = box((0, 0, 0))
    mesh.update_faces(mesh.face_normals[:, 0] < 0.5)  # remove the +X wall
    return mesh


def test_open_section_paths_are_kept_not_reported_empty():
    [found] = view.section_loops([view.Item('open_box', open_box())], axis='z', offset_mm=0)
    assert found['loops'] == 0 and found['open_paths'] == 1
    assert np.array(found['bounds_mm']) == pytest.approx(np.array([[-5, -5], [5, 5]]), abs=1e-6)


def test_closed_and_missed_sections_count_no_open_paths():
    [closed] = view.section_loops([view.Item('box', box((0, 0, 0)))], axis='z', offset_mm=0)
    assert (closed['loops'], closed['open_paths']) == (1, 0)
    [missed] = view.section_loops([view.Item('box', box((0, 0, 0)))], axis='z', offset_mm=50)
    assert (missed['loops'], missed['open_paths'], missed['bounds_mm']) == (0, 0, None)


def test_open_paths_are_drawn_unfilled(tmp_path):
    from matplotlib.path import Path as MplPath
    [found] = view.section_loops([view.Item('open_box', open_box())], axis='z', offset_mm=0)
    assert view._oriented_path(found['_loops']) is None, 'open paths must not be closed and filled'
    assert len(found['_open']) == 1 and isinstance(view._oriented_path(
        view.section_loops([view.Item('box', box((0, 0, 0)))], 'z', 0)[0]['_loops']), MplPath)
    summary = view.render_sections([view.Item('open_box', open_box())], [('z', 0.0)], tmp_path / 's.png')
    assert summary[0]['meshes'][0]['open_paths'] == 1
    assert summary[0]['empty'] is False


@pytest.mark.parametrize('labels', [['wall', 'pattern'], ['pattern', 'wall'], ['pattern'], ['wall'],
                                    ['object', 'pattern', 'wall', 'half_1', 'extra']])
def test_colour_is_a_pure_function_of_label(labels):
    alone = {label: view.colours([label])[label] for label in labels}
    assert view.colours(labels) == alone
    assert all(re.fullmatch(r'#[0-9a-f]{6}', c) for c in alone.values())


def test_hashed_colours_differ_and_stay_clear_of_mark_red():
    labels = [f'part{i}' for i in range(40)] + ['wall', 'pattern']
    found = view.colours(labels)
    assert len(set(found.values())) == len(labels)
    import colorsys
    for colour in found.values():
        r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        hue = colorsys.rgb_to_hls(r, g, b)[0] * 360
        assert 30 <= hue <= 330, (colour, hue)
