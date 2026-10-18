"""Private reusable mission-reference proposals; CPU preparation only. File version1.0.0."""
FILE_VERSION='1.0.0'
import hashlib,json,os,re,tempfile,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
from joat_job_assets import require_bucket,ROOT
PREFIX='JOAT_REFERENCE_PROPOSAL_INPUT_'
ROLES=('identity','environment','wardrobe_support')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def stable(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def fingerprint(value):return digest(stable(value).encode())
def validate(value):
 if not isinstance(value,dict) or set(value)!={'schema','file_version','proposal_id','mission','prompt','sources','notes'} or value['schema']!='joat.saved_reference_proposal.v1':raise ValueError('Use an exact saved reference proposal.')
 if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,95}',value['proposal_id']):raise ValueError('Invalid proposal ID.')
 if not isinstance(value['mission'],str) or not 1<=len(value['mission'])<=160 or not isinstance(value['prompt'],str) or not 1<=len(value['prompt'])<=4000:raise ValueError('Invalid mission/prompt.')
 if not isinstance(value['notes'],str) or len(value['notes'])>3000:raise ValueError('Invalid proposal notes.')
 sources=value['sources']
 if not isinstance(sources,list) or tuple(s.get('role') for s in sources)!=ROLES:raise ValueError('Require separate identity, environment and wardrobe references.')
 for s in sources:
  if set(s)!={'role','url','source_sha256','source_width','source_height','crop_bounds_pixels','prepared_sha256','prepared_width','prepared_height'}:raise ValueError('Invalid reference source contract.')
  for key in ('source_sha256','prepared_sha256'):
   if not isinstance(s[key],str) or not re.fullmatch('[a-f0-9]{64}',s[key]):raise ValueError('Invalid image hash.')
  if not re.fullmatch(r'https://huggingface\.co/spaces/Dezz-9-10/J\.O\.A\.T\.-(?:Character-Asset|Scene-Environment)-Master/resolve/[a-f0-9]{40}/(?:assets/CHAR-[0-9]{3}/|environment_assets/)[A-Za-z0-9_.-]+\.(?:jpeg|png)',s['url']):raise ValueError('Reference must use the pinned studio Master repository.')
  for key in ('source_width','source_height','prepared_width','prepared_height'):
   if type(s[key]) is not int or not 64<=s[key]<=8192:raise ValueError('Invalid image dimension.')
  box=s['crop_bounds_pixels']
  if box is not None:
   if s['role']=='identity' or not isinstance(box,list) or len(box)!=4 or any(type(n)is not int for n in box):raise ValueError('Canonical identity cannot be cropped or replaced.')
   l,t,r,b=box
   if not 0<=l<r<=s['source_width'] or not 0<=t<b<=s['source_height'] or (r-l,b-t)!=(s['prepared_width'],s['prepared_height']):raise ValueError('Invalid lossless reference crop.')
  elif s['source_sha256']!=s['prepared_sha256'] or (s['source_width'],s['source_height'])!=(s['prepared_width'],s['prepared_height']):raise ValueError('Exact original identity/reference copy required.')
 return value

def record(path,raw):
 if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise ValueError('Reference storage cannot use symlinks.')
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  if path.read_bytes()!=raw:raise ValueError('Existing reference proposal differs; no overwrite.')
 else:
  with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 if path.read_bytes()!=raw:raise ValueError('Reference readback failed.')

def stage_proposals():
 for name in sorted(n for n in os.environ if n.startswith(PREFIX)):
  try:
   require_bucket();value=validate(json.loads(os.environ[name]));raw=stable(value).encode();fp=digest(raw)
   record(ROOT/'reference-proposals'/value['proposal_id']/(fp+'.json'),raw)
   index=ROOT/'reference-proposals/index'/(fp+'.json')
   if not index.exists():record(index,stable({'proposal_id':value['proposal_id'],'fingerprint':fp,'created_at':datetime.now(timezone.utc).isoformat()}).encode())
   print('JOAT_REFERENCE_PROPOSAL '+json.dumps({'schema':'joat.saved_reference_proposal_receipt.v1','file_version':FILE_VERSION,'status':'private_proposal_saved','proposal_id':value['proposal_id'],'proposal_fingerprint':fp,'readback_verified':True,'gpu_called':False}),flush=True)
  except Exception as exc:print('JOAT_REFERENCE_PROPOSAL '+json.dumps({'schema':'joat.saved_reference_proposal_receipt.v1','file_version':FILE_VERSION,'status':'stopped_for_review','error_type':type(exc).__name__,'gpu_called':False}),flush=True)

def read_latest():
 require_bucket();indices=[json.loads(p.read_text()) for p in (ROOT/'reference-proposals/index').glob('*.json')]
 if not indices:raise ValueError('No saved job reference proposal is available.')
 index=max(indices,key=lambda x:x['created_at'])
 if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,95}',index['proposal_id']) or not re.fullmatch('[a-f0-9]{64}',index['fingerprint']):raise ValueError('Invalid stored proposal index.')
 raw=(ROOT/'reference-proposals'/index['proposal_id']/(index['fingerprint']+'.json')).read_bytes()
 if digest(raw)!=index['fingerprint']:raise ValueError('Stored proposal hash changed.')
 return validate(json.loads(raw))

def prepare_files(value):
 value=validate(value);directory=Path(tempfile.mkdtemp(prefix='joat-saved-reference-'));files=[]
 for source in value['sources']:
  with urllib.request.urlopen(source['url'],timeout=35) as response:raw=response.read(25*1024*1024+1)
  if len(raw)>25*1024*1024 or digest(raw)!=source['source_sha256']:raise ValueError('Pinned reference source hash/size changed.')
  original=directory/(source['role']+'.jpeg');original.write_bytes(raw)
  with Image.open(original) as image:
   image.load()
   if image.size!=(source['source_width'],source['source_height']):raise ValueError('Source image dimensions changed.')
   if source['crop_bounds_pixels'] is not None:
    target=directory/(source['role']+'.png');image.crop(tuple(source['crop_bounds_pixels'])).save(target,format='PNG')
   else:target=original
  if digest(target.read_bytes())!=source['prepared_sha256']:raise ValueError('Prepared lossless crop differs from reviewed proposal.')
  files.append(str(target))
 return files
