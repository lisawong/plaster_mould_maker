import unittest
import trimesh
from mouldflow.intersections import find_edge_face_crossings
class CrossingTests(unittest.TestCase):
 def test_detects_crossing_closed_shells(self):
  a=trimesh.creation.box([2,2,2]);b=a.copy();b.apply_translation([.73,.41,.29])
  mesh=trimesh.util.concatenate([a,b]);self.assertTrue(mesh.is_volume)
  self.assertGreater(find_edge_face_crossings(mesh)['crossing_count'],0)
 def test_clean_and_disjoint_shells_pass(self):
  a=trimesh.creation.icosphere(subdivisions=1);b=a.copy();b.apply_translation([5,0,0])
  self.assertEqual(find_edge_face_crossings(trimesh.util.concatenate([a,b]))['crossing_count'],0)
 def test_input_preparation_rejects_crossing_closed_shells(self):
  import tempfile
  from pathlib import Path
  from mouldflow.pipeline import prepare_stl
  a=trimesh.creation.box([2,2,2]);b=a.copy();b.apply_translation([.73,.41,.29])
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'crossing.stl';trimesh.util.concatenate([a,b]).export(path)
   with self.assertRaisesRegex(ValueError,'crossing'):prepare_stl(path,50)
