"""CPU preparation of visible character-speech qualification. File version 1.0.0.
No voice-over substitution, render grant, GPU execution or QC approval.
"""
FILE_VERSION='1.0.0'
import joat_managed_generation as m
PROJECT='PROJECT-OTU-STORY-60S-001'
MISSION='273587dbab64d7abe9396fbd184dda59e2c8c3789f7268ed1e21c5a9efefc1ac'
REQUIREMENT='Characters visibly speak their own dialogue with lip sync; narration is not a substitute.'
def shot_spec(mission):
 q=mission.get('qualification_shot',{})
 if q.get('shot_id')!='SHOT-011' or q.get('character_id')!='CHAR-002' or q.get('duration_seconds')!=6 or q.get('dialogue')!=mission['shots'][0]['voice_text']:raise ValueError('Exact approved short character line required.')
 words=q['dialogue']
 return dict(scene_id='SCENE-001',shot_id='SHOT-011',character_id='CHAR-002',environment_id='ENV-102',purpose=q['purpose'],duration_seconds=6,camera=dict(size='medium',angle='eye_level',movement='static'),performance=dict(emotion='frustrated but composed',expression='natural conversational expression with stable eye shape and facial identity',body_language='seated behind the reception counter, restrained posture and hands resting naturally',action='Facing the camera with her face and mouth clearly visible, Kiana says in English: "'+words+'". Her lips and jaw visibly articulate the audible words in natural synchronization. She is the only speaker. Keep identity, hairstyle, clothes, jewellery, hands and room unchanged.',gaze=dict(type='camera',target='camera'),blocking=dict(start_position='seated behind reception counter',end_position='seated behind reception counter'),interaction=dict(type='none',target='',action=''),timing=dict(pacing='natural',hold_seconds=0)),dialogue=words,narration='',audio='Generate the visible woman Kiana speaking this exact English dialogue in a natural feminine conversational voice. Speech and mouth movement are generated together. Preserve the generated dialogue audio. No off-screen narrator, voice-over, music, dubbed replacement or other speakers.',caption='',style=mission['art_style'],wardrobe='Preserve approved navy blazer, striped top, jewellery and hairstyle exactly.')
def verify_speaking_packet(packet,words):
 job=packet['generation_job'];shot=job['immutable_upstream_snapshot']['director']['per_shot'][0]
 if shot.get('dialogue_narration',{}).get('dialogue')!=words or shot.get('dialogue_narration',{}).get('narration'):raise ValueError('Native Director lost exact character dialogue or introduced narration.')
 return job

def prepare(payload,mission,directory,token):
 if mission.get('project_id')!=PROJECT or mission.get('plan_fingerprint')!=MISSION or payload!={'owner_statement':'Ok go','approved_requirement':REQUIREMENT}:raise ValueError('Exact owner speech correction required.')
 from joat_project_lifecycle import assert_active
 assert_active(PROJECT,m.ROOT)
 policy=dict(schema='joat.character_speech_policy.v1',file_version='1.0.0',project_id=PROJECT,owner=m.OWNER,owner_statement=payload['owner_statement'],visible_speech_required=True,narration_substitute_allowed=False,lip_sync_qualified=False)
 policy['requirement_fingerprint']=m.digest(policy)
 policy_path=m.ROOT/'production-projects'/PROJECT/'requirements'/'character_speech.json'
 if policy_path.exists():
  if m.read_json(policy_path)!=policy:raise ValueError('Existing speech requirement differs.')
 else:m.write_once(policy_path,policy)
 shot=shot_spec(mission)
 from joat_approved_reference import load_approved_frame
 origin=m.read_json(m.ROOT/'job-reference-bindings'/PROJECT/'158b2e903106136cfa29375de9251fda5697888208289e95a7d8b03462bf6c70'/'binding.json')
 manifest=origin['approved_frame_manifest'];load_approved_frame(manifest)
 if manifest['descriptor']['image_sha256']!='27f173091ae09e3355dea31782848bc47c63488b46f0b9876edc8032c607b714':raise ValueError('Wrong approved Kiana reference.')
 import joat_creative_workflow as workflow
 brief='One More Message: visible speaking character qualification. The owner expressly requires lip-synced character speech. Use existing Kiana/office assets and the approved exact opening words. This is not a voice-over or a finished-film QC approval. No new reference images.'
 state=workflow.build_drafts(workflow.validate_plan(PROJECT,brief,{'shots':[shot]}),recovery_approved=True)
 result=workflow.assemble(state,True,m.OWNER)
 if len(result['source_packets'])!=1:raise ValueError('One speaking-shot source required.')
 packet=result['source_packets'][0];job=verify_speaking_packet(packet,shot['dialogue'])
 from joat_job_frame_binding import create_binding,save_binding
 bound=save_binding(packet,create_binding(packet,manifest,True,m.OWNER))
 from joat_remote_generation import signed,save_plan
 prepared=m.proxy('executive','prepare',signed(packet,'prepare'),token)
 prompt=prepared['plan']['parameters']['prompt']
 if shot['dialogue'] not in prompt or 'Spoken dialogue' not in prompt or 'No generated dialogue' in prompt:raise ValueError('Compiled renderer prompt does not preserve speaking requirement.')
 path=save_plan(packet,prepared)
 m.write_once(directory/'owner_requirement.json',dict(schema='joat.character_speech_requirement.v1',file_version=FILE_VERSION,owner=m.OWNER,owner_statement=payload['owner_statement'],requirement=REQUIREMENT,mission_fingerprint=MISSION,production_qc_approved=False))
 m.write_once(directory/'approved_source.json',packet);m.write_once(directory/'managed_plan.json',prepared)
 return dict(status='character_speech_prepared_awaiting_exact_remote_grant',gpu_called=False,source_job_fingerprint=job['job_fingerprint'],source_supervisor_fingerprint=packet['packet_fingerprint'],plan_fingerprint=prepared['plan_fingerprint'],binding_fingerprint=bound['binding_fingerprint'],managed_plan_bucket_path=str(path.relative_to(m.ROOT.parent)),exact_dialogue=shot['dialogue'],audio_mode='native_joint_character_speech',lip_sync_qualified=False,render_grant_created=False,production_qc_approved=False)
