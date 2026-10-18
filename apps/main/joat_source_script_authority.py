"""Bind CPU drafts to the original owner-supplied mission. File version1.0.0.
Does not approve generated drafts, references, video, spending or final QC.
"""
FILE_VERSION='1.0.0'
import json,re
import joat_managed_generation as m

def verify_batches(mission,batches):
 if mission.get('schema')!='joat.production_film_plan.v1' or mission.get('owner_supplied_source_prompt') is not True or mission.get('owner_script_line_by_line_reviewed') is not False or not re.fullmatch('[a-f0-9]{64}',str(mission.get('owner_source_prompt_sha256'))):raise ValueError('An immutable original owner-supplied script is required.')
 timing=mission.get('timing_approval',{})
 if timing.get('owner')!=m.OWNER or timing.get('owner_statement')!='Approve corrected timing; preserve every word (Recommended)' or timing.get('spoken_script_changes_authorized') is not False or timing.get('duration_seconds')!=mission.get('target_duration_seconds'):raise ValueError('Exact owner-approved timing required.')
 expected={s['shot_id']:s for s in mission['shots'] if s['production_type']=='video'}
 shots=[s for b in batches for s in b['plan']['shots']]
 if len(shots)!=len(expected) or {s['shot_id'] for s in shots}!=set(expected):raise ValueError('Draft the exact declared video shots once.')
 for shot in shots:
  source=expected[shot['shot_id']]
  if shot['scene_id']!=source['scene_id'] or shot['duration_seconds']!=source['duration_seconds'] or any(shot[k]!=source['audio'][k] for k in ('dialogue','narration')):raise ValueError('Source dialogue, narration, scene and timing must remain exact.')
  purpose=json.loads(shot['purpose']);visible={r:mission['characters'][r.upper()] for r in source['visible_roles']}
  if purpose.get('original_visual')!=source['visual'] or purpose.get('original_camera')!=source['camera'] or purpose.get('lighting')!=source['lighting'] or purpose.get('visible_cast')!=visible or purpose.get('native_render_prompt')!=source['native_render_prompt'] or purpose.get('source_mission_fingerprint')!=mission['plan_fingerprint'] or purpose.get('source_shot_id')!=source['shot_id'] or shot['character_id'] not in visible.values():raise ValueError('Source visual direction and declared cast must remain exact.')
 return dict(schema='joat.production_story_approval.v1',file_version=FILE_VERSION,project_id=mission['project_id'],mission_fingerprint=mission['plan_fingerprint'],source_prompt_sha256=mission['owner_source_prompt_sha256'],approval_basis='Owner supplied this exact script and authorized production; source and corrected timing bound before CPU department drafting.',owner_approval=dict(owner=m.OWNER,approved=True,scope='draft_original_owner_script_only',owner_statement=mission['authorization_scope']),generated_drafts_approved=False,owner_script_line_by_line_reviewed=False,production_qc_approved=False,gpu_called=False,spending_authorized=False)

def ensure(mission,batches):
 approval=verify_batches(mission,batches)
 path=m.safe_path(m.ROOT/'production-projects'/m.valid_project(mission['project_id'])/'approvals'/(mission['plan_fingerprint']+'.json'))
 if path.exists():
  previous=m.read_json(path)
  if previous!=approval:raise ValueError('Different story approval is already retained.')
 else:m.write_once(path,approval)
 return m.read_json(path)
