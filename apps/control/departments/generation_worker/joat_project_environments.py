"""Approved project environments beside the unchanged canonical registry.
Embedded file version 1.0.1. Read-only helper; no implicit registration or approval.
"""
FILE_VERSION='1.0.1'
import hashlib,json,os,re,urllib.request
from pathlib import Path
from functools import lru_cache
ROOT=Path('/studio/joat-studio');BUCKET='Dezz-9-10/J.O.A.T.-Studio-storage'
def stable(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(v):return hashlib.sha256(stable(v).encode()).hexdigest()
def safe(p):
 p=Path(p)
 if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('Project storage links are not allowed.')
 return p
@lru_cache(maxsize=1)
def mount_check():
 space=os.environ.get('SPACE_ID','')
 if not re.fullmatch(r'Dezz-9-10/[A-Za-z0-9_.-]+',space):raise ValueError('Studio runtime required.')
 with urllib.request.urlopen('https://huggingface.co/api/spaces/'+space,timeout=15) as r:info=json.load(r)
 if not any(x.get('type')=='bucket' and x.get('source')==BUCKET and x.get('mountPath')=='/studio' for x in info.get('runtime',{}).get('volumes',[])) or not ROOT.is_dir():raise ValueError('Verified studio bucket mount required.')
def json_read(p):
 p=safe(p)
 if p.stat().st_size>1024*1024:raise ValueError('Oversized project record.')
 return json.loads(p.read_text())
def load(identifier,project=None):
 if not isinstance(identifier,str) or not re.fullmatch(r'ENV-[1-9][0-9]{2}',identifier):raise ValueError('Project environment ID required.')
 mount_check();return validate(json_read(ROOT/'project-environments'/identifier/'manifest.json'),identifier,project)
def validate(v,identifier,project=None):
 if v.get('schema')=='joat.project_environment_reuse.v1':
  if set(v)!={'schema','file_version','project_id','environment_id','source_environment_id','source_manifest_fingerprint','owner_reuse_approval','canonical_registration','manifest_fingerprint'} or digest({k:x for k,x in v.items() if k!='manifest_fingerprint'})!=v.get('manifest_fingerprint'):raise ValueError('Invalid environment reuse assignment.')
  pid=v.get('project_id','');source=v.get('source_environment_id','');a=v.get('owner_reuse_approval',{})
  if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',pid) or v.get('environment_id')!=identifier or not re.fullmatch(r'ENV-[1-9][0-9]{2}',source) or source==identifier or (project is not None and project!=pid) or v.get('canonical_registration') is not False:raise ValueError('Environment reuse scope differs.')
  if a!={'owner':'Dezz-9-10','approved':True,'scope':'story_and_existing_frame_reuse','owner_statement':'Approve story and frame reuse'}:raise ValueError('Explicit environment reuse approval required.')
  original=json_read(ROOT/'project-environments'/source/'manifest.json')
  if original.get('schema')!='joat.project_environment.v1' or original.get('manifest_fingerprint')!=v['source_manifest_fingerprint']:raise ValueError('Original environment source differs; reuse chains forbidden.')
  origin,image=validate(original,source)
  expanded=dict(origin,schema=v['schema'],environment_id=identifier,project_id=pid,manifest_fingerprint=v['manifest_fingerprint'],file_version=v['file_version'],source_environment_id=source,source_manifest_fingerprint=v['source_manifest_fingerprint'])
  return expanded,image
 core=dict(v);given=core.pop('manifest_fingerprint',None)
 if given!=digest(core) or v.get('schema')!='joat.project_environment.v1' or v.get('environment_id')!=identifier or v.get('canonical_registration') is not False:raise ValueError('Project environment manifest integrity failed.')
 pid=v.get('project_id','')
 if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',pid) or (project is not None and pid!=project):raise ValueError('Project environment scope mismatch.')
 approval=v.get('owner_approval',{})
 if approval.get('owner')!='Dezz-9-10' or approval.get('approved') is not True or approval.get('image_sha256')!=v.get('image_sha256') or approval.get('kind')!='project_location_visual_review':raise ValueError('Exact owner-reviewed project location required.')
 path=v.get('image_bucket_path','');review_path=v.get('review_bucket_path','')
 pattern='joat-studio/production-projects/'+re.escape(pid)+r'/references/[A-Za-z0-9_-]+/[a-f0-9]{32}/candidate\.png'
 if not re.fullmatch(pattern,path) or review_path!=path.removesuffix('candidate.png')+'candidate_review.json':raise ValueError('Invalid project environment source path.')
 image=safe(ROOT.parent/path);report=json_read(ROOT.parent/review_path)
 if image.stat().st_size>25*1024*1024 or hashlib.sha256(image.read_bytes()).hexdigest()!=v.get('image_sha256'):raise ValueError('Project environment image integrity failed.')
 if report.get('schema')!='joat.project_reference_candidate.v1' or report.get('project_id')!=pid or report.get('kind')!='environment' or report.get('sha256')!=v['image_sha256'] or report.get('plan_fingerprint')!=v.get('candidate_plan_fingerprint'):raise ValueError('Project environment evidence differs.')
 return v,image

def packet(identifier,task,time_of_day,lighting,weather,scene_id,shot_id):
 v,image=load(identifier)
 if task not in ('identity','all','scene','continuity'):raise ValueError('Unsupported project environment task.')
 alias='studio://project-environments/'+identifier+'/anchor';asset=identifier+'-PROJECT-A01'
 p=dict(schema='joat.environment_packet.v1',environment_id=identifier,environment_name=v['name'],environment_version=v['file_version'],task=task,environment_locked=True,asset_identity_lock_ready=True,identity_lock_asset=alias,identity_lock_sha256=v['image_sha256'],supporting_reference_assets=[],environment_rules=v['environment_rules'],continuity_rules=v['continuity_rules'],negative_rules=v['negative_rules'],scene_context=dict(scene_id=scene_id or None,shot_id=shot_id or None,time_of_day=time_of_day,lighting=lighting,weather=weather),source_asset_hashes={asset:v['image_sha256']},source_asset_locations={asset:alias},approval=dict(live_change_allowed=False,requires_human_approval_for_registry_mutation=True,project_location_owner_reviewed=True),downstream_handoff=dict(director_compatible=True,shot_camera_compatible=True,ltx_compatible=True,registry_mutation_allowed=False),project_scope=dict(project_id=v['project_id'],environment_manifest_fingerprint=v['manifest_fingerprint'],canonical_registration=False))
 p['packet_fingerprint']=digest(p);return p

def reference(environment,path,project):
 identifier=environment.get('environment_id');v,image=load(identifier,project)
 expected=packet(identifier,environment['task'],environment['scene_context']['time_of_day'],environment['scene_context']['lighting'],environment['scene_context']['weather'],environment['scene_context']['scene_id'],environment['scene_context']['shot_id'])
 if environment!=expected or path!=expected['identity_lock_asset']:raise ValueError('Project environment packet differs from approved source.')
 return dict(role='environment',path=path,url=path,sha256=v['image_sha256'],project_environment_manifest_fingerprint=v['manifest_fingerprint'])
