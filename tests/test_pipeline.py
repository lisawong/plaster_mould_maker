import sys, unittest, tempfile, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mouldflow.pipeline import prepare_stl

# A closed 2 mm cube: independent fixture with known dimensions and volume.
V = [(x,y,z) for z in (0,2) for y in (0,2) for x in (0,2)]
F = [(0,2,3),(0,3,1),(4,5,7),(4,7,6),(0,1,5),(0,5,4),
     (2,6,7),(2,7,3),(0,4,6),(0,6,2),(1,3,7),(1,7,5)]
def fixture(path, faces=F):
    with open(path,'wb') as f:
        f.write(b'fixture'.ljust(80,b' ')); f.write(struct.pack('<I',len(faces)))
        for face in faces:
            f.write(struct.pack('<12fH',0,0,0,*(c for i in face for c in V[i]),0))

class InputTests(unittest.TestCase):
    def test_open_stl_is_rejected_before_tooling(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'open.stl'; fixture(p, F[:-2])
            with self.assertRaisesRegex(ValueError, 'watertight'):
                prepare_stl(p, target_mm=50)

    def test_another_stl_scales_to_requested_width(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cube.stl'; fixture(p)
            obj, report=prepare_stl(p, target_mm=50, scale_axis='Y')
            self.assertAlmostEqual(report['dimensions_mm'][1],50,places=4)
            self.assertAlmostEqual(report['volume_mm3'],125000,places=1)
            self.assertEqual(report['nonmanifold_edges'],0)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful(): raise SystemExit(1)
