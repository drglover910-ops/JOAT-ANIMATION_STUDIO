"""Execute exact owner-approved creative source preparation on CPU. File version1.0.1.
A scoped private approval request cannot authorize rendering or waive QC.
"""
FILE_VERSION='1.0.1'
import json,os,re
from pathlib import Path
from huggingface_hub import HfApi
import joat_creative_workflow as workflow
import joat_managed_generation as managed
PREFIX='JOAT_CREATIVE_APPROVAL_INPUT_'

def load_approved_state(value):
 if not isinstance(value,dict) or set(value)!={'project_id','plan_fingerprint','draft_state_fingerprint','owner_approved','gpu_allowed'} or value['owner_approved'] is not True or value['gpu_allowed'] is not False:raise ValueError('Exact creative approval with GPU disabled is required.')
 managed.valid_project(value['project_id'])
 for key in ('plan_fingerprint','draft_state_fingerprint'):
  if not isinstance(value[key],str) or not re.fullmatch('[a-f0-9]{64}',value[key]):raise ValueError('Approval requires exact retained fingerprints.')
 path=managed.safe_path(workflow.ROOT/'creative-projects'/value['project_id']/value['plan_fingerprint']/'drafts.json')
 state=workflow.validate_state(managed.read_json(path))
 if state['state_fingerprint']!=value['draft_state_fingerprint'] or state['plan']['plan_fingerprint']!=value['plan_fingerprint'] or state['plan']['project_id']!=value['project_id']:raise ValueError('Approval does not match the exact saved drafts.')
 return state

def preflight_sources(result,token):
 checks=[]
 for source in result['source_packets']:
  job=source['generation_job'];context=job['project_context'];director=job['immutable_upstream_snapshot']['director']
  references=director.get('approved_job_references',[])
  selected=[r for r in references if r.get('descriptor',{}).get('scope',{}).get('shot_id')==context['shot_id'] and r.get('descriptor',{}).get('scope',{}).get('scene_id')==context['scene_id']]
  item={'project_context':context,'source_job_fingerprint':job['job_fingerprint'],'source_supervisor_fingerprint':source['packet_fingerprint'],'gpu_called':False}
  if len(selected)!=1:
   item.update(status='blocked_missing_approved_single_scene_start_frame',renderer_request_made=False,canonical_character_id=job['immutable_upstream_snapshot']['character']['character_id'],canonical_environment_id=job['immutable_upstream_snapshot']['environment']['environment_id'])
  else:
   # Only plan and connection metadata; no execute/reuse fallback here.
   prepared=managed.proxy('executive','prepare',managed.sign(source,'prepare'),token)
   if prepared.get('gpu_called') is not False:raise ValueError('Unexpected GPU authority in CPU preflight.')
   checked=managed.proxy('executive','check',managed.sign(source,'check',prepared['plan']),token)
   if checked.get('gpu_called') is not False or checked.get('status')!='passed':raise ValueError('Renderer CPU connection check did not pass.')
   item.update(status='cpu_renderer_connection_passed',renderer_request_made=True,render_plan_fingerprint=prepared['plan_fingerprint'])
  checks.append(item)
 return checks

def execute_creative_approvals():
 for name in sorted(k for k in os.environ if k.startswith(PREFIX)):
  try:
   value=json.loads(os.environ[name]);resume=value.pop('resume_after_fix',None)
   if resume not in (None,'projectless_performance_asset_references'):raise ValueError('Unrecognized repair continuation.')
   state=load_approved_state(value)
   token=os.environ.get('JOAT_SPECIALIST_TOKEN')
   owner=HfApi(token=token).whoami().get('name') if token else None
   if owner!='Dezz-9-10':raise ValueError('Existing owner runtime transport is unavailable.')
   directory=managed.safe_path(workflow.ROOT/'creative-projects'/value['project_id']/'owner-approval-executions'/managed.digest(value))
   if (directory/'reservation.json').exists() and resume is None:
    print('JOAT_CREATIVE_APPROVAL '+json.dumps({'schema':'joat.creative_approval_execution_receipt.v1','file_version':FILE_VERSION,'status':'already_reserved_no_request','gpu_called':False,'automatic_retry':False}),flush=True);continue
   if resume is not None:
    if managed.read_json(directory/'reservation.json').get('approval')!=value or (directory/'result.json').exists():raise ValueError('Repair must match unfinished original approval.')
    approval=managed.read_json(workflow.ROOT/'creative-projects'/value['project_id']/value['plan_fingerprint']/'approval.json')
    if approval.get('reviewer')!=owner or approval.get('draft_state_fingerprint')!=value['draft_state_fingerprint']:raise ValueError('Original creative approval unavailable for repair.')
    if (directory/'projectless-asset-repair-reservation.json').exists():raise ValueError('Repair already reserved; inspect existing receipts, no repeat.')
    managed.write_once(directory/'projectless-asset-repair-reservation.json',{'file_version':FILE_VERSION,'reason':resume,'gpu_called':False,'automatic_retry':False})
   else:managed.write_once(directory/'reservation.json',{'schema':'joat.creative_approval_execution_reservation.v1','file_version':FILE_VERSION,'approval':value,'gpu_called':False,'automatic_retry':False})
   result=workflow.assemble(state,True,owner)
   if result.get('gpu_called') is not False or result['shots_prepared']!=len(state['drafts']):raise ValueError('Source preparation changed authority or scope.')
   checks=preflight_sources(result,token)
   record={'schema':'joat.creative_approval_execution_receipt.v1','file_version':FILE_VERSION,'project_id':value['project_id'],'status':'approved_sources_saved','draft_state_fingerprint':state['state_fingerprint'],'creative_approval_recorded':True,'source_result_fingerprint':result['result_fingerprint'],'source_count':result['shots_prepared'],'private_source_readback_verified':True,'preflight':checks,'gpu_called':False,'production_qc_approved':False,'automatic_retry':False}
   managed.write_once(directory/'result.json',record)
   print('JOAT_CREATIVE_APPROVAL '+json.dumps(record),flush=True)
  except Exception as exc:
   # Error class/safe message only; do not print packets or credentials.
   message=re.sub(r'(?i)(?:Bearer\s+|hf_)[A-Za-z0-9._-]+','[REDACTED]',str(exc))[:600]
   print('JOAT_CREATIVE_APPROVAL '+json.dumps({'schema':'joat.creative_approval_execution_receipt.v1','file_version':FILE_VERSION,'status':'stopped_for_review','error_type':type(exc).__name__,'safe_error_message':message,'gpu_called':False,'automatic_retry':False}),flush=True)
