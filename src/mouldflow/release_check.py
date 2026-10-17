"""Release assessment along one translation, covering the whole motion.

Depth semantics (Stage 2 audit):

* Depth at a pose s is D(s) = max over overlap points p of max(d_fixed(p), d_moving(p)),
  where d_X(p) is the distance from p to the surface of solid X. It is reported in mm and
  bracketed by a measured lower bound and a conservative upper bound. Overlap volume (mm3)
  is reported separately and is never compared with the allowance.
* The prototype's one-sided depth (below the fixed surface only) is at most half the local
  thickness of the fixed solid, so a part sweeping through a thin fixed wall looked shallow.
  The moving side closes that gap.
* Between consecutive samples a and b, Minkowski sweeps give every overlap during that travel
  at once: F ∩ sweep(M, a..b) is the union of the overlaps F ∩ M(s) (and symmetrically in the
  moving part's frame), so depth over a swept interval is the largest depth at any s in it.
  The motion is always covered from 0 to the clearance distance (projections on the
  direction disjoint, depth exactly 0).
* Erosion certificates: if F eroded by a ball of radius r meets neither M(s) nor the sweep,
  no overlap point is r deep below F (likewise for M). This proves "below the allowance" and
  "contact only" for thin or shell-shaped overlaps where distance bounds are loose.
* D is also 1-Lipschitz in s, which bounds an interval from its end samples:
  D ≤ (U(a) + U(b) + (b-a)) / 2.
* Anything whose bound reaches the allowance is certified by erosion or refined spatially
  (interior cell branch-and-bound), then bisected. Still unresolved within budget →
  `inconclusive`.

Outcomes: `fail` when a measured lower bound reaches the allowance; `strict_pass` when every
sample and swept interval is contact-only (upper bound ≤ contact tolerance); `conditional_finishing`
when the whole-motion bound is below the allowance but something penetrates; `inconclusive`
otherwise; `unsupported` for invalid input solids.
"""
import numpy as np
import trimesh

from .intersections import find_edge_face_crossings
from .pipeline import boolean, erode, is_solid, solid_volume, sweep
from .release_depth import collision_depth_bound, is_contact_fragment
from .result import Metric, ResultRecord

MEASURE_CANDIDATES = 32
MEASURE_BATCHES = 4
SWEEP_THICKNESS_MM = 1e-4
METHOD = ('two-sided penetration depth (mm) at sampled translations and over swept travel intervals '
          '(Minkowski sweeps); adaptive spatial and temporal refinement')

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
    if not problems and not is_solid(mesh):
        problems.append(f'{label}: zero or inverted volume')
    if check_self_intersections and not problems:
        crossings = find_edge_face_crossings(mesh)['crossing_count']
        if crossings:
            problems.append(f'{label}: self-intersecting ({crossings} edge-face crossings)')
    return problems


def solid_warnings(mesh, label):
    """Notes that do not make a solid invalid. Boolean output often carries zero-area faces;
    they are dropped for distance queries (`distance_surface`)."""
    degenerate = int(np.count_nonzero(mesh.area_faces <= 1e-12))
    return [f'{label}: {degenerate} degenerate (zero-area) faces ignored for distances'] if degenerate else []


def distance_surface(mesh):
    """Copy of `mesh` without zero-area faces, for distance queries only.

    trimesh's closest-point and ray code divide by dot00*dot11 - dot01^2 of each triangle, which
    cancels to exactly zero for zero-area and near-collinear slivers (Boolean and Minkowski
    output carries both). Faces with sin^2 of their first corner angle below 1e-14 are dropped:
    such a face is within 1e-7 x its edge length of its neighbours' edges (1e-5 mm at 100 mm,
    two orders below the contact tolerance), so distances barely move, and containment parity
    is unchanged for all but measure-zero rays.
    """
    t = mesh.triangles
    e0, e1 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    d00, d11, d01 = (e0 * e0).sum(1), (e1 * e1).sum(1), (e0 * e1).sum(1)
    keep = d00 * d11 - d01 * d01 > 1e-14 * d00 * d11
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
        # Measured depth: test the deepest candidates for membership of both solids, a batch at
        # a time, until one overlaps. Kept near-surface centres may lie outside, so the very
        # deepest batch can miss entirely.
        candidates = np.flatnonzero(keep & (depth > lower))
        candidates = candidates[np.argsort(-depth[candidates])]
        for start in range(0, min(len(candidates), MEASURE_CANDIDATES * MEASURE_BATCHES), MEASURE_CANDIDATES):
            batch = candidates[start:start + MEASURE_CANDIDATES]
            overlap = solids[0].contains(centres[batch]) & solids[1].contains(centres[batch])
            if np.any(overlap):
                lower = max(lower, float(depth[batch[overlap]].max()))
                break
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
    """Depth bounds below surfaces[side] for each component: (lower, upper, per-component list)."""
    lower = upper = 0.
    per_component = []
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
        per_component.append((c_lower, c_upper))
        lower, upper = max(lower, c_lower), max(upper, c_upper)
    return lower, upper, per_component


class _Bounded:
    """Depth bracket for one pose or one swept interval, from two sides.

    Each side is (components, solids, surfaces, depth_index). Re-bounding only ever tightens:
    per side the lower bound is the maximum and the upper bound the minimum seen so far, and
    the overall bracket is derived from the sides, so a record never contradicts itself.
    """
    slack = 0.       # measured points may lie this far from a true overlap point

    def _init_bounds(self):
        self.certified_below = None
        self.refined = False
        self.lower = self.upper = 0.
        self.fixed_side = self.moving_side = (0., 0.)
        self.location = None
        self.location_key = (-1., -1.)

    def bound(self, tolerance, max_levels, interior_cells, target=0.):
        results = []
        for (components, solids, surfaces, index), old in zip(self.sides, (self.fixed_side, self.moving_side)):
            if not components:
                results.append(((0., 0.), []))
                continue
            lower, upper, per_component = _side_bound(components, index, solids, surfaces, tolerance, max_levels,
                                                      interior_cells, target)
            lower = float(max(0., lower - self.slack))
            upper = float(upper)
            if self.bounded:
                lower, upper = max(old[0], lower), min(old[1], upper)
            results.append(((lower, max(upper, lower)), per_component))
        self.bounded = True
        (self.fixed_side, fixed_parts), (self.moving_side, moving_parts) = results
        self.lower = max(self.fixed_side[0], self.moving_side[0])
        self.upper = max(self.fixed_side[1], self.moving_side[1], self.lower)
        self._locate(fixed_parts, moving_parts)

    def cap(self, radius):
        """Record an erosion certificate: no overlap point is `radius` deep on either side."""
        radius = float(radius)
        self.certified_below = radius if self.certified_below is None else min(self.certified_below, radius)
        self.fixed_side = (self.fixed_side[0], max(self.fixed_side[0], min(self.fixed_side[1], radius)))
        self.moving_side = (self.moving_side[0], max(self.moving_side[0], min(self.moving_side[1], radius)))
        self.upper = max(self.fixed_side[1], self.moving_side[1], self.lower)

    def _locate(self, fixed_parts, moving_parts):
        """Deepest component (by measured, then upper depth), not the largest by volume."""
        components = self.sides[0][0]
        for i, component in enumerate(components):
            parts = [fixed_parts[i]] if i < len(fixed_parts) else []
            if self.shared_components and i < len(moving_parts):
                parts.append(moving_parts[i])
            key = (max(p[0] for p in parts), max(p[1] for p in parts)) if parts else (0., 0.)
            if key > self.location_key:
                self.location_key, self.location = key, component.bounds.tolist()

    def _sides_record(self, contact_tolerance):
        return {'measured_depth_mm': self.lower, 'upper_bound_mm': self.upper,
                'fixed_side_mm': list(self.fixed_side), 'moving_side_mm': list(self.moving_side),
                'contact_only': self.upper <= contact_tolerance, 'spatially_refined': self.refined,
                'erosion_certified_below_mm': self.certified_below,
                'deepest_component_bounds_mm': self.location}


def _solid_components(collision):
    """Volumetric components of a Boolean result, and how many contact fragments were dropped."""
    components, contacts = [], 0
    if len(collision.faces):
        for component in collision.split(only_watertight=False):
            if is_contact_fragment(component):
                contacts += 1
            else:
                components.append(component)
    return components, contacts


class _Pose(_Bounded):
    shared_components = True

    def __init__(self, distance, moving, fixed, direction, tolerance, separated=False, fixed_surface=None):
        self._init_bounds()
        self.bounded = False
        self.distance = float(distance)
        self.volume = 0.
        self.contact_fragments = 0
        self.separated = separated
        self.sides = (([], (), (), 0), ([], (), (), 1))
        if separated:
            return
        moved = moving.copy(); moved.apply_translation(direction * distance)
        # Erosion probes: eroded fixed vs the moved part; eroded moving (shifted) vs the fixed part.
        self.fixed_probe, self.moving_probe = moved, (fixed, direction * distance)
        surfaces = (fixed_surface if fixed_surface is not None else distance_surface(fixed), distance_surface(moved))
        solids = surfaces      # zero-area faces change neither distance nor ray-parity containment
        collision = boolean('intersection', [moved, fixed])
        self.volume = max(0., solid_volume(collision))
        components, self.contact_fragments = _solid_components(collision)
        self.sides = ((components, solids, surfaces, 0), (components, solids, surfaces, 1))
        self.bound(tolerance, 12, 0)

    @property
    def components(self):
        return self.sides[0][0]

    def record(self, contact_tolerance):
        return {'distance_mm': self.distance, **self._sides_record(contact_tolerance),
                'overlap_volume_mm3': self.volume, 'zero_thickness_contact_fragments': self.contact_fragments,
                'separated_along_direction': self.separated}


class _Sweep(_Bounded):
    """Every overlap during travel a..b, at once, from two Minkowski sweeps.

    Fixed side: F ∩ sweep(M at a, b-a) is exactly the union of the overlaps F ∩ M(s), so the
    depth below F over it is the largest depth below F at any s in [a, b]. Moving side, in the
    moving part's own frame: M ∩ sweep(F at -b, b-a) is the union of M ∩ (F - s·d), giving the
    largest depth below M. The sweeps are thickened by SWEEP_THICKNESS_MM, so they are
    supersets: upper bounds stay valid and measured depths are reduced by the slack.
    """
    shared_components = False
    slack = SWEEP_THICKNESS_MM / np.sqrt(2)

    def __init__(self, a, b, moving, fixed, direction, tolerance, moving_surface, fixed_surface):
        self._init_bounds()
        self.bounded = False
        self.a, self.b = a.distance, b.distance
        length = self.b - self.a
        moving_at_a = moving.copy(); moving_at_a.apply_translation(direction * self.a)
        swept_moving = sweep(moving_at_a, direction, length, SWEEP_THICKNESS_MM)
        fixed_at_b = fixed.copy(); fixed_at_b.apply_translation(-direction * self.b)
        swept_fixed = sweep(fixed_at_b, direction, length, SWEEP_THICKNESS_MM)
        self.fixed_probe, self.moving_probe = swept_moving, (swept_fixed, np.zeros(3))
        fixed_overlap = boolean('intersection', [fixed, swept_moving])
        moving_overlap = boolean('intersection', [moving, swept_fixed])
        self.volume = max(0., solid_volume(fixed_overlap))
        fixed_components, contacts_f = _solid_components(fixed_overlap)
        moving_components, contacts_m = _solid_components(moving_overlap)
        self.contact_fragments = contacts_f + contacts_m
        fixed_pair = (fixed_surface, distance_surface(swept_moving))
        moving_pair = (moving_surface, distance_surface(swept_fixed))
        self.sides = ((fixed_components, fixed_pair, fixed_pair, 0), (moving_components, moving_pair, moving_pair, 0))
        self.bound(tolerance, 12, 0)

    @property
    def components(self):
        return self.sides[0][0] + self.sides[1][0]

    def record(self, contact_tolerance, lipschitz):
        return {'travel_mm': [self.a, self.b], **self._sides_record(contact_tolerance),
                'lipschitz_bound_mm': lipschitz, 'swept_overlap_volume_mm3': self.volume,
                'zero_thickness_contact_fragments': self.contact_fragments}


def _lipschitz(a, b):
    """Two-sided depth is 1-Lipschitz in travel: bound between two bracketed poses."""
    return (a.upper + b.upper + b.distance - a.distance) / 2


def assess_release(moving, fixed, direction, allowance_mm, *, distances=None, spatial_tolerance_mm=.02,
                   contact_tolerance_mm=1e-3, max_samples=200, min_step_mm=1e-3, refine=True,
                   interior_cells=20000, validate_inputs=True, check_self_intersections=True):
    """Assess translating `moving` along `direction` away from `fixed` (see module docstring).

    `distances` are optional extra sample poses; the motion from 0 to the clearance distance
    is always covered by swept intervals between consecutive samples.
    """
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

    problems, warnings_ = [], []
    if validate_inputs:
        for mesh, label in ((moving, 'moving'), (fixed, 'fixed')):
            problems += solid_problems(mesh, label, check_self_intersections)
            warnings_ += solid_warnings(mesh, label)
    if problems:
        return {**base, 'outcome': 'unsupported', 'reason': '; '.join(problems), 'input_problems': problems,
                'input_warnings': warnings_, 'clearance_mm': None, 'metrics': {}, 'samples': [], 'intervals': [],
                'worst_location': None, 'next_action': NEXT_ACTIONS['unsupported'],
                'limitations': ['Release was not assessed because an input is not a valid closed solid.']}

    # Beyond this distance the solids' projections on the direction are disjoint: no overlap.
    clearance = max(0., float(fixed.vertices.dot(direction).max() - moving.vertices.dot(direction).min()))
    seeds = sorted({0.} | {float(s) for s in (() if distances is None else distances) if 0 < s < clearance})
    fixed_surface = distance_surface(fixed)
    moving_surface = distance_surface(moving)

    def new_pose(s, separated=False):
        return _Pose(s, moving, fixed, direction, spatial_tolerance_mm, separated, fixed_surface)

    def new_sweep(a, b):
        return _Sweep(a, b, moving, fixed, direction, spatial_tolerance_mm, moving_surface, fixed_surface)

    poses = [new_pose(s) for s in seeds]
    if clearance > 0:
        poses.append(new_pose(clearance, separated=True))
    sweeps = [new_sweep(poses[i], poses[i + 1]) for i in range(len(poses) - 1)]

    def interval_bound(i):
        return min(sweeps[i].upper, _lipschitz(poses[i], poses[i + 1]))

    erosions = {}

    def certify(item, radius):
        """Cap `item` at `radius` if neither eroded solid meets the other part (or its sweep)."""
        if item.certified_below is not None and item.certified_below <= radius:
            return False
        if not item.components:
            return False
        for name, mesh in (('fixed', fixed), ('moving', moving)):
            if (name, radius) not in erosions:
                erosions[name, radius] = erode(mesh, radius)
        eroded_moving = erosions['moving', radius].copy()
        eroded_moving.apply_translation(item.moving_probe[1])
        for eroded, other in ((erosions['fixed', radius], item.fixed_probe), (eroded_moving, item.moving_probe[0])):
            if len(eroded.faces) and _solid_components(boolean('intersection', [eroded, other]))[0]:
                return False
        item.cap(radius)
        return True

    # Certify strictly below the allowance, never at it.
    allowance_radius = allowance_mm * (1 - 1e-3)

    def refine_item(item):
        if item.refined or not item.components or item.upper <= item.lower + 1e-12:
            return False
        item.refined = True
        # Aim halfway between the measured depth and the allowance, so neighbouring
        # intervals can also close; the bound never goes below what is measured.
        item.bound(spatial_tolerance_mm, 12, interior_cells, target=(item.lower + allowance_mm) / 2)
        return True

    outcome = reason = None
    while outcome is None:
        worst = max(poses + sweeps, key=lambda item: item.lower)
        if worst.lower >= allowance_mm:
            outcome = 'fail'
            where = (f'at {worst.distance:.4f} mm' if isinstance(worst, _Pose)
                     else f'between {worst.a:.4f} and {worst.b:.4f} mm')
            reason = f'Measured depth {worst.lower:.4f} mm {where} of travel reaches the {allowance_mm} mm allowance.'
            break
        bad_samples = [p for p in poses if p.upper >= allowance_mm]
        bad = sorted((i for i in range(len(sweeps)) if interval_bound(i) >= allowance_mm),
                     key=lambda i: (-interval_bound(i), i))
        if not bad and not bad_samples:
            break
        changed = False
        if refine:
            for item in bad_samples + [x for i in bad for x in (sweeps[i], poses[i], poses[i + 1])]:
                if item.upper >= allowance_mm and (certify(item, allowance_radius) or refine_item(item)):
                    changed = True
        if changed:
            continue
        exhausted = None
        if bad_samples:     # a sample bound that refinement cannot tighten: more samples won't help
            bad = []
        for i in sorted(bad, reverse=True):     # from the end, so earlier indices stay valid
            a, b = poses[i], poses[i + 1]
            if not refine or b.distance - a.distance <= min_step_mm:
                continue
            if len(poses) >= max_samples:
                exhausted = f'Sample budget of {max_samples} exhausted'
                break
            middle = new_pose((a.distance + b.distance) / 2)
            poses.insert(i + 1, middle)
            sweeps[i:i + 1] = [new_sweep(a, middle), new_sweep(middle, b)]
            changed = True
        if not changed:
            worst_upper = max([p.upper for p in poses] + [interval_bound(i) for i in range(len(sweeps))])
            outcome = 'inconclusive'
            reason = ((exhausted + '; ' if exhausted else '')
                      + f'upper bound {worst_upper:.4f} mm reaches the {allowance_mm} mm allowance but no measured '
                      f'depth does (max {max(x.lower for x in poses + sweeps):.4f} mm).')

    if outcome is None:
        items = poses + sweeps
        penetrating = [x for x in items if x.upper > contact_tolerance_mm]
        if refine and penetrating and all(x.lower <= contact_tolerance_mm for x in penetrating):
            for item in penetrating:     # tell sub-tolerance slivers from penetration
                if not certify(item, contact_tolerance_mm):
                    item.refined = True
                    item.bound(contact_tolerance_mm / 2, 20, 0)
            penetrating = [x for x in items if x.upper > contact_tolerance_mm]
        if penetrating:
            outcome = 'conditional_finishing'
            reason = (f'Penetration below the {allowance_mm} mm allowance over the whole motion '
                      f'(max upper bound {max(x.upper for x in items):.4f} mm).')
        else:
            outcome = 'strict_pass'
            reason = 'Only contact (no penetration above the contact tolerance) over the whole motion.'

    motion_upper = max([p.upper for p in poses] + [interval_bound(i) for i in range(len(sweeps))])
    lower = max(x.lower for x in poses + sweeps)
    if outcome == 'fail':
        worst = max(poses + sweeps, key=lambda x: (x.lower, x.upper))
    else:
        worst = max(poses + sweeps, key=lambda x: (x.upper, x.lower))
    travel = [worst.distance, worst.distance] if isinstance(worst, _Pose) else [worst.a, worst.b]
    limitations = list(LIMITATIONS)
    if sweeps:
        limitations.insert(0, f'Between samples, depth comes from swept volumes thickened by {SWEEP_THICKNESS_MM} mm '
                              '(a superset of the exact sweep); measured depths there are reduced by that slack.')
    if any(x.volume > 0 and x.upper <= contact_tolerance_mm for x in poses + sweeps):
        limitations.append(f'Overlaps no deeper than the {contact_tolerance_mm} mm contact tolerance are treated as '
                           'contact; their volumes are retained in the samples as numerical evidence.')
    return {**base, 'outcome': outcome, 'reason': reason, 'input_problems': [], 'input_warnings': warnings_,
            'clearance_mm': clearance,
            'metrics': {
                'max_depth_lower_bound': {'value': lower, 'unit': 'mm', 'kind': 'lower_bound'},
                'max_depth_upper_bound': {'value': max(motion_upper, lower), 'unit': 'mm', 'kind': 'upper_bound'},
                'max_overlap_volume': {'value': max(p.volume for p in poses), 'unit': 'mm3', 'kind': 'measured'},
                'samples': {'value': len(poses), 'unit': 'count', 'kind': 'measured'}},
            'samples': [p.record(contact_tolerance_mm) for p in poses],
            'intervals': [sweeps[i].record(contact_tolerance_mm, _lipschitz(poses[i], poses[i + 1]))
                          for i in range(len(sweeps))],
            'worst_location': {'travel_mm': travel, 'bounds_mm': worst.location},
            'next_action': NEXT_ACTIONS[outcome], 'limitations': limitations}


def assessment_record(assessment, command, stage=None, evidence=()):
    """Wrap an assessment in the versioned result record (PRD R9.1)."""
    details = {k: v for k, v in assessment.items() if k not in ('outcome', 'metrics', 'limitations', 'next_action')}
    return ResultRecord(command=command, status='ok', stage=stage, outcome=assessment['outcome'],
                        metrics={k: Metric(**v) for k, v in assessment['metrics'].items()},
                        limitations=assessment['limitations'], next_action=assessment['next_action'],
                        evidence=list(evidence), details=details)
