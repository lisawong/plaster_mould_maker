import unittest
import trimesh
from mouldflow.simplify import apply_feature_edits
class RecessEditTests(unittest.TestCase):
 def test_authorized_local_fill_preserves_outer_size_and_serializes(self):
  source=trimesh.creation.torus(major_radius=3,minor_radius=1,major_sections=24,minor_sections=12)
  edit={'feature':'inner-recess','choice':'simplify','authorization':'User permits local fill only','operation':'fill_local_undercut','bounds':[[-2.5,-2.5,-.3],[2.5,2.5,.3]],'axis':'Y','padding_mm':.001}
  result,report=apply_feature_edits(source,[edit])
  self.assertTrue(result.is_volume)
  self.assertTrue(result.contains([[0,0,0]])[0])
  self.assertFalse(result.contains([[0,0,.8]])[0])
  self.assertEqual(report['features'][0]['feature'],'inner-recess')
  self.assertLess(max(abs(result.extents-source.extents)),.001)
