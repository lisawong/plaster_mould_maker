import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import trimesh
from mouldflow.pipeline import partition_with_top_cap, check_release
class PartitionTests(unittest.TestCase):
 def test_top_cap_preserves_plaster_volume_and_has_three_parts(self):
  source=trimesh.creation.icosphere(subdivisions=2,radius=10)
  result=partition_with_top_cap(source,split_z=5,core_radius=4,core_x=0)
  self.assertEqual(len(result['plaster']),3)
  self.assertTrue(all(p.is_volume for p in result['plaster']))
  assembled=trimesh.boolean.union(result['plaster'],engine='manifold')
  self.assertAlmostEqual(sum(p.volume for p in result['plaster']),assembled.volume,places=2)
  self.assertTrue(check_release(result['plaster'][2],source,[0,0,1],[0,.2,1,5,30])['passed'])
if __name__=='__main__':unittest.main()
