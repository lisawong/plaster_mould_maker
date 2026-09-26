import unittest, tempfile, io
import numpy as np
import trimesh
from mouldflow.simplify import apply_feature_edits
class FeatureEditTests(unittest.TestCase):
 def test_individual_authorization_and_closed_trim(self):
  mesh=trimesh.creation.box([10,10,10]); original=mesh.vertices.copy()
  edit={'feature':'spout','choice':'simplify','authorization':'User permits shortening','operation':'trim_max','axis':'X','position_mm':3}
  result,report=apply_feature_edits(mesh,[edit])
  self.assertAlmostEqual(result.bounds[1,0],3)
  self.assertTrue(trimesh.load_mesh(io.BytesIO(result.export(file_type='stl')),file_type='stl').is_volume)
  np.testing.assert_array_equal(mesh.vertices,original)
  self.assertEqual(report['features'][0]['feature'],'spout')
  with self.assertRaises(ValueError):apply_feature_edits(mesh,[edit,{**edit,'feature':'handle','authorization':''}])
 def test_collar_fills_selected_ring_without_changing_extents(self):
  mesh=trimesh.creation.torus(major_radius=3,minor_radius=1)
  edit={'feature':'rim','choice':'simplify','authorization':'User permits collar','operation':'add_frustum','center_xy':[0,0],'z_mm':[-.4,.4],'radius_mm':[3,2.8]}
  result,report=apply_feature_edits(mesh,[edit])
  self.assertTrue(result.is_volume);self.assertTrue(result.contains([[0,0,0]])[0])
  np.testing.assert_allclose(result.bounds,mesh.bounds,atol=1e-6)
  self.assertGreater(report['features'][0]['volume_change_mm3'],0)
