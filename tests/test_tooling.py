import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import trimesh
from mouldflow.pipeline import build_tooling

class ToolingTests(unittest.TestCase):
    def test_sphere_produces_two_complementary_plaster_parts(self):
        sphere=trimesh.creation.icosphere(subdivisions=2,radius=10)
        result=build_tooling(sphere, margin=12, backing=12, gate_radius=3)
        self.assertEqual(len(result['plaster']),2)
        for p in result['plaster']:
            self.assertTrue(p.is_volume)
        overlap=trimesh.boolean.intersection(result['plaster'],engine='manifold')
        self.assertLess(abs(overlap.volume),1e-4)
        self.assertEqual(len(result['masters']),2)
        for m in result['masters']:
            self.assertTrue(m.is_volume)
            x0,x1,z0,z1=result['bounds']
            self.assertTrue(m.contains([[x0-1.5,-0.5,0]])[0], 'wall must seat on master base')
            self.assertLessEqual(max(m.extents),250)

if __name__=='__main__': unittest.main()
