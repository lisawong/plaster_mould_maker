import unittest
import trimesh
from mouldflow.pipeline import build_tooling,partition_local_insert,boolean,check_release
class LocalInsertTests(unittest.TestCase):
 def test_partition_preserves_material_and_withholds_obsolete_forms(self):
  mesh=trimesh.creation.icosphere(subdivisions=2,radius=5)
  original=build_tooling(mesh)
  bounds=[[2,-8,2],[18,8,18]]
  result=partition_local_insert(mesh,bounds)
  self.assertEqual(len(result['plaster']),3)
  self.assertEqual(result['masters'],[]);self.assertEqual(result['walls'],[])
  self.assertAlmostEqual(sum(p.volume for p in result['plaster']),sum(p.volume for p in original['plaster']),places=3)
  for p in result['plaster']:self.assertTrue(p.is_volume)
  for i in range(3):
   for j in range(i):self.assertLess(abs(boolean('intersection',[result['plaster'][i],result['plaster'][j]]).volume),.001)
  self.assertTrue(check_release(result['plaster'][2],mesh,[0,0,1],[0,.2,2,20])['passed'])
