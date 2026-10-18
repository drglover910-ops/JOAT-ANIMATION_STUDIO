"""Owner-authenticated consolidated department gateway. Embedded file version1.0.1.
Only fixed snapshotted departments, staged inputs and selected outputs are exposed.
"""
FILE_VERSION='1.0.1'
import hashlib,json,os,shutil,tempfile
from pathlib import Path
from typing import Optional
import gradio as gr
from joat_local_cpu import POOL,ROLES,stable,enabled
from joat_managed_generation import owner_token,OWNER
ROOT=Path(__file__).parent

def owner(profile,oauth,request):
 owner_token(profile,oauth,request)
 return OWNER
def login():
 if os.environ.get('SPACE_ID'):gr.LoginButton()
 else:gr.Markdown('Owner OAuth is enabled on the deployed Studio Control.')
def resolve_inputs(value,files):
 if isinstance(value,dict) and set(value)=={'__joat_input_file__'}:
  i=value['__joat_input_file__']
  if type(i) is not int or not 0<=i<len(files):raise ValueError('Invalid uploaded input mapping.')
  p=Path(files[i]);temp=Path(tempfile.gettempdir()).resolve()
  if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(temp):raise ValueError('Only uploaded temporary input files are allowed.')
  return str(p)
 if isinstance(value,dict):return {k:resolve_inputs(v,files) for k,v in value.items()}
 if isinstance(value,list):return [resolve_inputs(v,files) for v in value]
 return value

def export_outputs(result,file_output_indices,output_count):
 directory=Path(tempfile.mkdtemp(prefix='joat-local-exports-'));files=[];seen={}
 allowed={'.mp4','.wav','.mp3','.flac','.m4a','.json','.png','.jpg','.jpeg','.webp','.zip'}
 def export(v):
  if isinstance(v,str) and v.startswith('/'):
   path=Path(v)
   if path.suffix.lower() in allowed and path.is_file() and (path.is_relative_to('/tmp') or path.is_relative_to('/studio/joat-studio')):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or path.stat().st_size>2*1024**3:raise ValueError('Unsafe selected output file.')
    if v not in seen:
     i=len(files);target=directory/(str(i)+'-'+path.name);shutil.copyfile(path,target);seen[v]=i;files.append(str(target))
    return {'__joat_output_file__':seen[v]}
  if isinstance(v,dict):return {k:export(x) for k,x in v.items()}
  if isinstance(v,(list,tuple)):return [export(x) for x in v]
  return v
 if output_count==1:
  result=export(result) if 0 in file_output_indices else result
 elif isinstance(result,(list,tuple)):
  result=[export(v) if i in file_output_indices else v for i,v in enumerate(result)]
 return result,files or None

def describe(role:str,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 owner(profile,oauth,request)
 if role not in ROLES:raise gr.Error('Unknown native department.')
 try:return POOL.request(role,'describe',timeout=120)['result']
 except Exception:raise gr.Error('Native department contract loading failed; no operation submitted.') from None

def validate_file_inputs(args,kwargs,contract):
 def staged(v):
  if v is None:return True
  if isinstance(v,list):return all(staged(x) for x in v)
  return isinstance(v,dict) and set(v)=={'__joat_input_file__'}
 for i in contract.get('file_input_indices',[]):
  name=contract['parameters'][i]['parameter_name'];value=args[i] if i<len(args) else kwargs.get(name)
  if not staged(value):raise ValueError('File inputs must use the uploaded file mapping, not raw server paths.')

def execute(role:str,endpoint:str,args_json:str,kwargs_json:str,input_files:list[str]|None,profile:Optional[gr.OAuthProfile],oauth:Optional[gr.OAuthToken],request:gr.Request):
 owner(profile,oauth,request)
 if not enabled():raise gr.Error('Consolidated execution is not enabled; original routes remain active.')
 if role not in ROLES or not isinstance(endpoint,str) or not endpoint.startswith('/'):raise gr.Error('Invalid department route.')
 try:
  if len(args_json.encode())+len(kwargs_json.encode())>8*1024**2:raise ValueError('Department inputs exceed8MiB.')
  args=json.loads(args_json);kwargs=json.loads(kwargs_json)
  if not isinstance(args,list) or not isinstance(kwargs,dict):raise ValueError('Exact positional/named department inputs required.')
  contract=POOL.request(role,'describe',timeout=120)['result']['named_endpoints'].get(endpoint)
  if contract is None:raise ValueError('Unknown native department endpoint.')
  validate_file_inputs(args,kwargs,contract)
  files=input_files or [];args=resolve_inputs(args,files);kwargs=resolve_inputs(kwargs,files)
  response=POOL.request(role,'call',endpoint,args,kwargs,timeout=3000)
  return export_outputs(response['result'],contract['file_output_indices'],contract['output_count'])
 except (ValueError,RuntimeError,TimeoutError) as exc:raise gr.Error(str(exc)) from None

def status():
 manifest=json.loads((ROOT/'consolidated_manifest.json').read_text())
 return dict(schema='joat.consolidated_cpu_status.v1',file_version=FILE_VERSION,physical_space=os.environ.get('SPACE_ID'),enabled=enabled(),gpu_hold=os.environ.get('JOAT_STUDIO_GPU_HOLD','true').lower()=='true',department_count=len(ROLES),manifest_fingerprint=manifest['manifest_fingerprint'],maximum_cached_department_processes_per_pool=POOL.max_workers,cpu_voice_enabled=os.environ.get('JOAT_CPU_VOICE_ENABLED','').lower()=='true',department_processes_cached=len(POOL.workers),gpu_called=False,secret_values_exposed=False,studio_capability_registry_fingerprint=__import__('joat_studio_capabilities').registry()['registry_fingerprint'])

def add_cpu_control_ui():
 with gr.Tab('Consolidated Studio Control'):
  gr.Markdown('The original departments run as isolated modules in this CPU Space. Logical identities, source fingerprints and independent owner approvals remain in place. GPU generation stays on separate workers.')
  login();gr.JSON(status(),label='Verified deployment and GPU hold');role=gr.Dropdown(list(ROLES),value='character',label='Native department');description=gr.JSON(label='Native API contract');gr.Button('Inspect department contract — no execution').click(describe,[role],description,api_name='cpu_department_describe',api_visibility='undocumented',concurrency_limit=1)
  endpoint=gr.Textbox(label='Exact native endpoint',value='/packet');args=gr.Code(label='Positional arguments JSON',language='json',value='[]');kwargs=gr.Code(label='Named arguments JSON',language='json',value='{"cid":"CHAR-001","task":"scene"}');uploads=gr.File(label='Exact input files, when required',file_count='multiple',type='filepath');result=gr.JSON(label='Unchanged native department result');files=gr.File(label='Selected department artifacts',file_count='multiple')
  gr.Button('Run owner-authorized native department action').click(execute,[role,endpoint,args,kwargs,uploads],[result,files],api_name='cpu_department_call',api_visibility='undocumented',concurrency_limit=1,trigger_mode='once')
  gr.Button('Refresh deployment status — no GPU').click(status,[],gr.JSON(label='Current consolidated status'),api_name='cpu_consolidation_status',api_visibility='public')
