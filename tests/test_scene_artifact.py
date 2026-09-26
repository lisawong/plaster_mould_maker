"""HISTORICAL fixture check: older three-part study, not the current two-part mould.

Kept so the 45-test baseline stays reproducible. Passing it says nothing about V7 release.
"""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'fixtures'/'historical'
class SceneArtifactTests(unittest.TestCase):
 def test_saved_scene_contains_both_requested_geometry_groups(self):
  manifest=json.loads((ROOT/'scene-manifest.json').read_text())
  self.assertEqual(manifest['plaster_parts'],3)
  self.assertEqual(manifest['printed_form_reference_parts'],6)
  self.assertFalse(manifest['print_ready'])
  self.assertGreater((ROOT/'teapot-design-study.blend').stat().st_size,10000)
if __name__=='__main__':unittest.main()
