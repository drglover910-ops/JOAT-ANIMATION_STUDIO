"""Exact append-only scene dependencies under live included-quota checks.
File version: 1.0.2. Original one-reference mission remains immutable.
"""
FILE_VERSION='1.0.2'
import hashlib,json,os,threading,uuid
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).parent
REGISTRY_SHA256='41d1f2adcc514443d411d8efa9d523e7798bfc4aef8a9a9ea9cfffbe6635f2ba'
LOCK=threading.Lock()

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def registry():
    p=ROOT/'joat_style001_reference_supplement.json'
    if p.is_symlink() or p.stat().st_size>128*1024:raise ValueError('Invalid reference supplement path.')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=REGISTRY_SHA256:raise ValueError('Reference supplement integrity failed.')
    return json.loads(raw)

def authorize(mission,payload):
    if not isinstance(payload,dict) or set(payload)!={'requests','spending_approval','additional_reference_scope'}:raise ValueError('Exact supplementary candidate scope required.')
    r=registry();unsigned=dict(mission);given=unsigned.pop('plan_fingerprint',None)
    if given!=r['mission_fingerprint'] or digest(unsigned)!=given or mission.get('project_id')!=r['project_id'] or mission.get('owner_source_prompt_sha256')!=r['source_prompt_sha256'] or mission.get('owner_supplied_source_prompt') is not True:raise ValueError('Supplement cannot alter the original approved source mission.')
    if mission.get('reference_preparation',{}).get('maximum_candidate_requests')!=1:raise ValueError('Keep the original one-reference allowance unchanged.')
    if payload['additional_reference_scope']!={'registry_sha256':REGISTRY_SHA256,'original_mission_changed':False}:raise ValueError('Supplement scope differs from reviewed exact requests.')
    requests=payload['requests']
    if not isinstance(requests,list) or len(requests)!=1:raise ValueError('One exact missing candidate per task; never an automatic batch.')
    request=requests[0];matches=[x for x in r['requests'] if x['request']==request and x['request_fingerprint']==digest(request)]
    if len(matches)!=1:raise ValueError('Candidate differs from the exact missing-scene request.')
    grant=payload['spending_approval']
    expected={'schema':'joat.included_quota_only_execution.v1','file_version':'1.0.0','owner':'Dezz-9-10','request_id':request['request_id'],'request_fingerprint':digest(request),'maximum_usd':0,'maximum_attempts':1,'gpu_seconds_ceiling':600,'gpu_size':'large','credit_purchase_authorized':False}
    if grant!=expected or type(grant.get('maximum_usd')) is not int or type(grant.get('maximum_attempts')) is not int:raise ValueError('Included-quota-only one-candidate authority required.')
    return requests

def reserve(request,payload):
    """Check the live account and pending local ceilings atomically; no scheduling."""
    from joat_provider_quota import read_quota
    from joat_gpu_quota_panel import ROOT as quota_root,seal,write_once,read
    with LOCK:
        quota=read_quota(os.environ.get('JOAT_SPECIALIST_TOKEN',''))
        if quota.get('provider_live_balance') is not True:raise ValueError('Live ZeroGPU quota is not authorized or unavailable; no GPU request sent.')
        root=quota_root/'live-reference-reservations';pending=0
        for file in root.glob('*/reservation.json'):
            reservation=read(file);settled=False;settlement=file.parent/'settlement.json'
            if settlement.exists():
                result=read(settlement)
                settled=(result.get('status')=='response_received_artifact_verified' and
                         result.get('request_id')==reservation['request_id'] and
                         result.get('request_fingerprint')==reservation['request_fingerprint'])
            if not settled:pending+=reservation['ceiling_seconds']
        if quota['remaining_seconds']-pending<720:raise ValueError('Included quota cannot cover the 600-second ceiling and 120-second headroom; no GPU request sent.')
        folder=root/request['request_id']
        if (folder/'reservation.json').exists():raise ValueError('Exact candidate already reserved; inspect its original outcome, no automatic retry.')
        if folder.exists():
            archive=read(folder/'pre_gpu_failure_reconciliation.json')
            original=archive.get('original_reservation',{})
            if (archive.get('schema')!='joat.pre_gpu_failure_reconciliation.v1' or archive.get('reference_request_id')!=request['request_id'] or archive.get('reference_side_directory_absent') is not True or archive.get('gpu_called') is not False or original.get('request_id')!=request['request_id'] or original.get('request_fingerprint')!=digest(request)):
                raise ValueError('Existing candidate folder has no verified pre-GPU reconciliation; do not retry.')
        value=seal(dict(schema='joat.live_reference_reservation.v1',file_version=FILE_VERSION,request_id=request['request_id'],request_fingerprint=digest(request),ceiling_seconds=600,quota_observation=quota,reserved_at=datetime.now(timezone.utc).isoformat(),paid_spending_authorized_usd=0))
        write_once(folder/'reservation.json',value)
        # Exact supplemental source is an append-only dependency, not a mission rewrite.
        import joat_managed_generation as m
        write_once(m.ROOT/'production-projects'/request['project_id']/'reference-supplements'/REGISTRY_SHA256/'scope.json',seal({'schema':'joat.applied_reference_supplement.v1','file_version':'1.0.0','registry_sha256':REGISTRY_SHA256,'scope':payload['additional_reference_scope'],'original_mission_changed':False,'canonical_registration':False,'production_qc_approved':False}))

def settle(request,review):
    from joat_gpu_quota_panel import ROOT as quota_root,seal,write_once
    write_once(quota_root/'live-reference-reservations'/request['request_id']/'settlement.json',seal({'schema':'joat.live_reference_settlement.v1','file_version':FILE_VERSION,'request_id':request['request_id'],'request_fingerprint':digest(request),'candidate_sha256':review['sha256'],'status':'response_received_artifact_verified','actual_provider_charge_usd':None,'production_qc_approved':False}))
