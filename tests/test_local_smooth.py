import unittest
import numpy as np,trimesh
from mouldflow.simplify import smooth_local_patch,apply_feature_edits
class LocalSmoothTests(unittest.TestCase):
 def test_smoothing_is_local_bounded_and_nonmutating(self):
  mesh=trimesh.creation.icosphere(subdivisions=3,radius=4);original=mesh.vertices.copy()
  result,report=smooth_local_patch(mesh,[0,0,4],[2,2,2],iterations=12,max_displacement_mm=.1)
  outside=np.sum(((original-[0,0,4])/[2,2,2])**2,axis=1)>=1
  np.testing.assert_array_equal(result.vertices[outside],original[outside])
  np.testing.assert_array_equal(mesh.vertices,original)
  self.assertGreater(report['moved_vertices'],0)
  self.assertLessEqual(np.linalg.norm(result.vertices-original,axis=1).max(),.10000001)
  self.assertTrue(result.is_volume)
 def test_invalid_parameters_rejected(self):
  mesh=trimesh.creation.icosphere()
  for radii,iterations,limit in [([1,0,1],10,.1),([1,1,1],-1,.1),([1,1,1],10,-.1)]:
   with self.assertRaises(ValueError):smooth_local_patch(mesh,[0,0,0],radii,iterations=iterations,max_displacement_mm=limit)

 def test_authorized_feature_edit_round_trip(self):
  mesh=trimesh.creation.icosphere(subdivisions=2,radius=4)
  edit={'feature':'handle-ridge','choice':'simplify','authorization':'User permits local smoothing','operation':'smooth_local_patch','center_mm':[0,0,4],'radii_mm':[2,2,2],'iterations':10,'max_displacement_mm':.1}
  result,report=apply_feature_edits(mesh,[edit])
  self.assertTrue(result.is_volume)
  self.assertEqual(report['features'][0]['feature'],'handle-ridge')
