"""Check exact saved, frame-bound jobs through signed CPU routing. File version 1.0.1."""
FILE_VERSION='1.0.1'
import json, os, re, threading
from huggingface_hub import HfApi
import joat_managed_generation as managed
import joat_job_frame_binding as binding
from joat_job_frame_ui import read_source
PREFIX='JOAT_FRAME_PREFLIGHT_INPUT_'

def validate(value):
 if not isinstance(value,dict) or set(value)!={'project_id','jobs','gpu_allowed'} or value['gpu_allowed'] is not False:raise ValueError('Exact CPU-only frame preflight required.')
 managed.valid_project(value['project_id'])
 if not isinstance(value['jobs'],list) or not 1<=len(value['jobs'])<=8:raise ValueError('Bounded saved jobs required.')
 seen=set()
 for row in value['jobs']:
  if not isinstance(row,dict) or set(row)!={'job_fingerprint','supervisor_fingerprint'}:raise ValueError('Exact saved job fingerprints required.')
  if any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in row.values()):raise ValueError('Invalid job fingerprint.')
  if row['job_fingerprint'] in seen:raise ValueError('Duplicate preflight job.')
  seen.add(row['job_fingerprint'])
 return value

def run_frame_preflight_tasks():
 for name in sorted(n for n in os.environ if n.startswith(PREFIX)):
  context={'schema':'joat.frame_preflight_task_receipt.v1','file_version':FILE_VERSION,'gpu_called':False,'automatic_retry':False}
  try:
   value=json.loads(os.environ[name]);repair=value.pop('resume_after_fix',None)
   if repair not in (None,'director_media_field_compatibility'):raise ValueError('Unrecognized CPU preparation repair.')
   value=validate(value);context['project_id']=value['project_id'];managed.mount_check('main')
   token=os.environ.get('JOAT_SPECIALIST_TOKEN')
   if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Existing runtime owner credential unavailable.')
   sources=[]
   for row in value['jobs']:
    packet=read_source(value['project_id'],row['job_fingerprint']+'/'+row['supervisor_fingerprint']);frame=binding.load_binding(packet)
    if frame is None:raise ValueError('Saved job lacks an approved scene frame assignment.')
    binding.load_approved_frame(frame['approved_frame_manifest']);sources.append((packet,frame))
   original=binding.safe(binding.ROOT/'frame-preflight-tasks'/value['project_id']/binding.digest(value));root=original
   if repair is not None:
    previous=managed.read_json(original/'reservation.json')
    if previous.get('scope')!=value or (original/'result.json').exists() or any((original/row['job_fingerprint']/'prepared.json').exists() for row in value['jobs']):raise ValueError('Repair must match the exact unfinished original CPU prepare failure.')
    root=binding.safe(original/'repairs'/repair);context['repair']=repair;context['original_reservation_retained']=True
   result=root/'result.json'
   if result.exists():print('JOAT_FRAME_PREFLIGHT '+json.dumps(json.loads(result.read_text())),flush=True);continue
   if (root/'reservation.json').exists():raise ValueError('Preflight already reserved; inspect records before any further request.')
   managed.write_once(root/'reservation.json',dict(context,scope=value))
   checks=[]
   for packet,frame in sources:
    job=packet['generation_job'];context['source_job_fingerprint']=job['job_fingerprint']
    prepared=managed.proxy('executive','prepare',managed.sign(packet,'prepare'),token)
    plan=prepared['plan']
    if prepared.get('gpu_called') is not False or plan.get('source_job_fingerprint')!=job['job_fingerprint'] or prepared.get('plan_fingerprint')!=managed.digest(plan):raise ValueError('Signed CPU preparation changed job or authority.')
    managed.write_once(root/job['job_fingerprint']/'prepared.json',prepared)
    checked=managed.proxy('executive','check',managed.sign(packet,'check',plan),token)
    if checked.get('gpu_called') is not False or checked.get('status')!='passed' or checked.get('source_job_fingerprint')!=job['job_fingerprint']:raise ValueError('CPU renderer check did not pass for the exact job.')
    managed.write_once(root/job['job_fingerprint']/'connection.json',checked)
    item={'project_context':job['project_context'],'source_job_fingerprint':job['job_fingerprint'],'plan_fingerprint':prepared['plan_fingerprint'],'binding_fingerprint':frame['binding_fingerprint'],'approved_image_sha256':frame['owner_approval']['image_sha256'],'status':'cpu_renderer_connection_passed','gpu_called':False,'renderer_revision':checked.get('renderer_revision')}
    checks.append(item);print('JOAT_FRAME_PREFLIGHT_PROGRESS '+json.dumps(item),flush=True)
   context.pop('source_job_fingerprint',None)
   record=dict(context,status='cpu_frame_preflight_passed',checks=checks,private_readback_verified=True,original_source_packets_unchanged=True,production_qc_approved=False)
   managed.write_once(result,record);print('JOAT_FRAME_PREFLIGHT '+json.dumps(record),flush=True)
  except Exception as exc:
   message=re.sub(r'(?i)(?:Bearer\s+|hf_)[A-Za-z0-9._-]+','[REDACTED]',str(exc))[:500]
   print('JOAT_FRAME_PREFLIGHT '+json.dumps(dict(context,status='stopped_for_review',error_type=type(exc).__name__,safe_error_message=message)),flush=True)

def start_frame_preflights():
 if any(n.startswith(PREFIX) for n in os.environ):threading.Thread(target=run_frame_preflight_tasks,name='joat-cpu-frame-preflight',daemon=True).start()
