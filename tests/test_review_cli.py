import unittest,sys,tempfile,subprocess,json,os
from pathlib import Path
WORK=Path(__file__).resolve().parents[1];sys.path.insert(0,str(WORK))
from mouldflow.workflow import ReviewWorkflow
class ReviewCliTests(unittest.TestCase):
 def call(self,*args):
  return subprocess.run([sys.executable,'-m','mouldflow.review',*map(str,args)],env={**os.environ,'PYTHONPATH':str(WORK)},capture_output=True,text=True)
 def test_user_can_inspect_and_approve_exact_review_revision(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'object.stl';artifact.write_text('fixture')
   state=root/'review.json';rev=ReviewWorkflow(state).submit('input',{},[artifact],True)
   status=self.call('status',state);self.assertEqual(status.returncode,0,status.stderr)
   self.assertEqual(json.loads(status.stdout)['next_action'],'review_input')
   approved=self.call('approve',state,'input','--revision',rev,'--decision','Reviewed size and shape')
   self.assertEqual(approved.returncode,0,approved.stderr)
   self.assertEqual(json.loads(approved.stdout)['next_action'],'generate_plaster')
 def test_change_request_reports_regeneration_as_next_action(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'object.stl';artifact.write_text('fixture');state=root/'review.json'
   revision=ReviewWorkflow(state).submit('input',{},[artifact],True)
   changed=self.call('changes',state,'input','--note','Rotate the object')
   self.assertEqual(changed.returncode,0,changed.stderr)
   self.assertEqual(json.loads(changed.stdout)['next_action'],'regenerate_input')
 def test_prepare_creates_reviewable_input_without_advancing(self):
  import trimesh
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'cube.stl';trimesh.creation.box([2,2,2]).export(source)
   config=root/'settings.json';config.write_text(json.dumps({'target_mm':50,'scale_axis':'Y'}))
   state=root/'review.json';out=root/'prepared'
   prepared=self.call('prepare','--stl',source,'--config',config,'--state',state,'--out',out)
   self.assertEqual(prepared.returncode,0,prepared.stderr)
   self.assertEqual(json.loads(prepared.stdout)['next_action'],'review_input')
   self.assertTrue((out/'preview.png').is_file())
   self.assertAlmostEqual(trimesh.load_mesh(out/'input.stl').extents[1],50)
   self.assertFalse(ReviewWorkflow(state).status()['input']['approved'])
 def test_local_edit_keeps_original_and_returns_to_input_review(self):
  import trimesh,hashlib
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'torus.stl';trimesh.creation.torus(major_radius=3,minor_radius=1,major_sections=24,minor_sections=12).export(source)
   old_hash=hashlib.sha256(source.read_bytes()).hexdigest();state=root/'review.json';flow=ReviewWorkflow(state)
   revision=flow.submit('input',{'target_mm':8,'scale_axis':'Y'},[source],True);flow.approve('input',revision,'Source accepted')
   spec=root/'edit.json';spec.write_text(json.dumps({'operation':'fill_local_undercut','bounds':[[-2.5,-2.5,-.3],[2.5,2.5,.3]],'axis':'Y'}))
   out=root/'changed'
   result=self.call('modify',state,'--source',source,'--spec',spec,'--out',out,'--decision','User permits filling this selected recess')
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(json.loads(result.stdout)['next_action'],'review_input')
   self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),old_hash)
   self.assertTrue((out/'original.stl').exists())
   self.assertEqual(json.loads((out/'edit-report.json').read_text())['parent_revision'],revision)
   self.assertFalse(ReviewWorkflow(state).status()['input']['approved'])
if __name__=='__main__':unittest.main()
