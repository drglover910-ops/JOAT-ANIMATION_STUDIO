"""Private storage checks use authentication and reject wrong mount access. Version 1.0.1."""
import importlib.util,io,json,os,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('reference_assets_mount',Path(__file__).resolve().parents[1]/'apps/reference/joat_job_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
class Tests(unittest.TestCase):
 def test_private_metadata_uses_existing_service_credential(self):
  response=io.BytesIO(json.dumps({'runtime':{'volumes':[{'type':'bucket','source':assets.BUCKET,'mountPath':'/studio','readOnly':False}]}}).encode())
  with patch.dict(os.environ,{'SPACE_ID':assets.WRITER_SPACE,'HF_TOKEN':'test-service-auth'},clear=True),patch.object(assets.urllib.request,'urlopen',return_value=response) as fetch,patch.object(assets.Path,'is_dir',return_value=True):
   assets.require_bucket()
   self.assertEqual(fetch.call_args.args[0].get_header('Authorization'),'Bearer test-service-auth')
 def test_missing_credential_cannot_use_anonymous_metadata(self):
  with patch.dict(os.environ,{'SPACE_ID':assets.WRITER_SPACE},clear=True),patch.object(assets.urllib.request,'urlopen') as fetch:
   with self.assertRaises(ValueError):assets.require_bucket()
   fetch.assert_not_called()
 def test_read_only_mount_does_not_qualify_as_writer(self):
  response=io.BytesIO(json.dumps({'runtime':{'volumes':[{'type':'bucket','source':assets.BUCKET,'mountPath':'/studio','readOnly':True}]}}).encode())
  with patch.dict(os.environ,{'SPACE_ID':assets.WRITER_SPACE,'HF_TOKEN':'test-service-auth'},clear=True),patch.object(assets.urllib.request,'urlopen',return_value=response),patch.object(assets.Path,'is_dir',return_value=True):
   with self.assertRaises(ValueError):assets.require_bucket()

 def test_verified_caller_auth_overrides_unusable_runtime_credential(self):
  response=io.BytesIO(json.dumps({'runtime':{'volumes':[{'type':'bucket','source':assets.BUCKET,'mountPath':'/studio','readOnly':False}]}}).encode())
  with patch.dict(os.environ,{'SPACE_ID':assets.WRITER_SPACE,'HF_TOKEN':'unusable-runtime-auth'},clear=True),patch.object(assets.urllib.request,'urlopen',return_value=response) as fetch,patch.object(assets.Path,'is_dir',return_value=True):
   assets.require_bucket(token='verified-owner-auth')
   self.assertEqual(fetch.call_args.args[0].get_header('Authorization'),'Bearer verified-owner-auth')
