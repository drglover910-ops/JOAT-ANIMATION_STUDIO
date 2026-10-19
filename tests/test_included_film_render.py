"""Zero-credit source scope and actual worker-policy readiness gates. Version1.0.1."""
import importlib.util,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'apps/main'))
import joat_included_film_render as render
class Tests(unittest.TestCase):
 def setUp(self):
  self.mission=json.loads((ROOT/'tests/fixtures/style001_mission.json').read_text());shot=next(s for s in self.mission['shots'] if s['shot_id']=='SHOT-010')
  self.packet={'packet_fingerprint':'b'*64,'generation_job':{'job_fingerprint':'a'*64,'project_context':{'project_id':render.PROJECT,'scene_id':shot['scene_id'],'shot_id':shot['shot_id']},'generation_specification':{'duration_seconds':shot['duration_seconds'],'aspect_ratio':'9:16'}}}
  self.scope={'shot_id':'SHOT-010','source_job_fingerprint':'a'*64,'source_supervisor_fingerprint':'b'*64,'gpu_ceiling_seconds':420,'maximum_attempts':1,'maximum_paid_usd':0,'credit_purchase_authorized':False}
 def test_original_source_exact_shot_and_zero_credit_scope(self):
  self.assertEqual(render.validate(self.mission,self.scope,self.packet)['shot_id'],'SHOT-010')
  for key,value in [('maximum_paid_usd',1),('maximum_attempts',2),('maximum_attempts',True),('gpu_ceiling_seconds',600),('credit_purchase_authorized',0),('shot_id','SHOT-009')]:
   with self.assertRaises(ValueError):render.validate(self.mission,dict(self.scope,**{key:value}),self.packet)
 def test_unknown_low_or_invalid_quota_cannot_release_gpu(self):
  for value in [{'provider_live_balance':False},{'provider_live_balance':True,'remaining_seconds':959},{'provider_live_balance':True,'remaining_seconds':None},{'provider_live_balance':True,'remaining_seconds':float('nan')}]:
   with self.assertRaises(ValueError):render.quota_guard(value,420)
  self.assertEqual(render.quota_guard({'provider_live_balance':True,'remaining_seconds':960},420),960)
 def test_hub_running_alone_does_not_prove_worker_release(self):
  api=types.SimpleNamespace(space_info=lambda _:types.SimpleNamespace(runtime=types.SimpleNamespace(stage='RUNNING')))
  with patch.object(render,'describe_policy',side_effect=[{'gpu_hold':True,'composed_i2v_gpu_ceiling_seconds':'420'},{'gpu_hold':False,'composed_i2v_gpu_ceiling_seconds':'420'}]) as probe,patch.object(render.time,'sleep') as pause:
   render.wait_ready(api,'test-owner-auth',False)
   self.assertEqual(probe.call_count,2);pause.assert_called_once()
 def test_speech_and_post_narration_are_kept_separate(self):
  shot=next(s for s in self.mission['shots'] if s['shot_id']=='SHOT-010');p={'seconds':4,'max_width':576,'max_height':1024,'input_mode':'single image (i2v)','gen_budget':420,'skip_refine':True,'prompt':shot['voice_text']}
  render.check_plan(shot,{'parameters':p})
  with self.assertRaises(ValueError):render.check_plan(shot,{'parameters':dict(p,prompt='An off-screen narrator speaks instead.')})
  narrator=next(s for s in self.mission['shots'] if s['shot_id']=='SHOT-001')
  render.check_plan(narrator,{'parameters':dict(p,seconds=5,prompt='Silent tired face; no voice.')})
  with self.assertRaises(ValueError):render.check_plan(narrator,{'parameters':dict(p,seconds=5,prompt=narrator['voice_text'])})
