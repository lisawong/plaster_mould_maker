import unittest
import trimesh
from mouldflow.pipeline import box_between
from mouldflow.release_depth import collision_depth_bound,check_release_depth
class DepthTests(unittest.TestCase):
 def test_thin_overlap_uses_linear_depth_not_volume(self):
  fixed=trimesh.creation.box([10,10,10])
  overlap=box_between([4.9,-4,-4],[5,4,4])
  report=collision_depth_bound(overlap,fixed,.03)
  self.assertAlmostEqual(report['measured_depth_mm'],.1,places=5)
  self.assertGreaterEqual(report['upper_bound_mm'],.1)
  self.assertLess(report['upper_bound_mm'],.2)
  self.assertGreater(overlap.volume,.5)
 def test_deep_overlap_fails_allowance(self):
  fixed=trimesh.creation.box([10,10,10]);moving=box_between([4,-1,-1],[6,1,1])
  report=check_release_depth(moving,fixed,[1,0,0],[0,1,2],.5,.03)
  self.assertFalse(report['within_allowance_at_samples'])
 def test_disjoint_returns_zero(self):
  fixed=trimesh.creation.box();moving=fixed.copy();moving.apply_translation([3,0,0])
  report=check_release_depth(moving,fixed,[1,0,0],[0,1],.5,.03)
  self.assertTrue(report['within_allowance_at_samples']);self.assertEqual(report['max_upper_bound_mm'],0)
 def test_open_collision_fragment_gets_conservative_enclosure(self):
  fixed=trimesh.creation.box([10,10,10]);fragment=box_between([4.9,-1,-1],[5,1,1]);fragment.update_faces([0,1,2])
  report=collision_depth_bound(fragment,fixed,.03)
  self.assertGreaterEqual(report['upper_bound_mm'],.1)
  self.assertLess(report['upper_bound_mm'],.2)
 def test_loose_oriented_box_cannot_worsen_axis_aligned_bound(self):
  from unittest.mock import patch
  import numpy as np
  fixed=trimesh.creation.box([10,10,10]);overlap=box_between([4.9,-4,-4],[5,4,4])
  with patch('trimesh.bounds.oriented_bounds',return_value=(np.eye(4),np.array([8,8,8]))):
   report=collision_depth_bound(overlap,fixed,.03)
  self.assertLess(report['upper_bound_mm'],.2)
