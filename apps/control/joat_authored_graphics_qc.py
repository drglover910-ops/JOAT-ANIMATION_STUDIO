"""Independent QC for authored graphic sources, without pretending they are LTX shots.
Embedded file version1.0.0. Four owner checks plus an independent full decode.
"""
FILE_VERSION='1.0.0'
import copy,hashlib,json
from joat_media_tools import inspect_video
CHECKS={'design','legibility','transaction_accuracy','brand_claims'}
def fp(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def verify(v,key):
 if not isinstance(v,dict) or v.get(key)!=fp({k:x for k,x in v.items() if k!=key}):raise ValueError('Invalid '+key)
def inspect_authored(candidate,media,checks,reviewer,notes=''):
 if reviewer!='Dezz-9-10' or set(checks)!=CHECKS or any(type(v) is not bool for v in checks.values()):raise ValueError('Four explicit owner-authored-graphics checks are required.')
 verify(candidate,'candidate_fingerprint');plan=candidate.get('source_plan',{});verify(plan,'plan_fingerprint')
 if candidate.get('schema')!='joat.authored_graphics_candidate.v1' or candidate.get('source_kind')!='authored_motion_graphics' or candidate.get('production_qc_approved') is not False or candidate.get('delivery_authorized') is not False or plan.get('schema')!='joat.authored_graphics_plan.v1' or candidate.get('project_id')!=plan.get('project_id') or candidate.get('shot_id')!=plan.get('shot_id') or candidate.get('illustrative') is not True:raise ValueError('Actual unapproved authored candidate required.')
 specification={'duration_seconds':plan['duration_seconds'],'aspect_ratio':'16:9'};evidence=inspect_video(media,specification)
 expected=candidate.get('media_evidence',{})
 if any(evidence.get(k)!=expected.get(k) for k in ('sha256','width','height','fps','decoded_frames','audio_present')) or evidence['width']!=1024 or evidence['height']!=576 or evidence['fps']!=24:raise ValueError('Uploaded graphics differ from the exact candidate.')
 passed=all(checks.values());result=dict(schema='joat.authored_graphics_qc.v1',file_version=FILE_VERSION,source_kind='authored_motion_graphics',project_context={'project_id':plan['project_id'],'scene_id':'AUTHORED-GRAPHICS','shot_id':plan['shot_id']},source_job_fingerprint=plan['plan_fingerprint'],source_candidate_fingerprint=candidate['candidate_fingerprint'],source_mission_fingerprint=plan['mission_fingerprint'],source_asset={'sha256':evidence['sha256']},media_evidence=evidence,independent_review={'reviewer':reviewer,'checks':copy.deepcopy(checks),'notes':str(notes)[:2000],'technical_check_is_automatic':True,'actor_identity_review_applicable':False},decision='PASS' if passed else 'REWORK',post_production_authorized=passed,production_source_is_generated_actor=False,gpu_called=False,illustrative=True,delivery_authorized=False)
 result['qc_fingerprint']=fp(result);return result

def validate_authored_qc(qc):
 verify(qc,'qc_fingerprint');review=qc.get('independent_review',{});checks=review.get('checks',{});evidence=qc.get('media_evidence',{})
 if qc.get('schema')!='joat.authored_graphics_qc.v1' or qc.get('source_kind')!='authored_motion_graphics' or qc.get('decision')!='PASS' or qc.get('post_production_authorized') is not True or qc.get('production_source_is_generated_actor') is not False or review.get('reviewer')!='Dezz-9-10' or review.get('actor_identity_review_applicable') is not False or set(checks)!=CHECKS or any(v is not True for v in checks.values()) or evidence.get('video_fully_decoded') is not True or evidence.get('sha256')!=qc.get('source_asset',{}).get('sha256') or qc.get('delivery_authorized') is not False:raise ValueError('Independent authored graphics QC PASS required.')
 return evidence
