"""Original-script one-action browser orchestration security. File version1.0.1."""
import copy,hashlib,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from gradio.context import LocalContext
ROOT=Path(__file__).resolve().parents[1]
PLAN=json.loads((ROOT/'tests/fixtures/opening_plan_candidate_v1.0.0.json').read_text())['plan']
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.calls=[];self.grants=[];self.submits=[]
  self.m=types.ModuleType('joat_managed_generation');m=self.m;m.ROOT=self.root;m.OWNER='Dezz-9-10';m.owner_token=lambda *a:'owner-token';m.mount_check=lambda *a:None;m.safe_path=lambda p:p;m.safe_validation_message=lambda exc,*a:str(exc)
  m.digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
  m.file_hash=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();m.read_json=lambda p:json.loads(Path(p).read_text())
  def write(p,v):
   p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('x') as f:json.dump(v,f)
  m.write_once=write
  class API:
   def __init__(self,**k):pass
   def get_space_variables(self,*a):return {'JOAT_STUDIO_GPU_HOLD':types.SimpleNamespace(value='false')}
   def space_info(self,*a):return types.SimpleNamespace(runtime=types.SimpleNamespace(stage='RUNNING'))
   def whoami(self):return {'name':'Dezz-9-10'}
   def add_space_variable(self,*a,**k):pass
  m.HfApi=API
  self.remote=types.ModuleType('joat_remote_generation');v=self.remote;v.PREFIX='JOAT_REMOTE_GENERATION_REQUEST_';v.source_for=lambda *a:{};v.signed=lambda packet,phase,plan=None:dict(phase=phase);v.prepared_path=lambda *a:self.root/'prepared.json';v.save_plan=lambda packet,r:write(self.root/'prepared.json',r)
  def proxy(role,phase,data,token):
   self.calls.append((phase,LocalContext.request.get(None)))
   if phase=='prepare':return dict(schema='joat.managed_render_plan.v1',gpu_called=False,plan=copy.deepcopy(PLAN),plan_fingerprint=m.digest(PLAN))
   return dict(schema='joat.render_connection_check.v1',status='passed',gpu_called=False,source_job_fingerprint=self.mod.JOB)
  m.proxy=proxy
  def grant(packet,plan,approved):self.grants.append((packet,plan,approved));return {'grant_id':'b'*32}
  v.grant=grant;v.load_grant=lambda *a:{'gpu_ceiling_seconds':420}
  def run(name,raw):
   e=json.loads(raw);self.submits.append(e);receipt={'status':'pending_or_unknown','gpu_requested':True};write(self.root/'remote-generation'/'requests'/e['request_id']/'receipt.json',receipt);return receipt
  v.run=run
  constants=types.ModuleType('joat_style001_opening_grant');constants.PROJECT='PROJECT-OTU-STYLE001-90S-001';constants.JOB='222eedbf801f0a847e0fe2f470d3c7d211e5ab08a668c8a19027d2400ce51227';constants.SUPERVISOR='8d0657bcdcacd16bae2eae587d05ac083e533d00ac0f089817b9bee6f411df79'
  self.patch=patch.dict(sys.modules,{'joat_managed_generation':m,'joat_remote_generation':v,'joat_style001_opening_grant':constants});self.patch.start()
  spec=importlib.util.spec_from_file_location('actual_corrected',ROOT/'apps/main/joat_style001_corrected_opening.py');self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod);self.request=types.SimpleNamespace(headers={'x-ip-token':'platform-current-request'})
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def test_one_click_checks_then_issues_and_submits_once(self):
  previous=LocalContext.request.get(None);self.mod.run_approved(None,None,self.request)
  self.assertEqual([x[0] for x in self.calls],['prepare','check']);self.assertTrue(all(x[1] is self.request for x in self.calls));self.assertEqual(len(self.grants),1);self.assertEqual(len(self.submits),1);self.assertEqual(self.submits[0]['plan_fingerprint'],self.mod.PLAN);self.assertIs(LocalContext.request.get(None),previous)
 def test_repeated_clicks_retrieve_unknown_attempt_without_resubmission(self):
  for n in range(2):self.mod.run_approved(None,None,self.request)
  self.assertEqual(len(self.grants),1);self.assertEqual(len(self.submits),1)
 def test_nonowner_stops_before_network_or_grant(self):
  def deny(*a):raise ValueError('Owner required')
  self.m.owner_token=deny
  with self.assertRaises(Exception):self.mod.run_approved(None,None,self.request)
  self.assertFalse(self.calls);self.assertFalse(self.grants)
 def test_held_director_does_not_consume_authorization(self):
  self.m.HfApi.get_space_variables=lambda *a:{'JOAT_STUDIO_GPU_HOLD':types.SimpleNamespace(value='true')}
  with self.assertRaises(Exception):self.mod.run_approved(None,None,self.request)
  self.assertFalse(self.calls);self.assertFalse(self.grants)
 def test_different_plan_rejected_before_check_grant_or_render(self):
  prior=self.m.proxy
  def changed(*a):
   r=prior(*a)
   if a[1]=='prepare':r['plan']['parameters']['prompt']='changed'
   return r
  self.m.proxy=changed
  with self.assertRaises(Exception):self.mod.run_approved(None,None,self.request)
  self.assertEqual(len(self.calls),1);self.assertFalse(self.grants);self.assertFalse(self.submits)
 def test_connection_failure_is_cpu_only_and_preserves_context(self):
  prior=self.m.proxy
  def fail(*a):
   if a[1]=='check':raise RuntimeError('HTTP429')
   return prior(*a)
  self.m.proxy=fail;previous=LocalContext.request.get(None)
  with self.assertRaises(Exception):self.mod.run_approved(None,None,self.request)
  self.assertFalse(self.grants);self.assertFalse(self.submits);self.assertIs(LocalContext.request.get(None),previous)
 def test_failed_issuance_is_reserved_and_not_repeated(self):
  def crash(*a):self.grants.append(a);raise RuntimeError('interrupted issuance')
  self.remote.grant=crash
  for n in range(2):
   with self.assertRaises(Exception):self.mod.run_approved(None,None,self.request)
  self.assertEqual(len(self.grants),1);self.assertFalse(self.submits)
 def test_wrong_grant_ceiling_does_not_submit(self):
  self.remote.load_grant=lambda *a:{'gpu_ceiling_seconds':600}
  with self.assertRaises(Exception):self.mod.run_approved(None,None,self.request)
  self.assertFalse(self.submits)
 def test_corrupted_saved_media_not_returned(self):
  p=self.root/'result';self.m.write_once(p/'artifact_index.json',{'files':[{'filename':'output.mp4','sha256':'bad','size_bytes':3}]});f=p/'artifacts/output.mp4';f.parent.mkdir();f.write_bytes(b'abc')
  with self.assertRaises(Exception):self.mod.result_outputs(p,{'status':'completed'})
 def test_no_hold_restart_for_unknown_submission(self):
  calls=[];self.m.HfApi.add_space_variable=lambda *a,**k:calls.append(True)
  self.mod.run_approved(None,None,self.request);self.assertFalse(calls)
if __name__=='__main__':unittest.main()
