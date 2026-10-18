"""Private, owner-reviewed commercial proposal storage. File version1.0.0.
Campaign data stays in shared studio storage, never in public Space source.
"""
FILE_VERSION='1.0.0'
import base64,hashlib,json,os,zlib
from pathlib import Path
import joat_managed_generation as managed
PREFIX='JOAT_COMMERCIAL_PROPOSAL_INPUT_'
ROOT=Path('/studio/joat-studio')
MAX_BYTES=512*1024

def validate(value):
 if not isinstance(value,dict) or value.get('schema')!='joat.private_commercial_proposal.v1' or value.get('creative_approved') is not False:raise ValueError('Use an unapproved private commercial proposal.')
 managed.valid_project(value.get('project_id'))
 if not isinstance(value.get('brief'),str) or not isinstance(value.get('storyboard'),str):raise ValueError('Proposal requires brief and storyboard text.')
 from joat_creative_workflow import validate_plan
 validate_plan(value['project_id'],value['brief'],value.get('shot_plan'))
 return value

def directory(project):return managed.safe_path(ROOT/'commercial-proposals'/managed.valid_project(project))

def stage_proposals():
 for name in sorted(k for k in os.environ if k.startswith(PREFIX)):
  try:
   wrapper=json.loads(os.environ[name]);compressed=base64.b64decode(wrapper['compressed'],validate=True)
   decoder=zlib.decompressobj();raw=decoder.decompress(compressed,MAX_BYTES+1)
   if len(raw)>MAX_BYTES or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:raise ValueError('Proposal exceeds bounds or has trailing data.')
   digest=hashlib.sha256(raw).hexdigest()
   if digest!=wrapper['sha256']:raise ValueError('Proposal transfer hash mismatch.')
   value=validate(json.loads(raw));managed.mount_check('main')
   target=directory(value['project_id'])/(digest+'.json')
   if target.exists():
    if managed.read_json(target)!=value:raise ValueError('Stored proposal differs.')
   else:managed.write_once(target,value)
   if managed.read_json(target)!=value:raise ValueError('Proposal readback failed.')
   # Index updated only after immutable proposal write and readback.
   latest=managed.safe_path(ROOT/'commercial-proposals'/'latest.json');latest.parent.mkdir(parents=True,exist_ok=True)
   temporary=latest.parent/'latest.tmp';managed.safe_path(temporary)
   with temporary.open('w') as f:json.dump({'project_id':value['project_id'],'sha256':digest},f);f.flush();os.fsync(f.fileno())
   temporary.replace(latest)
   print('JOAT_COMMERCIAL_PROPOSAL_STORED '+json.dumps({'schema':'joat.private_proposal_storage_receipt.v1','file_version':FILE_VERSION,'project_id':value['project_id'],'payload_sha256':digest,'private_readback_verified':True,'creative_approved':False,'gpu_called':False}),flush=True)
  except Exception as exc:
   print('JOAT_COMMERCIAL_PROPOSAL_FAILURE '+json.dumps({'schema':'joat.private_proposal_failure.v1','file_version':FILE_VERSION,'error_type':type(exc).__name__,'gpu_called':False,'automatic_retry':False}),flush=True)

def proposal():
 managed.mount_check('main')
 index=managed.read_json(managed.safe_path(ROOT/'commercial-proposals'/'latest.json'))
 digest=index.get('sha256')
 import re
 if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Invalid proposal index.')
 value=validate(managed.read_json(directory(index['project_id'])/(digest+'.json')))
 if hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()!=digest:raise ValueError('Private proposal fingerprint mismatch.')
 return value['project_id'],value['brief'],json.dumps(value['shot_plan'],indent=2),value['storyboard']
