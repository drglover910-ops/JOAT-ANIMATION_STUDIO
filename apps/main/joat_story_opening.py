"""Owner-approved first-shot preparation for One More Message. File version 1.0.4.
CPU only. Original source evidence preserved; no GPU grant or QC approval.
"""
FILE_VERSION='1.0.4'
import joat_managed_generation as m
PROJECT='PROJECT-OTU-STORY-60S-001'
MISSION='8baeea41dfca2cd30d58a7ef7038a1bd970f0df63e4389fa1c3fcf98a3650101'
IMAGE='27f173091ae09e3355dea31782848bc47c63488b46f0b9876edc8032c607b714'
def preserve(path,value):
 if path.exists():
  if m.read_json(path)!=value:raise ValueError('Existing story/reuse approval differs; no overwrite.')
 else:m.write_once(path,value)
def prepare(payload,mission,directory,token):
 if mission.get('project_id')!=PROJECT or mission.get('plan_fingerprint')!=MISSION or payload!={'owner_statement':'Approve story and frame reuse'}:raise ValueError('Exact approved story/frame reuse required.')
 from joat_project_lifecycle import assert_active
 assert_active(PROJECT,m.ROOT)
 from joat_job_frame_binding import create_binding,save_binding
 from joat_approved_reference import load_approved_frame
 prior=m.read_json(m.ROOT/'job-reference-bindings'/'PROJECT-OTU-SALON-001'/'6271e355c92bf46909ec3cb24a9419a3a713a5a65ba9aa4e27e7eff5615a6126'/'binding.json')
 manifest=prior['approved_frame_manifest'];load_approved_frame(manifest)
 # A new project assignment references unchanged, previously reviewed geometry.
 from joat_project_environments import load as load_environment
 original_environment,image=load_environment('ENV-101')
 reuse=dict(schema='joat.project_environment_reuse.v1',file_version='1.0.0',project_id=PROJECT,environment_id='ENV-102',source_environment_id='ENV-101',source_manifest_fingerprint=original_environment['manifest_fingerprint'],owner_reuse_approval=dict(owner=m.OWNER,approved=True,scope='story_and_existing_frame_reuse',owner_statement=payload['owner_statement']),canonical_registration=False)
 from joat_project_environments import digest
 reuse['manifest_fingerprint']=digest(reuse)
 preserve(m.ROOT/'project-environments'/'ENV-102'/'manifest.json',reuse)
 load_environment('ENV-102',PROJECT)
 if manifest['descriptor']['image_sha256']!=IMAGE:raise ValueError('Wrong original approved frame.')
 approval=dict(schema='joat.production_story_approval.v1',file_version='1.0.1',project_id=PROJECT,mission_fingerprint=MISSION,owner_approval=dict(owner=m.OWNER,approved=True,owner_statement=payload['owner_statement'],scope='story_and_existing_frame_reuse'),production_qc_approved=False,gpu_called=False)
 preserve(m.ROOT/'production-projects'/PROJECT/'approvals'/(MISSION+'.json'),approval)
 first=mission['shots'][0]
 shot=dict(scene_id='SCENE-001',shot_id='SHOT-001',character_id='CHAR-002',environment_id='ENV-102',purpose='Personal interruption: one more appointment message delays Kiana leaving her salon.',duration_seconds=6,camera=dict(size='medium',angle='eye_level',movement='static'),performance=dict(emotion='frustrated',expression='initial pleasant expression fades into controlled concern, no exaggerated grimace',body_language='seated behind reception counter, shoulders settle with fatigue',action=first['visual_intent'],gaze=dict(type='object',target='exit then phone on reception counter'),blocking=dict(start_position='seated behind reception counter',end_position='seated behind reception counter'),interaction=dict(type='none',target='',action=''),timing=dict(pacing='natural',hold_seconds=0)),dialogue='',narration='',audio='No generated dialogue or music. Character voice-over and subtle notification sound will be added in post.',caption='',style=mission['art_style'],wardrobe='Preserve approved navy blazer, striped top, jewellery and hairstyle exactly.')
 brief='One More Message: '+mission['owner_request']+' First shot only. Match the existing approved frame. Phone interruption creates a story beat; no visible speech, added people or camera movement.'
 import joat_creative_workflow as workflow
 plan=workflow.validate_plan(PROJECT,brief,{'shots':[shot]});state=workflow.build_drafts(plan,recovery_approved=True);result=workflow.assemble(state,True,m.OWNER)
 if len(result['source_packets'])!=1:raise ValueError('One first-shot packet required.')
 packet=result['source_packets'][0]
 # New descriptor assigns the unchanged approved still to the explicitly reused location.
 from joat_project_frame_reference import register
 manifest=register('PROJECT-OTU-SALON-001','KIANA-SALON-RECEPTION-CORRECTED','48dfb35061b74409b9769e07b9bb3b56',dict(project_id='PROJECT-OTU-SALON-001',scene_id='SCENE-001',shot_id='SHOT-001',character_id='CHAR-002',environment_id='ENV-102'),packet['generation_job']['immutable_upstream_snapshot']['character'],True)
 binding=save_binding(packet,create_binding(packet,manifest,True,m.OWNER))
 from joat_remote_generation import signed,save_plan
 prepared=m.proxy('executive','prepare',signed(packet,'prepare'),token);path=save_plan(packet,prepared)
 m.write_once(directory/'managed_plan.json',prepared);m.write_once(directory/'approved_source.json',packet)
 return dict(status='story_opening_prepared_awaiting_exact_remote_grant',gpu_called=False,source_job_fingerprint=packet['generation_job']['job_fingerprint'],source_supervisor_fingerprint=packet['packet_fingerprint'],plan_fingerprint=prepared['plan_fingerprint'],binding_fingerprint=binding['binding_fingerprint'],managed_plan_bucket_path=str(path.relative_to(m.ROOT.parent)),render_grant_created=False,production_qc_approved=False)
