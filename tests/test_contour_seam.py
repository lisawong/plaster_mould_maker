import unittest
import trimesh
from mouldflow.pipeline import build_tooling,check_release,boolean
from mouldflow.contour_seam import contour_seam
class ContourSeamTests(unittest.TestCase):
 def test_offset_sphere_gets_releasing_partition_without_cavity_edit(self):
  mesh=trimesh.creation.icosphere(subdivisions=2,radius=4);mesh.apply_translation([0,-1.5,0])
  original=mesh.vertices.copy();candidate=build_tooling(mesh);result=contour_seam(candidate,seam_offset_mm=.002)
  self.assertEqual(len(result['plaster']),2);self.assertEqual(result['masters'],[])
  self.assertAlmostEqual(sum(p.volume for p in result['plaster']),sum(p.volume for p in candidate['plaster']),places=3)
  for part,direction in zip(result['plaster'],[[0,1,0],[0,-1,0]]):
   self.assertTrue(part.is_volume)
   self.assertTrue(check_release(part,mesh,direction,[0,.1,.25,.5,1,4,16])['passed'])
  self.assertTrue(check_release(result['plaster'][0],result['plaster'][1],[0,1,0],[0,.1,1,8,32])['passed'])
  self.assertTrue((mesh.vertices==original).all())
