"""Stage 3: intake and prepare (PRD R1.2, R2.1-R2.3).

`intake` copies and hashes the source STL and records the human's declarations. Units are
required: STL has no units, so scale is never guessed. `prepare` validates the mesh, applies only
the repairs the human asked for, then the declared rotations, target scale and centring. It writes
a new revision folder `candidates/input/rNNN/` with before/after previews and submits the input gate.
A rejected mesh writes nothing.

Order of operations: units -> repairs -> rotations (in order, about fixed axes) -> target scale
-> centre the bounding box on the origin. Prepared meshes are Z-up millimetres.
"""
import hashlib
import io
import json
import math
import shutil
from pathlib import Path

import numpy as np
import trimesh

from .intersections import find_edge_face_crossings
from .job import JobError
from .pipeline import solid_volume
from .repair import stitch_boundaries
from .result import Metric, ResultRecord
from .view import inspect

UNIT_MM = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0, 'in': 25.4}
AXES = ('X', 'Y', 'Z')
DEGENERATE_AREA_MM2 = 1e-12  # same threshold as release_check.solid_warnings
REPAIRS = ('drop-degenerate', 'stitch', 'fix-winding')  # always applied in this order
# Which problem code each repair fixes; problems without one are unsupported.
FIXES = {'degenerate_faces': 'drop-degenerate', 'open': 'stitch', 'inverted': 'fix-winding',
         'inconsistent_winding': 'fix-winding'}
REPORT_VERSION = 'mouldflow.prepare/1'
LIMITATIONS = [
    'Input checks cover mesh validity, scale and orientation only; no mould release has been checked.',
    'Self-intersection check finds strict edge-face crossings only; coplanar overlaps and endpoint contacts '
    'may be missed. Zero is not a complete self-intersection proof.',
    'Previews are a locator and before/after views; marked close-ups of repaired regions arrive with the '
    'Stage 9 review packages.',
    'Binary STL stores float32 coordinates, so prepared dimensions are exact to about 1e-6 of their size.',
]


class IntakeError(JobError):
    pass


class InputRejected(IntakeError):
    """The mesh is not a valid single closed solid. Carries every problem and its repair, if any."""

    def __init__(self, problems, applied=(), rotations=()):
        self.problems = problems
        self.applied = list(applied)
        self.rotations = list(rotations)
        self.outcome = 'unsupported' if any(p['repair'] is None for p in problems) else None
        super().__init__('input rejected: ' + '; '.join(p['message'] for p in problems))

    def next_action(self):
        if self.outcome == 'unsupported':
            fatal = ', '.join(p['code'] for p in self.problems if p['repair'] is None)
            return (f'Input is unsupported ({fatal}); mouldflow cannot repair this. Tell the human, fix the '
                    'source STL in a modelling tool, then start a new job with `mouldflow job init`.')
        flags = [f'--rotate {axis.lower()}={degrees}' for axis, degrees in self.rotations]
        flags += [_flag(a) for a in self.applied] + [f'--repair {p["repair"]}' for p in self.problems]
        return ('Show the human these problems and ask whether to repair them. If they agree, rerun '
                f'`mouldflow prepare DIR {" ".join(dict.fromkeys(flags))}` (stitch=TOL: a gap tolerance in '
                'mm the human chooses, e.g. 0.01). Never repair without asking.')


def _flag(applied):
    name = applied['repair']
    return f'--repair stitch={applied["tolerance_mm"]}' if name == 'stitch' else f'--repair {name}'


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(data, name):
    """Load STL bytes as one triangle mesh, merging duplicate vertices as every later stage will.

    Non-finite coordinates are rejected before processing, which would otherwise delete those
    triangles silently. Vertex merging is the only cleanup applied.
    """
    try:
        with np.errstate(invalid='ignore'):  # face normals of non-finite triangles
            mesh = trimesh.load(io.BytesIO(data), file_type='stl', force='mesh', process=False)
    except Exception as error:  # trimesh raises many types for malformed files
        raise IntakeError(f'{name}: could not read as an STL triangle mesh ({error})') from error
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise IntakeError(f'{name}: no triangles found; is this an STL mesh?')
    bad = int(np.count_nonzero(~np.isfinite(mesh.triangles).all(axis=(1, 2))))
    if bad:
        raise InputRejected([_problem('non_finite', f'{name}: {bad} triangles have non-finite coordinates '
                                                    '(NaN or infinity)', bad)])
    mesh.merge_vertices()
    return mesh


# --- intake ---------------------------------------------------------------------------------------

def intake(job, stl, units, target_mm=None, target_axis=None, purpose=None):
    """Copy and hash the source STL into `source/` and record the human's declarations."""
    if units not in UNIT_MM:
        raise IntakeError(f'declare units (one of {", ".join(UNIT_MM)}); STL has no units and scale is never '
                          f'guessed, got {units!r}')
    if target_mm is None and target_axis is not None:
        raise IntakeError('--target-axis needs --target-mm (the size the object should have on that axis)')
    if target_mm is not None and not (math.isfinite(target_mm) and target_mm > 0):
        raise IntakeError(f'target must be a positive size in mm, got {target_mm!r}')
    axis = (target_axis or 'Y').upper()
    if axis not in AXES:
        raise IntakeError(f'target axis must be X, Y or Z, got {target_axis!r}')
    stl = Path(stl)
    if not stl.is_file():
        raise IntakeError(f'source not found: {stl}')
    if stl.suffix.lower() != '.stl':
        raise IntakeError(f'{stl.name}: intake accepts STL files only')
    data = stl.read_bytes()
    mesh = _load(data, stl.name)
    digest = hashlib.sha256(data).hexdigest()
    rel = f'source/{stl.name}'
    recorded = job.settings.source
    if recorded.file and (recorded.file != rel or recorded.sha256 != digest):
        raise IntakeError(f'this job already has source {recorded.file}; a different STL needs a new job '
                          '(`mouldflow job init`)')
    destination = job.root / rel
    if not (destination.exists() and destination.resolve() == stl.resolve()):
        shutil.copyfile(stl, destination)
    job.update_settings(job.settings.with_overrides({'source': {
        'file': rel, 'sha256': digest, 'units': units, 'target_mm': target_mm, 'target_axis': axis,
        'purpose': purpose}}))
    raw = mesh.extents.tolist()
    return ResultRecord(command='intake', status='ok', stage='input', next_action=job.next_action(),
                        evidence=[rel, 'job.json'], hashes={rel: digest},
                        details={'source': job.settings.source.model_dump(mode='json'), 'raw_extents': raw,
                                 'extents_mm': [x * UNIT_MM[units] for x in raw], 'unit_scale': UNIT_MM[units],
                                 'faces': len(mesh.faces)})


# --- validation and repairs -----------------------------------------------------------------------

def _problem(code, message, count=None):
    return {'code': code, 'message': message, 'count': count,
            'repair': ('stitch=TOL' if FIXES[code] == 'stitch' else FIXES[code]) if code in FIXES else None}


def validate(mesh, check_self_intersections=True):
    """Reasons `mesh` (in mm) is not a single closed solid (PRD R2.1). Empty list means valid."""
    if not np.isfinite(mesh.vertices).all():
        return [_problem('non_finite', 'vertices are not finite (NaN or infinity)')]
    problems = []
    degenerate = int(np.count_nonzero(mesh.area_faces <= DEGENERATE_AREA_MM2))
    if degenerate:
        problems.append(_problem('degenerate_faces', f'{degenerate} zero-area faces', degenerate))
    if not mesh.is_watertight:
        edges = int(np.count_nonzero(np.bincount(mesh.edges_unique_inverse) != 2))
        problems.append(_problem('open', f'not closed: {edges} edges not shared by exactly two faces '
                                         '(stitching closes T-junctions and tiny gaps, not holes)', edges))
    if not mesh.is_winding_consistent:
        problems.append(_problem('inconsistent_winding', 'neighbouring faces wind in opposite directions'))
    bodies = int(mesh.body_count)
    if bodies > 1:
        problems.append(_problem('multiple_components', f'{bodies} separate pieces; Release 1 needs one solid',
                                 bodies))
    if mesh.is_watertight and mesh.is_winding_consistent:
        volume = solid_volume(mesh)
        if volume < 0:
            problems.append(_problem('inverted', 'faces point inwards (negative volume)'))
        elif volume == 0:
            problems.append(_problem('zero_volume', 'encloses no volume'))
    # Crossing rays are reliable on closed, consistently wound shells, even several of them.
    if check_self_intersections and mesh.is_watertight and mesh.is_winding_consistent:
        crossings = find_edge_face_crossings(mesh)['crossing_count']
        if crossings:
            problems.append(_problem('self_intersecting', f'self-intersecting: {crossings} edge-face crossings',
                                     crossings))
    return problems


def parse_repair(text):
    name, sep, value = str(text).partition('=')
    if name not in REPAIRS:
        raise IntakeError(f'unknown repair {text!r}; expected one of drop-degenerate, fix-winding, stitch=TOL')
    if name != 'stitch':
        if sep:
            raise IntakeError(f'repair {name} takes no value')
        return name, None
    try:
        tolerance = float(value)
    except ValueError:
        tolerance = math.nan
    if not (math.isfinite(tolerance) and tolerance > 0):
        raise IntakeError(f'repair stitch needs a positive gap tolerance in mm: stitch=TOL, got {text!r}')
    return name, tolerance


def _repair(mesh, name, tolerance):
    if name == 'drop-degenerate':
        keep = mesh.area_faces > DEGENERATE_AREA_MM2
        result = mesh.copy()
        result.update_faces(keep)
        result.remove_unreferenced_vertices()
        return result, {'repair': name, 'faces_removed': int(np.count_nonzero(~keep))}
    if name == 'stitch':
        before = int(np.count_nonzero(np.bincount(mesh.edges_unique_inverse) != 2))
        result = stitch_boundaries(mesh, tolerance)
        after = int(np.count_nonzero(np.bincount(result.edges_unique_inverse) != 2))
        return result, {'repair': name, 'tolerance_mm': tolerance, 'open_edges_before': before,
                        'open_edges_after': after}
    result = mesh.copy()
    result.fix_normals()
    return result, {'repair': name, 'faces_flipped': int(np.count_nonzero((result.faces != mesh.faces).any(axis=1)))}


def apply_repairs(mesh, requested):
    """Apply requested repairs in REPAIRS order. Each must fix a problem the mesh has at that point."""
    by_name = dict(parse_repair(r) for r in requested)
    if len(by_name) != len(requested):
        raise IntakeError('each repair may be given once')
    applied = []
    for name in REPAIRS:
        if name not in by_name:
            continue
        current = {FIXES.get(p['code']) for p in validate(mesh, check_self_intersections=False)}
        if name not in current:
            raise IntakeError(f'repair {name} was requested but the mesh has no problem it fixes; '
                              'drop it (repairs only run for reported problems)')
        if name == 'stitch' and 'drop-degenerate' in current:
            # stitch_boundaries drops zero-area faces; only its own new fan slivers may go unasked.
            raise IntakeError('repair stitch would also delete the zero-area source faces; ask the human about '
                              '--repair drop-degenerate as well')
        mesh, info = _repair(mesh, name, by_name[name])
        applied.append(info)
    return mesh, applied


# --- prepare --------------------------------------------------------------------------------------

def parse_rotation(text):
    axis, sep, degrees = str(text).partition('=')
    try:
        value = float(degrees)
    except ValueError:
        value = math.nan
    if not sep or axis.upper() not in AXES or not math.isfinite(value):
        raise IntakeError(f'--rotate expects AXIS=DEG with AXIS x, y or z, got {text!r}')
    return axis.upper(), value


def _rotation_matrix(rotations):
    matrix = np.eye(4)
    for axis, degrees in rotations:
        direction = np.eye(3)[AXES.index(axis)]
        matrix = trimesh.transformations.rotation_matrix(math.radians(degrees), direction) @ matrix
    return matrix


def _next_revision_dir(job):
    base = job.root / 'candidates' / 'input'
    numbers = [int(p.name[1:]) for p in base.glob('r[0-9][0-9][0-9]') if p.is_dir()] if base.is_dir() else []
    return f'candidates/input/r{max(numbers, default=0) + 1:03d}'


def prepare(job, rotations=(), repairs=()):
    """Validate, repair (only as asked), orient, scale and centre the source; submit the input gate."""
    source = job.settings.source
    if not source.file or not source.units:
        raise IntakeError('no source STL recorded; run `mouldflow intake DIR STL --units ...` first')
    rotations = tuple(parse_rotation(r) for r in rotations)
    for r in repairs:
        parse_repair(r)
    path = job.root / source.file
    if not path.is_file() or _sha256(path) != source.sha256:
        job.gate_status('input')  # reverify, so a submitted input gate goes stale now
        raise IntakeError(f'source STL changed or missing since intake: {source.file}; restore the original '
                          'or start a new job')

    unit_scale = UNIT_MM[source.units]
    before = _load(path.read_bytes(), source.file)
    before.apply_scale(unit_scale)
    problems = validate(before, check_self_intersections=False)
    mesh, applied = apply_repairs(before, list(repairs))
    # The cheap pass decides; a rejection reruns the full check so it lists every reason.
    if applied and validate(mesh, check_self_intersections=False):
        raise InputRejected(validate(mesh), applied, rotations)
    if not applied and problems:
        raise InputRejected(validate(before), rotations=rotations)

    transform = _rotation_matrix(rotations)
    mesh = mesh.copy()
    mesh.apply_transform(transform)
    target_scale = 1.0
    if source.target_mm is not None:
        target_scale = source.target_mm / mesh.extents[AXES.index(source.target_axis)]
        scale = np.diag([target_scale] * 3 + [1.0])
        mesh.apply_transform(scale)
        transform = scale @ transform
    centre = trimesh.transformations.translation_matrix(-mesh.bounds.mean(axis=0))
    mesh.apply_transform(centre)
    transform = centre @ transform @ np.diag([unit_scale] * 3 + [1.0])

    # Validate what will actually be written: binary STL rounds to float32.
    data = trimesh.exchange.stl.export_stl(mesh)
    prepared = _load(data, 'prepared.stl')
    final_problems = validate(prepared)
    if final_problems:
        raise InputRejected(final_problems, applied, rotations)

    if rotations != source.rotations:
        job.update_settings(job.settings.with_overrides({'source': {'rotations': [list(r) for r in rotations]}}))
    rel = _next_revision_dir(job)
    folder = job.root / rel
    folder.mkdir(parents=True)
    (folder / 'prepared.stl').write_bytes(data)
    before.export(folder / 'before.stl')
    after_view = inspect([f'{folder / "prepared.stl"}=object'], folder,
                         title=f'{Path(source.file).name}, prepared ({rel.rsplit("/", 1)[1]})')
    before_view = inspect([f'{folder / "before.stl"}=object'], folder / 'before',
                          title=f'{Path(source.file).name}, as declared ({source.units} -> mm), before prepare')

    extents = prepared.extents.tolist()
    metrics = {f'extent_{a.lower()}_mm': Metric(value=v, unit='mm', kind='measured') for a, v in zip(AXES, extents)}
    metrics['volume_mm3'] = Metric(value=solid_volume(prepared), unit='mm3', kind='measured')
    report = {'schema_version': REPORT_VERSION, 'revision_dir': rel,
              'source': {'file': source.file, 'sha256': source.sha256, 'units': source.units},
              'unit_scale': unit_scale, 'rotations': [list(r) for r in rotations],
              'target': {'mm': source.target_mm, 'axis': source.target_axis} if source.target_mm else None,
              'target_scale': target_scale, 'transform': transform.tolist(),
              'problems_found': problems, 'repairs': applied,
              'prepared': {'extents_mm': extents, 'volume_mm3': metrics['volume_mm3'].value,
                           'faces': len(prepared.faces), 'checks': 'single closed solid, consistent winding, '
                           'positive volume, no zero-area faces, no strict edge-face crossings'},
              'limitations': LIMITATIONS}
    (folder / 'prepare-report.json').write_text(json.dumps(report, indent=2) + '\n')

    evidence = [f'{rel}/{name}' for name in ('prepared.stl', 'prepare-report.json', 'before.stl')]
    evidence += [f'{rel}/{e}' for e in after_view.evidence] + [f'{rel}/before/{e}' for e in before_view.evidence]
    revision = job.submit('input', [source.file, *evidence], 'strict_pass',
                          metrics={k: m.model_dump() for k, m in metrics.items()}, limitations=LIMITATIONS)
    return ResultRecord(command='prepare', status='ok', stage='input', outcome='strict_pass', metrics=metrics,
                        limitations=LIMITATIONS + after_view.limitations, next_action=job.next_action(),
                        evidence=evidence, hashes={source.file: source.sha256,
                                                   f'{rel}/prepared.stl': hashlib.sha256(data).hexdigest()},
                        details={'revision': revision, 'revision_dir': rel, 'unit_scale': unit_scale,
                                 'rotations': report['rotations'], 'target_scale': target_scale,
                                 'transform': report['transform'], 'problems_found': problems,
                                 'repairs': applied})
