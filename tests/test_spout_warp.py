import unittest,io
import numpy as np
import trimesh
from mouldflow.simplify import lower_tip_smoothly
class SpoutWarpTests(unittest.TestCase):
 def test_root_fixed_tip_translated_and_stl_closed(self):
  mesh=trimesh.creation.icosphere(subdivisions=3,radius=10);original=mesh.vertices.copy()
  result=lower_tip_smoothly(mesh,2,7,3)
  root=original[:,0]<=2;tip=original[:,0]>=7
  np.testing.assert_array_equal(result.vertices[root],original[root])
  np.testing.assert_allclose(result.vertices[tip],original[tip]+[0,0,-3])
  np.testing.assert_array_equal(mesh.vertices,original)
  np.testing.assert_array_equal(result.faces,mesh.faces)
  self.assertTrue(trimesh.load_mesh(io.BytesIO(result.export(file_type='stl')),file_type='stl').is_volume)
 def test_invalid_transition_rejected(self):
  mesh=trimesh.creation.box()
  for args in [(2,1,3),(1,2,-3),(1,2,float('nan'))]:
   with self.assertRaises(ValueError):lower_tip_smoothly(mesh,*args)
