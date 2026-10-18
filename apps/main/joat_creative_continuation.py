"""Continue an already owner-requested CPU draft after a mechanical source fix.
File version1.0.0. Never locks creative decisions, assembles sources, or invokes GPU.
"""
FILE_VERSION='1.0.0'
import hashlib,json,os,re
from pathlib import Path
from huggingface_hub import HfApi
import joat_creative_workflow as workflow
import joat_executive_handoff as handoff
import joat_managed_generation as managed
import joat_commercial_proposal as proposals
PREFIX='JOAT_CREATIVE_CONTINUATION_INPUT_'

def guard(value):
 if not isinstance(value,dict) or set(value)!={'project_id','payload_sha256'}:raise ValueError('Invalid continuation request scope.')
 managed.valid_project(value['project_id'])
 index=managed.read_json(managed.safe_path(proposals.ROOT/'commercial-proposals/latest.json'))
 if {'project_id':index.get('project_id'),'payload_sha256':index.get('sha256')}!=value:raise ValueError('Continuation does not match the exact private campaign.')
 project,brief,raw,story=proposals.proposal();plan=workflow.validate_plan(project,brief,raw);first=plan['shots'][0]
 if project!=value['project_id']:raise ValueError('Wrong continuation project.')
 def receipt(role,args,recovery=False):
  prepared=handoff.prepare(project,role,args);stored=handoff.read_checkpoint(prepared,root=workflow.ROOT,recovery=recovery)
  if stored.get('department_role')!=role:raise ValueError('Stored owner request uses another department.')
  return stored
 char=receipt('character',{'cid':first['character_id'],'task':'scene'})
 if char.get('status')!='department_api_returned':raise ValueError('Owner Character handoff has not completed.')
 env_args=dict(environment_id=first['environment_id'],task='scene',time_of_day='director_defined',lighting='director_defined',weather='director_defined',scene_id=first['scene_id'],shot_id=first['shot_id'])
 environment=receipt('environment',env_args,recovery=True)
 if environment.get('status')!='department_api_returned':raise ValueError('Owner Environment recovery has not completed.')
 old=receipt('director',workflow.director_args(brief,first))
 artifact=old.get('department_artifact')
 if old.get('status')!='department_api_returned' or not isinstance(artifact,(list,tuple)) or len(artifact)!=3 or not str(artifact[0]).startswith('ERROR:') or artifact[1] or artifact[2]:
  raise ValueError('The original Director outcome is not a confirmed error-only draft response.')
 return plan,{'character':char['receipt_fingerprint'],'environment':environment['receipt_fingerprint'],'original_director_error':old['receipt_fingerprint']},str(artifact[0])

def continue_cpu_drafts():
 for name in sorted(k for k in os.environ if k.startswith(PREFIX)):
  try:
   value=json.loads(os.environ[name]);plan,binding,error=guard(value)
   token=os.environ.get('JOAT_SPECIALIST_TOKEN')
   if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Runtime owner transport is not verified.')
   attempt=workflow.ROOT/'creative-projects'/plan['project_id']/'continuations'/managed.digest(value)
   managed.safe_path(attempt)
   if (attempt/'reservation.json').exists():
    print('JOAT_CREATIVE_CONTINUATION '+json.dumps({'schema':'joat.creative_continuation_receipt.v1','file_version':FILE_VERSION,'project_id':plan['project_id'],'status':'already_reserved_no_request','gpu_called':False,'automatic_retry':False}),flush=True);continue
   managed.write_once(attempt/'reservation.json',{'schema':'joat.creative_continuation_reservation.v1','file_version':FILE_VERSION,'scope':value,'prior_owner_receipts':binding,'plan_fingerprint':plan['plan_fingerprint'],'automatic_retry':False})
   print('JOAT_CREATIVE_CONTINUATION '+json.dumps({'schema':'joat.creative_continuation_diagnostic.v1','file_version':FILE_VERSION,'project_id':plan['project_id'],'original_director_error':re.sub(r'(?i)(?:Bearer\s+|hf_)[A-Za-z0-9._-]+','[REDACTED]',error)[:500],'gpu_called':False}),flush=True)
   # The unchanged campaign's owner-requested CPU draft only. build_drafts is
   # fixed to character/environment/director; no creative approval or render.
   state=workflow.build_drafts(plan)
   if state.get('creative_approved') is not False or state.get('gpu_called') is not False or len(state['drafts'])!=len(plan['shots']):raise ValueError('Continuation returned unexpected authority or scope.')
   result={'schema':'joat.creative_continuation_receipt.v1','file_version':FILE_VERSION,'project_id':plan['project_id'],'status':'director_drafts_saved_awaiting_owner_creative_review','prior_owner_receipts':binding,'plan_fingerprint':plan['plan_fingerprint'],'draft_state_fingerprint':state['state_fingerprint'],'draft_count':len(state['drafts']),'private_draft_readback_verified':True,'creative_approved':False,'production_sources_assembled':False,'gpu_called':False,'automatic_retry':False}
   managed.write_once(attempt/'result.json',result)
   print('JOAT_CREATIVE_CONTINUATION '+json.dumps(result),flush=True)
  except Exception as exc:
   print('JOAT_CREATIVE_CONTINUATION '+json.dumps({'schema':'joat.creative_continuation_receipt.v1','file_version':FILE_VERSION,'status':'stopped_for_review','error_type':type(exc).__name__,'safe_error_message':re.sub(r'(?i)(?:Bearer\s+|hf_)[A-Za-z0-9._-]+','[REDACTED]',str(exc))[:600],'gpu_called':False,'automatic_retry':False}),flush=True)
