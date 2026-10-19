"""One owner-staged original-film shot through the existing signed native chain.
File version: 1.0.2. Included quota only, no retry, canon change or QC approval.
"""
FILE_VERSION='1.0.2'
import os,re,threading,time,uuid,math
import joat_managed_generation as m
PROJECT='PROJECT-OTU-STYLE001-90S-001'
MISSION='2a881aa9651cd9058fd3f9ddaf199f1c2cbfc849b82caf511b1bcd661921868d'
SOURCE='1aee010f5c991fd25ed48245b7fbbd9271232c8dc4e9ebd90616db245aa2329b'
CONTROL='Dezz-9-10/J.O.A.T.-Executive-Producer-Bot'
LOCK=threading.Lock()

def validate(mission,payload,packet):
 fields={'shot_id','source_job_fingerprint','source_supervisor_fingerprint','gpu_ceiling_seconds','maximum_attempts','maximum_paid_usd','credit_purchase_authorized'}
 if not isinstance(payload,dict) or set(payload)!=fields:raise ValueError('Exact original-film shot and zero-credit scope required.')
 m.verify(mission,'plan_fingerprint')
 if mission.get('plan_fingerprint')!=MISSION or mission.get('project_id')!=PROJECT or mission.get('owner_source_prompt_sha256')!=SOURCE or mission.get('owner_supplied_source_prompt') is not True:raise ValueError('Only the unchanged approved original film is authorized.')
 if type(payload['gpu_ceiling_seconds']) is not int or payload['gpu_ceiling_seconds']!=420 or type(payload['maximum_attempts']) is not int or payload['maximum_attempts']!=1 or type(payload['maximum_paid_usd']) is not int or payload['maximum_paid_usd']!=0 or payload['credit_purchase_authorized'] is not False:raise ValueError('One420second included-quota attempt; no paid authority.')
 if any(not isinstance(payload[k],str) or not re.fullmatch('[a-f0-9]{64}',payload[k]) for k in ['source_job_fingerprint','source_supervisor_fingerprint']):raise ValueError('Exact source packet fingerprints required.')
 matches=[s for s in mission['shots'] if s['shot_id']==payload['shot_id'] and s['production_type']=='video']
 if len(matches)!=1:raise ValueError('One original video shot required.')
 shot=matches[0];job=packet['generation_job']
 if packet.get('packet_fingerprint')!=payload['source_supervisor_fingerprint'] or job.get('job_fingerprint')!=payload['source_job_fingerprint'] or job.get('project_context')!={'project_id':PROJECT,'scene_id':shot['scene_id'],'shot_id':shot['shot_id']} or job.get('generation_specification',{}).get('duration_seconds')!=shot['duration_seconds'] or job['generation_specification'].get('aspect_ratio')!='9:16':raise ValueError('Native source differs from the original approved shot.')
 return shot

def check_plan(shot,plan):
 p=plan.get('parameters',{})
 if (p.get('seconds'),p.get('max_width'),p.get('max_height'),p.get('input_mode'),p.get('gen_budget'))!=(shot['duration_seconds'],576,1024,'single image (i2v)',420) or p.get('skip_refine') is not True:raise ValueError('Prepared shot changed reviewed duration, geometry, route or allocation.')
 words=shot.get('voice_text','');dialogue=shot.get('audio',{}).get('dialogue','')
 if dialogue:
  if dialogue!=words or dialogue not in p.get('prompt',''):raise ValueError('Native character speech lost original words.')
 elif words and words in p.get('prompt',''):raise ValueError('Post narration must not leak into native speech generation.')
 return p

def quota_guard(observation,budget):
 # Conservative normalization covers up to2quota seconds per GPU second.
 # This is a local guard, not a provider cap against simultaneous account use.
 required=budget*2+120
 if observation.get('provider_live_balance') is not True or type(observation.get('remaining_seconds')) not in (int,float) or not math.isfinite(observation['remaining_seconds']) or observation['remaining_seconds']<required:raise ValueError('Fresh included quota cannot cover the conservative allocation and headroom; no GPU request sent.')
 return required

def describe_policy(token):
 # Reuse the proven signed-chain transport and its verified cached API contract.
 client=m.client_for('executive',token,False)
 try:
  value=client.submit('generation_worker',api_name='/cpu_department_describe').result(timeout=30)
  from joat_studio_capabilities import registry
  if value.get('studio_capability_registry_fingerprint')!=registry()['registry_fingerprint']:raise ValueError('Worker capability registry differs.')
  return value.get('runtime_policy',{})
 finally:client.close()

def wait_ready(api,token,expected_hold):
 end=time.monotonic()+90;last_error=None;last_policy=None
 while time.monotonic()<end:
  if str(api.space_info(CONTROL).runtime.stage)=='RUNNING':
   try:
    policy=describe_policy(token);last_policy=policy
    if policy.get('gpu_hold') is expected_hold and policy.get('composed_i2v_gpu_ceiling_seconds')=='420':return
   except Exception as exc:
    from joat_production_tasks import safe_error
    detail=dict(error_type=type(exc).__name__,error_message=safe_error(exc))
    if detail!=last_error:print('JOAT_RUNTIME_POLICY_PROBE '+m.stable(detail),flush=True)
    last_error=detail  # Read-only probe; no GPU operation submitted.
  time.sleep(3)
 raise ValueError('Studio Control runtime policy unconfirmed; no execution request sent. '+m.stable(dict(last_error=last_error,last_policy=last_policy)))

def execute(mission,payload,directory,token):
 from joat_remote_generation import source_for,signed,save_plan,grant,run,PREFIX
 from joat_provider_quota import read_quota
 from joat_job_frame_binding import load_binding,load_approved_frame
 with LOCK:
  packet=source_for(PROJECT,payload.get('source_job_fingerprint'),payload.get('source_supervisor_fingerprint'));shot=validate(mission,payload,packet)
  frame=load_binding(packet)
  if frame is None:raise ValueError('An approved exact scene-frame binding is required.')
  load_approved_frame(frame['approved_frame_manifest'])
  api=m.HfApi(token=token);hold=api.get_space_variables(CONTROL).get('JOAT_STUDIO_GPU_HOLD')
  if hold is None or hold.value.lower()!='true':raise ValueError('Studio Control must be held before staging this single render.')
  wait_ready(api,token,True)
  prepared=m.proxy('executive','prepare',signed(packet,'prepare'),token);p=check_plan(shot,prepared['plan']);save_plan(packet,prepared)
  checked=m.proxy('executive','check',signed(packet,'check',prepared['plan']),token)
  if checked.get('status')!='passed' or checked.get('gpu_called') is not False or checked.get('source_job_fingerprint')!=payload['source_job_fingerprint']:raise ValueError('Exact signed CPU preflight did not pass.')
  prior=m.existing_attempt(packet,prepared['plan'],m.ROOT)[0]
  if prior.get('status')!='not_submitted':raise ValueError('Existing completed or unknown attempt must be reviewed/reused; no duplicate render.')
  for reservation in (m.ROOT/'gpu-quota'/'live-reference-reservations').glob('*/reservation.json'):
   from joat_gpu_quota_panel import read
   settlement=reservation.parent/'settlement.json'
   if not settlement.exists():raise ValueError('Unsettled reference allocation exists; no concurrent film render.')
   pending=read(reservation);settled=read(settlement)
   if settled.get('status')!='response_received_artifact_verified' or settled.get('request_id')!=pending['request_id'] or settled.get('request_fingerprint')!=pending['request_fingerprint']:raise ValueError('Reference outcome is not verified; keep GPU execution held.')
  quota=read_quota(token);required=quota_guard(quota,p['gen_budget'])
  ledger=m.ROOT/'production-projects'/PROJECT/'included-film-renders'/payload['source_job_fingerprint']/prepared['plan_fingerprint']
  m.write_once(ledger/'reservation.json',dict(file_version=FILE_VERSION,original_scope=payload,source_prompt_sha256=SOURCE,quota_observation=quota,required_included_seconds=required,maximum_paid_usd=0,maximum_attempts=1,automatic_retry=False,production_qc_approved=False))
  m.write_once(directory/'managed_plan.json',prepared);m.write_once(directory/'connection_check.json',checked)
  released=False;outcome=None
  try:
   issued=grant(packet,prepared['plan'],True);m.write_once(ledger/'grant.json',issued)
   released=True;api.add_space_variable(CONTROL,'JOAT_STUDIO_GPU_HOLD','false');wait_ready(api,token,False)
   final_quota=read_quota(token);quota_guard(final_quota,p['gen_budget']);m.write_once(ledger/'pre_submission_quota.json',final_quota)
   identifier=uuid.uuid4().hex
   request=dict(schema='joat.remote_generation_request.v1',file_version='1.0.0',request_id=identifier,operation='execute',project_id=PROJECT,source_job_fingerprint=payload['source_job_fingerprint'],source_supervisor_fingerprint=payload['source_supervisor_fingerprint'],plan_fingerprint=prepared['plan_fingerprint'],grant_id=issued['grant_id'])
   m.write_once(ledger/'execution_request.json',request)
   receipt=run(PREFIX+identifier,m.stable(request));m.write_once(ledger/'execution_receipt.json',receipt)
   complete=receipt.get('status')=='completed'
   outcome=dict(status='render_candidate_awaiting_independent_qc' if complete else 'render_stopped_for_review',gpu_called=True if complete else None,gpu_requested=receipt.get('gpu_requested'),shot_id=shot['shot_id'],execution_id=identifier,plan_fingerprint=prepared['plan_fingerprint'],artifact_index_bucket_path=receipt.get('artifact_index_path'),paid_authority_usd=0,production_qc_approved=False)
  finally:
   if released:
    try:
     api.add_space_variable(CONTROL,'JOAT_STUDIO_GPU_HOLD','true')
     restored=api.get_space_variables(CONTROL).get('JOAT_STUDIO_GPU_HOLD');ok=restored is not None and restored.value.lower()=='true'
     if not ok:raise ValueError('Hold confirmation missing.')
     wait_ready(api,token,True)
     if outcome is not None:outcome['gpu_hold_restored']=True
    except Exception as exc:
     print('JOAT_RENDER_HOLD_RESTORE '+m.stable(dict(status='requires_operator_review',error_type=type(exc).__name__,project_id=PROJECT)),flush=True)
     if outcome is not None:outcome.update(gpu_hold_restored=False,status='render_result_requires_hold_recovery')
  return outcome
