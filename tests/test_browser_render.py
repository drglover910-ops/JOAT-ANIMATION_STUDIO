"""Existing-grant browser render boundaries. File version1.0.4."""
FILE_VERSION='1.0.4'
import hashlib,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from gradio.context import LocalContext
R=Path(__file__).resolve().parents[1]/'apps/main'
sys.path.insert(0,str(R))
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.calls=[];self.holds=[];self.grant_id='a'*32
  self.m=types.ModuleType('joat_managed_generation');self.m.ROOT=self.root;self.m.OWNER='Dezz-9-10';self.m.owner_token=lambda *a:'owner-token';self.m.mount_check=lambda *a:None;self.m.read_json=lambda p:json.loads(Path(p).read_text());self.m.safe_path=lambda p:p;self.m.file_hash=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
  def write(p,v):
   p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('x') as f:json.dump(v,f)
  self.m.write_once=write
  parent=self
  class API:
   def __init__(self,**kw):pass
   def whoami(self):return {'name':'Dezz-9-10'}
   def get_space_variables(self,*a):return {'JOAT_STUDIO_GPU_HOLD':types.SimpleNamespace(value='false')}
   def space_info(self,*a):return types.SimpleNamespace(runtime=types.SimpleNamespace(stage='RUNNING'))
   def add_space_variable(self,repo,**kw):parent.holds.append((repo,kw))
  self.m.HfApi=API
  self.remote=types.ModuleType('joat_remote_generation');self.remote.source_for=lambda *a:{};self.remote.load_grant=lambda *a:{'gpu_ceiling_seconds':420};self.remote.PREFIX='JOAT_REMOTE_GENERATION_REQUEST_'
  def run(name,raw):self.calls.append((name,json.loads(raw),LocalContext.request.get(None)));return dict(status='pending_or_unknown',gpu_requested=True)
  self.remote.run=run
  self.mods=patch.dict(sys.modules,{'joat_managed_generation':self.m,'joat_remote_generation':self.remote});self.mods.start()
  spec=importlib.util.spec_from_file_location('actual_render',R/'joat_style001_browser_check.py');self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)
  write(self.root/'production-projects'/self.mod.PROJECT/'opening-authorization'/self.mod.REVISED_PLAN/'grant.json',{'grant_id':self.grant_id})
  self.request=types.SimpleNamespace(headers={'x-ip-token':'real-platform-delegation'})
 def tearDown(self):self.mods.stop();self.tmp.cleanup()
 def test_repeated_clicks_use_same_exact_attempt_and_restore_context(self):
  previous=LocalContext.request.get(None)
  for n in range(2):
   result=self.mod.browser_render(None,None,self.request);self.assertIsNone(result[2])
  self.assertEqual(self.calls[0][1],self.calls[1][1]);self.assertEqual(self.calls[0][1]['request_id'],self.grant_id);self.assertEqual(self.calls[0][1]['plan_fingerprint'],self.mod.REVISED_PLAN);self.assertIs(self.calls[0][2],self.request);self.assertIs(LocalContext.request.get(None),previous);self.assertFalse(self.holds)
 def test_wrong_ceiling_rejected_before_run(self):
  self.remote.load_grant=lambda *a:{'gpu_ceiling_seconds':600}
  with self.assertRaises(Exception):self.mod.browser_render(None,None,self.request)
  self.assertFalse(self.calls)
 def test_nonowner_cannot_run(self):
  def denied(*a):raise ValueError('Owner required')
  self.m.owner_token=denied
  with self.assertRaises(ValueError):self.mod.browser_render(None,None,self.request)
  self.assertFalse(self.calls)
 def test_success_exports_verified_video_and_restores_hold_once(self):
  d=self.root/'remote-generation'/'requests'/self.grant_id;video=d/'artifacts'/'output.mp4';video.parent.mkdir(parents=True);video.write_bytes(b'test-media-bytes');self.m.write_once(d/'artifact_index.json',{'files':[{'filename':'output.mp4','sha256':self.m.file_hash(video)}]});self.m.write_once(d/'artifacts'/'generation_result.json',{'schema':'joat.generation_result.v1','status':'completed'})
  self.remote.run=lambda *a:{'status':'completed','gpu_requested':True}
  for n in range(2):
   out=self.mod.browser_render(None,None,self.request);self.assertEqual(Path(out[2]).read_bytes(),b'test-media-bytes');self.assertEqual(out[2],out[3])
  self.assertEqual(len(self.holds),1);self.assertEqual(self.holds[0][1]['value'],'true')
 def test_exception_does_not_leak_context_or_restart_uncertain_task(self):
  previous=LocalContext.request.get(None)
  def fail(*a):raise RuntimeError('Uncertain connection')
  self.remote.run=fail
  with self.assertRaises(RuntimeError):self.mod.browser_render(None,None,self.request)
  self.assertIs(LocalContext.request.get(None),previous);self.assertFalse(self.holds)
 def test_active_hold_does_not_consume_the_grant(self):
  self.m.HfApi.get_space_variables=lambda *a:{'JOAT_STUDIO_GPU_HOLD':types.SimpleNamespace(value='true')}
  with self.assertRaises(Exception):self.mod.browser_render(None,None,self.request)
  self.assertFalse(self.calls)
 def test_other_reserved_attempt_never_restarts_control(self):
  self.remote.run=lambda *a:{'status':'already_reserved_no_retry','gpu_requested':False}
  self.mod.browser_render(None,None,self.request)
  self.assertFalse(self.holds)
 def recovery_evidence(self, **changes):
  d=self.root/'remote-generation'/'requests'/self.mod.FAILED_GUARD_ATTEMPT;d.mkdir(parents=True,exist_ok=True)
  self.m.write_once(d/'request.json',{'request_id':self.mod.FAILED_GUARD_ATTEMPT,'grant_id':self.mod.FAILED_GUARD_ATTEMPT,'plan_fingerprint':self.mod.REVISED_PLAN})
  out=dict(schema='joat.render_failure.v1',status='render_failed',source_job_fingerprint=self.mod.JOB,stage='validate_locked_plan',submission_state='not_submitted',render_outcome='not_submitted',error_type='ValueError',error_message=self.mod.FAILED_GUARD_MESSAGE);out.update(changes)
  self.m.write_once(d/'artifacts'/'generation_result.json',out);self.m.write_once(d/'artifact_index.json',{'files':[{'filename':'generation_result.json','sha256':self.m.file_hash(d/'artifacts'/'generation_result.json')}]})
  plan=self.root/'prepared.json';self.m.write_once(plan,{'plan':{'parameters':{'gen_budget':420}}});self.remote.prepared_path=lambda *a:plan;self.m.digest=lambda p:self.mod.REVISED_PLAN
  self.issued=[]
  def issue(*a):self.issued.append(a);return {'grant_id':self.grant_id}
  self.remote.grant=issue
 def test_corrected_click_issues_only_one_replacement(self):
  self.recovery_evidence()
  for n in range(2):self.mod.browser_render_corrected(None,None,self.request)
  self.assertEqual(len(self.issued),1);self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[0][1],self.calls[1][1])
 def test_uncertain_submission_cannot_issue_replacement(self):
  self.recovery_evidence(submission_state='submitted',render_outcome='unverified')
  with self.assertRaises(Exception):self.mod.browser_render_corrected(None,None,self.request)
  self.assertFalse(self.issued);self.assertFalse(self.calls)
 def test_altered_failure_hash_cannot_issue_replacement(self):
  self.recovery_evidence();p=self.root/'remote-generation'/'requests'/self.mod.FAILED_GUARD_ATTEMPT/'artifacts'/'generation_result.json';p.write_text('{}')
  with self.assertRaises(Exception):self.mod.browser_render_corrected(None,None,self.request)
  self.assertFalse(self.issued)
 def test_failed_issuance_is_not_automatically_repeated(self):
  self.recovery_evidence()
  def crash(*a):self.issued.append(a);raise RuntimeError('interrupted')
  self.remote.grant=crash
  for n in range(2):
   with self.assertRaises(Exception):self.mod.browser_render_corrected(None,None,self.request)
  self.assertEqual(len(self.issued),1);self.assertFalse(self.calls)
 def test_presubmission_failure_restores_hold(self):
  d=self.root/'remote-generation'/'requests'/self.grant_id;self.m.write_once(d/'artifact_index.json',{'files':[]});self.m.write_once(d/'artifacts'/'generation_result.json',{'submission_state':'not_submitted','render_outcome':'not_submitted'})
  self.remote.run=lambda *a:{'status':'render_failed','gpu_requested':True}
  self.mod.browser_render(None,None,self.request);self.assertEqual(len(self.holds),1)
 def test_view_button_cannot_submit_if_saved_receipt_missing(self):
  with self.assertRaises(Exception):self.mod.browser_view_saved(None,None,self.request)
  self.assertFalse(self.calls)
 def test_view_button_requires_completed_exact_plan(self):
  ledger=self.root/'production-projects'/self.mod.PROJECT/'opening-authorization'/self.mod.REVISED_PLAN/'guard-fix-1.0.2';self.m.write_once(ledger/'grant.json',{'grant_id':self.grant_id})
  self.m.write_once(self.root/'remote-generation'/'requests'/self.grant_id/'receipt.json',{'status':'pending_or_unknown','plan_fingerprint':self.mod.REVISED_PLAN})
  with self.assertRaises(Exception):self.mod.browser_view_saved(None,None,self.request)
  self.assertFalse(self.calls)
if __name__=='__main__':unittest.main()
