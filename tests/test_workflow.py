import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mouldflow.workflow import ReviewWorkflow, ReviewRequired
class WorkflowTests(unittest.TestCase):
 def test_pending_review_blocks_next_stage_and_resume_keeps_approval(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); artifact=root/'model.stl';artifact.write_text('revision one')
   flow=ReviewWorkflow(root/'state.json')
   revision=flow.submit('input',{'scale_mm':50},[artifact],checks_passed=True)
   with self.assertRaises(ReviewRequired):flow.require_approved('input')
   flow.approve('input',revision,decision='User approves reviewed scale and shape')
   resumed=ReviewWorkflow(root/'state.json');resumed.require_approved('input')
   self.assertEqual(resumed.status()['input']['decision'],'User approves reviewed scale and shape')
 def test_changed_artifact_revokes_it_and_downstream_approval(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/'input.stl';source.write_text('old'); plaster=root/'plaster.stl';plaster.write_text('part')
   flow=ReviewWorkflow(root/'state.json')
   for stage,artifact in [('input',source),('plaster',plaster)]:
    rev=flow.submit(stage,{},[artifact],True);flow.approve(stage,rev,'approved')
   source.write_text('changed geometry')
   with self.assertRaises(ReviewRequired):flow.require_approved('plaster')
   self.assertFalse(flow.status()['input']['approved'])
   self.assertFalse(ReviewWorkflow(root/'state.json').status()['plaster']['approved'])
 def test_cannot_approve_failed_checks_or_skip_previous_checkpoint(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'part.stl';artifact.write_text('geometry')
   flow=ReviewWorkflow(root/'state.json')
   revision=flow.submit('plaster',{},[artifact],True)
   with self.assertRaises(ReviewRequired):flow.approve('plaster',revision,'skip input')
   revision=flow.submit('input',{},[artifact],False)
   with self.assertRaises(ReviewRequired):flow.approve('input',revision,'override failure')
 def test_revision_change_invalidates_downstream_and_rejects_old_review(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'part.stl';artifact.write_text('geometry')
   flow=ReviewWorkflow(root/'state.json');old=flow.submit('input',{'size':50},[artifact],True);flow.approve('input',old,'approved')
   later=flow.submit('plaster',{},[artifact],True);flow.approve('plaster',later,'approved')
   new=flow.submit('input',{'size':60},[artifact],True)
   self.assertNotEqual(old,new)
   with self.assertRaises(ReviewRequired):flow.approve('input',old,'stale')
   self.assertFalse(flow.status()['plaster']['approved'])
 def test_status_detects_changed_files_without_attempting_next_stage(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'object.stl';artifact.write_text('old')
   flow=ReviewWorkflow(root/'review.json');revision=flow.submit('input',{},[artifact],True);flow.approve('input',revision,'approved')
   artifact.write_text('new')
   self.assertFalse(flow.status()['input']['approved'])
 def test_request_changes_preserves_decision_history(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'object.stl';artifact.write_text('geometry')
   flow=ReviewWorkflow(root/'review.json');revision=flow.submit('input',{},[artifact],True);flow.approve('input',revision,'Shape approved')
   flow.request_changes('input','Rotate the handle before partitioning')
   resumed=ReviewWorkflow(root/'review.json');self.assertFalse(resumed.status()['input']['approved'])
   self.assertEqual(resumed.status()['input']['change_request'],'Rotate the handle before partitioning')
   self.assertTrue(any(event.get('decision')=='Shape approved' for event in resumed.history()))
 def test_requested_changes_require_resubmission_before_approval(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);artifact=root/'object.stl';artifact.write_text('geometry')
   flow=ReviewWorkflow(root/'review.json');revision=flow.submit('input',{},[artifact],True)
   flow.request_changes('input','Change orientation')
   with self.assertRaises(ReviewRequired):flow.approve('input',revision,'Reuse old result')
if __name__=='__main__':unittest.main()
