import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import trimesh
from mouldflow.pipeline import check_release
class ReleaseTests(unittest.TestCase):
    def test_detects_motion_into_an_obstacle(self):
        a=trimesh.creation.box([2,2,2]); b=a.copy(); b.apply_translation([3,0,0])
        self.assertFalse(check_release(a,b,[1,0,0],[0,1,2,3,5])['passed'])
        self.assertTrue(check_release(a,b,[-1,0,0],[0,1,2,3,5])['passed'])
if __name__=='__main__': unittest.main()
