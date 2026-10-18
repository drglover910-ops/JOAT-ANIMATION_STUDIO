"""Scoped private owner-approved frame assignment task; no department/GPU calls. Version1.0.1."""
FILE_VERSION='1.0.1'
import json,os,re
from pathlib import Path
from huggingface_hub import HfApi
import joat_managed_generation as managed
import joat_job_frame_binding as binding
from joat_job_frame_ui import read_source,read_frame
PREFIX='JOAT_FRAME_ASSIGNMENT_INPUT_'
def validate(value):
 if not isinstance(value,dict) or set(value)!={'project_id','assignments','owner_approved','gpu_allowed'} or value['owner_approved'] is not True or value['gpu_allowed'] is not False:raise ValueError('Exact owner-approved CPU frame assignment required.')
 managed.valid_project(value['project_id']);rows=value['assignments']
 if not isinstance(rows,list) or not 1<=len(rows)<=8:raise ValueError('Bounded scene assignments required.')
 seen=set()
 for row in rows:
  common={'scene_id','shot_id','job_fingerprint','supervisor_fingerprint'}
  if not isinstance(row,dict) or set(row) not in (common|{'asset_id'},common|{'asset_key','request_id'}):raise ValueError('Invalid assignment scope.')
  if 'request_id' in row and (not isinstance(row['request_id'],str) or not re.fullmatch('[a-f0-9]{32}',row['request_id']) or not isinstance(row['asset_key'],str) or not re.fullmatch('[A-Z0-9-]{1,96}',row['asset_key'])):raise ValueError('Exact approved candidate identifiers required.')
  for key in ('job_fingerprint','supervisor_fingerprint')+ (('asset_id',) if 'asset_id' in row else ()) :
   if not isinstance(row[key],str) or not re.fullmatch('[a-f0-9]{64}',row[key]):raise ValueError('Exact assignment fingerprints required.')
  if row['job_fingerprint'] in seen:raise ValueError('Duplicate source assignment.')
  seen.add(row['job_fingerprint'])
 return value

def run_frame_assignment_tasks():
 for name in sorted(n for n in os.environ if n.startswith(PREFIX)):
  try:
   value=validate(json.loads(os.environ[name]));managed.mount_check('main');token=os.environ.get('JOAT_SPECIALIST_TOKEN')
   if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Existing runtime owner credential unavailable.')
   proposals=[]
   for row in value['assignments']:
    packet=read_source(value['project_id'],row['job_fingerprint']+'/'+row['supervisor_fingerprint']);ctx=packet['generation_job']['project_context']
    if ctx['scene_id']!=row['scene_id'] or ctx['shot_id']!=row['shot_id']:raise ValueError('Assignment scene/shot differs from saved source.')
    if 'asset_id' in row:manifest=read_frame(row['asset_id'])
    else:
     from joat_project_frame_reference import register_from_source
     manifest=register_from_source(packet,row['asset_key'],row['request_id'],True)
    proposal=binding.create_binding(packet,manifest,True,'Dezz-9-10');binding.load_approved_frame(manifest);proposals.append((packet,proposal))
   root=binding.safe(binding.ROOT/'frame-assignment-tasks'/value['project_id']/binding.digest(value));file=root/'result.json'
   if file.exists():
    record=json.loads(file.read_text());print('JOAT_FRAME_ASSIGNMENT '+json.dumps(record),flush=True);continue
   if (root/'reservation.json').exists():raise ValueError('Assignment task already reserved; inspect prior records before resuming.')
   managed.write_once(root/'reservation.json',{'file_version':FILE_VERSION,'scope':value,'gpu_called':False})
   assigned=[]
   for packet,proposal in proposals:
    stored=binding.save_binding(packet,proposal);assigned.append({'project_context':stored['project_context'],'source_job_fingerprint':stored['source_job_fingerprint'],'source_supervisor_fingerprint':stored['source_supervisor_fingerprint'],'image_sha256':stored['owner_approval']['image_sha256'],'binding_fingerprint':stored['binding_fingerprint']})
   record={'schema':'joat.frame_assignment_task_receipt.v1','file_version':FILE_VERSION,'project_id':value['project_id'],'status':'approved_frames_assigned','assignments':assigned,'private_readback_verified':True,'original_source_packets_unchanged':True,'gpu_called':False,'production_qc_approved':False,'automatic_retry':False};managed.write_once(file,record)
   print('JOAT_FRAME_ASSIGNMENT '+json.dumps(record),flush=True)
  except Exception as exc:print('JOAT_FRAME_ASSIGNMENT '+json.dumps({'schema':'joat.frame_assignment_task_receipt.v1','file_version':FILE_VERSION,'status':'stopped_for_review','error_type':type(exc).__name__,'gpu_called':False,'automatic_retry':False}),flush=True)
