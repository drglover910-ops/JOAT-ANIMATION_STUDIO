"""Owner-staged private CPU qualification inside Main. File version 1.0.1.
Uses the existing runtime credential and signing key. No GPU/execute route exists.
"""
FILE_VERSION='1.0.1'
import base64,hashlib,json,os,re,shutil,threading,zlib
from pathlib import Path
from joat_managed_generation import HfApi,OWNER,SPACES,sign,proxy,digest,write_once
PREFIX='JOAT_CPU_QUALIFICATION_REQUEST_'
def report(value):print('JOAT_CPU_QUALIFICATION '+json.dumps(value,sort_keys=True),flush=True)
def decode(raw,expected):
 request=json.loads(raw)
 if (request.get('schema')!='joat.owner_cpu_qualification.v1' or request.get('request_id')!=expected
     or request.get('operation')!='prepare_and_check' or request.get('gpu_allowed') is not False):raise ValueError('Invalid CPU audit request.')
 compressed=base64.b64decode(request['payload'],validate=True);decoder=zlib.decompressobj()
 data=decoder.decompress(compressed,2*1024*1024+1)
 if len(data)>2*1024*1024 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('Invalid bounded source packet.')
 if hashlib.sha256(data).hexdigest()!=request['source_sha256']:raise ValueError('CPU audit source hash differs.')
 return json.loads(data)
def run(name,raw,root=None,client_proxy=proxy,identity_api=HfApi):
 identifier=name[len(PREFIX):]
 if not re.fullmatch('[a-f0-9]{32}',identifier):return
 if os.environ.get('SPACE_ID')!=SPACES['main']:return
 folder=Path(root or os.environ.get('JOAT_DATA_DIR','/data/joat-main-assistant'))/'cpu-qualifications'/identifier
 reservation=folder/'reservation.json';receipt=folder/'receipt.json'
 if receipt.exists():
  value=json.loads(receipt.read_text());value['checkpoint_reused']=True;report(value);return value
 if reservation.exists():
  value={'schema':'joat.cpu_qualification_status.v1','file_version':FILE_VERSION,'request_id':identifier,'status':'pending_or_unknown','gpu_called':False,'automatic_retry':False};report(value);return value
 stage='validate_private_request'
 try:
  packet=decode(raw,identifier)
  token=os.environ.get('JOAT_SPECIALIST_TOKEN','')
  if not token:raise ValueError('Existing runtime credential unavailable.')
  stage='verify_runtime_owner'
  if identity_api(token=token).whoami().get('name')!=OWNER:raise ValueError('Existing runtime credential is not the owner.')
  value=sign(packet,'prepare')
  write_once(reservation,{'schema':'joat.cpu_qualification_reservation.v1','file_version':FILE_VERSION,'request_id':identifier,'source_job_fingerprint':packet['generation_job']['job_fingerprint'],'gpu_called':False,'automatic_retry':False})
  stage='main_signed_prepare'
  prepared=client_proxy('executive','prepare',value,token)
  if (prepared.get('schema')!='joat.managed_render_plan.v1' or prepared.get('gpu_called') is not False
      or prepared.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']
      or prepared.get('source_supervisor_fingerprint')!=packet['packet_fingerprint']
      or digest(prepared.get('plan'))!=prepared.get('plan_fingerprint')):raise ValueError('Exact CPU plan validation failed.')
  write_once(folder/'managed_plan.json',prepared)
  stage='main_signed_connection_check'
  checked=client_proxy('executive','check',sign(packet,'check',prepared['plan']),token)
  if (checked.get('schema')!='joat.render_connection_check.v1' or checked.get('status')!='passed'
      or checked.get('gpu_called') is not False or checked.get('source_job_fingerprint')!=packet['generation_job']['job_fingerprint']):raise ValueError('CPU renderer connection validation failed.')
  write_once(folder/'connection_check.json',checked)
  stage='main_readonly_approved_reuse'
  reused=client_proxy('executive','reuse',sign(packet,'reuse',prepared['plan']),token)
  reuse,video,_,_,approved_file=reused
  if reuse.get('gpu_called') is not False or reuse.get('source_job_fingerprint')!=prepared['source_job_fingerprint']:raise ValueError('Read-only reuse response differs.')
  media_sha=None;final_fp=None
  if reuse.get('status')=='approved_delivery_reused':
   from joat_managed_generation import read_json,verify,file_hash,store_media
   approved=read_json(approved_file);verify(approved,'result_fingerprint');qc=approved.get('final_qc',{})
   if (approved.get('source_job_fingerprint')!=prepared['source_job_fingerprint'] or approved.get('delivery_authorized') is not True
       or qc.get('decision')!='PASS' or qc.get('reviewer')!=OWNER or set(qc.get('checks',{}))!={'picture','audio','titles','continuity'}
       or not all(v is True for v in qc['checks'].values()) or file_hash(video)!=approved['final_master']['sha256']
       or qc.get('asset_sha256')!=approved['final_master']['sha256']):raise ValueError('Reused approved master validation failed.')
   store_media(video,folder/'approved_master.mp4');write_once(folder/'approved_final_result.json',approved)
   media_sha=approved['final_master']['sha256'];final_fp=approved['result_fingerprint']
  elif reuse.get('status')!='no_approved_delivery_available':raise ValueError('Unexpected read-only reuse outcome.')
  value={'schema':'joat.cpu_qualification_receipt.v1','file_version':FILE_VERSION,'request_id':identifier,'status':'passed','route':['main','executive','supervisor','worker'],
   'runtime_owner_verified':True,'source_job_fingerprint':prepared['source_job_fingerprint'],'source_supervisor_fingerprint':prepared['source_supervisor_fingerprint'],'plan_fingerprint':prepared['plan_fingerprint'],
   'approved_delivery_available':prepared.get('approved_delivery_available'),'approved_source_registered':prepared.get('source_registered'),'approved_source_readback_verified':prepared.get('source_readback_verified'),'source_studio_uri':prepared.get('source_studio_uri'),'renderer_revision':checked.get('renderer_revision'),'locked_reference_hashes_verified':checked.get('locked_reference_hashes_verified'),
   'readonly_reuse_status':reuse['status'],'reused_master_sha256':media_sha,'reused_final_result_fingerprint':final_fp,
   'gpu_called':False,'automatic_retry':False,'private_checkpoint_readback_verified':True}
  write_once(receipt,value);report(value);return value
 except Exception as exc:
  msg=str(exc);code=next((v for v in ('Existing runtime credential unavailable','not the owner','Invalid CPU audit','source hash differs','JOAT_DISPATCH_ENABLED','Owner credential could not be verified','Managed request or checkpoint validation failed','Managed prepare connection failed','Managed check connection failed') if v in msg),'cpu_audit_failed')
  value={'schema':'joat.cpu_qualification_failure.v1','file_version':FILE_VERSION,'request_id':identifier,'status':'failed','stage':stage,'error_type':type(exc).__name__,'safe_error_code':code,'gpu_called':False,'automatic_retry':False}
  try:
   if reservation.exists() and not receipt.exists():write_once(receipt,value)
  except Exception:pass
  report(value);return value

def start_cpu_qualifications():
 for name in sorted(os.environ):
  if name.startswith(PREFIX):threading.Thread(target=run,args=(name,os.environ[name]),daemon=True).start()
