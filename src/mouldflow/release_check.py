"""Release assessment along one translation, with a proven between-sample bound.

Depth semantics (Stage 2 audit):

* Depth at a pose s is D(s) = max over overlap points p of max(d_fixed(p), d_moving(p)),
  where d_X(p) is the distance from p to the surface of solid X. It is reported in mm and
  bracketed by a measured lower bound and a conservative upper bound. Overlap volume (mm3)
  is reported separately and is never compared with the allowance.
* The prototype's one-sided depth (below the fixed surface only) is at most half the local
  thickness of the fixed solid, so a part sweeping through a thin fixed wall looked shallow.
  The moving side closes that gap.
* D is 1-Lipschitz in s: a point at depth h at s+δ was inside both solids at depth ≥ h-δ at
  s (it lies in an h-ball inside the fixed solid; the moving side is symmetric). Between
  samples a and b, D ≤ (U(a) + U(b) + (b-a)) / 2. That turns discrete samples into a bound
  over the whole motion from 0 until the parts are separated along the direction.
* Intervals and samples whose bound reaches the allowance are refined: first spatially
  (tighter boundary tolerance, then an interior cell branch-and-bound), then temporally
  (bisection). Anything still unresolved within budget is `inconclusive`.

Outcomes: `fail` when a measured lower bound reaches the allowance; `strict_pass` when every
sample is contact-only (upper bound ≤ contact tolerance) and the motion bound is below the
allowance; `conditional_finishing` when the motion bound is below the allowance but some
sample penetrates; `inconclusive` otherwise; `unsupported` for invalid input solids.
"""
import numpy as np
import trimesh

from .intersections import find_edge_face_crossings
from .pipeline import boolean, is_solid, solid_volume
from .release_depth import collision_depth_bound
from .result import Metric, ResultRecord

MEASURE_CANDIDATES = 32
DEFAULT_DISTANCES = (0, .025, .05, .1, .2, .3, .4, .5, .75, 1, 1.5, 2, 3, 4, 8, 16, 32, 64)
METHOD = ('two-sided penetration depth (mm) at sampled translations; 1-Lipschitz bound between '
          'samples; adaptive spatial and temporal refinement')

NEXT_ACTIONS = {
    'strict_pass': 'Release check passed; continue to the review gate and show the limitations.',
    'conditional_finishing': ('Show the depth bound and its locations to the human; release is conditional on '
                              'manual finishing strictly below the job allowance.'),
    'inconclusive': ('Do not approve. Report the check as inconclusive: re-run with a larger sample budget or '
                     'tighter tolerance, or change the design.'),
    'fail': ('Do not approve. Show the catch location and ask whether to simplify the feature or change '
             'the partition.'),
    'unsupported': 'Do not run release checks on this input. Prepare or repair the solids first (intake/prepare).',
}

LIMITATIONS = [
    'Pure translation along one direction; rotation, wobble and other removal paths are not checked.',
    'Depth bounds are penetration measures, not a map of exact material to sand away.',
    'Physical release, plaster expansion and surface friction are not modelled.',
]


def solid_problems(mesh, label, check_self_intersections=True):
    """Reasons a mesh is not a valid closed solid. Watertight alone is not enough."""
    if not len(mesh.faces):
        return [f'{label}: empty mesh']
    problems = []
    if not mesh.is_watertight:
        problems.append(f'{label}: not closed (not watertight)')
    if not mesh.is_winding_consistent:
        problems.append(f'{label}: inconsistent face winding')
    if solid_volume(mesh) <= 0:
        problems.append(f'{label}: zero or inverted volume')
    degenerate = int(np.count_nonzero(mesh.area_faces <= 1e-12))
    if degenerate:
        problems.append(f'{label}: {degenerate} degenerate faces')
    if check_self_intersections and not problems:
        crossings = find_edge_face_crossings(mesh)['crossing_count']
        if crossings:
            problems.append(f'{label}: self-intersecting ({crossings} edge-face crossings)')
    return problems


def distance_surface(mesh):
    """Copy of `mesh` without zero-area faces, for distance queries only.

    trimesh's closest-point code divides by zero on degenerate triangles (Boolean results
    carry some). A zero-area triangle lies on its neighbours' edges, so dropping it does not
    change the distance to the surface.
    """
    keep = mesh.nondegenerate_faces(height=1e-9)
    if keep.all():
        return mesh
    surface = mesh.copy()
    surface.update_faces(keep)
    return surface


def _interior_refine(bounds, side, solids, surfaces, lower, tolerance, max_cells, target=0.):
    """Branch-and-bound over axis-aligned cells covering one collision component.

    `solids` are the two valid input solids (fixed, moved) and `surfaces` their distance
    meshes; `side` picks whose depth is bounded. For p in a cell with centre c and
    half-diagonal r, d(p) ≤ d(c) + r. A cell is dropped only when its centre is more than r
    outside either input solid, so the kept cells cover the overlap. A centre inside both
    solids is an overlap point, so its depth is a measurement. Membership is tested on the
    input solids, never on the collision fragment: ray containment on thin Boolean fragments
    gives false insides (seen on the teapot at the assembled pose). A cell settles once its
    bound is within `tolerance` of the best measured depth or below `target`. Returns
    (lower, upper), or None if the budget ran out first.
    """
    cells = [(np.asarray(bounds[0], float), np.asarray(bounds[1], float))]
    settled = 0.
    evaluated = 0
    while cells:
        if evaluated + len(cells) > max_cells:
            return None
        evaluated += len(cells)
        lows = np.array([c[0] for c in cells]); highs = np.array([c[1] for c in cells])
        centres = (lows + highs) / 2
        radii = np.linalg.norm(highs - lows, axis=1) / 2
        distances = [trimesh.proximity.closest_point(surface, centres)[1] for surface in surfaces]
        # Ray containment is slow on dense meshes: only ask where the answer matters, i.e.
        # where the centre is farther than r from that surface.
        keep = np.ones(len(cells), bool)
        for solid, d in zip(solids, distances):
            far = np.flatnonzero(d > radii)
            if len(far):
                keep[far[~solid.contains(centres[far])]] = False
        depth = distances[side]
        # Measured depth: check only the deepest few candidates for membership of both solids.
        candidates = np.flatnonzero(keep & (depth > lower))
        candidates = candidates[np.argsort(-depth[candidates])][:MEASURE_CANDIDATES]
        if len(candidates):
            overlap = solids[0].contains(centres[candidates]) & solids[1].contains(centres[candidates])
            if np.any(overlap):
                lower = max(lower, float(depth[candidates[overlap]].max()))
        upper = depth + radii
        done = keep & (upper <= max(lower + tolerance, target))
        settled = max(settled, float(upper[done].max(initial=0)))
        split = []
        for a, b in zip(lows[keep & ~done], highs[keep & ~done]):
            axis = int(np.argmax(b - a)); middle = (a[axis] + b[axis]) / 2
            left_high = b.copy(); left_high[axis] = middle
            right_low = a.copy(); right_low[axis] = middle
            split += [(a, left_high), (right_low, b)]
        cells = split
    return lower, max(settled, lower)


def _side_bound(components, side, solids, surfaces, tolerance, max_levels, interior_cells, target=0.):
    lower = upper = 0.
    for component in components:
        report = collision_depth_bound(component, surfaces[side], tolerance, max_levels)
        c_upper = report['upper_bound_mm']
        # A non-volume fragment is bounded through its convex enclosure, whose boundary points
        # need not overlap anything: its "measured" depth is not a measurement (audit finding).
        c_lower = report['measured_depth_mm'] if is_solid(component) else 0.
        if interior_cells and c_upper > c_lower + tolerance:
            refined = _interior_refine(component.bounds, side, solids, surfaces, c_lower, tolerance,
                                       interior_cells, target)
            if refined:
                c_lower, c_upper = refined[0], min(c_upper, refined[1])
        lower, upper = max(lower, c_lower), max(upper, c_upper)
    return lower, upper


class _Pose:
    def __init__(self, distance, moving, fixed, direction, tolerance, separated=False, fixed_surface=None):
        self.distance = float(distance)
        self.refined = False
        self.lower = self.upper = self.volume = 0.
        self.fixed_side = self.moving_side = (0., 0.)
        self.contact_fragments = 0
        self.components = []
        self.worst_bounds = None
        self.separated = separated
        if separated:
            return
        moved = moving.copy(); moved.apply_translation(direction * distance)
        self.solids = (fixed, moved)
        self.surfaces = (fixed_surface if fixed_surface is not None else distance_surface(fixed),
                         distance_surface(moved))
        collision = boolean('intersection', [moved, fixed])
        self.volume = max(0., solid_volume(collision))
        if len(collision.faces):
            for component in collision.split(only_watertight=False):
                if np.linalg.matrix_rank(component.vertices - component.vertices.mean(axis=0), tol=1e-10) < 3:
                    self.contact_fragments += 1
                else:
                    self.components.append(component)
        self.bound(tolerance, 12, 0)

    def bound(self, tolerance, max_levels, interior_cells, target=0.):
        if self.separated or not self.components:
            return
        self.fixed_side, self.moving_side = (
            _side_bound(self.components, side, self.solids, self.surfaces, tolerance, max_levels, interior_cells,
                        target) for side in (0, 1))
        # Refinement only ever tightens: keep the better of old and new bounds.
        lower = max(self.fixed_side[0], self.moving_side[0])
        upper = max(self.fixed_side[1], self.moving_side[1])
        self.lower = max(self.lower, lower)
        self.upper = upper if not self.refined else min(self.upper, upper)
        self.upper = max(self.upper, self.lower)
        worst = max(self.components, key=lambda c: abs(solid_volume(c)))
        self.worst_bounds = worst.bounds.tolist()

    def record(self, contact_tolerance):
        return {'distance_mm': self.distance, 'measured_depth_mm': self.lower, 'upper_bound_mm': self.upper,
                'fixed_side_mm': list(self.fixed_side), 'moving_side_mm': list(self.moving_side),
                'overlap_volume_mm3': self.volume, 'zero_thickness_contact_fragments': self.contact_fragments,
                'contact_only': self.upper <= contact_tolerance, 'spatially_refined': self.refined,
                'separated_along_direction': self.separated, 'largest_component_bounds_mm': self.worst_bounds}


def _interval_bounds(poses):
    return [(poses[i].upper + poses[i + 1].upper + poses[i + 1].distance - poses[i].distance) / 2
            for i in range(len(poses) - 1)]


def assess_release(moving, fixed, direction, allowance_mm, *, distances=None, spatial_tolerance_mm=.02,
                   contact_tolerance_mm=1e-3, max_samples=200, min_step_mm=1e-3, refine=True,
                   interior_cells=20000, validate_inputs=True, check_self_intersections=True):
    """Assess translating `moving` along `direction` away from `fixed` (see module docstring)."""
    direction = np.asarray(direction, float)
    if direction.shape != (3,) or not np.isfinite(direction).all() or np.linalg.norm(direction) == 0:
        raise ValueError('Finite nonzero direction required')
    for name, value in (('allowance_mm', allowance_mm), ('spatial_tolerance_mm', spatial_tolerance_mm),
                        ('contact_tolerance_mm', contact_tolerance_mm), ('min_step_mm', min_step_mm)):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be positive and finite')
    if distances is not None:
        distances = np.asarray(distances, float)
        if distances.ndim != 1 or not np.isfinite(distances).all() or np.any(distances < 0):
            raise ValueError('Nonnegative finite motion samples required')
    direction = direction / np.linalg.norm(direction)
    base = {'method': METHOD, 'direction': direction.tolist(), 'allowance_mm': float(allowance_mm),
            'spatial_tolerance_mm': spatial_tolerance_mm, 'contact_tolerance_mm': contact_tolerance_mm}

    problems = []
    if validate_inputs:
        problems = (solid_problems(moving, 'moving', check_self_intersections)
                    + solid_problems(fixed, 'fixed', check_self_intersections))
    if problems:
        return {**base, 'outcome': 'unsupported', 'reason': '; '.join(problems), 'input_problems': problems,
                'clearance_mm': None, 'metrics': {}, 'samples': [], 'next_action': NEXT_ACTIONS['unsupported'],
                'limitations': ['Release was not assessed because an input is not a valid closed solid.']}

    # Beyond this distance the solids' projections on the direction are disjoint: no overlap.
    clearance = max(0., float(fixed.vertices.dot(direction).max() - moving.vertices.dot(direction).min()))
    seeds = DEFAULT_DISTANCES if distances is None else distances
    seeds = sorted({0.} | {float(s) for s in seeds if 0 < s < clearance})
    fixed_surface = distance_surface(fixed)
    poses = [_Pose(s, moving, fixed, direction, spatial_tolerance_mm, fixed_surface=fixed_surface) for s in seeds]
    if clearance > 0:
        poses.append(_Pose(clearance, moving, fixed, direction, spatial_tolerance_mm, separated=True))

    def refine_pose(pose):
        if pose.refined or pose.separated or not pose.components or pose.upper <= pose.lower + 1e-12:
            return False
        pose.refined = True
        # Aim halfway between the measured depth and the allowance, so neighbouring
        # intervals can also close; the bound never goes below what is measured.
        pose.bound(spatial_tolerance_mm, 12, interior_cells, target=(pose.lower + allowance_mm) / 2)
        return True

    outcome = reason = None
    while outcome is None:
        worst = max(poses, key=lambda p: p.lower)
        if worst.lower >= allowance_mm:
            outcome = 'fail'
            reason = (f'Measured depth {worst.lower:.4f} mm at {worst.distance:.4f} mm of travel reaches the '
                      f'{allowance_mm} mm allowance.')
            break
        bounds = _interval_bounds(poses)
        bad = sorted((i for i, b in enumerate(bounds) if b >= allowance_mm), key=lambda i: (-bounds[i], i))
        bad_samples = [p for p in poses if p.upper >= allowance_mm]
        if not bad and not bad_samples:
            break
        changed = False
        if refine:
            for pose in bad_samples + [p for i in bad for p in (poses[i], poses[i + 1])]:
                if refine_pose(pose):
                    changed = True
        if changed:
            continue
        exhausted = None
        if bad_samples:     # a sample bound that refinement cannot tighten: more samples won't help
            bad = []
        for i in bad:
            a, b = poses[i], poses[i + 1]
            if not refine or b.distance - a.distance <= min_step_mm:
                continue
            if len(poses) >= max_samples:
                exhausted = f'Sample budget of {max_samples} exhausted'
                break
            poses.append(_Pose((a.distance + b.distance) / 2, moving, fixed, direction, spatial_tolerance_mm,
                               fixed_surface=fixed_surface))
            changed = True
        poses.sort(key=lambda p: p.distance)
        if not changed:
            worst_upper = max([p.upper for p in poses] + _interval_bounds(poses))
            outcome = 'inconclusive'
            reason = ((exhausted + '; ' if exhausted else '')
                      + f'upper bound {worst_upper:.4f} mm reaches the {allowance_mm} mm allowance but no measured '
                      f'depth does (max {max(p.lower for p in poses):.4f} mm).')

    if outcome is None:
        penetrating = [p for p in poses if p.upper > contact_tolerance_mm]
        if refine and penetrating and all(p.lower <= contact_tolerance_mm for p in penetrating):
            for pose in penetrating:     # tighten to tell sub-tolerance slivers from penetration
                pose.refined = True
                pose.bound(contact_tolerance_mm / 2, 20, 0)
            penetrating = [p for p in poses if p.upper > contact_tolerance_mm]
        if penetrating:
            outcome = 'conditional_finishing'
            reason = (f'Penetration below the {allowance_mm} mm allowance over the whole motion '
                      f'(max upper bound {max([p.upper for p in poses] + _interval_bounds(poses)):.4f} mm).')
        else:
            outcome = 'strict_pass'
            reason = 'Only contact (no penetration above the contact tolerance) at every sample.'

    motion_upper = max([p.upper for p in poses] + _interval_bounds(poses))
    lower = max(p.lower for p in poses)
    limitations = list(LIMITATIONS)
    if len(poses) > 1:
        limitations.insert(0, f'Between samples, depth is bounded by {motion_upper:.4f} mm (1-Lipschitz bound), '
                              'not measured.')
    if any(p.volume > 0 and p.upper <= contact_tolerance_mm for p in poses):
        limitations.append(f'Overlaps no deeper than the {contact_tolerance_mm} mm contact tolerance are treated as '
                           'contact; their volumes are retained in the samples as numerical evidence.')
    return {**base, 'outcome': outcome, 'reason': reason, 'input_problems': [], 'clearance_mm': clearance,
            'metrics': {
                'max_depth_lower_bound': {'value': lower, 'unit': 'mm', 'kind': 'lower_bound'},
                'max_depth_upper_bound': {'value': max(motion_upper, lower), 'unit': 'mm', 'kind': 'upper_bound'},
                'max_overlap_volume': {'value': max(p.volume for p in poses), 'unit': 'mm3', 'kind': 'measured'},
                'samples': {'value': len(poses), 'unit': 'count', 'kind': 'measured'}},
            'samples': [p.record(contact_tolerance_mm) for p in poses],
            'next_action': NEXT_ACTIONS[outcome], 'limitations': limitations}


def assessment_record(assessment, command, stage=None, evidence=()):
    """Wrap an assessment in the versioned result record (PRD R9.1)."""
    details = {k: v for k, v in assessment.items() if k not in ('outcome', 'metrics', 'limitations', 'next_action')}
    return ResultRecord(command=command, status='ok', stage=stage, outcome=assessment['outcome'],
                        metrics={k: Metric(**v) for k, v in assessment['metrics'].items()},
                        limitations=assessment['limitations'], next_action=assessment['next_action'],
                        evidence=list(evidence), details=details)
