import unittest,tempfile
from pathlib import Path
from mouldflow.workflow import ReviewWorkflow,ReviewRequired
class FeatureReviewTests(unittest.TestCase):
 def test_each_area_needs_its_own_decision_and_changes_invalidate_approval(self):
  with tempfile.TemporaryDirectory() as d:
   artifact=Path(d)/'mesh';artifact.write_text('fixture');flow=ReviewWorkflow(Path(d)/'state.json')
   rev=flow.submit('input',{},[artifact],True)
   flow.add_feature('input','lip','lid rim','Traps sideways removal')
   flow.add_feature('input','spout','tip','Requires separate cap')
   flow.decide_feature('input','lip','simplify','User permits lip filling')
   with self.assertRaises(ReviewRequired):flow.approve('input',rev,'Looks good')
   flow.decide_feature('input','spout','preserve','User wants original tip')
   rev=flow.submit('input',{},[artifact],True)
   flow.approve('input',rev,'Reviewed resulting geometry')
   flow.decide_feature('input','spout','simplify','User now permits shortening')
   self.assertFalse(flow.status()['input']['approved'])
   with self.assertRaises(ReviewRequired):flow.approve('input',rev,'Old result')
