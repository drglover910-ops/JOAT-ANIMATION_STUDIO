"""Deployment bundle integrity regression. File version: 1.0.0."""
import hashlib,json,unittest
from pathlib import Path
FILE_VERSION='1.0.0'
ROOT=Path(__file__).resolve().parents[1]/'apps/control'
class ReleaseManifestTests(unittest.TestCase):
 def test_reviewed_control_bundle_matches_deployed_integrity_gate(self):
  m=json.loads((ROOT/'consolidated_manifest.json').read_text());given=m.pop('manifest_fingerprint')
  self.assertEqual(given,hashlib.sha256(json.dumps(m,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest())
  for entry in m['files']:
   path=ROOT/entry['path']
   if not path.is_file() and path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
    self.assertTrue(path.with_name(path.name+'.base64').is_file());continue
   self.assertTrue(path.is_file(),entry['path'])
   self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry['sha256'],entry['path'])
   self.assertEqual(path.stat().st_size,entry['size_bytes'],entry['path'])
