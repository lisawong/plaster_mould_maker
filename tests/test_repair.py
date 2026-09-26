import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,trimesh
from mouldflow.repair import stitch_boundaries
class RepairTests(unittest.TestCase):
 def test_stitches_a_t_junction_without_rounding_the_shape(self):
  v=[(x,y,z) for z in (0,2) for y in (0,2) for x in (0,2)]+[(1,1,0)]
  f=[(0,2,8),(8,2,3),(0,3,1),(4,5,7),(4,7,6),(0,1,5),(0,5,4),(2,6,7),(2,7,3),(0,4,6),(0,6,2),(1,3,7),(1,7,5)]
  source=trimesh.Trimesh(v,f,process=False);self.assertFalse(source.is_watertight)
  repaired=stitch_boundaries(source,.0001)
  self.assertTrue(repaired.is_volume)
  self.assertAlmostEqual(repaired.volume,8)
  np.testing.assert_allclose(repaired.bounds,[[0,0,0],[2,2,2]])
if __name__=='__main__':unittest.main()

class ProjectionTests(unittest.TestCase):
 def test_projects_repaired_surface_back_to_reference(self):
  from mouldflow.repair import project_to_reference
  reference=trimesh.creation.box([2,2,2]);rough=trimesh.creation.box([2.1,2.1,2.1])
  fitted,report=project_to_reference(rough,reference,max_distance_mm=.2)
  self.assertTrue(fitted.is_volume)
  np.testing.assert_allclose(fitted.bounds,reference.bounds,atol=1e-6)
  self.assertLess(report['max_displacement_mm'],.09)
