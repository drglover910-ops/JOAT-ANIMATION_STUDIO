"""Exact owner-staged canonical-source reference requests. File version1.0.1.
Only prepares new candidate images. Never registers canonical identities or approves unseen stills.
"""
FILE_VERSION='1.0.1'
import hashlib,json,re

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def authorize(mission,payload):
 if not isinstance(mission,dict) or not isinstance(payload,dict) or set(payload)!={'requests','spending_approval'}:raise ValueError('Exact canonical reference task and spending scope required.')
 auth=mission.get('reference_preparation',{})
 if auth.get('schema')!='joat.canonical_project_reference_preparation.v1' or auth.get('mode')!='existing_canonical_sources' or auth.get('owner')!='Dezz-9-10' or auth.get('maximum_candidate_requests')!=1 or not mission.get('owner_supplied_source_prompt'):raise ValueError('No exact owner-supplied canonical reference mission.')
 if auth.get('source_prompt_sha256')!=mission.get('owner_source_prompt_sha256') or not re.fullmatch('[a-f0-9]{64}',str(auth.get('source_prompt_sha256',''))):raise ValueError('Owner source prompt differs.')
 timing=mission.get('timing_approval',{})
 if timing.get('owner')!='Dezz-9-10' or timing.get('owner_statement')!='Approve corrected timing; preserve every word (Recommended)' or timing.get('duration_seconds')!=90 or timing.get('long_shots')!=[11,12,15] or timing.get('short_shots')!=[10,16,18]:raise ValueError('Exact corrected owner timing approval required.')
 requests=payload['requests']
 if not isinstance(requests,list) or len(requests)!=1 or requests!=mission.get('reference_requests') or [digest(q) for q in requests]!=auth.get('allowed_request_fingerprints'):raise ValueError('Reference request differs from exact staged mission; no inference requested.')
 request=requests[0]
 if request.get('project_id')!=mission.get('project_id') or request.get('kind')!='shot_start_frame' or request.get('generation_authorized') is not True or request.get('canonical_registration') is not False or request.get('aspect_ratio')!='9:16' or request.get('gpu_ceiling_seconds')!=600:raise ValueError('Preserve exact portrait candidate and600second ceiling.')
 grant=payload['spending_approval']
 if isinstance(grant,dict) and grant.get('schema')=='joat.included_quota_confirmation.v1':
  from datetime import datetime,timezone
  from joat_gpu_quota_panel import checked_time
  expected={'schema','file_version','owner','owner_statement','request_id','request_fingerprint','maximum_usd','maximum_attempts','gpu_seconds_ceiling','gpu_size','credit_purchase_authorized','report_id','confirmed_at','included_seconds_available','included_seconds_total','source'}
  if set(grant)!=expected or grant.get('owner')!='Dezz-9-10' or grant.get('request_id')!=request['request_id'] or grant.get('request_fingerprint')!=digest(request) or grant.get('maximum_usd')!=0 or type(grant.get('maximum_usd')) is not int or grant.get('maximum_attempts')!=1 or grant.get('gpu_seconds_ceiling')!=600 or grant.get('gpu_size')!='large' or grant.get('credit_purchase_authorized') is not False or grant.get('source')!='owner_chat_report' or not isinstance(grant.get('owner_statement'),str) or not grant['owner_statement']:raise ValueError('Exact included-quota confirmation required.')
  if any(type(grant.get(k)) is not int for k in ('included_seconds_available','included_seconds_total')) or not 600<=grant['included_seconds_available']<=grant['included_seconds_total']<=86400:raise ValueError('At least600 included GPU seconds must be confirmed.')
  age=(datetime.now(timezone.utc)-checked_time(grant['confirmed_at'])).total_seconds()
  if not -30<=age<=900:raise ValueError('Included GPU confirmation is stale; refresh before inference.')
  return requests
 expected={'schema','file_version','owner','owner_statement','request_id','request_fingerprint','maximum_usd','maximum_attempts','gpu_seconds_ceiling','gpu_size','credit_purchase_authorized'}
 if not isinstance(grant,dict) or set(grant)!=expected or grant.get('schema')!='joat.reference_spending_approval.v1' or grant.get('owner')!='Dezz-9-10' or grant.get('owner_statement')!='Approve up to $1 for this one reference' or grant.get('request_id')!=request['request_id'] or grant.get('request_fingerprint')!=digest(request) or type(grant.get('maximum_usd')) is not int or grant['maximum_usd']!=1 or grant.get('maximum_attempts')!=1 or grant.get('gpu_seconds_ceiling')!=600 or grant.get('gpu_size')!='large' or grant.get('credit_purchase_authorized') is not False:raise ValueError('Explicit one-call owner spending approval required; no GPU request sent.')
 return requests
