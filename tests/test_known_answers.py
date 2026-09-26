"""Stage 2 known-answer release fixtures (EVALUATION-PLAN geometry rows).

Each fixture has an independently known depth and outcome. Tests assert the metric
unit (mm depth vs mm3 volume), bound-vs-measured semantics and the outcome.
"""
import unittest
import warnings

from mouldflow.known_answers import FIXTURES, fixture
from mouldflow.pipeline import check_release
from mouldflow.release_check import assess_release, assessment_record
from mouldflow.release_depth import check_release_depth
from mouldflow.result import Metric


_CACHE = {}


def run(name, **overrides):
    """Assess a fixture with RuntimeWarnings as errors; default runs are shared between tests."""
    if not overrides and name in _CACHE:
        return _CACHE[name]
    f = fixture(name)
    kwargs = dict(distances=f.distances, **f.options)
    kwargs.update(overrides)
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        result = f, assess_release(f.moving, f.fixed, f.direction, f.allowance_mm, **kwargs)
    if not overrides:
        _CACHE[name] = result
    return result


class FixtureLibraryTests(unittest.TestCase):
    def test_every_fixture_declares_its_known_answer(self):
        self.assertGreaterEqual(len(FIXTURES), 9)
        for name in FIXTURES:
            f = fixture(name)
            self.assertIn(f.expected_outcome, ('strict_pass', 'conditional_finishing', 'inconclusive', 'fail', 'unsupported'))
            self.assertTrue(f.evaluation_row, name)
            self.assertGreater(f.allowance_mm, 0)

    def test_unknown_fixture_is_an_error(self):
        with self.assertRaises(KeyError):
            fixture('no-such-fixture')


class KnownAnswerOutcomeTests(unittest.TestCase):
    def assertDepthMetrics(self, report):
        lower = Metric(**report['metrics']['max_depth_lower_bound'])
        upper = Metric(**report['metrics']['max_depth_upper_bound'])
        volume = Metric(**report['metrics']['max_overlap_volume'])
        self.assertEqual((lower.unit, lower.kind), ('mm', 'lower_bound'))
        self.assertEqual((upper.unit, upper.kind), ('mm', 'upper_bound'))
        self.assertEqual((volume.unit, volume.kind), ('mm3', 'measured'))
        self.assertLessEqual(lower.value, upper.value)
        return lower.value, upper.value, volume.value

    def test_known_outcomes(self):
        for name in FIXTURES:
            with self.subTest(name):
                f, report = run(name)
                self.assertEqual(report['outcome'], f.expected_outcome, report['reason'])
                if f.expected_outcome == 'unsupported':
                    continue
                lower, upper, _ = self.assertDepthMetrics(report)
                if f.expected_max_depth_mm is not None:
                    # The bracket must contain the independently known depth.
                    self.assertLessEqual(lower, f.expected_max_depth_mm + 1e-4)
                    self.assertGreaterEqual(upper, f.expected_max_depth_mm - 1e-4)

    def test_thin_wide_overlap_volume_is_not_depth(self):
        f, report = run('thin-wide-overlap')
        lower, upper, volume = self.assertDepthMetrics(report)
        self.assertGreater(volume, f.allowance_mm)       # large mm3 ...
        self.assertLess(upper, f.allowance_mm)           # ... but shallow mm
        self.assertAlmostEqual(lower, .05, places=4)
        self.assertEqual(report['outcome'], 'conditional_finishing')

    def test_deep_catch_measured_lower_bound_fails(self):
        f, report = run('deep-catch')
        lower, _, _ = self.assertDepthMetrics(report)
        self.assertGreaterEqual(lower, f.allowance_mm)
        self.assertEqual(report['outcome'], 'fail')

    def test_loose_bound_is_refined_or_inconclusive(self):
        f, refined = run('bound-wider-than-depth')
        lower, upper, _ = self.assertDepthMetrics(refined)
        self.assertEqual(refined['outcome'], 'conditional_finishing')
        self.assertLess(upper, f.allowance_mm)
        self.assertAlmostEqual(lower, .4, places=4)
        # Without refinement the slab bound (~0.6 mm) straddles the 0.5 mm allowance.
        _, coarse = run('bound-wider-than-depth', refine=False)
        self.assertEqual(coarse['outcome'], 'inconclusive')
        self.assertGreaterEqual(coarse['metrics']['max_depth_upper_bound']['value'], f.allowance_mm)
        self.assertLess(coarse['metrics']['max_depth_lower_bound']['value'], f.allowance_mm)

    def test_zero_thickness_contact_is_not_penetration(self):
        _, report = run('zero-thickness-contact')
        self.assertEqual(report['outcome'], 'strict_pass')
        self.assertEqual(report['metrics']['max_depth_lower_bound']['value'], 0)

    def test_near_coplanar_sliver_is_contact_with_numerical_evidence(self):
        _, report = run('near-coplanar-sliver')
        self.assertEqual(report['outcome'], 'strict_pass')
        evidence = [s for s in report['samples'] if s['overlap_volume_mm3'] > 0]
        self.assertTrue(evidence, 'numerical overlap evidence must be retained')
        self.assertTrue(all(s['contact_only'] for s in evidence))
        self.assertTrue(any('contact' in item for item in report['limitations']))

    def test_shallow_sliver_above_contact_tolerance_is_conditional(self):
        _, report = run('shallow-sliver')
        self.assertEqual(report['outcome'], 'conditional_finishing')

    def test_catch_between_coarse_samples_is_found(self):
        f, report = run('between-sample-catch')
        self.assertEqual(report['outcome'], 'fail')
        self.assertGreater(len(report['samples']), len(f.distances))
        # The legacy checks only look at the coarse samples and miss the catch.
        self.assertTrue(check_release_depth(f.moving, f.fixed, f.direction, f.distances, f.allowance_mm)['within_allowance_at_samples'])
        self.assertTrue(check_release(f.moving, f.fixed, f.direction, f.distances)['passed'])

    def test_thin_fixed_wall_is_caught_from_the_moving_side(self):
        f, report = run('thin-fixed-wall')
        self.assertEqual(report['outcome'], 'fail')
        # One-sided depth below the fixed surface is at most half the wall thickness.
        legacy = check_release_depth(f.moving, f.fixed, f.direction, [0, 1, 2, 2.9, 3.1, 4], f.allowance_mm)
        self.assertTrue(legacy['within_allowance_at_samples'])
        self.assertGreaterEqual(report['metrics']['max_depth_lower_bound']['value'], f.allowance_mm)

    def test_self_intersecting_input_is_unsupported_although_watertight(self):
        f, report = run('self-intersecting-input')
        self.assertTrue(f.fixed.is_watertight)
        self.assertEqual(report['outcome'], 'unsupported')
        self.assertTrue(any('self-intersect' in p for p in report['input_problems']))

    def test_clean_withdrawal_is_strict(self):
        f, report = run('clean-withdrawal')
        self.assertEqual(report['outcome'], 'strict_pass')
        self.assertTrue(all(s['upper_bound_mm'] == 0 for s in report['samples']))
        # Zero at every sample; between samples only the Lipschitz bound, stated as a limitation.
        self.assertLess(report['metrics']['max_depth_upper_bound']['value'], f.allowance_mm)
        self.assertTrue(any('Between samples' in item for item in report['limitations']))


class AssessmentContractTests(unittest.TestCase):
    def test_every_outcome_has_next_action_and_limitations(self):
        for name in FIXTURES:
            with self.subTest(name):
                _, report = run(name)
                self.assertTrue(report['next_action'])
                self.assertTrue(report['limitations'])

    def test_record_is_a_valid_result(self):
        _, report = run('thin-wide-overlap')
        record = assessment_record(report, command='release-check', stage='plaster')
        self.assertEqual(record.outcome, 'conditional_finishing')
        self.assertEqual(record.metrics['max_depth_upper_bound'].unit, 'mm')
        self.assertEqual(record.metrics['max_overlap_volume'].unit, 'mm3')
        self.assertEqual(record.next_action, report['next_action'])

    def test_motion_is_covered_until_clearance(self):
        f, report = run('clean-withdrawal')
        distances = [s['distance_mm'] for s in report['samples']]
        self.assertEqual(distances[0], 0)
        self.assertAlmostEqual(distances[-1], report['clearance_mm'])

    def test_sample_budget_exhaustion_is_inconclusive(self):
        _, report = run('between-sample-catch', max_samples=10)
        self.assertEqual(report['outcome'], 'inconclusive')
        self.assertIn('budget', report['reason'])

    def test_invalid_arguments_raise(self):
        f = fixture('clean-withdrawal')
        for kwargs in (dict(direction=[0, 0, 0]), dict(allowance_mm=0), dict(allowance_mm=float('nan')),
                       dict(distances=[-1, 2]), dict(spatial_tolerance_mm=0)):
            args = dict(moving=f.moving, fixed=f.fixed, direction=f.direction, allowance_mm=.1)
            args.update(kwargs)
            with self.subTest(kwargs), self.assertRaises(ValueError):
                assess_release(**args)


class InteriorRefinementTests(unittest.TestCase):
    def test_measured_depth_only_counts_points_inside_both_solids(self):
        from mouldflow.pipeline import box_between
        from mouldflow.release_check import _interior_refine
        fixed = box_between([-5, -5, -5], [5, 5, 5])
        moved = box_between([4.95, -1, -1], [6, 1, 1])        # true overlap depth 0.05 mm
        # Cover far more than the overlap: cells deep inside `fixed` but outside `moved`
        # must never raise the measured depth.
        lower, upper = _interior_refine(fixed.bounds, 0, (fixed, moved), (fixed, moved), 0., .01, 20000, target=.2)
        self.assertLessEqual(lower, .05 + 1e-9)
        self.assertGreaterEqual(upper, .05)
        self.assertLess(upper, .2 + 1e-9)


class VolumeWarningTests(unittest.TestCase):
    def test_touching_solids_volume_check_emits_no_runtime_warning(self):
        import trimesh
        a = trimesh.creation.box([2, 2, 2]); b = a.copy(); b.apply_translation([3, 0, 0])
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            self.assertFalse(check_release(a, b, [1, 0, 0], [0, 1, 2, 3, 5])['passed'])

    def test_zero_volume_closed_fragment_bounds_without_runtime_warning(self):
        import numpy as np
        import trimesh
        from mouldflow.pipeline import is_solid
        from mouldflow.release_depth import collision_depth_bound
        # Box whose top face collapses onto its bent bottom face (same diagonal): closed,
        # consistently wound, 3D vertex rank, zero volume -- as at the teapot's initial pose.
        bottom = np.array([[0, 0, 0], [1, 0, 0], [1, 1, .3], [0, 1, 0]], float)
        faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7]]
        for i in range(4):
            j = (i + 1) % 4
            faces += [[i, j, j + 4], [i, j + 4, i + 4]]
        fragment = trimesh.Trimesh(np.vstack([bottom, bottom]), faces, process=False)
        self.assertTrue(fragment.is_watertight)
        self.assertFalse(is_solid(fragment))
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            report = collision_depth_bound(fragment, trimesh.creation.box([10, 10, 10]), .03)
        self.assertEqual(report['components'][0]['enclosure'], 'convex_enclosure_of_fragment')

    def test_distance_surface_drops_only_degenerate_faces(self):
        import numpy as np
        import trimesh
        from mouldflow.release_check import distance_surface
        box = trimesh.creation.box([2, 2, 2])
        with_sliver = trimesh.Trimesh(np.vstack([box.vertices, [[1, 0, 0]]]),
                                      np.vstack([box.faces, [[0, 1, 8]]]), process=False)
        vertices = with_sliver.vertices
        vertices[8] = (vertices[0] + vertices[1]) / 2          # zero-area face on an edge
        surface = distance_surface(with_sliver)
        self.assertEqual(len(surface.faces), len(box.faces))
        points = np.array([[0, 0, 0], [3, 0, 0], [.5, .2, -.9]])
        self.assertTrue(np.allclose(trimesh.proximity.closest_point(surface, points)[1],
                                    trimesh.proximity.closest_point(box, points)[1]))

    def test_solid_volume_matches_trimesh_for_closed_meshes(self):
        import trimesh
        from mouldflow.pipeline import solid_volume
        for mesh in (trimesh.creation.box([1, 2, 3]), trimesh.creation.icosphere(subdivisions=2)):
            self.assertAlmostEqual(solid_volume(mesh), mesh.volume, places=9)


if __name__ == '__main__':
    unittest.main()
