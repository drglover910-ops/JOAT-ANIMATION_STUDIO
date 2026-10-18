"""Owner-staged private frame import/approval; no public API, inference or GPU. Version1.0.2."""
FILE_VERSION='1.0.2'
import base64,hashlib,json,os,re,types
from pathlib import Path
from huggingface_hub import HfApi
import joat_job_assets as assets
CONTROL='JOAT_FRAME_TRANSFER_CONTROL_'
PART='JOAT_FRAME_TRANSFER_PART_'
def fp(v):return assets.fingerprint(v)
def safe(path):
 path=Path(path)
 if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Private frame paths cannot contain symlinks.')
 return path

def validate_control(value):
 if not isinstance(value,dict) or set(value)!={'schema','file_version','transfer_id','operation','image_sha256','part_count','part_indices','candidate_review','descriptor','owner_approved','hf_gpu_allowed'} or value['schema']!='joat.private_frame_transfer.v1':raise ValueError('Exact private frame transfer required.')
 if not re.fullmatch('[a-f0-9]{32}',value['transfer_id']) or not re.fullmatch('[a-f0-9]{64}',value['image_sha256']):raise ValueError('Invalid transfer/image identity.')
 if value['operation'] not in ('stage_candidate','approve_candidate') or value['hf_gpu_allowed'] is not False:raise ValueError('Only non-generating frame storage operations are allowed.')
 if type(value['part_count'])is not int or not 0<=value['part_count']<=64:raise ValueError('Invalid bounded image part count.')
 indices=value['part_indices']
 if not isinstance(indices,list) or len(indices)>8 or len(set(indices))!=len(indices) or any(type(i)is not int or not 0<=i<value['part_count'] for i in indices):raise ValueError('Use at most eight exact image parts per bounded batch.')
 if value['owner_approved'] is not (value['operation']=='approve_candidate'):raise ValueError('Storage approval and operation differ.')
 d=value['descriptor'];review=value['candidate_review'];plan=review.get('plan',{})
 if fp({k:v for k,v in d.items() if k!='asset_id'})!=d.get('asset_id') or fp(review)!=d.get('candidate_review_sha256') or fp({k:v for k,v in plan.items() if k!='fingerprint'})!=plan.get('fingerprint'):raise ValueError('Transfer descriptor/review/plan fingerprints differ.')
 if value['candidate_review'].get('sha256')!=value['image_sha256'] or value['descriptor'].get('image_sha256')!=value['image_sha256']:raise ValueError('Image/control evidence differs.')
 return value

def paths(value):
 directory=safe(assets.ROOT/'pending-reference-candidates'/value['image_sha256'])
 return directory,directory/'candidate.png',directory/'candidate_review.json',directory/'descriptor.json'

def check_descriptor(value,image,report):
 d=value['descriptor'];s=d['scope'];l=d['labels']
 actual=assets.prepare_asset(str(image),str(report),s['project_id'],s['scene_id'],s['shot_id'],s['character_id'],s['environment_id'],l['art_style'],l['wardrobe'],l['purpose'])
 if actual!=d:raise ValueError('Actual image/review differs from the proposed descriptor.')
 return actual

def stage(value):
 value=validate_control(value)
 if value['operation']!='stage_candidate':raise ValueError('Candidate staging operation required.')
 assets.require_bucket();directory,image,report,descriptor=paths(value)
 if value['part_count']<1:raise ValueError('Candidate import requires bounded image parts.')
 indices=value['part_indices']
 if not indices:raise ValueError('Candidate import requires a nonempty bounded batch.')
 transfer=safe(assets.ROOT/'pending-reference-transfers'/value['transfer_id'])
 control={k:v for k,v in value.items() if k!='part_indices'}
 assets.write_once(safe(transfer/'control.json'),json.dumps(control,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
 for i in indices:
  part=os.environ.get(PART+value['transfer_id']+'_'+str(i).zfill(2))
  if part is None or len(part)>60000:raise ValueError('Missing or oversized private image part.')
  assets.write_once(safe(transfer/(str(i).zfill(2)+'.part')),part.encode('ascii'))
 present=[i for i in range(value['part_count']) if (transfer/(str(i).zfill(2)+'.part')).is_file()]
 if len(present)!=value['part_count']:
  return {'schema':'joat.private_frame_transfer_receipt.v1','file_version':FILE_VERSION,'status':'private_image_parts_saved','transfer_id':value['transfer_id'],'image_sha256':value['image_sha256'],'part_count':value['part_count'],'parts_stored':len(present),'batch_indices':indices,'private_readback_verified':True,'owner_visual_approved':False,'hf_gpu_called':False}
 parts=[safe(transfer/(str(i).zfill(2)+'.part')).read_text('ascii') for i in range(value['part_count'])]
 encoded=''.join(parts)
 if len(encoded)>3840000:raise ValueError('Image transfer exceeds bounded size.')
 raw=base64.b64decode(encoded,validate=True)
 if len(raw)>2800000 or hashlib.sha256(raw).hexdigest()!=value['image_sha256']:raise ValueError('Image parts differ from the reviewed source hash.')
 assets.write_once(safe(image),raw);assets.write_once(safe(report),json.dumps(value['candidate_review'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
 check_descriptor(value,image,report);assets.write_once(safe(descriptor),json.dumps(value['descriptor'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
 return {'schema':'joat.private_frame_transfer_receipt.v1','file_version':FILE_VERSION,'status':'candidate_stored_awaiting_owner_visual_approval','image_sha256':value['image_sha256'],'descriptor_asset_id':value['descriptor']['asset_id'],'private_readback_verified':True,'owner_visual_approved':False,'production_qc_approved':False,'hf_gpu_called':False}

def approve(value):
 value=validate_control(value)
 if value['operation']!='approve_candidate' or value['owner_approved'] is not True:raise ValueError('Exact owner approval operation required.')
 assets.require_bucket();directory,image,report,descriptor=paths(value)
 if value['part_count']!=0 or value['part_indices']:raise ValueError('Approval uses previously stored bytes; image parts must not be replaced.')
 if json.loads(safe(descriptor).read_text())!=value['descriptor'] or json.loads(safe(report).read_text())!=value['candidate_review']:raise ValueError('Approval differs from the exact stored preview.')
 check_descriptor(value,image,report)
 token=os.environ.get('HF_TOKEN')
 if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Existing writer owner credential cannot be verified.')
 profile=types.SimpleNamespace(username='Dezz-9-10')
 manifest=assets.AssetStore().approve(value['descriptor'],str(image),str(report),profile,True)
 if manifest['descriptor']!=value['descriptor']:raise ValueError('Approved asset readback differs from owner preview.')
 return {'schema':'joat.private_frame_transfer_receipt.v1','file_version':FILE_VERSION,'status':'approved_reference_saved','image_sha256':value['image_sha256'],'asset_id':manifest['asset_id'],'manifest_fingerprint':manifest['fingerprint'],'private_readback_verified':True,'owner_visual_approved':True,'production_qc_approved':False,'hf_gpu_called':False}

def run_private_frame_transfers():
 for name in sorted(n for n in os.environ if n.startswith(CONTROL)):
  try:
   value=validate_control(json.loads(os.environ[name]));record=stage(value) if value['operation']=='stage_candidate' else approve(value)
   print('JOAT_PRIVATE_FRAME_TRANSFER '+json.dumps(record),flush=True)
  except Exception as exc:
   print('JOAT_PRIVATE_FRAME_TRANSFER '+json.dumps({'schema':'joat.private_frame_transfer_receipt.v1','file_version':FILE_VERSION,'status':'stopped_for_review','error_type':type(exc).__name__,'hf_gpu_called':False}),flush=True)
