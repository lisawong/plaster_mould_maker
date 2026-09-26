import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import trimesh,numpy as np
from mouldflow.simplify import fill_local_undercut
class SimplifyTests(unittest.TestCase):
 def test_local_fill_preserves_original_and_unselected_features(self):
  source=trimesh.creation.torus(major_radius=3,minor_radius=1,major_sections=32,minor_sections=16)
  original=source.vertices.copy()
  result,report=fill_local_undercut(source,[[-2.5,-2.5,-.3],[2.5,2.5,.3]],axis='Y')
  self.assertTrue(result.is_volume)
  self.assertTrue(result.contains([[0,0,0]])[0])
  self.assertFalse(result.contains([[0,0,.8]])[0])
  np.testing.assert_array_equal(source.vertices,original)
  np.testing.assert_allclose(result.bounds,source.bounds,atol=.0001)
  self.assertGreater(report['added_volume_mm3'],0)
if __name__=='__main__':unittest.main()
