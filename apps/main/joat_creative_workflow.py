"""Guided, owner-reviewed Main→Executive creative Master workflow. File version 1.0.8.
Only existing CPU packet endpoints. Never invokes GPU or approves production QC.
"""
FILE_VERSION='1.0.8'
# Unchanged creative-plan semantics retain saved draft/checkpoint hashes.
PLAN_VERSION='1.0.5'
import copy,json,math,re,tempfile,threading
from datetime import datetime,timezone
from pathlib import Path
from typing import Optional
import gradio as gr
import joat_executive_handoff as handoff
import joat_managed_generation as managed
from joat_production_ui import require_owner,login

ROOT=Path('/studio/joat-studio')
LOCK=threading.Lock()
SIZES=['extreme_wide','wide','full','medium_wide','medium','medium_close_up','close_up','extreme_close_up','insert']
ANGLES=['eye_level','high_angle','low_angle','overhead','birds_eye','worms_eye','dutch_angle','over_the_shoulder','point_of_view']
MOVEMENTS=['static','pan_left','pan_right','tilt_up','tilt_down','push_in','pull_out','dolly_in','dolly_out','truck_left','truck_right','pedestal_up','pedestal_down','orbit_left','orbit_right','crane_up','crane_down','handheld','steadicam','tracking']

def object_json(raw):
 if isinstance(raw,str):
  if len(raw.encode())>512*1024:raise ValueError('Shot plan is too large.')
  raw=json.loads(raw)
 if not isinstance(raw,dict):raise ValueError('Use one shot-plan JSON object.')
 return json.loads(handoff.stable(raw))

def validate_plan(project,brief,raw):
 managed.valid_project(project)
 if not isinstance(brief,str) or not brief.strip() or len(brief)>16000:raise ValueError('Enter a production idea or brief (up to 16000 characters).')
 plan=object_json(raw)
 if set(plan)!={'shots'} or not isinstance(plan['shots'],list) or not 1<=len(plan['shots'])<=8:raise ValueError('Plan requires 1–8 shots and only a shots field.')
 seen=set()
 for shot in plan['shots']:
  required={'scene_id','shot_id','character_id','environment_id','purpose','duration_seconds','camera','performance','dialogue','narration','audio','caption','style','wardrobe'}
  if not isinstance(shot,dict) or set(shot)!=required:raise ValueError('Each shot must use all displayed shot fields exactly.')
  for key in ('scene_id','shot_id'):managed.valid_project(shot[key])
  if shot['shot_id'] in seen:raise ValueError('Shot IDs must be unique in this project plan.')
  seen.add(shot['shot_id'])
  if not re.fullmatch(r'CHAR-00[1-7]',shot['character_id']) or not re.fullmatch(r'ENV-\d{3}',shot['environment_id']):raise ValueError('Use existing canonical character/environment IDs.')
  duration=shot['duration_seconds']
  if type(duration) not in (int,float) or not math.isfinite(duration) or not 1<=duration<=10:raise ValueError('Each shot must be 1–10 seconds; renderer compatibility is checked later.')
  for key in ('purpose','dialogue','narration','audio','caption','style','wardrobe'):
   if not isinstance(shot[key],str) or len(shot[key])>4000:raise ValueError('Shot descriptions must be text.')
  camera=shot['camera']
  if not isinstance(camera,dict) or set(camera)!={'size','angle','movement'} or camera['size'] not in SIZES or camera['angle'] not in ANGLES or camera['movement'] not in MOVEMENTS:raise ValueError('Use the displayed supported camera values.')
  perf=shot['performance']
  if not isinstance(perf,dict) or set(perf)!={'emotion','expression','body_language','action','gaze','blocking','interaction','timing'}:raise ValueError('Performance must include all eight displayed fields.')
  for key in ('emotion','expression','body_language','action'):
   if not isinstance(perf[key],str) or not perf[key].strip():raise ValueError('Describe emotion, expression, body language, and action explicitly.')
  for key in ('gaze','blocking','interaction','timing'):
   if not isinstance(perf[key],dict):raise ValueError('Gaze, blocking, interaction and timing must be objects.')
 # Existing handoff recursively rejects credentials/route overrides.
 handoff.prepare(project,'character',{'plan':plan})
 return handoff.seal({'schema':'joat.creative_workflow_plan.v1','file_version':PLAN_VERSION,'project_id':project,'brief':brief.strip(),'shots':plan['shots'],'gpu_called':False,'automatic_retry':False},'plan_fingerprint')

def validate_state(state):
 handoff.verify(state,'state_fingerprint')
 expected=validate_plan(state['plan']['project_id'],state['plan']['brief'],{'shots':state['plan']['shots']})
 if expected!=state['plan']:raise ValueError('Creative plan changed; prepare and review a fresh draft.')
 for item in state['drafts']:
  if managed.digest(item['director'])!=item['director_sha256']:raise ValueError('Director draft changed after preparation.')
 return state

def call(project,role,args,recovery_approved=False):
 plan=handoff.prepare(project,role,args)
 directory=ROOT/'missions'/project/'executive-handoffs'/plan['plan_fingerprint']
 if (directory/'reservation.json').exists():
  receipt=handoff.read_checkpoint(plan,root=ROOT)
  recovered=directory/'connection-recovery'
  if (recovered/'reservation.json').exists():
   receipt=handoff.read_checkpoint(plan,root=ROOT,recovery=True)
  elif receipt.get('status')!='department_api_returned' and recovery_approved and handoff.recoverable_unsubmitted_environment(receipt):
   receipt=handoff.execute(plan,True,root=ROOT,recovery_parent=receipt)
 else:receipt=handoff.execute(plan,True,root=ROOT)
 if receipt.get('status')!='department_api_returned':raise ValueError('CPU handoff stopped at '+role+'. Review Executive Department Handoff receipts; no automatic retry.')
 return receipt['department_artifact']

def packet(value,schema):
 # Native Supervisor returns its visible packet plus an identical retained-state packet.
 # Accept only this proved duplicate contract; never discard differing outputs.
 if isinstance(value,(list,tuple)) and len(value)==2 and isinstance(value[0],dict) and value[0]==value[1] and value[0].get('schema')==schema:value=value[0]
 if isinstance(value,str):value=json.loads(value)
 if not isinstance(value,dict) or value.get('schema')!=schema:raise ValueError('Department returned an invalid '+schema+' packet.')
 return value

def record(path,value):
 managed.safe_path(path)
 if path.exists():
  previous=json.loads(path.read_text())
  if previous!=value:raise ValueError('Stored creative checkpoint differs; no overwrite permitted.')
 else:managed.write_once(path,value)
 return json.loads(path.read_text())

def director_args(brief,shot,character=None):
 scene,ident=shot['scene_id'],shot['shot_id'];cam=shot['camera'];perf=shot['performance']
 args = dict(creative_brief=brief,character_id=shot['character_id'],production_intent='animation',scene_plan=handoff.stable([{'scene_id':scene,'shot_id':ident}]),environment_requirements=shot['environment_id'],camera_framing=handoff.stable([{'shot_id':ident,'framing':cam['size'],'angle':cam['angle'],'movement':cam['movement']}]),performance_action=handoff.stable([dict(perf,shot_id=ident)]),dialogue_narration=handoff.stable([{'shot_id':ident,'dialogue':shot['dialogue'],'narration':shot['narration']}]),audio_music_sfx=handoff.stable([{'shot_id':ident,'instructions':shot['audio']}]),caption_on_screen_text=handoff.stable([{'shot_id':ident,'text':shot['caption']}]),duration='00:'+format(shot['duration_seconds'],'.6f').rstrip('0').rstrip('.'),continuity_constraints='Preserve canonical identity, environment and reviewed wardrobe. Style: '+shot['style']+'. Wardrobe: '+shot['wardrobe'],generation_instructions='Follow owner-reviewed shot decisions exactly. No extra people, captions or effects.',qc_gates='["identity_anchor_match","source_hash_integrity","continuity_check","negative_rule_check"]',downstream_handoff='{}')
 if character is not None:args['character_packet_json']=handoff.stable(character)
 return args

def build_drafts(plan,recovery_approved=False):
 expected=validate_plan(plan['project_id'],plan['brief'],{'shots':plan['shots']})
 if expected!=plan:raise ValueError('Prepared idea plan changed.')
 handoff.require_studio_mount()
 path=ROOT/'creative-projects'/plan['project_id']/plan['plan_fingerprint']/'drafts.json'
 if path.exists():return validate_state(json.loads(path.read_text()))
 drafts=[]
 for shot in plan['shots']:
  project=plan['project_id']
  char=packet(call(project,'character',{'cid':shot['character_id'],'task':'scene'}),'joat.character_packet.v1')
  if char.get('character_id')!=shot['character_id'] or char.get('identity_locked') is not True:raise ValueError('Character ID/lock mismatch.')
  env=packet(call(project,'environment',dict(environment_id=shot['environment_id'],task='scene',time_of_day='director_defined',lighting='director_defined',weather='director_defined',scene_id=shot['scene_id'],shot_id=shot['shot_id']),recovery_approved=recovery_approved),'joat.environment_packet.v1')
  if env.get('environment_id')!=shot['environment_id']:raise ValueError('Environment ID mismatch.')
  result=call(project,'director',director_args(plan['brief'],shot,char))
  if not isinstance(result,(list,tuple)) or len(result)!=3 or not str(result[0]).startswith('OK:'):raise ValueError('Director draft could not be generated.')
  original=packet(result[1],'joat.director_packet.v1')
  if original.get('character_refs',[{}])[0].get('character_id')!=char['character_id']:raise ValueError('Director uses a different character.')
  if original.get('per_shot',[{}])[0].get('character_constraints',{}).get('source_asset_hashes')!=char.get('source_asset_hashes'):
   raise ValueError('Director canonical asset hashes differ from Character Master.')
  draft=copy.deepcopy(original)
  # Explicit project assignment happens only in the visible unapproved draft.
  # Original Director API artifact remains unchanged in the signed receipt.
  draft['project_id']=project
  draft['project_assignment']={'original_project_id':original['project_id'],'original_director_sha256':managed.digest(original),'assigned_project_id':project,'owner_review_required':True}
  drafts.append({'shot':shot,'character':char,'environment':env,'director':draft,'director_sha256':managed.digest(draft)})
 state=handoff.seal({'schema':'joat.creative_workflow_drafts.v1','file_version':PLAN_VERSION,'plan':plan,'drafts':drafts,'creative_approved':False,'gpu_called':False},'state_fingerprint')
 return record(path,state)

def assemble(state,approved,reviewer,aspect_ratio='16:9',source_script_review=None):
 if aspect_ratio not in ('16:9','9:16'):raise ValueError('Use supported landscape16:9 or portrait9:16 assembly.')
 if approved is not True or reviewer!='Dezz-9-10':raise ValueError('Owner must explicitly approve the exact Director drafts and shot decisions.')
 if source_script_review is not None:
  fields={'schema','file_version','owner','reviewer','project_id','plan_fingerprint','source_prompt_sha256','scope','review_statement'}
  if not isinstance(source_script_review,dict) or set(source_script_review)!=fields or source_script_review['schema']!='joat.original_script_packet_review.v1' or source_script_review['file_version']!='1.0.0' or source_script_review['owner']!=reviewer or source_script_review['reviewer']!='Codex' or source_script_review['project_id']!=state['plan']['project_id'] or source_script_review['plan_fingerprint']!=state['plan']['plan_fingerprint'] or source_script_review['scope']!='original_owner_script_machine_verified_packet_mapping' or not re.fullmatch('[a-f0-9]{64}',source_script_review['source_prompt_sha256']):raise ValueError('Exact original-source packet review provenance required.')
 state=validate_state(state);handoff.require_studio_mount();plan=state['plan'];project=plan['project_id']
 base=ROOT/'creative-projects'/project/plan['plan_fingerprint']
 # Portrait has a separate immutable approval/result checkpoint. Default
 # landscape paths and result versions remain byte-compatible.
 if aspect_ratio=='9:16':base=base/'portrait-9x16'
 if source_script_review is not None:base=base/state['state_fingerprint']
 approval_path=base/'approval.json'
 if approval_path.exists():approval=json.loads(approval_path.read_text())
 else:
  value={'reviewer':reviewer,'draft_state_fingerprint':state['state_fingerprint'],'approved_at':datetime.now(timezone.utc).isoformat()}
  if source_script_review is not None:value['source_script_review']=source_script_review
  approval=record(approval_path,value)
 if approval.get('reviewer')!=reviewer or approval.get('draft_state_fingerprint')!=state['state_fingerprint']:raise ValueError('Creative approval does not match these drafts.')
 sources=[];previous_camera=None;previous_perf=None;previous_shot=None
 for item in state['drafts']:
  shot=item['shot'];char=item['character'];env=item['environment'];director=copy.deepcopy(item['director']);cam=shot['camera']
  linked=previous_shot is not None and all(shot[k]==previous_shot[k] for k in ('scene_id','character_id','environment_id','wardrobe','style'))
  director['approval']={'creative_intent_locked':True,'approved_by':reviewer,'approved_at':approval['approved_at'],'reviewed_draft_sha256':item['director_sha256'],'character_packet_sha256':managed.digest(char)}
  if source_script_review is not None:director['approval']['source_script_review']=source_script_review
  director=handoff.seal(director,'packet_fingerprint')
  camera=packet(call(project,'shot_camera',dict(project_id=project,scene_id=shot['scene_id'],shot_id=shot['shot_id'],shot_purpose=shot['purpose'],shot_size=cam['size'],camera_angle=cam['angle'],camera_movement=cam['movement'],composition='director_defined',focus_mode='director_defined',duration_seconds=shot['duration_seconds'],subject=shot['character_id'],action=shot['performance']['action'],lens_guidance='Director defined',depth_guidance='Director defined',transition_in='cut',transition_out='cut',character_json=handoff.stable(char),environment_json=handoff.stable(env),director_json=handoff.stable(director),previous_shot_json=handoff.stable(previous_camera) if linked else '')),'joat.shot_camera_packet.v1')
  performance_spec=shot['performance']
  if source_script_review is not None:
   from joat_original_source_assembly import typed_performance
   performance_spec=typed_performance(performance_spec)
  perf=packet(call(project,'performance_action',dict(character_json=handoff.stable(char),environment_json=handoff.stable(env),director_json=handoff.stable(director),shot_json=handoff.stable(camera),performance_json=handoff.stable(performance_spec),previous_json=handoff.stable(previous_perf) if linked else '')),'joat.performance_action_packet.v1')
  source=packet(call(project,'generation_supervisor',dict(character_raw=handoff.stable(char),environment_raw=handoff.stable(env),director_raw=handoff.stable(director),shot_camera_raw=handoff.stable(camera),performance_raw=handoff.stable(perf),job_type='video',requested_engine='ltx',project_id=project,scene_id=shot['scene_id'],shot_id=shot['shot_id'],duration_seconds=shot['duration_seconds'],aspect_ratio=aspect_ratio,generation_notes='Owner-reviewed creative plan '+plan['plan_fingerprint'])),'joat.generation_supervisor_packet.v1')
  managed.verify(source,'packet_fingerprint');managed.verify(source['generation_job'],'job_fingerprint')
  if source['generation_job'].get('generation_specification',{}).get('aspect_ratio')!=aspect_ratio:raise ValueError('Supervisor returned a different delivery aspect ratio.')
  if source.get('production_ready') is not True or source['generation_job']['project_context']!={'project_id':project,'scene_id':shot['scene_id'],'shot_id':shot['shot_id']}:raise ValueError('Supervisor source project/shot/readiness mismatch.')
  for role,value in source['generation_job']['immutable_upstream_snapshot'].items():
   expected={'character':char,'environment':env,'director':director,'shot_camera':camera,'performance_action':perf}[role]
   if value!=expected:raise ValueError('Supervisor changed an approved '+role+' input.')
  path=ROOT/'approved-jobs'/project/source['generation_job']['job_fingerprint']/(source['packet_fingerprint']+'.json')
  record(path,source);sources.append(source)
  previous_camera,previous_perf,previous_shot=camera,perf,shot
 result=handoff.seal({'schema':'joat.creative_workflow_result.v1','file_version':PLAN_VERSION if aspect_ratio=='16:9' else FILE_VERSION,'project_id':project,'plan_fingerprint':plan['plan_fingerprint'],'shots_prepared':len(sources),'source_packets':sources,'status':'approved_sources_saved_awaiting_renderer_preflight','gpu_called':False,'production_qc_approved':False,'automatic_retry':False},'result_fingerprint')
 return record(base/'result.json',result)

EXAMPLE={'shots':[{'scene_id':'SCENE-001','shot_id':'SHOT-001','character_id':'CHAR-001','environment_id':'ENV-001','purpose':'Opening shot','duration_seconds':6,'camera':{'size':'medium','angle':'eye_level','movement':'static'},'performance':{'emotion':'calm','expression':'neutral','body_language':'relaxed seated posture','action':'Remain seated and blink naturally','gaze':{'type':'camera','target':'camera'},'blocking':{'start_position':'seated behind desk','end_position':'seated behind desk'},'interaction':{'type':'none','target':'','action':''},'timing':{'pacing':'natural','hold_seconds':0}},'dialogue':'','narration':'','audio':'No dialogue or music requested','caption':'','style':'Stylized 3D matching canonical references','wardrobe':'Approved black outfit'}]}

def add_creative_workflow_ui(inference_factory=None,model=None):
 def propose(project,brief,profile:Optional[gr.OAuthProfile],request:gr.Request):
  require_owner(profile,request);managed.valid_project(project)
  if not brief.strip():raise gr.Error('Enter your idea first.')
  if inference_factory is None:raise gr.Error('Configured text model unavailable; edit the example shot plan directly.')
  prompt='Return only JSON matching this example schema, with 1–8 short shots. Propose an original production plan from the user idea. Preserve supplied character IDs CHAR-001..007; use ENV-001 unless the user supplies another canonical environment. These are proposals requiring owner review. Never claim generated audio, missing assets, or approved creative decisions. Camera values: '+handoff.stable({'sizes':SIZES,'angles':ANGLES,'movements':MOVEMENTS})+' Example: '+handoff.stable(EXAMPLE)
  try:
   response=inference_factory().chat_completion(model=model,messages=[{'role':'system','content':prompt},{'role':'user','content':brief[:16000]}],max_tokens=3500,temperature=0.3)
   raw=response.choices[0].message.content.strip()
   if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
   plan=validate_plan(project,brief,raw)
   return json.dumps({'shots':plan['shots']},indent=2),None,None,False,False
  except Exception:raise gr.Error('Text proposal failed or needs correction. No Master or GPU request was made; edit the shot plan directly.') from None
 def load_otu(profile:Optional[gr.OAuthProfile],request:gr.Request):
  require_owner(profile,request)
  from joat_commercial_proposal import proposal
  project,brief,raw,story=proposal()
  return project,brief,raw,story,None,None,False,False
 def draft(project,brief,raw,confirmed,profile:Optional[gr.OAuthProfile],request:gr.Request):
  require_owner(profile,request)
  if confirmed is not True:raise gr.Error('Review the shot plan and approve CPU Master preparation first.')
  try:state=build_drafts(validate_plan(project,brief,raw))
  except Exception as exc:raise gr.Error(str(exc)) from None
  return state,state,False
 def resume(project,brief,raw,confirmed,profile:Optional[gr.OAuthProfile],request:gr.Request):
  require_owner(profile,request)
  if confirmed is not True:raise gr.Error('Review the unchanged shot plan and approve CPU preparation before recovery.')
  try:state=build_drafts(validate_plan(project,brief,raw),recovery_approved=True)
  except Exception as exc:raise gr.Error(str(exc)) from None
  return state,state,False
 def saved_drafts(project,brief,raw,profile:Optional[gr.OAuthProfile],request:gr.Request):
  require_owner(profile,request)
  try:
   plan=validate_plan(project,brief,raw)
   path=ROOT/'creative-projects'/plan['project_id']/plan['plan_fingerprint']/'drafts.json'
   state=validate_state(managed.read_json(managed.safe_path(path)))
  except Exception:raise gr.Error('No saved draft matches this exact project and reviewed shot plan.') from None
  return state,state,False
 def finish(state,approved,profile:Optional[gr.OAuthProfile],request:gr.Request):
  require_owner(profile,request)
  try:result=assemble(state,approved,profile.username)
  except Exception as exc:raise gr.Error(str(exc)) from None
  folder=Path(tempfile.mkdtemp(prefix='joat-creative-sources-'));files=[]
  for source in result['source_packets']:
   path=folder/(source['generation_job']['project_context']['shot_id']+'_source_supervisor_packet.json');path.write_text(json.dumps(source,indent=2));files.append(str(path))
  return result,files
 with gr.Tab('Idea to Production'):
  gr.Markdown('Propose and review your story, then prepare approved shot packets through Executive and the existing Masters. CPU packet preparation does not generate media. Missing references, voice, music and renderer compatibility are checked before production.')
  login()
  project=gr.Textbox(value='PROJECT-002',label='New production project ID')
  brief=gr.Textbox(lines=5,label='Production idea or brief',placeholder='Describe the product, audience, emotional hook, style, and desired CTA.')
  raw=gr.Code(value=json.dumps(EXAMPLE,indent=2),language='json',label='Proposed shot plan — edit before approval')
  state=gr.State(None);shown=gr.JSON(label='Director drafts — review before creative approval');ready=gr.Checkbox(label='I reviewed this shot plan and approve CPU Master preparation',value=False)
  approval=gr.Checkbox(label='I approve these exact Director drafts and all shot decisions',value=False)
  storyboard=gr.Markdown('')
  gr.Button('Load prepared commercial proposal (no model call)').click(load_otu,outputs=[project,brief,raw,storyboard,state,shown,ready,approval],api_visibility='private')
  gr.Button('Propose shot plan from idea (configured text model)').click(propose,[project,brief],[raw,state,shown,ready,approval],api_visibility='private')
  gr.Button('Prepare Director drafts through Executive (no GPU)').click(draft,[project,brief,raw,ready],[shown,state,approval],api_visibility='private')
  gr.Button('Resume verified unsubmitted Environment handoff (no GPU)').click(resume,[project,brief,raw,ready],[shown,state,approval],api_visibility='private')
  gr.Button('Load saved Director drafts (no department call)').click(saved_drafts,[project,brief,raw],[shown,state,approval],api_visibility='private')
  result=gr.JSON(label='Approved source preparation result — no GPU');files=gr.File(file_count='multiple',label='Prepared source packets (also saved in studio storage)')
  gr.Button('Approve drafts and prepare production sources (no GPU)').click(finish,[state,approval],[result,files],api_visibility='private')
  gr.Markdown('When source preparation succeeds: open Managed Generation, enter this project ID, refresh saved jobs, and load a shot. Check its renderer plan and references before approving any GPU run. Each shot needs independent production QC before post-production and final delivery.')
  for field in (project,brief,raw):field.change(lambda:(None,None,False,False),outputs=[state,shown,ready,approval],api_visibility='private')


def inspect_environment_checkpoint():
 """Read stored failed CPU receipt only; never issues a department request."""
 try:
  from joat_commercial_proposal import proposal
  project,brief,raw,story=proposal();shot=json.loads(raw)['shots'][0]
  args=dict(environment_id=shot['environment_id'],task='scene',time_of_day='director_defined',lighting='director_defined',weather='director_defined',scene_id=shot['scene_id'],shot_id=shot['shot_id'])
  prepared=handoff.prepare(project,'environment',args)
  receipt=handoff.read_checkpoint(prepared,root=ROOT)
  executive=receipt.get('executive_response',{})
  message=str(executive.get('error',''))
  message=re.sub(r'(?i)(?:Bearer\s+|hf_)[A-Za-z0-9._-]+','[REDACTED]',message)
  message=re.sub(r'https?://[^\s]+','[endpoint]',message)
  diagnostic={'schema':'joat.creative_checkpoint_diagnostic.v1','file_version':FILE_VERSION,'project_id':project,'role':'environment','plan_fingerprint':prepared['plan_fingerprint'],'receipt_fingerprint':receipt['receipt_fingerprint'],'status':receipt.get('status'),'executive_status':executive.get('status'),'error_type':executive.get('error_type',receipt.get('error_type')),'safe_error_message':message[:1200],'downstream_execution_performed':executive.get('downstream_execution_performed'),'request_made':receipt.get('request_made'),'gpu_called':False,'department_request_made_by_diagnostic':False}
  print('JOAT_CREATIVE_CHECKPOINT_DIAGNOSTIC '+json.dumps(diagnostic),flush=True)
 except Exception as exc:
  print('JOAT_CREATIVE_CHECKPOINT_DIAGNOSTIC '+json.dumps({'schema':'joat.creative_checkpoint_diagnostic.v1','file_version':FILE_VERSION,'status':'diagnostic_unavailable','error_type':type(exc).__name__,'gpu_called':False,'department_request_made_by_diagnostic':False}),flush=True)
