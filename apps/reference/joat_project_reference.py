"""Owner-authorized project reference candidates. File version1.0.6.
Uses the existing qualified Qwen generator unchanged. Never registers canonical assets.
"""
FILE_VERSION='1.0.6'
import hashlib,json,os,re,tempfile,threading,time,urllib.request
from pathlib import Path
from typing import Optional
import gradio as gr
from huggingface_hub import HfApi
from PIL import Image,ImageOps
import joat_job_assets as assets
LOCK=threading.Lock()
def stable(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(v):return hashlib.sha256(stable(v).encode()).hexdigest()
def owner(oauth,request):
 token=getattr(oauth,'token',None)
 if not token:
  h=request.headers.get('x-hf-authorization','') or request.headers.get('authorization','')
  if h.lower().startswith('bearer '):token=h[7:]
 if not token or HfApi(token=token).whoami().get('name')!='Dezz-9-10':raise ValueError('Verified studio owner required.')
 return token
def validate(v):
 keys={'schema','file_version','request_id','project_id','asset_key','kind','sources','prompt','gpu_ceiling_seconds','generation_authorized','authorization_basis','canonical_registration'}
 if not isinstance(v,dict) or not keys<=set(v) or set(v)-keys-{'aspect_ratio','model_image_order'} or v['schema']!='joat.project_reference_request.v1':raise ValueError('Exact project reference request required.')
 if v.get('aspect_ratio','16:9') not in ('16:9','9:16'):raise ValueError('Only reviewed landscape or portrait reference ratios are supported.')
 if not re.fullmatch('[a-f0-9]{32}',v['request_id']):raise ValueError('Invalid request ID.')
 for k in ('project_id','asset_key'):
  if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',v[k]):raise ValueError('Invalid project asset scope.')
 if v['kind'] not in ('environment','shot_start_frame') or v['gpu_ceiling_seconds']!=600 or v['generation_authorized'] is not True or v['canonical_registration'] is not False:raise ValueError('Bounded candidate authorization required.')
 if not isinstance(v['authorization_basis'],str) or not 1<=len(v['authorization_basis'])<=2000 or not isinstance(v['prompt'],str) or not 1<=len(v['prompt'])<=4000:raise ValueError('Missing bounded instructions.')
 if not isinstance(v['sources'],list) or not 1<=len(v['sources'])<=4:raise ValueError('Require1–4 exact source images.')
 for source in v['sources']:
  if set(source)!={'role','url','source_sha256','crop_bounds_pixels','prepared_sha256'} or source['role'] not in ('style_reference','identity','environment','wardrobe_support'):raise ValueError('Invalid source role.')
  project_source=re.fullmatch(r'studio://project-environments/(ENV-[1-9][0-9]{2})/anchor',source['url'])
  if project_source:
   if source['role']!='environment' or source['crop_bounds_pixels'] is not None:raise ValueError('Project anchor only supports an exact environment source.')
  elif not re.fullmatch(r'https://huggingface\.co/spaces/Dezz-9-10/J\.O\.A\.T\.-(?:Character-Asset|Scene-Environment)-Master/resolve/[a-f0-9]{40}/(?:assets/CHAR-[0-9]{3}/|environment_assets/)[A-Za-z0-9_.-]+\.(?:jpeg|png)',source['url']):raise ValueError('Only pinned approved Master source URLs allowed.')
  if any(not re.fullmatch('[a-f0-9]{64}',source[k]) for k in ('source_sha256','prepared_sha256')):raise ValueError('Exact source hashes required.')
  box=source['crop_bounds_pixels']
  if box is not None:
   if not isinstance(box,list) or len(box)!=4 or any(type(x)is not int for x in box) or not 0<=box[0]<box[2] or not 0<=box[1]<box[3]:raise ValueError('Invalid source crop.')
   if source['role']=='identity' and not (v['file_version']=='1.0.5' and v.get('model_image_order') is not None and source['source_sha256']=='fd27d3bf68dfa6daaf12dbc6421a84c67fedb6656f492672f6f78a0a867f1c1f' and box==[512,0,1402,1122] and source['prepared_sha256']=='8d6b3eec1ed13ddb3db2b07f05ddde964910b371b781e6c4fbc2bd32b6a5d0bc'):raise ValueError('Only the reviewed full-face view of the exact canonical Cristu card may be cropped.')
 order=v.get('model_image_order')
 if order is not None:
  if v['file_version']!='1.0.5' or not isinstance(order,list) or any(type(i) is not int for i in order) or sorted(order)!=list(range(len(v['sources']))) or v['sources'][order[0]]['role']!='environment':raise ValueError('Reviewed environment-first source permutation required.')
 if v['kind']=='environment' and any(s['role']=='identity' for s in v['sources']):raise ValueError('Empty environment preparation does not use character identity images.')
 if v['kind']=='shot_start_frame' and v['sources'][0]['role']!='identity':raise ValueError('Opening frame requires the exact primary identity source first.')
 return v

def sources(v,directory):
 images=[]
 for i,s in enumerate(v['sources']):
  if s['url'].startswith('studio://'):
   from joat_project_environments import load
   manifest,path=load(s['url'].split('/')[3],v['project_id']);raw=path.read_bytes()
   if manifest['image_sha256']!=s['source_sha256']:raise ValueError('Project environment differs from approved location.')
  else:
   with urllib.request.urlopen(s['url'],timeout=45) as response:raw=response.read(25*1024*1024+1)
  if len(raw)>25*1024*1024 or hashlib.sha256(raw).hexdigest()!=s['source_sha256']:raise ValueError('Source bytes differ.')
  path=directory/(str(i)+'.jpeg');path.write_bytes(raw)
  with Image.open(path) as im:
   im=ImageOps.exif_transpose(im).convert('RGB');im.load()
   if im.width*im.height>20000000:raise ValueError('Oversized source.')
   box=s['crop_bounds_pixels']
   if box is not None:
    if box[2]>im.width or box[3]>im.height:raise ValueError('Crop outside source.')
    im=im.crop(tuple(box));path=directory/(str(i)+'.png');im.save(path,format='PNG')
   if hashlib.sha256(path.read_bytes()).hexdigest()!=s['prepared_sha256']:raise ValueError('Prepared source hash differs.')
   images.append(im.copy())
 return images

def model_order(v):return v.get('model_image_order',list(range(len(v['sources']))))

def run(v,generate,root=None,require_mount=assets.require_bucket):
 v=validate(v)
 from joat_project_lifecycle import assert_active
 assert_active(v['project_id'],Path(root or assets.ROOT))
 require_mount();root=Path(root or assets.ROOT)/'production-projects'/v['project_id']/'references'/v['asset_key']/v['request_id']
 if root.is_symlink() or any(x.is_symlink() for x in root.parents):raise ValueError('Invalid project path.')
 report=root/'candidate_review.json';image=root/'candidate.png'
 if report.exists():
  value=json.loads(report.read_text())
  if value.get('plan_fingerprint')!=digest(v) or json.loads((root/'plan.json').read_text())!=v:raise ValueError('Stored candidate plan differs.')
  if hashlib.sha256(image.read_bytes()).hexdigest()!=value['sha256']:raise ValueError('Stored candidate integrity failed.')
  return value,str(image),str(report)
 root.mkdir(parents=True,exist_ok=True)
 with LOCK:
  with (root/'reservation.json').open('xb') as f:f.write(stable(dict(request_id=v['request_id'],plan_fingerprint=digest(v),automatic_retry=False)).encode());f.flush();os.fsync(f.fileno())
 assets.write_once(root/'plan.json',stable(v).encode())
 directory=Path(tempfile.mkdtemp(prefix='joat-project-reference-'));prepared=sources(v,directory);images=[prepared[i] for i in model_order(v)]
 dimensions=(576,1024) if v.get('aspect_ratio','16:9')=='9:16' else (1024,576)
 result=generate(images,v['prompt'],width=dimensions[0],height=dimensions[1]) if v.get('aspect_ratio','16:9')=='9:16' else generate(images,v['prompt'])
 if result.size!=dimensions:raise ValueError('Unexpected candidate dimensions.')
 path=directory/'candidate.png';result.save(path,format='PNG');raw=path.read_bytes();assets.write_once(image,raw)
 value=dict(schema='joat.project_reference_candidate.v1',file_version=FILE_VERSION,request_id=v['request_id'],project_id=v['project_id'],asset_key=v['asset_key'],kind=v['kind'],model='Qwen/Qwen-Image-Edit-2511',plan_fingerprint=digest(v),sha256=hashlib.sha256(raw).hexdigest(),width=dimensions[0],height=dimensions[1],size_bytes=len(raw),candidate_only=True,owner_visual_approved=False,canonical_registration=False,production_qc_approved=False,automatic_retry=False,source_request=v)
 assets.write_once(report,stable(value).encode());return value,str(image),str(report)

def add_project_reference_api(generate):
 def execute(payload:str,oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner(oauth,request)
  if len(payload.encode())>65536:raise gr.Error('Oversized project reference request.')
  value,image,report=run(json.loads(payload),generate,require_mount=lambda:assets.require_bucket(token=token))
  # Export only verified copies to Gradio's normal temp cache, never /studio.
  import shutil
  export=Path(tempfile.mkdtemp(prefix='joat-project-candidate-'));shutil.copyfile(image,export/'candidate.png');shutil.copyfile(report,export/'candidate_review.json')
  return value,str(export/'candidate.png'),str(export/'candidate_review.json')
 def check_storage(oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner(oauth,request);assets.require_bucket(token=token)
  return dict(schema='joat.reference_storage_check.v1',file_version=FILE_VERSION,status='private_mount_verified',gpu_called=False,files_written=False)
 gr.Button(visible=False).click(check_storage,[],[gr.JSON(visible=False)],api_name='check_project_storage',api_visibility='public')
 def check_inputs(payload:str,oauth:Optional[gr.OAuthToken],request:gr.Request):
  token=owner(oauth,request);assets.require_bucket(token=token)
  if len(payload.encode())>65536:raise gr.Error('Oversized project reference request.')
  v=validate(json.loads(payload));images=sources(v,Path(tempfile.mkdtemp(prefix='joat-project-reference-preflight-')))
  order=model_order(v)
  return dict(schema='joat.project_reference_input_check.v1',file_version=FILE_VERSION,status='verified',plan_fingerprint=digest(v),model_image_order=order,model_image_sources=[dict(model_picture=picture+1,source_index=index,role=v['sources'][index]['role'],prepared_sha256=v['sources'][index]['prepared_sha256'],width=images[index].width,height=images[index].height) for picture,index in enumerate(order)],gpu_called=False,bucket_files_written=False)
 gr.Button(visible=False).click(check_inputs,[gr.Textbox(visible=False)],[gr.JSON(visible=False)],api_name='check_project_reference_inputs',api_visibility='public')
 payload=gr.Textbox(visible=False)
 gr.Button(visible=False).click(execute,[payload],[gr.JSON(visible=False),gr.File(visible=False),gr.File(visible=False)],api_name='project_reference_candidate',api_visibility='public',concurrency_limit=1)
