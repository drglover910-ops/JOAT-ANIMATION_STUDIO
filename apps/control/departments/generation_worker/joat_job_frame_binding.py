"""Approved image dependencies for immutable source jobs. File version1.0.1.
Never changes the originating image scope, Supervisor packet or upstream decisions.
"""
FILE_VERSION='1.0.1'
import hashlib,json,re,os
from datetime import datetime,timezone
from pathlib import Path
from joat_approved_reference import validate_manifest,bind_character,load_approved_frame
ROOT=Path('/studio/joat-studio')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def verify(value,key):
 if not isinstance(value,dict) or digest({k:v for k,v in value.items() if k!=key})!=value.get(key):raise ValueError('Invalid '+key)
def safe(path):
 path=Path(path)
 if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Frame assignment paths cannot contain symlinks.')
 return path

def source(packet):
 verify(packet,'packet_fingerprint');job=packet['generation_job'];verify(job,'job_fingerprint')
 if packet.get('production_ready') is not True or job.get('job_type')!='video' or job.get('engine')!='ltx':raise ValueError('Validated LTX Supervisor source required.')
 context=job['project_context']
 for key in ('project_id','scene_id','shot_id'):
  if not isinstance(context.get(key),str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',context[key]):raise ValueError('Invalid source context.')
 snap=job['immutable_upstream_snapshot'];contract=job['prompt_contract']
 for role in ('character','environment','director','shot_camera','performance_action'):
  if snap[role]!=contract[role+'_packet']:raise ValueError('Source snapshots changed.')
 director=snap['director']
 if director.get('project_assignment',{}).get('owner_review_required') is True and (director.get('approval',{}).get('creative_intent_locked') is not True or director.get('approval',{}).get('approved_by')!='Dezz-9-10'):raise ValueError('Reviewed creative source must be owner-approved.')
 return job,context,snap

def create_binding(packet,manifest,approved,owner):
 if approved is not True or owner!='Dezz-9-10':raise ValueError('Owner must review this exact scene frame for the selected job.')
 job,context,snap=source(packet);descriptor=bind_character(manifest,snap['character'])
 from joat_visible_cast import validate_for_job
 validate_for_job(descriptor,snap['director'],snap['character'])
 if descriptor['scope']['environment_id']!=snap['environment']['environment_id']:raise ValueError('Approved frame belongs to a different environment.')
 value={'schema':'joat.job_frame_binding.v1','file_version':FILE_VERSION,'project_context':context,'source_job_fingerprint':job['job_fingerprint'],'source_supervisor_fingerprint':packet['packet_fingerprint'],'source_character_sha256':digest(snap['character']),'source_environment_sha256':digest(snap['environment']),'source_director_sha256':digest(snap['director']),'approved_frame_manifest':manifest,'owner_approval':{'owner':owner,'kind':'job_reference_assignment','approved_at':datetime.now(timezone.utc).isoformat(),'image_sha256':descriptor['image_sha256'],'reviewed_for_this_job':True},'canonical_registration':False,'production_qc_approved':False,'gpu_called':False}
 return dict(value,binding_fingerprint=digest(value))

def validate_binding(value,packet):
 verify(value,'binding_fingerprint')
 if value.get('schema')!='joat.job_frame_binding.v1' or value.get('canonical_registration') is not False or value.get('production_qc_approved') is not False or value.get('gpu_called') is not False:raise ValueError('Frame binding cannot authorize generation or QC.')
 job,context,snap=source(packet)
 if value.get('project_context')!=context or value.get('source_job_fingerprint')!=job['job_fingerprint'] or value.get('source_supervisor_fingerprint')!=packet['packet_fingerprint']:raise ValueError('Frame assignment belongs to another source job.')
 for role in ('character','environment','director'):
  if value.get('source_'+role+'_sha256')!=digest(snap[role]):raise ValueError('Frame assignment source changed.')
 manifest=value['approved_frame_manifest'];d=bind_character(manifest,snap['character'])
 from joat_visible_cast import validate_for_job
 validate_for_job(d,snap['director'],snap['character'])
 if d['scope']['environment_id']!=snap['environment']['environment_id']:raise ValueError('Frame assignment environment changed.')
 a=value.get('owner_approval',{})
 if a.get('owner')!='Dezz-9-10' or a.get('kind')!='job_reference_assignment' or not a.get('approved_at') or a.get('reviewed_for_this_job') is not True or a.get('image_sha256')!=d['image_sha256']:raise ValueError('Exact image assignment approval is missing.')
 return value

def location(packet,root=None):
 job,context,_=source(packet)
 return safe((ROOT if root is None else Path(root))/'job-reference-bindings'/context['project_id']/job['job_fingerprint']/'binding.json')

def save_binding(packet,value,root=None):
 from joat_managed_generation import mount_check
 mount_check('main');validate_binding(value,packet);path=location(packet,root)
 # Read original image bytes/review first; origin metadata is never rewritten.
 load_approved_frame(value['approved_frame_manifest']);path.parent.mkdir(parents=True,exist_ok=True);safe(path)
 if path.exists():
  stored=json.loads(path.read_text());validate_binding(stored,packet)
  if stored['approved_frame_manifest']!=value['approved_frame_manifest']:raise ValueError('An approved frame is already bound to this job; no overwrite.')
  return stored
 raw=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
 with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 if path.read_bytes()!=raw:raise ValueError('Frame binding readback failed.')
 return json.loads(path.read_text())

def load_binding(packet,root=None):
 path=location(packet,root)
 if not path.exists():return None
 if not path.is_file() or path.stat().st_size>2*1024*1024:raise ValueError('Invalid stored frame assignment.')
 return validate_binding(json.loads(path.read_text()),packet)

def reference_from_binding(value,packet):
 validate_binding(value,packet);manifest=value['approved_frame_manifest'];d=validate_manifest(manifest)
 load_approved_frame(manifest)
 return {'asset_id':manifest['asset_id'],'sha256':d['image_sha256'],'path':'image.png','url':manifest['image_uri'],'approved_job_reference':manifest}
