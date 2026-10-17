"""Visual inspection: PNG contact sheets, cross-sections and a rotatable HTML viewer (Stage 2.5).

Pictures are evidence for a human or agent to look at; they never change a technical outcome.
PNG views may be decimated for speed; sections and the HTML viewer always use the full meshes.
"""
import base64
import hashlib
import html
import json
import os
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh

from .pipeline import solid_volume
from .result import ResultRecord

AXES = {'x': 0, 'y': 1, 'z': 2}
THREE_VERSION = '0.160.0'
# Colours follow labels (crc32 slot), so a part keeps its colour across renders; ordered so that
# object → tan, half_1 → blue, half_2 → green.
PALETTE = ('#d4a93c', '#5b8bd0', '#9a7bc7', '#6aa874', '#c99762', '#3fa7a3', '#8c8c8c', '#7f6a5a')
MARK_COLOUR = '#ff2a2a'
MAX_PREVIEW_FACES = 80000
# name: (elevation, azimuth, what it shows) in the up-aligned frame. "depth" is the axis after `up`
# in the cycle x → y → z → x minus one step: +y for up=z, +x for up=y, +z for up=x.
VIEWS = {
    'iso': (25, -60, 'from the front-right, above'),
    'iso-back': (25, 120, 'from the back-left, above'),
    'front': (0, -90, 'looks along +depth (+y when up=z)'),
    'back': (0, 90, 'looks along -depth'),
    'right': (0, 0, 'looks toward the left (along -x when up=z)'),
    'left': (0, 180, 'looks toward the right (along +x when up=z)'),
    'top': (90, -90, 'looks down the up axis'),
    'bottom': (-90, -90, 'looks up the up axis'),
}
DEFAULT_VIEWS = ('iso', 'iso-back', 'front', 'top')
MESH_SUFFIXES = ('.stl', '.obj', '.ply', '.off', '.glb', '.gltf')
LIMITATIONS = [
    'Pictures are inspection aids only; release outcomes come from the release checks, not from these images.',
    'PNG views use painter-sorted triangles and may be decimated; judge fine detail from sections or the HTML viewer.',
    'The HTML viewer loads three.js from cdn.jsdelivr.net, so it needs a network connection.',
]
NEXT_ACTION = ('Look at views.png and sections.png (agents: Read the images); open viewer.html in a browser to '
               'rotate, toggle parts and slide a section plane. Report what you see; never treat a picture as a pass.')


class ViewError(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    label: str
    mesh: trimesh.Trimesh
    offset: tuple = (0., 0., 0.)


@dataclass(frozen=True, eq=False)
class Mark:
    bounds: np.ndarray
    label: str = 'mark'

    def record(self):
        return {'label': self.label, 'bounds_mm': np.asarray(self.bounds, float).tolist()}


@dataclass
class Cut:
    axis: str
    offset_mm: float
    meshes: list = field(default_factory=list)


# --- inputs -------------------------------------------------------------------------------

def parse_mark(text):
    try:
        values = [float(v) for v in text.split(',')]
    except ValueError:
        raise ViewError(f'mark must be six numbers x0,y0,z0,x1,y1,z1: {text!r}') from None
    if len(values) != 6:
        raise ViewError(f'mark must be six numbers x0,y0,z0,x1,y1,z1: {text!r}')
    bounds = np.array(values).reshape(2, 3)
    if (bounds[0] > bounds[1]).any():
        raise ViewError(f'mark minimum corner must not exceed its maximum: {text!r}')
    return Mark(bounds, 'mark')


def marks_from_record(path):
    """The worst location from a release assessment or its `mouldflow.result/1` record."""
    data = json.loads(Path(path).read_text())
    location = data.get('worst_location') or data.get('details', {}).get('worst_location')
    if not location or not location.get('bounds_mm'):
        return []
    return [Mark(np.asarray(location['bounds_mm'], float), data.get('outcome') or 'worst_location')]


def parse_axis_value(text, what):
    axis, sep, value = text.partition('=')
    axis = axis.strip().lower()
    if not sep or axis not in AXES:
        raise ViewError(f'{what} must look like AXIS=MM with AXIS one of x, y, z: {text!r}')
    try:
        return axis, float(value)
    except ValueError:
        raise ViewError(f'{what} value must be a number in mm: {text!r}') from None


def parse_mesh_arg(text):
    path, sep, label = text.rpartition('=')
    if sep and path.lower().endswith(MESH_SUFFIXES) and label:
        return Path(path), label
    return Path(text), Path(text).stem


def load_items(specs):
    items, labels = [], set()
    for path, label in specs:
        if not path.is_file():
            raise ViewError(f'mesh not found: {path}')
        if label in labels:
            raise ViewError(f'duplicate label {label!r}; give each mesh a unique PATH=LABEL')
        labels.add(label)
        mesh = trimesh.load(path, force='mesh')
        if not len(mesh.faces):
            raise ViewError(f'mesh has no faces: {path}')
        items.append(Item(label, mesh))
    return items


# --- geometry helpers ---------------------------------------------------------------------

def scene_bounds(items, marks=()):
    corners = [i.mesh.bounds for i in items] + [np.asarray(m.bounds, float) for m in marks]
    stacked = np.vstack(corners)
    return np.array([stacked.min(axis=0), stacked.max(axis=0)])


def explode(items, axis, distance_mm):
    """Move each part `distance_mm` away from the scene centre along `axis`; centred parts stay."""
    a = AXES[axis]
    bounds = scene_bounds(items)
    centre, scale = bounds.mean(axis=0)[a], max(float(np.ptp(bounds[:, a])), 1.)
    moved = []
    for item in items:
        delta = item.mesh.bounds.mean(axis=0)[a] - centre
        step = np.zeros(3)
        if abs(delta) > 1e-6 * scale:
            step[a] = np.sign(delta) * distance_mm
        moved.append(Item(item.label, item.mesh.copy().apply_translation(step),
                          tuple(float(v) for v in np.add(item.offset, step))))
    return moved


def preview_mesh(mesh, max_faces=MAX_PREVIEW_FACES):
    if len(mesh.faces) <= max_faces:
        return mesh
    return mesh.simplify_quadric_decimation(face_count=max_faces)


def _cut(mesh, axis, offset):
    """Section polylines projected to the two remaining axes, nudging off exact vertex planes."""
    a = AXES[axis]
    normal = np.eye(3)[a]
    eps = 1e-6 * max(float(mesh.extents.max()), 1.)
    for shift in (0., eps, -eps):
        section = mesh.section(plane_origin=normal * (offset + shift), plane_normal=normal)
        if section is not None:
            keep = [i for i in range(3) if i != a]
            return [np.asarray(loop)[:, keep] for loop in section.discrete if len(loop) > 1], shift
    return [], 0.


def section_loops(items, axis, offset_mm):
    found = []
    for item in items:
        loops, shift = _cut(item.mesh, axis, offset_mm)
        bounds = None
        if loops:
            points = np.vstack(loops)
            bounds = [points.min(axis=0).tolist(), points.max(axis=0).tolist()]
        found.append({'label': item.label, 'loops': len(loops), 'bounds_mm': bounds,
                      'nudged_mm': shift, '_loops': loops})
    return found


def _public(section):
    return {k: v for k, v in section.items() if not k.startswith('_')}


# --- PNG rendering ------------------------------------------------------------------------

def _pyplot(path):
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'mouldflow-matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


def _up_frame(up):
    """Cyclic permutation so the chosen axis is plotted vertically (keeps handedness)."""
    return {'z': [0, 1, 2], 'y': [2, 0, 1], 'x': [1, 2, 0]}[up]


def colours(labels):
    """Label → colour from the label's crc32 slot; clashes within one render take the next free slot."""
    taken, result = set(), {}
    for label in labels:
        slot = zlib.crc32(label.encode()) % len(PALETTE)
        for step in range(len(PALETTE)):
            if (slot + step) % len(PALETTE) not in taken:
                slot = (slot + step) % len(PALETTE)
                break
        taken.add(slot)
        result[label] = PALETTE[slot]
    return result


def _legend(fig, plt, items, marks, y=.04):
    from matplotlib.patches import Patch
    palette = colours([i.label for i in items])
    handles = [Patch(color=palette[item.label], label=item.label) for item in items]
    handles += [Patch(facecolor='none', edgecolor=MARK_COLOUR, linewidth=2, label=f'mark: {m.label}') for m in marks]
    fig.legend(handles=handles, loc='lower center', ncol=min(len(handles), 6), frameon=False,
               bbox_to_anchor=(.5, y - .03))


def render_views(items, path, marks=(), up='z', title=None, max_faces=MAX_PREVIEW_FACES, views=DEFAULT_VIEWS):
    """Contact sheet of named views. Returns the labels whose meshes were decimated for the picture."""
    unknown = [v for v in views if v not in VIEWS]
    if unknown or not views:
        raise ViewError(f'unknown view(s) {unknown}; choose from {", ".join(VIEWS)}')
    matplotlib, plt = _pyplot(path)
    palette = colours([i.label for i in items])
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    order = _up_frame(up)
    triangles, face_colours, decimated = [], [], []
    for item in items:
        preview = preview_mesh(item.mesh, max_faces)
        if preview is not item.mesh:
            decimated.append(item.label)
        triangles.append(preview.triangles[:, :, order])
        face_colours.append(np.tile(matplotlib.colors.to_rgba(palette[item.label]), (len(preview.faces), 1)))
    triangles, face_colours = np.concatenate(triangles), np.concatenate(face_colours)
    bounds = scene_bounds(items, marks)[:, order]
    centre, radius = bounds.mean(axis=0), max(float(np.ptp(bounds, axis=0).max()) * .55, 1e-3)
    extents = np.ptp(scene_bounds(items), axis=0)

    columns = 1 if len(views) == 1 else 2
    rows = -(-len(views) // columns)
    height = 5.2 * rows + 0.6
    fig = plt.figure(figsize=(7 * columns, height), facecolor='#f4f1ec')
    fig.text(.03, 1 - .35 / height, title or 'mouldflow view', fontsize=18, weight='bold', color='#222')
    fig.text(.03, 1 - .6 / height, f'scene {extents[0]:.2f} × {extents[1]:.2f} × {extents[2]:.2f} mm (x × y × z)  ·  up = {up}',
             fontsize=11, color='#444')
    light = matplotlib.colors.LightSource(azdeg=315, altdeg=45)
    for n, name in enumerate(views):
        elev, azim, _ = VIEWS[name]
        ax = fig.add_subplot(rows, columns, n + 1, projection='3d', facecolor='#f4f1ec')
        ax.computed_zorder = False
        ax.add_collection3d(Poly3DCollection(triangles, facecolors=face_colours, edgecolors=face_colours, linewidths=.1,
                                             shade=True, lightsource=light, zorder=1))
        for mark in marks:
            _box_edges(ax, np.asarray(mark.bounds, float)[:, order])
        ax.set(xlim=(centre[0] - radius, centre[0] + radius), ylim=(centre[1] - radius, centre[1] + radius),
               zlim=(centre[2] - radius, centre[2] + radius))
        ax.set_box_aspect((1, 1, 1), zoom=1.35)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(name, fontsize=12, color='#333')
    _legend(fig, plt, items, marks)
    fig.subplots_adjust(top=1 - .9 / height, bottom=.6 / height, left=.01, right=.99, wspace=0, hspace=.05)
    fig.savefig(path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    return decimated


def _box_edges(ax, bounds):
    lo, hi = bounds
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    for i in range(8):
        for j in range(i + 1, 8):
            if np.count_nonzero(corners[i] != corners[j]) == 1:
                ax.plot(*zip(corners[i], corners[j]), color=MARK_COLOUR, linewidth=2.5, zorder=10)


def _oriented_path(loops):
    """Compound path whose nonzero fill equals even-odd: nesting depth decides each loop's winding."""
    from matplotlib.path import Path as MplPath
    closed = [np.asarray(l) for l in loops if len(l) > 2]
    vertices, codes = [], []
    for i, loop in enumerate(closed):
        depth = sum(MplPath(other).contains_point(loop[0]) for j, other in enumerate(closed) if j != i)
        x, y = loop[:, 0], loop[:, 1]
        ccw = (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() > 0
        if ccw != (depth % 2 == 0):
            loop = loop[::-1]
        vertices += [*loop, loop[0]]
        codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(loop) - 1) + [MplPath.CLOSEPOLY]
    return MplPath(vertices, codes) if vertices else None


def render_sections(items, cuts, path, marks=(), title=None):
    """One panel per (axis, offset) cut; filled material, holes left open. Returns the cut summaries."""
    matplotlib, plt = _pyplot(path)
    from matplotlib.patches import PathPatch, Rectangle
    columns = min(len(cuts), 3)
    rows = -(-len(cuts) // columns)
    fig = plt.figure(figsize=(5.2 * columns, 5.2 * rows + 1.2), facecolor='#f4f1ec')
    fig.text(.03, 1 - .45 / (5.2 * rows + 1.2), title or 'sections', fontsize=16, weight='bold', color='#222')
    summaries = []
    palette = colours([i.label for i in items])
    for n, (axis, offset) in enumerate(cuts):
        ax = fig.add_subplot(rows, columns, n + 1, facecolor='white')
        found = section_loops(items, axis, offset)
        keep = [a for a in 'xyz' if a != axis]
        for section in found:
            colour = palette[section['label']]
            for loop in section['_loops']:
                ax.plot(loop[:, 0], loop[:, 1], color=colour, linewidth=1.2)
            shape = _oriented_path(section['_loops'])
            if shape is not None:
                ax.add_patch(PathPatch(shape, facecolor=colour, alpha=.45, edgecolor='none'))
        for mark in marks:
            b = np.asarray(mark.bounds, float)
            lo, hi = b[0, AXES[axis]], b[1, AXES[axis]]
            if lo - 1e-9 <= offset <= hi + 1e-9:
                i0, i1 = AXES[keep[0]], AXES[keep[1]]
                ax.add_patch(Rectangle((b[0, i0], b[0, i1]), b[1, i0] - b[0, i0], b[1, i1] - b[0, i1],
                                       fill=False, edgecolor=MARK_COLOUR, linewidth=2))
        if not any(s['loops'] for s in found):
            ax.text(.5, .5, 'no material on this plane', transform=ax.transAxes, ha='center', color='#777')
        else:
            ax.autoscale_view()
        ax.set_aspect('equal', adjustable='datalim')
        ax.set_xlabel(f'{keep[0]} (mm)')
        ax.set_ylabel(f'{keep[1]} (mm)')
        ax.grid(True, color='#e3e3e3', linewidth=.6)
        ax.set_title(f'{axis.upper()} = {offset:g} mm', fontsize=12)
        summaries.append({'axis': axis, 'offset_mm': offset, 'meshes': [_public(s) for s in found]})
    _legend(fig, plt, items, marks, y=.02)
    fig.tight_layout(rect=(0, .05, 1, 1 - .7 / (5.2 * rows + 1.2)))
    fig.savefig(path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    return summaries


# --- HTML viewer --------------------------------------------------------------------------

def write_html(items, path, marks=(), title='mouldflow view', up='z'):
    """Self-contained viewer: meshes embedded as base64 binary STL, three.js pinned from jsDelivr."""
    palette = colours([i.label for i in items])
    data = {'up': up, 'marks': [m.record() for m in marks], 'meshes': [
        {'label': item.label, 'colour': palette[item.label], 'faces': len(item.mesh.faces),
         'bounds_mm': item.mesh.bounds.tolist(),
         'stl_base64': base64.b64encode(item.mesh.export(file_type='stl')).decode('ascii')}
        for i, item in enumerate(items)]}
    payload = json.dumps(data).replace('</', '<\\/')
    page = (_HTML.replace('__TITLE__', html.escape(title))
            .replace('__THREE__', f'https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/')
            .replace('__SCENE__', payload))
    Path(path).write_text(page)


# --- command ------------------------------------------------------------------------------

def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(mesh_args, out_dir, sections=(), explode_spec=None, marks=(), marks_from=(), up='z',
            title=None, html_viewer=True, max_preview_faces=MAX_PREVIEW_FACES, views=DEFAULT_VIEWS):
    """`mouldflow view`: render every requested picture and return a `mouldflow.result/1` record."""
    if up not in AXES:
        raise ViewError(f'up must be x, y or z: {up!r}')
    specs = [parse_mesh_arg(a) for a in mesh_args]
    items = load_items(specs)
    cuts = [parse_axis_value(s, 'section') for s in sections]
    all_marks = [parse_mark(m) for m in marks] + [m for p in marks_from for m in marks_from_record(p)]
    assembled = items  # sections and marks always use the assembled pose
    if explode_spec:
        axis, distance = parse_axis_value(explode_spec, 'explode')
        items = explode(items, axis, distance)
    if not cuts:
        centre = scene_bounds(assembled).mean(axis=0)
        cuts = [(a, float(round(centre[i], 3))) for a, i in AXES.items()]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    title = title or ' + '.join(i.label for i in items)
    decimated = render_views(items, out / 'views.png', all_marks, up, title, max_preview_faces, views)
    summaries = render_sections(assembled, cuts, out / 'sections.png', all_marks, f'{title} — sections')
    evidence = ['views.png', 'sections.png']
    if html_viewer:
        write_html(items, out / 'viewer.html', all_marks, title, up)
        evidence.append('viewer.html')
    meshes = [{'label': item.label, 'path': str(path), 'faces': len(item.mesh.faces),
               'pieces': int(item.mesh.body_count), 'watertight': bool(item.mesh.is_watertight),
               'volume_mm3': float(solid_volume(item.mesh)), 'extents_mm': item.mesh.extents.tolist(),
               'bounds_mm': item.mesh.bounds.tolist(), 'explode_offset_mm': list(moved.offset)}
              for item, moved, (path, _) in zip(assembled, items, specs)]
    limitations = list(LIMITATIONS)
    if decimated:
        limitations.insert(0, f'PNG views decimated to {max_preview_faces} faces for: {", ".join(decimated)}.')
    if explode_spec:
        limitations.insert(0, f'Parts are exploded ({explode_spec} mm) in views.png and viewer.html only; mesh '
                              'bounds, sections and marks use the assembled pose.')
    return ResultRecord(command='view', status='ok', next_action=NEXT_ACTION, evidence=evidence,
                        hashes={item.label: _sha256(path) for item, (path, _) in zip(items, specs)},
                        limitations=limitations,
                        details={'out_dir': str(out), 'up': up, 'views': list(views), 'meshes': meshes, 'sections': summaries,
                                 'marks': [m.record() for m in all_marks], 'preview_decimated': decimated})


_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { --bg:#f4f1ec; --panel:#fffdf9ee; --ink:#222; --muted:#666; --line:#d8d2c8; --accent:#c99762; }
  @media (prefers-color-scheme: dark) { :root { --bg:#14181f; --panel:#1d232ccc; --ink:#e8e6e1; --muted:#9aa3ad; --line:#333b46; } }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--ink); font:14px/1.4 system-ui, sans-serif; }
  #stage { position:fixed; inset:0; }
  #panel { position:fixed; top:12px; left:12px; width:min(300px, calc(100vw - 48px)); max-height:calc(100vh - 48px);
           overflow:auto; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 12px;
           backdrop-filter:blur(6px); }
  #panel h1 { font-size:15px; margin:0 0 4px; display:inline; }
  #panel summary { cursor:pointer; margin-bottom:4px; }
  #panel h2 { font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:12px 0 4px; }
  .row { display:flex; align-items:center; gap:6px; margin:3px 0; }
  .row label { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .swatch { width:12px; height:12px; border-radius:3px; flex:none; }
  .dims { color:var(--muted); font-size:12px; margin-left:18px; }
  input[type=range] { width:100%; }
  button, select { font:inherit; color:var(--ink); background:transparent; border:1px solid var(--line);
                   border-radius:6px; padding:2px 8px; cursor:pointer; }
  .buttons { display:flex; flex-wrap:wrap; gap:4px; }
  #hint { position:fixed; right:12px; bottom:10px; color:var(--muted); font-size:12px; }
  #error { position:fixed; inset:auto 12px 40px 12px; color:#ff6b6b; }
</style>
<script type="importmap">{"imports": {"three": "__THREE__build/three.module.js", "three/addons/": "__THREE__examples/jsm/"}}</script>
</head>
<body>
<div id="stage"></div>
<details id="panel" open>
  <summary><h1>__TITLE__</h1></summary>
  <div class="dims" style="margin:0" id="scene-dims"></div>
  <h2>Parts</h2><div id="parts"></div>
  <h2>Section</h2>
  <div class="row"><select id="cut-axis"><option value="">off</option><option>x</option><option>y</option><option>z</option></select>
    <label><input type="checkbox" id="cut-flip"> flip</label><span id="cut-value"></span></div>
  <input type="range" id="cut-offset" min="0" max="1000" value="500">
  <h2>Camera</h2>
  <div class="buttons" id="views"></div>
  <h2 id="marks-title">Marks</h2><div class="buttons" id="marks"></div>
</details>
<div id="hint">drag to orbit · scroll to zoom · right-drag to pan · units mm · inner faces darker</div>
<div id="error"></div>
<script type="application/json" id="scene">__SCENE__</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const data = JSON.parse(document.getElementById('scene').textContent);
if (window.innerWidth < 600) document.getElementById('panel').open = false;
const AX = { x: 0, y: 1, z: 2 };
const UP = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }[data.up];
const stage = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.localClippingEnabled = true;
stage.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
camera.up.set(...UP);
const controls = new OrbitControls(camera, renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
camera.add(sun); sun.position.set(1, 2, 3); scene.add(camera);
function background() {
  scene.background = new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim());
}
background();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', background);

const clip = new THREE.Plane(new THREE.Vector3(1, 0, 0), 1e9);
const box = new THREE.Box3();
const loader = new STLLoader();
const parts = document.getElementById('parts');
for (const m of data.meshes) {
  const bytes = Uint8Array.from(atob(m.stl_base64), c => c.charCodeAt(0));
  const geometry = loader.parse(bytes.buffer);
  geometry.computeVertexNormals();
  const colour = new THREE.Color(m.colour);
  const front = new THREE.MeshStandardMaterial({ color: colour, side: THREE.FrontSide, roughness: .75,
                                                 clippingPlanes: [clip] });
  const back = new THREE.MeshStandardMaterial({ color: colour.clone().multiplyScalar(.35), side: THREE.BackSide,
                                                clippingPlanes: [clip] });
  const group = new THREE.Group();
  group.add(new THREE.Mesh(geometry, front), new THREE.Mesh(geometry, back));
  scene.add(group);
  geometry.computeBoundingBox(); box.union(geometry.boundingBox);
  const size = new THREE.Vector3(); geometry.boundingBox.getSize(size);
  const row = document.createElement('div');
  row.innerHTML = '<div class="row"><span class="swatch"></span><label><input type="checkbox" checked> <span></span></label>' +
                  '<input type="range" min="0" max="1" step="0.05" value="1" style="width:80px" title="opacity"></div><div class="dims"></div>';
  row.querySelector('.swatch').style.background = m.colour;
  row.querySelector('label span').textContent = m.label;
  row.querySelector('.dims').textContent = `${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} mm · ${m.faces} faces`;
  row.querySelector('input[type=checkbox]').onchange = e => { group.visible = e.target.checked; };
  row.querySelector('input[type=range]').oninput = e => {
    const value = +e.target.value;
    for (const mat of [front, back]) {
      mat.opacity = value; mat.transparent = value < .99; mat.depthWrite = value >= .99; mat.needsUpdate = true;
    }
  };
  parts.appendChild(row);
}
const marksEl = document.getElementById('marks');
for (const mark of data.marks) {
  const b = new THREE.Box3(new THREE.Vector3(...mark.bounds_mm[0]), new THREE.Vector3(...mark.bounds_mm[1]));
  // Drawn last and through everything, so a catch is never hidden behind the part that causes it.
  const helper = new THREE.Box3Helper(b, 0xff2a2a);
  Object.assign(helper.material, { depthTest: false, transparent: true });
  helper.renderOrder = 20;
  const size = new THREE.Vector3(), centre = new THREE.Vector3();
  b.getSize(size); b.getCenter(centre);
  const fill = new THREE.Mesh(new THREE.BoxGeometry(Math.max(size.x, 1e-3), Math.max(size.y, 1e-3), Math.max(size.z, 1e-3)),
                              new THREE.MeshBasicMaterial({ color: 0xff2a2a, transparent: true, opacity: .28, depthTest: false }));
  fill.position.copy(centre); fill.renderOrder = 19;
  scene.add(helper, fill); box.union(b);
  const button = document.createElement('button');
  button.textContent = `zoom: ${mark.label}`;
  button.onclick = () => frame(b, 3);
  marksEl.appendChild(button);
}
if (!data.marks.length) { marksEl.remove(); document.getElementById('marks-title').remove(); }

const sceneSize = new THREE.Vector3(); box.getSize(sceneSize);
document.getElementById('scene-dims').textContent =
  `scene ${sceneSize.x.toFixed(2)} × ${sceneSize.y.toFixed(2)} × ${sceneSize.z.toFixed(2)} mm · up = ${data.up}`;
const axes = new THREE.AxesHelper(Math.max(sceneSize.x, sceneSize.y, sceneSize.z) * .25);
axes.position.copy(box.min); scene.add(axes);

function frame(target, pad = 1.6, direction) {
  const centre = new THREE.Vector3(), size = new THREE.Vector3();
  target.getCenter(centre); target.getSize(size);
  const radius = Math.max(size.length() / 2, 1e-3) * pad;
  const dir = direction || camera.position.clone().sub(controls.target).normalize();
  if (!isFinite(dir.x) || dir.lengthSq() === 0) dir.set(1, -1.2, .8).normalize();
  controls.target.copy(centre);
  camera.position.copy(centre).addScaledVector(dir, radius / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
  camera.near = radius / 100; camera.far = radius * 100; camera.updateProjectionMatrix();
  controls.update();
}
const up = new THREE.Vector3(...UP);
const side = new THREE.Vector3(...({ x: [0, 1, 0], y: [0, 0, 1], z: [1, 0, 0] }[data.up]));
const depth = new THREE.Vector3().crossVectors(up, side);
const VIEWS = {
  iso: side.clone().add(depth.clone().negate()).add(up.clone().multiplyScalar(.8)),
  front: depth.clone().negate().add(up.clone().multiplyScalar(.001)),
  side: side.clone().add(up.clone().multiplyScalar(.001)),
  top: up.clone().add(depth.clone().multiplyScalar(-.001)),
  back: depth.clone().add(up.clone().multiplyScalar(.001)),
  bottom: up.clone().negate().add(depth.clone().multiplyScalar(-.001)),
};
for (const [name, dir] of Object.entries(VIEWS)) {
  const button = document.createElement('button');
  button.textContent = name;
  button.onclick = () => frame(box, 1.6, dir.clone().normalize());
  document.getElementById('views').appendChild(button);
}

const cutAxis = document.getElementById('cut-axis'), cutFlip = document.getElementById('cut-flip');
const cutOffset = document.getElementById('cut-offset'), cutValue = document.getElementById('cut-value');
function updateCut() {
  const axis = cutAxis.value;
  if (!axis) { clip.normal.set(1, 0, 0); clip.constant = 1e9; cutValue.textContent = ''; return; }
  const i = AX[axis], lo = box.min.getComponent(i), hi = box.max.getComponent(i);
  const at = lo + (hi - lo) * cutOffset.value / 1000;
  const sign = cutFlip.checked ? 1 : -1;
  clip.normal.set(0, 0, 0).setComponent(i, sign);
  clip.constant = -sign * at;
  cutValue.textContent = `${axis} = ${at.toFixed(2)} mm`;
}
for (const el of [cutAxis, cutFlip, cutOffset]) el.addEventListener('input', updateCut);

function resize() {
  renderer.setSize(stage.clientWidth, stage.clientHeight);
  camera.aspect = stage.clientWidth / stage.clientHeight; camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize(); frame(box, 1.6, VIEWS.iso.clone().normalize());
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
</script>
<script>
  window.addEventListener('error', e => { document.getElementById('error').textContent = 'Viewer error: ' + e.message; });
</script>
</body>
</html>
"""
