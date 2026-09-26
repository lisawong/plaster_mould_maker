import unittest
import numpy as np,trimesh
from mouldflow.print_layout import print_orientation
class PrintOrientationTests(unittest.TestCase):
 def test_pattern_base_faces_bed_and_transform_is_reversible(self):
  mesh=trimesh.creation.box([40,20,30]);mesh.apply_translation([7,6,-2])
  placed,transform=print_orientation(mesh,'pattern')
  self.assertAlmostEqual(placed.bounds[0,2],0)
  np.testing.assert_allclose(placed.extents,[40,30,20],atol=1e-8)
  placed.apply_transform(np.linalg.inv(transform));np.testing.assert_allclose(placed.vertices,mesh.vertices,atol=1e-8)
 def test_panels_lie_on_their_broad_face(self):
  for size in [[60,30,3],[3,30,60]]:
   mesh=trimesh.creation.box(size);placed,_=print_orientation(mesh,'panel')
   self.assertAlmostEqual(placed.extents[2],3);self.assertAlmostEqual(placed.bounds[0,2],0)
