"""Private owner-staged production preflight, assets and voice. File version1.0.25.
No canonical/creative QC approval is invented. Candidate generation is separate from registration.
"""
FILE_VERSION='1.0.25'
import base64,hashlib,json,os,re,tempfile,threading,time,uuid,wave,zlib
from pathlib import Path
from gradio_client import Client
from gradio_client.utils import TooManyRequestsError
import joat_managed_generation as m
PREFIX='JOAT_PRODUCTION_TASK_'
URLS={'titles':'https://dezz-9-10-j-o-a-t-titles-graphics-worker-bot.hf.space','reference':'https://dezz-9-10-joat-reference-lab.hf.space','narration':'https://dezz-9-10-joat-narration.hf.space'}
def fp(v):return m.digest(v)
def root(project):return m.safe_path(m.ROOT/'production-projects'/m.valid_project(project))
def read_mission(project,expected):
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('Invalid mission fingerprint.')
 value=m.read_json(root(project)/'missions'/(expected+'.json'));unsigned=dict(value);given=unsigned.pop('plan_fingerprint',None)
 if fp(unsigned)!=given or given!=expected or value['project_id']!=project:raise ValueError('Production mission integrity failed.')
 return value

def client(role,token,directory):
 headers={'Authorization':'Bearer '+token}
 from gradio.context import LocalContext
 incoming=LocalContext.request.get(None)
 delegation=incoming.headers.get('x-ip-token') if incoming is not None else None
 if isinstance(delegation,str) and 0<len(delegation)<=8192:headers['x-ip-token']=delegation
 def create():return Client(URLS[role],token=token,oauth_token=token,headers=headers,verbose=False,httpx_kwargs={'params':{'all_endpoints':'true','_joat_contract_version':FILE_VERSION}},download_files=str(directory))
 try:return create()
 except TooManyRequestsError:
  # Metadata only, before an API call exists.
  time.sleep(60);return create()

def report(v):print('JOAT_PRODUCTION_TASK '+m.stable(v),flush=True)
def local_file(value):
 if isinstance(value,(list,tuple)):value=value[0]
 if isinstance(value,dict):value=value.get('path') or value.get('audio')
 if isinstance(value,dict):value=value.get('path')
 if not isinstance(value,str) or not Path(value).is_file():raise ValueError('Native production service returned no file.')
 return Path(value)

def safe_error(exc):
 text=str(exc)
 for key,value in os.environ.items():
  if re.search(r'token|secret|password|_key',key,re.I) and len(value)>=8:text=text.replace(value,'[REDACTED]')
 text=re.sub(r'hf_[A-Za-z0-9]+','[REDACTED]',text)
 text=re.sub(r'(?i)Bearer\s+[^\s\"\']+','Bearer [REDACTED]',text)
 text=re.sub(r'https?://[^\s\"\']+','[endpoint]',text)
 return text[:1200]

def run(name,raw):
 identifier=name[len(PREFIX):];result=None;claimed=False;stage='validate_request';c=None
 try:
  if not re.fullmatch('[a-f0-9]{32}',identifier) or len(raw.encode())>131072:raise ValueError('Invalid bounded task envelope.')
  v=json.loads(raw)
  if set(v)!={'schema','file_version','request_id','project_id','operation','mission_fingerprint','payload'} or v['schema']!='joat.production_task.v1' or v['request_id']!=identifier or v['operation'] not in ('stage_mission','reference','voices','approve_location','frames','drafts','approve_frame','graphics','opening_prepare','speech_prepare','film_prepare','cancel_project','sources','first_plan','opening_grant','release_pre_gpu_reference','included_render'):raise ValueError('Unsupported production task.')
  stage='verify_studio_mount';m.mount_check('main');token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  stage='verify_owner_service'
  if not token or m.HfApi(token=token).whoami().get('name')!=m.OWNER:raise ValueError('Verified owner service credential required.')
  stage='validate_mission';project=m.valid_project(v['project_id']);directory=root(project)/'tasks'/identifier;receipt=directory/'receipt.json'
  if receipt.exists():report(m.read_json(receipt));return
  if (directory/'reservation.json').exists():report(dict(schema='joat.production_task_receipt.v1',file_version=FILE_VERSION,request_id=identifier,status='pending_or_unknown',automatic_retry=False));return
  if v['operation']=='stage_mission':
   data=base64.b64decode(v['payload']['compressed'],validate=True);decoder=zlib.decompressobj();data=decoder.decompress(data,512*1024+1)
   if len(data)>512*1024 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('Invalid bounded mission payload.')
   mission=json.loads(data);unsigned=dict(mission);given=unsigned.pop('plan_fingerprint',None)
   if mission.get('schema')!='joat.production_film_plan.v1' or mission['project_id']!=project or given!=v['mission_fingerprint'] or fp(unsigned)!=given:raise ValueError('Mission fingerprint mismatch.')
   if len(mission.get('shots',[]))>32 or not 1<=len(mission.get('shots',[])):raise ValueError('Production needs1–32 planned shots.')
   if mission.get('authorization_scope') is None or mission.get('owner_script_line_by_line_reviewed') is not False:raise ValueError('Preserve truthful owner authorization scope.')
  else:mission=read_mission(project,v['mission_fingerprint'])
  from joat_project_lifecycle import assert_active
  if v['operation']!='cancel_project':assert_active(project,m.ROOT)
  m.write_once(directory/'reservation.json',dict(request_id=identifier,operation=v['operation'],mission_fingerprint=v['mission_fingerprint'],automatic_retry=False));claimed=True
  if v['operation']=='stage_mission':
   m.write_once(root(project)/'missions'/(given+'.json'),mission)
   result=dict(status='mission_saved',gpu_called=False,shots=len(mission['shots']),target_duration_seconds=mission['target_duration_seconds'])
  elif v['operation']=='included_render':
   stage='exact_included_film_render'
   from joat_included_film_render import execute
   result=execute(mission,v['payload'],directory,token)
  elif v['operation']=='release_pre_gpu_reference':
   stage='verify_private_reference_storage'
   c=client('reference',token,Path(tempfile.mkdtemp(prefix='joat-reference-storage-check-')))
   check=c.submit(api_name='/check_project_storage').result(timeout=90)
   if not isinstance(check,dict) or check.get('status')!='private_mount_verified' or check.get('gpu_called') is not False or check.get('files_written') is not False:raise ValueError('Private reference storage check did not pass; retain reservation.')
   stage='reconcile_proven_pre_gpu_failure'
   from joat_reference_recovery import release
   result=release(project,v['payload'])
  elif v['operation']=='approve_location':
   from joat_project_environments import load,validate
   manifest=v['payload']['manifest'];core=dict(manifest);given=core.pop('manifest_fingerprint',None)
   if manifest.get('project_id')!=project or manifest.get('source_mission_fingerprint')!=v['mission_fingerprint'] or fp(core)!=given or manifest.get('environment_id')!='ENV-101':raise ValueError('Exact approved salon manifest required.')
   approval=manifest.get('owner_approval',{})
   if approval.get('approved') is not True or approval.get('owner')!=m.OWNER or approval.get('owner_statement')!='Approve salon and story':raise ValueError('Explicit owner location/story sign-off required.')
   if manifest.get('image_sha256')!='66c0236e5d0c9c81d73feabb07b80a9efb51ec534be190b39f01df17808a5f67':raise ValueError('Owner reviewed a different location image.')
   validate(manifest,'ENV-101',project)
   path=m.ROOT/'project-environments'/'ENV-101'/'manifest.json';m.write_once(path,manifest);load('ENV-101',project)
   m.write_once(root(project)/'approvals'/(v['mission_fingerprint']+'.json'),dict(schema='joat.production_story_approval.v1',file_version=FILE_VERSION,project_id=project,mission_fingerprint=v['mission_fingerprint'],owner_approval=approval,environment_manifest_fingerprint=given,production_qc_approved=False))
   result=dict(status='project_location_and_story_approval_saved',gpu_called=False,environment_id='ENV-101',manifest_fingerprint=given)
  elif v['operation']=='approve_frame':
   stage='save_exact_frame_approval'
   from joat_project_frame_approval import save
   result=save(project,v['mission_fingerprint'],v['payload'])
  elif v['operation']=='drafts':
   import joat_creative_workflow as workflow
   batches=v['payload'].get('batches')
   if not isinstance(batches,list) or not 1<=len(batches)<=2:raise ValueError('Use1–2 native creative batches.')
   approval_path=root(project)/'approvals'/(v['mission_fingerprint']+'.json')
   if mission.get('owner_supplied_source_prompt') is True:
    from joat_source_script_authority import verify_batches,ensure
    verify_batches(mission,batches)
    approval=m.read_json(approval_path) if approval_path.exists() else ensure(mission,batches)
   else:approval=m.read_json(approval_path)
   if approval['owner_approval']['approved'] is not True:raise ValueError('Owner story approval required.')
   selected=[s['shot_id'] for b in batches for s in b.get('plan',{}).get('shots',[])]
   expected=[s['shot_id'] for s in mission['shots'] if s['production_type']=='video']
   if sorted(selected)!=sorted(expected) or len(set(selected))!=len(selected):raise ValueError('Draft the exact story actor shots once.')
   plans=[workflow.validate_plan(project,b['brief'],b['plan']) for b in batches];files=[]
   for index,plan in enumerate(plans):
    stage='native_master_drafts_'+str(index+1);state=workflow.build_drafts(plan,recovery_approved=v['payload'].get('recovery_approved') is True)
    if state.get('creative_approved') is not False or state.get('gpu_called') is not False or state.get('plan')!=plan:raise ValueError('Master draft status differs.')
    target=directory/('drafts_'+str(index+1)+'.json');m.write_once(target,state)
    files.append(dict(batch=index+1,state_fingerprint=state['state_fingerprint'],plan_fingerprint=plan['plan_fingerprint'],shot_ids=[s['shot_id'] for s in plan['shots']],bucket_path=str(target.relative_to(m.ROOT.parent))))
    report(dict(schema='joat.production_drafts_progress.v1',file_version=FILE_VERSION,request_id=identifier,completed_batches=len(files),planned_batches=len(plans)))
   m.write_once(directory/'draft_manifest.json',dict(file_version=FILE_VERSION,project_id=project,mission_fingerprint=v['mission_fingerprint'],files=files,creative_approved=False,gpu_called=False))
   result=dict(status='native_director_drafts_awaiting_review',gpu_called=False,draft_count=len(selected),draft_manifest_bucket_path=str((directory/'draft_manifest.json').relative_to(m.ROOT.parent)),creative_approved=False)
  elif v['operation']=='opening_grant':
   stage='authorize_exact_opening_only'
   from joat_style001_opening_grant import authorize
   result=authorize(mission,v['payload'],directory)
  elif v['operation']=='first_plan':
   stage='prepare_exact_portrait_opening_plan'
   from joat_style001_opening import prepare
   result=prepare(mission,v['payload'],directory,token)
  elif v['operation']=='sources':
   stage='assemble_original_script_sources'
   from joat_original_source_assembly import prepare
   result=prepare(mission,v['payload'],directory)
  elif v['operation']=='graphics':
   from joat_authored_graphics import validate as validate_graphics
   approval=m.read_json(root(project)/'approvals'/(v['mission_fingerprint']+'.json'))
   if approval['owner_approval']['approved'] is not True:raise ValueError('Owner story approval required.')
   plans=v['payload'].get('plans');expected={s['shot_id'] for s in mission['shots'] if s['production_type']=='graphic'}
   if not isinstance(plans,list) or len(plans)!=len(expected) or {p.get('shot_id') for p in plans}!=expected:raise ValueError('Use the exact unique story graphics shot set.')
   for plan in plans:
    validate_graphics(plan)
    if plan['project_id']!=project or plan['mission_fingerprint']!=v['mission_fingerprint']:raise ValueError('Graphics plan belongs to a different approved mission.')
   stage='titles_api_connection';c=client('titles',token,Path(tempfile.mkdtemp(prefix='joat-production-graphics-')));files=[]
   for plan in plans:
    stage='graphics_'+plan['shot_id'];candidate,output,report_file=c.submit(m.stable(plan),True,api_name='/create_authored_graphics').result(timeout=300)
    output=local_file(output);report_file=local_file(report_file)
    core=dict(candidate);given=core.pop('candidate_fingerprint',None)
    if given!=fp(core) or candidate.get('schema')!='joat.authored_graphics_candidate.v1' or candidate.get('source_plan')!=plan or candidate.get('gpu_called') is not False or candidate.get('production_qc_approved') is not False or candidate.get('delivery_authorized') is not False or candidate.get('media_evidence',{}).get('sha256')!=m.file_hash(output) or m.read_json(report_file)!=candidate:raise ValueError('Native authored graphics evidence differs.')
    target=root(project)/'graphics'/plan['shot_id']/plan['plan_fingerprint'];m.store_media(output,target/'candidate.mp4');m.write_once(target/'candidate_review.json',candidate)
    files.append(dict(shot_id=plan['shot_id'],plan_fingerprint=plan['plan_fingerprint'],candidate_fingerprint=given,media_bucket_path=str((target/'candidate.mp4').relative_to(m.ROOT.parent)),review_bucket_path=str((target/'candidate_review.json').relative_to(m.ROOT.parent)),sha256=candidate['media_evidence']['sha256']))
    report(dict(schema='joat.production_graphics_progress.v1',file_version=FILE_VERSION,request_id=identifier,completed_shots=len(files),planned_shots=len(plans),gpu_called=False))
   m.write_once(directory/'graphics_manifest.json',dict(file_version=FILE_VERSION,project_id=project,mission_fingerprint=v['mission_fingerprint'],files=files,gpu_called=False,production_qc_approved=False))
   result=dict(status='authored_graphics_candidates_awaiting_qc',gpu_called=False,graphics_count=len(files),graphics_manifest_bucket_path=str((directory/'graphics_manifest.json').relative_to(m.ROOT.parent)),production_qc_approved=False)
  elif v['operation']=='cancel_project':
   if set(v['payload'])!={'owner_statement'}:raise ValueError('Exact cancellation request required.')
   from joat_project_lifecycle import cancel
   cancellation=cancel(project,m.OWNER,v['payload']['owner_statement'],m.ROOT)
   result=dict(status='project_cancelled',gpu_called=False,cancellation_fingerprint=cancellation['cancellation_fingerprint'],existing_assets_preserved=True)
  elif v['operation']=='film_prepare':
   stage='full_film_cpu_preparation'
   from joat_film_completion import prepare
   result=prepare(v['payload'],mission,directory,token)
  elif v['operation']=='speech_prepare':
   stage='character_speech_cpu_preparation'
   from joat_character_speech import prepare
   result=prepare(v['payload'],mission,directory,token)
  elif v['operation']=='opening_prepare':
   stage='opening_cpu_preparation'
   if mission['project_id']=='PROJECT-OTU-STORY-60S-001':
    from joat_story_opening import prepare
   else:
    from joat_salon_opening import prepare
   result=prepare(v['payload'],mission,directory,token)
  elif v['operation']=='frames':
   if mission.get('reference_preparation',{}).get('mode')=='existing_canonical_sources':
    from joat_canonical_project_references import authorize
    requests=authorize(mission,v['payload'])
   else:
    from joat_project_environments import load
    load('ENV-101',project);approval=m.read_json(root(project)/'approvals'/(v['mission_fingerprint']+'.json'))
    if approval['owner_approval']['approved'] is not True:raise ValueError('Owner story approval required.')
    requests=v['payload'].get('requests')
   if not isinstance(requests,list) or not 1<=len(requests)<=5 or len({q.get('asset_key') for q in requests})!=len(requests):raise ValueError('Use1–5 distinct opening frame requests.')
   if any(q.get('project_id')!=project or q.get('kind')!='shot_start_frame' for q in requests):raise ValueError('Only this project opening frames are allowed.')
   stage='reference_api_connection';c=client('reference',token,Path(tempfile.mkdtemp(prefix='joat-production-frames-')));files=[]
   for payload in requests:
    if payload.get('model_image_order') is not None:
     stage='reference_source_preflight';proof=c.submit(m.stable(payload),api_name='/check_project_reference_inputs').result(timeout=90)
     if proof.get('status')!='verified' or proof.get('gpu_called') is not False or proof.get('bucket_files_written') is not False or proof.get('plan_fingerprint')!=fp(payload) or proof.get('model_image_order')!=payload['model_image_order'] or len(proof.get('model_image_sources',[]))!=len(payload['sources']) or proof['model_image_sources'][0].get('role')!='environment':raise ValueError('Native reference source preflight failed; no GPU request sent.')
     m.write_once(directory/'reference_input_preflight.json',proof)
    if mission.get('reference_preparation',{}).get('mode')=='existing_canonical_sources':
     from joat_canonical_project_references import authorize
     authorize(mission,v['payload'])
     if 'additional_reference_scope' in v['payload']:
      from joat_reference_supplement import reserve
      reserve(payload,v['payload'])
     elif v['payload']['spending_approval'].get('schema')=='joat.included_quota_confirmation.v1':
      from joat_gpu_quota_panel import reserve
      reserve(payload,v['payload']['spending_approval'])
    stage='frame_'+payload['asset_key'];review,image,report_file=c.submit(m.stable(payload),api_name='/project_reference_candidate').result(timeout=1200)
    image=local_file(image);report_file=local_file(report_file)
    if review.get('project_id')!=project or review.get('request_id')!=payload['request_id'] or review.get('plan_fingerprint')!=fp(payload) or review.get('source_request')!=payload or review.get('owner_visual_approved') is not False or review.get('canonical_registration') is not False or m.file_hash(image)!=review.get('sha256') or json.loads(report_file.read_text())!=review:raise ValueError('Opening frame result integrity failed.')
    dest=directory/'frames'/payload['asset_key'];m.store_media(image,dest/'candidate.png');m.write_once(dest/'candidate_review.json',review)
    if 'additional_reference_scope' in v['payload']:
     from joat_reference_supplement import settle
     settle(payload,review)
    files.append(dict(asset_key=payload['asset_key'],sha256=review['sha256'],image_bucket_path=str((dest/'candidate.png').relative_to(m.ROOT.parent)),review_bucket_path=str((dest/'candidate_review.json').relative_to(m.ROOT.parent)),owner_visual_approved=False))
    report(dict(schema='joat.production_frames_progress.v1',file_version=FILE_VERSION,request_id=identifier,completed=len(files),planned=len(requests),asset_key=payload['asset_key']))
   m.write_once(directory/'frame_manifest.json',dict(file_version=FILE_VERSION,project_id=project,mission_fingerprint=v['mission_fingerprint'],files=files,production_qc_approved=False))
   result=dict(status='opening_frames_awaiting_review',gpu_called=True,frame_count=len(files),frame_manifest_bucket_path=str((directory/'frame_manifest.json').relative_to(m.ROOT.parent)),owner_visual_approved=False)
  elif v['operation']=='reference':
   payload=v['payload']
   if payload.get('project_id')!=project or payload.get('kind')!='environment' or mission['locations']['SALON']['canonical_id'] is not None:raise ValueError('Only missing project salon environment creation is enabled.')
   stage='reference_api_connection';c=client('reference',token,Path(tempfile.mkdtemp(prefix='joat-production-reference-')))
   stage='reference_generation';review,image,report_file=c.submit(m.stable(payload),api_name='/project_reference_candidate').result(timeout=1200)
   image=local_file(image);report_file=local_file(report_file)
   if (review.get('project_id')!=project or review.get('request_id')!=payload['request_id'] or review.get('plan_fingerprint')!=fp(payload) or review.get('owner_visual_approved') is not False or review.get('canonical_registration') is not False or m.file_hash(image)!=review.get('sha256') or json.loads(report_file.read_text())!=review):raise ValueError('Project reference result integrity failed.')
   m.store_media(image,directory/'candidate.png');m.write_once(directory/'candidate_review.json',review)
   result=dict(status='reference_candidate_ready',gpu_called=True,candidate_sha256=review['sha256'],candidate_bucket_path=str((directory/'candidate.png').relative_to(m.ROOT.parent)),review_bucket_path=str((directory/'candidate_review.json').relative_to(m.ROOT.parent)),owner_visual_approved=False)
  else:
   stage='narration_api_connection';c=client('narration',token,Path(tempfile.mkdtemp(prefix='joat-production-voice-')));files=[]
   # This command generates selected approved-story lines once, sequentially.
   ids=v['payload'].get('shot_ids');selected=[s for s in mission['shots'] if s['shot_id'] in ids] if isinstance(ids,list) else []
   if not selected or len(selected)!=len(ids) or len(set(ids))!=len(ids):raise ValueError('Use exact unique mission shot IDs.')
   for shot in selected:
    stage='narration_'+shot['shot_id'];speaker=shot['speaker'];cid={'NARRATOR':'NARRATOR','FOUNDER':'CHAR-001','KIANA':'CHAR-002'}.get(speaker)
    if not cid:raise ValueError('Unknown approved-story voice role.')
    audio=local_file(c.submit(shot['voice_text'],cid,api_name='/generate').result(timeout=300));target=directory/'voices'/(shot['shot_id']+'.wav');m.store_media(audio,target)
    with wave.open(str(target),'rb') as w:duration=w.getnframes()/w.getframerate();rate=w.getframerate()
    if not duration>0 or rate!=24000:raise ValueError('Native speech audio is invalid.')
    entry=dict(shot_id=shot['shot_id'],speaker=speaker,character_id=cid,text_sha256=hashlib.sha256(shot['voice_text'].encode()).hexdigest(),sha256=m.file_hash(target),duration_seconds=duration,sample_rate=rate,bucket_path=str(target.relative_to(m.ROOT.parent)),qc_approved=False)
    files.append(entry);m.write_once(directory/'voices'/(shot['shot_id']+'.json'),entry)
    report(dict(schema='joat.production_voice_progress.v1',file_version=FILE_VERSION,request_id=identifier,completed_shots=len(files),planned_shots=len(selected),last_shot=shot['shot_id']))
   m.write_once(directory/'voice_manifest.json',dict(file_version=FILE_VERSION,mission_fingerprint=v['mission_fingerprint'],files=files,production_qc_approved=False))
   result=dict(status='voice_candidates_ready',gpu_called=True,voice_count=len(files),speech_duration_seconds=sum(x['duration_seconds'] for x in files),voice_manifest_bucket_path=str((directory/'voice_manifest.json').relative_to(m.ROOT.parent)),production_qc_approved=False)
  receipt_value=dict(schema='joat.production_task_receipt.v1',file_version=FILE_VERSION,request_id=identifier,operation=v['operation'],project_id=project,mission_fingerprint=v['mission_fingerprint'],automatic_retry=False,**result)
  m.write_once(receipt,receipt_value);report(receipt_value)
 except Exception as exc:
  result=dict(schema='joat.production_task_receipt.v1',file_version=FILE_VERSION,request_id=identifier,status='failed_or_unknown' if claimed else 'rejected',stage=stage,error_type=type(exc).__name__,safe_error_message=safe_error(exc),automatic_retry=False)
  if claimed and not receipt.exists():m.write_once(receipt,result)
  report(result)
 finally:
  if c:c.close()

def start_production_tasks():
 if os.environ.get('SPACE_ID')!=m.SPACES['main']:return
 for name in sorted(os.environ):
  if name.startswith(PREFIX):threading.Thread(target=run,args=(name,os.environ[name]),daemon=True).start()
