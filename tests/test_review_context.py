import unittest,tempfile,json
from pathlib import Path
import trimesh
from mouldflow.review_context import review_context
class ReviewContextTests(unittest.TestCase):
 def test_locates_change_and_binds_exact_meshes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);a=trimesh.creation.box();a.export(root/'before.stl');a.vertices[0,2]+=.03;a.export(root/'after.stl')
   context=review_context(root/'before.stl',root/'after.stl','Underside of the base')
   self.assertEqual(context['area_description'],'Underside of the base')
   self.assertEqual(context['changed_vertex_count'],1)
   self.assertEqual(len(context['before_sha256']),64)
   self.assertIn('whole_object',context['required_views'])
   self.assertIn('rotatable_3d',context['required_views'])
