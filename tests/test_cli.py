import sys, unittest, tempfile, subprocess, json, os
from pathlib import Path
import trimesh
WORK=Path(__file__).resolve().parents[1]
class CliTests(unittest.TestCase):
 def test_second_stl_creates_replayable_candidate_and_report(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/'sphere.stl';trimesh.creation.icosphere(subdivisions=2,radius=5).export(source)
   config=root/'settings.json';config.write_text(json.dumps({'target_mm':20,'scale_axis':'Y','mode':'two_part','gate_radius':3}))
   result=subprocess.run([sys.executable,'-m','mouldflow',str(source),'--config',str(config),'--out',str(root/'result')],env={**os.environ,'PYTHONPATH':str(WORK)},capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   report=json.loads((root/'result/report.json').read_text())
   self.assertEqual(report['input']['dimensions_mm'],[20,20,20])
   self.assertEqual(report['status'],'candidate_passed_sampled_checks')
   self.assertFalse(report['print_ready'])
   exported=trimesh.load_mesh(root/'result/print_candidates/master_1.stl')
   self.assertTrue(exported.is_volume)
   self.assertTrue((root/'result/settings.json').exists())
 def test_gated_run_stops_before_geometry_without_input_review(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'sphere.stl';trimesh.creation.icosphere(subdivisions=1).export(source)
   config=root/'settings.json';config.write_text(json.dumps({'target_mm':20}))
   result=subprocess.run([sys.executable,'-m','mouldflow',str(source),'--config',str(config),'--out',str(root/'result'),'--workflow',str(root/'reviews.json')],env={**os.environ,'PYTHONPATH':str(WORK)},capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0)
   self.assertIn('input: review and approval required',result.stderr)
   self.assertFalse((root/'result').exists())
 def test_approved_input_generates_plaster_review_but_not_forms(self):
  sys.path.insert(0,str(WORK))
  from mouldflow.workflow import ReviewWorkflow,ReviewRequired
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'sphere.stl';trimesh.creation.icosphere(subdivisions=2,radius=5).export(source)
   config=root/'settings.json';config.write_text(json.dumps({'target_mm':20,'gate_radius':3}))
   state=root/'review.json';flow=ReviewWorkflow(state)
   revision=flow.submit('input',{},[source,config],True);flow.approve('input',revision,'approved test fixture')
   result=subprocess.run([sys.executable,'-m','mouldflow',str(source),'--config',str(config),'--out',str(root/'result'),'--workflow',str(state)],env={**os.environ,'PYTHONPATH':str(WORK)},capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(list((root/'result/print_candidates').glob('*.stl')),[])
   with self.assertRaises(ReviewRequired):ReviewWorkflow(state).require_approved('plaster')
if __name__=='__main__':unittest.main()
